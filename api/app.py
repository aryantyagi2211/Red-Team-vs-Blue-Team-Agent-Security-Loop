import asyncio
import json
import logging
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from a2a.helpers import (
    new_task_from_user_message,
    new_text_artifact_update_event,
    new_text_status_update_event,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
    TaskState,
)
from fastapi import FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    ValidationError,
    field_validator,
)

from core import loop
from core.attacker import AttackClient
from core.loop import MAX_ROUNDS, RUN_ID_PATTERN, RunSummary
from targets.sandbox import TARGET_NAME_PATTERN, load_target

logger = logging.getLogger(__name__)
DASHBOARD_DIR = Path(__file__).parents[1] / "dashboard"
SAMPLE_RUN_ID = "sample-calendar-hardening"
_CANARY_PATTERN = re.compile(r"SECRET-CANARY-[A-Z]+-[A-Z0-9]+")


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: str = Field(min_length=1)
    rounds: StrictInt = Field(default=3, ge=0, le=MAX_ROUNDS)

    @field_validator("target")
    @classmethod
    def validate_target_name(cls, value: str) -> str:
        if not TARGET_NAME_PATTERN.fullmatch(value):
            raise ValueError("target must be a lowercase identifier")
        return value


class RunStarted(BaseModel):
    run_id: str


class RunStatus(BaseModel):
    run_id: str
    target: str
    status: Literal["running", "done", "error"]
    progress: dict[str, object] | None = None
    error: str | None = None


def _new_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}_{secrets.token_hex(3)}"


class RunCoordinator:
    def __init__(self, client: AttackClient | None = None) -> None:
        self.client = client
        self.statuses: dict[str, RunStatus] = {}
        self.tasks: set[asyncio.Task[None]] = set()

    def start(self, request: RunRequest) -> str:
        run_id = _new_run_id()
        self.statuses[run_id] = RunStatus(
            run_id=run_id,
            target=request.target,
            status="running",
        )
        task = asyncio.create_task(self._execute(run_id, request))
        self.tasks.add(task)

        def on_done(completed: asyncio.Task[None]) -> None:
            self.tasks.discard(completed)
            if completed.cancelled():
                return
            error = completed.exception()
            if error is not None:
                current = self.statuses[run_id]
                current.status = "error"
                current.error = f"run failed ({type(error).__name__}); see server logs"
                logger.error(
                    "Red-team run %s failed with %s",
                    run_id,
                    type(error).__name__,
                )

        task.add_done_callback(on_done)
        return run_id

    async def _execute(self, run_id: str, request: RunRequest) -> None:
        current = self.statuses[run_id]

        def on_progress(event: dict[str, object]) -> None:
            current.progress = event

        try:
            result: RunSummary = await loop.run_loop(
                request.target,
                request.rounds,
                run_id=run_id,
                on_progress=on_progress,
                client=self.client,
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.error(
                "Red-team run %s failed with %s",
                run_id,
                type(exc).__name__,
            )
            current.status = "error"
            current.error = f"run failed ({type(exc).__name__}); see server logs"
            return

        current.status = "done" if result.status == "ok" else "error"
        if current.status == "error":
            current.error = result.stop_reason or "run failed"

    def get_status(self, run_id: str) -> RunStatus:
        current = self.statuses.get(run_id)
        if current is not None:
            return current

        summary_path = loop.RUNS_DIR / run_id / "summary.json"
        if not summary_path.is_file():
            raise HTTPException(status_code=404, detail="run not found")
        try:
            summary = RunSummary.model_validate_json(
                summary_path.read_text(encoding="utf-8")
            )
        except (OSError, ValueError) as exc:
            logger.exception("Could not read saved run status for %s", run_id)
            raise HTTPException(
                status_code=500,
                detail="saved run status is invalid",
            ) from exc

        status_value: Literal["running", "done", "error"]
        if summary.status == "running":
            status_value = "running"
        elif summary.status == "ok":
            status_value = "done"
        else:
            status_value = "error"
        return RunStatus(
            run_id=summary.run_id,
            target=summary.target,
            status=status_value,
            error=summary.stop_reason if status_value == "error" else None,
        )


class RedTeamAgentExecutor(AgentExecutor):
    def __init__(self, coordinator: RunCoordinator) -> None:
        self.coordinator = coordinator

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task = context.current_task or new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)
        await event_queue.enqueue_event(
            new_text_status_update_event(
                task_id=task.id,
                context_id=task.context_id,
                state=TaskState.TASK_STATE_WORKING,
                text="Validating red-team run request...",
            )
        )

        try:
            raw_request = json.loads(context.get_user_input())
            run_request = RunRequest.model_validate(raw_request)
            _validate_target(run_request.target)
            run_id = self.coordinator.start(run_request)
        except (json.JSONDecodeError, ValidationError, HTTPException, TypeError) as exc:
            if isinstance(exc, ValidationError):
                message = "A2A input must be JSON with a known target and rounds from 0 to 10."
            elif isinstance(exc, json.JSONDecodeError):
                message = "A2A input must be valid JSON."
            elif isinstance(exc, HTTPException):
                message = str(exc.detail)
            else:
                message = "A2A input must be a JSON object."
            await event_queue.enqueue_event(
                new_text_status_update_event(
                    task_id=task.id,
                    context_id=task.context_id,
                    state=TaskState.TASK_STATE_FAILED,
                    text=message,
                )
            )
            return

        response = (
            f"Started red-team run {run_id} for {run_request.target}. "
            f"Poll GET /runs/{run_id} for status and GET /runs/{run_id}/report "
            "for the summary."
        )
        await event_queue.enqueue_event(
            new_text_artifact_update_event(
                task_id=task.id,
                context_id=task.context_id,
                name="run-started",
                text=response,
            )
        )
        await event_queue.enqueue_event(
            new_text_status_update_event(
                task_id=task.id,
                context_id=task.context_id,
                state=TaskState.TASK_STATE_COMPLETED,
                text=response,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return None


def _validate_target(target: str) -> None:
    try:
        load_target(target)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"unknown sandbox target: {target}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def create_app(client: AttackClient | None = None) -> FastAPI:
    app = FastAPI(title="Nasiko Red-Team Loop API", version="0.1.0")
    coordinator = RunCoordinator(client)
    app.state.run_coordinator = coordinator

    @app.post(
        "/runs",
        response_model=RunStarted,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def start_run(run_request: RunRequest) -> RunStarted:
        _validate_target(run_request.target)
        return RunStarted(run_id=coordinator.start(run_request))

    @app.get("/runs/{run_id}", response_model=RunStatus)
    async def get_run_status(run_id: str) -> RunStatus:
        if not _valid_run_id(run_id):
            raise HTTPException(status_code=404, detail="run not found")
        return coordinator.get_status(run_id)

    @app.get("/runs/{run_id}/report")
    async def get_run_report(run_id: str) -> dict[str, object]:
        if not _valid_run_id(run_id):
            raise HTTPException(status_code=404, detail="run not found")
        report_path = loop.RUNS_DIR / run_id / "summary.json"
        try:
            return json.loads(report_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="run report not found") from exc
        except (OSError, json.JSONDecodeError) as exc:
            logger.exception("Could not read saved run report for %s", run_id)
            raise HTTPException(
                status_code=500,
                detail="saved run report is invalid",
            ) from exc

    @app.get("/dashboard/runs")
    async def list_dashboard_runs() -> dict[str, list[dict[str, object]]]:
        runs: list[dict[str, object]] = []
        sample_summary = _read_dashboard_summary(SAMPLE_RUN_ID, recorded=True)
        runs.append(_dashboard_run_option(sample_summary, recorded=True))

        for run_id, current in coordinator.statuses.items():
            if (
                run_id != SAMPLE_RUN_ID
                and RUN_ID_PATTERN.fullmatch(run_id)
                and not _dashboard_run_path(run_id, recorded=False).is_file()
            ):
                runs.append(
                    {
                        "run_id": run_id,
                        "target": current.target,
                        "status": current.status,
                        "recorded": False,
                    }
                )

        if loop.RUNS_DIR.is_dir():
            for run_dir in loop.RUNS_DIR.iterdir():
                if (
                    not run_dir.is_dir()
                    or run_dir.name == SAMPLE_RUN_ID
                    or not RUN_ID_PATTERN.fullmatch(run_dir.name)
                ):
                    continue
                try:
                    summary = _read_dashboard_summary(run_dir.name, recorded=False)
                except HTTPException as exc:
                    logger.warning(
                        "Skipping unavailable dashboard run %s: %s",
                        run_dir.name,
                        exc.detail,
                    )
                    continue
                runs.append(_dashboard_run_option(summary, recorded=False))

        runs[1:] = sorted(runs[1:], key=lambda run: str(run["run_id"]), reverse=True)
        return {"runs": runs}

    @app.get("/dashboard/runs/{run_id}")
    async def get_dashboard_run(run_id: str) -> dict[str, object]:
        recorded = run_id == SAMPLE_RUN_ID
        if (
            not recorded
            and run_id in coordinator.statuses
            and not _dashboard_run_path(run_id, recorded=False).is_file()
        ):
            current = coordinator.statuses[run_id]
            return {
                "run_id": run_id,
                "target": current.target,
                "status": current.status,
                "recorded": False,
                "rounds": [],
                "progress": current.progress,
            }
        summary = _read_dashboard_summary(run_id, recorded=recorded)
        rounds = [
            {
                "round": record.round,
                "train_asr": record.train_asr,
                "holdout_asr": record.holdout_asr,
                "utility_pass_rate": record.utility_pass_rate,
                "status": record.status,
                "asr_by_category": record.asr_by_category,
                "holdout_asr_by_category": record.holdout_asr_by_category,
            }
            for record in summary.rounds
        ]
        progress = None
        if not recorded and run_id in coordinator.statuses:
            progress = coordinator.statuses[run_id].progress
        return {
            "run_id": summary.run_id,
            "target": summary.target,
            "status": summary.status,
            "recorded": recorded,
            "rounds": rounds,
            "progress": progress,
        }

    @app.get("/dashboard/runs/{run_id}/diffs")
    async def get_dashboard_diffs(run_id: str) -> dict[str, list[dict[str, str]]]:
        recorded = run_id == SAMPLE_RUN_ID
        if (
            not recorded
            and run_id in coordinator.statuses
            and not _dashboard_run_path(run_id, recorded=False).is_file()
        ):
            return {"diffs": []}
        _read_dashboard_summary(run_id, recorded=recorded)
        path = _dashboard_run_path(run_id, recorded=recorded)
        diffs_dir = path.parent / "diffs"
        diffs: list[dict[str, str]] = []
        if diffs_dir.is_dir():
            for diff_path in sorted(diffs_dir.glob("*.diff")):
                try:
                    text = diff_path.read_text(encoding="utf-8")
                except OSError as exc:
                    logger.exception("Could not read dashboard diff %s", diff_path.name)
                    raise HTTPException(
                        status_code=500,
                        detail="saved prompt diff is unavailable",
                    ) from exc
                diffs.append(
                    {
                        "name": diff_path.name,
                        "text": _CANARY_PATTERN.sub("[fake canary redacted]", text),
                    }
                )
        return {"diffs": diffs}

    card = AgentCard(
        name="redteam-agent",
        description="Starts local red-team evaluations against controlled sandbox agents.",
        supported_interfaces=[
            AgentInterface(
                url="http://localhost:8000/",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        version="0.1.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="start-redteam-run",
                name="Start Red-Team Run",
                description=(
                    "Starts an asynchronous evaluation for a known local sandbox "
                    "target. Input is JSON text with target and optional rounds."
                ),
                tags=["security-evaluation", "sandbox", "red-team"],
                examples=['{"target":"calendar_assistant","rounds":0}'],
            )
        ],
    )
    handler = DefaultRequestHandler(
        agent_executor=RedTeamAgentExecutor(coordinator),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    app.router.routes.extend(create_agent_card_routes(card))
    app.router.routes.extend(create_jsonrpc_routes(handler, rpc_url="/"))
    app.mount(
        "/dashboard", StaticFiles(directory=DASHBOARD_DIR, html=True), name="dashboard"
    )
    return app


def _dashboard_run_path(run_id: str, *, recorded: bool) -> Path:
    if not RUN_ID_PATTERN.fullmatch(run_id):
        raise HTTPException(status_code=404, detail="run not found")
    if recorded:
        if run_id != SAMPLE_RUN_ID:
            raise HTTPException(status_code=404, detail="run not found")
        return DASHBOARD_DIR / "sample_run" / "summary.json"
    runs_dir = loop.RUNS_DIR.resolve()
    run_dir = (runs_dir / run_id).resolve()
    if run_dir.parent != runs_dir:
        raise HTTPException(status_code=404, detail="run not found")
    return run_dir / "summary.json"


def _read_dashboard_summary(run_id: str, *, recorded: bool) -> RunSummary:
    path = _dashboard_run_path(run_id, recorded=recorded)
    try:
        summary = RunSummary.model_validate_json(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="run not found") from exc
    except (OSError, ValueError) as exc:
        logger.exception("Could not read dashboard run %s", run_id)
        raise HTTPException(
            status_code=500,
            detail="saved dashboard run is invalid",
        ) from exc
    if summary.run_id != run_id:
        logger.error("Dashboard run id mismatch while reading %s", run_id)
        raise HTTPException(status_code=500, detail="saved dashboard run is invalid")
    return summary


def _dashboard_run_option(
    summary: RunSummary,
    *,
    recorded: bool,
) -> dict[str, object]:
    return {
        "run_id": summary.run_id,
        "target": summary.target,
        "status": summary.status,
        "recorded": recorded,
    }


def _valid_run_id(run_id: str) -> bool:
    return RUN_ID_PATTERN.fullmatch(run_id) is not None


app = create_app()
