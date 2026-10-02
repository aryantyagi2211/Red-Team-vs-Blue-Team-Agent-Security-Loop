import asyncio
import json
import os
import re
import secrets
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from core.attacker import (
    AttackClient,
    FakeSandboxClient,
    TargetRequestError,
    run_attacks,
)
from core.defender import (
    UtilityChecker,
    apply_patch,
    build_defensive_patch,
    train_failure_categories,
)
from core.holdout import (
    GENERALIZATION_GAP_THRESHOLD,
    create_holdout_report,
    holdout_asr_by_category,
    load_fixed_splits,
    save_split_hashes,
)
from core.judge import ASRReport, calculate_asr
from core.models import Attack, AttackResult, Patch, RoundRecord
from targets.sandbox import SandboxTarget, load_target

RUNS_DIR = Path(__file__).parents[1] / "runs"
ATTACKS_DIR = Path(__file__).parents[1] / "attacks"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
CANARY_PATTERN = re.compile(r"SECRET-CANARY-[A-Z]+-[A-Z0-9]+")
CONCURRENCY_LIMIT = 5
MAX_ROUNDS = 10
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 0.05
UNAVAILABLE_PREFIX = "target unavailable after retries:"


class RunSummary(BaseModel):
    run_id: str
    target: str
    status: Literal["running", "ok", "error", "cancelled"]
    rounds: list[RoundRecord]
    stop_reason: str | None = None


ProgressCallback = Callable[[dict[str, object]], None]


class _RetryingClient:
    def __init__(self, client: AttackClient) -> None:
        self._client = client

    async def send(self, target: str, payload: str) -> str:
        for attempt in range(MAX_RETRIES + 1):
            try:
                return await self._client.send(target, payload)
            except TargetRequestError as exc:
                if str(exc).startswith("unknown sandbox target:"):
                    raise
                if attempt == MAX_RETRIES:
                    raise TargetRequestError(
                        f"{UNAVAILABLE_PREFIX} {exc}"
                    ) from exc
                await asyncio.sleep(RETRY_DELAY_SECONDS)
        raise RuntimeError("unreachable retry state")


def _new_run_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}_{secrets.token_hex(3)}"


def _target_canary(target: SandboxTarget) -> str:
    matches = CANARY_PATTERN.findall(target.prompt)
    if len(matches) != 1:
        raise ValueError(
            f"target {target.name!r} must contain exactly one fake canary"
        )
    return matches[0]


def _utility_pass_rate(
    target: SandboxTarget,
    utility_checker: UtilityChecker | None,
) -> float:
    if utility_checker is None:
        passed = sum(
            task.expected_contains in target.respond(task.request)
            for task in target.benign_tasks
        )
        total = len(target.benign_tasks)
    else:
        passed, total = utility_checker(target, target.benign_tasks)
    if total <= 0 or passed < 0 or passed > total:
        raise ValueError("utility checker returned invalid pass counts")
    return passed / total


def _atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(value, temporary, indent=2)
            temporary.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _emit(
    callback: ProgressCallback | None,
    run_id: str,
    round_number: int,
    step: str,
    **details: object,
) -> None:
    if callback is not None:
        callback(
            {
                "run_id": run_id,
                "round": round_number,
                "step": step,
                **details,
            }
        )


async def _run_phase(
    target: str,
    attacks: list[Attack],
    canary: str,
    client: AttackClient,
    on_result: Callable[[AttackResult], None] | None = None,
) -> list[AttackResult]:
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)
    retrying_client = _RetryingClient(client)
    tasks: list[asyncio.Task[tuple[int, AttackResult]]] = []

    async def run_one(index: int, attack: Attack) -> tuple[int, AttackResult]:
        async with semaphore:
            result = await run_attacks(
                target,
                [attack],
                retrying_client,
                canary,
            )
            return index, result[0]

    tasks = [
        asyncio.create_task(run_one(index, attack))
        for index, attack in enumerate(attacks)
    ]
    completed: dict[int, AttackResult] = {}
    try:
        for task in asyncio.as_completed(tasks):
            index, result = await task
            completed[index] = result
            if on_result is not None:
                on_result(result)
            if result.reason.startswith(UNAVAILABLE_PREFIX) or result.reason.startswith(
                "unknown sandbox target:"
            ):
                for pending in tasks:
                    if not pending.done():
                        pending.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                break
    except BaseException:
        for pending in tasks:
            if not pending.done():
                pending.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    return [completed[index] for index in sorted(completed)]


def _make_record(
    run_id: str,
    target: str,
    round_number: int,
    results: list[AttackResult],
    utility_pass_rate: float,
    status: Literal["ok", "rolled_back", "error"],
    patch: Patch | None,
) -> RoundRecord:
    asr: ASRReport = calculate_asr(results)
    return RoundRecord(
        run_id=run_id,
        target=target,
        round=round_number,
        train_asr=asr.train,
        holdout_asr=asr.holdout,
        asr_by_category=asr.by_category,
        holdout_asr_by_category=holdout_asr_by_category(results),
        utility_pass_rate=utility_pass_rate,
        status=status,
        results=results,
        patch=patch,
    )


async def run_loop(
    target: str,
    rounds: int = 3,
    run_id: str | None = None,
    on_progress: ProgressCallback | None = None,
    *,
    client: AttackClient | None = None,
    utility_checker: UtilityChecker | None = None,
) -> RunSummary:
    if not isinstance(rounds, int) or isinstance(rounds, bool) or rounds < 0:
        raise ValueError("rounds must be a non-negative integer")
    rounds = min(rounds, MAX_ROUNDS)
    actual_run_id = run_id if run_id is not None else _new_run_id()
    if not RUN_ID_PATTERN.fullmatch(actual_run_id):
        raise ValueError("run_id must be a safe alphanumeric identifier")

    run_dir = RUNS_DIR / actual_run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    summary = RunSummary(
        run_id=actual_run_id,
        target=target,
        status="running",
        rounds=[],
    )
    _atomic_write_json(run_dir / "summary.json", summary.model_dump(mode="json"))

    def persist_summary() -> None:
        _atomic_write_json(run_dir / "summary.json", summary.model_dump(mode="json"))

    current_round: int | None = None
    current_patch: Patch | None = None
    current_results: list[AttackResult] = []
    current_utility_pass_rate = 1.0

    def save_incomplete_round() -> None:
        if current_round is None:
            return
        round_path = run_dir / f"round_{current_round}.json"
        if round_path.exists():
            return
        record = _make_record(
            actual_run_id,
            target,
            current_round,
            current_results,
            current_utility_pass_rate,
            "error",
            current_patch,
        )
        _atomic_write_json(round_path, record.model_dump(mode="json"))
        summary.rounds.append(record)

    try:
        train_attacks, holdout_attacks = load_fixed_splits(
            actual_run_id,
            ATTACKS_DIR,
            RUNS_DIR,
        )
        initial_target = load_target(target)
        canary = _target_canary(initial_target)
        previous_results: list[AttackResult] = []
        for round_number in range(rounds + 1):
            save_split_hashes(
                actual_run_id,
                ATTACKS_DIR / "train.json",
                ATTACKS_DIR / "holdout.json",
                RUNS_DIR,
            )
            current_round = round_number
            current_patch = None
            current_results = []
            current_utility_pass_rate = 1.0
            _emit(on_progress, actual_run_id, round_number, "round_started")
            patch: Patch | None = None
            utility_pass_rate = (
                _utility_pass_rate(initial_target, utility_checker)
                if round_number == 0
                else 1.0
            )
            current_utility_pass_rate = utility_pass_rate
            status: Literal["ok", "rolled_back", "error"] = "ok"

            if round_number > 0:
                failed_categories = train_failure_categories(previous_results)
                patch = build_defensive_patch(
                    target,
                    round_number,
                    load_target(target).prompt,
                    failed_categories,
                )
                current_patch = patch
                if utility_checker is None:
                    raise ValueError(
                        "utility_checker is required before a prompt patch can be applied"
                    )
                patch_outcome = apply_patch(patch, actual_run_id, utility_checker)
                utility_pass_rate = patch_outcome.utility_pass_rate
                if patch_outcome.rolled_back:
                    status = "rolled_back"
                current_utility_pass_rate = utility_pass_rate
                _emit(
                    on_progress,
                    actual_run_id,
                    round_number,
                    "patch_applied" if patch_outcome.applied else "patch_rolled_back",
                    utility_pass_rate=utility_pass_rate,
                )

            phase_client = (
                client
                if client is not None
                else FakeSandboxClient({target: load_target(target)})
            )
            train_results = await _run_phase(
                target,
                train_attacks,
                canary,
                phase_client,
                current_results.append,
            )
            _emit(
                on_progress,
                actual_run_id,
                round_number,
                "train_completed",
                result_count=len(train_results),
            )
            results = list(train_results)
            unavailable = any(
                item.reason.startswith(UNAVAILABLE_PREFIX)
                or item.reason.startswith("unknown sandbox target:")
                for item in train_results
            )
            if not unavailable:
                phase_client = (
                    client
                    if client is not None
                    else FakeSandboxClient({target: load_target(target)})
                )
                holdout_results = await _run_phase(
                    target,
                    holdout_attacks,
                    canary,
                    phase_client,
                    current_results.append,
                )
                results.extend(holdout_results)
                _emit(
                    on_progress,
                    actual_run_id,
                    round_number,
                    "holdout_completed",
                    result_count=len(holdout_results),
                )
                unavailable = any(
                    item.reason.startswith(UNAVAILABLE_PREFIX)
                    or item.reason.startswith("unknown sandbox target:")
                    for item in holdout_results
                )

            if unavailable:
                status = "error"
            save_split_hashes(
                actual_run_id,
                ATTACKS_DIR / "train.json",
                ATTACKS_DIR / "holdout.json",
                RUNS_DIR,
            )
            record = _make_record(
                actual_run_id,
                target,
                round_number,
                results,
                utility_pass_rate,
                status,
                patch,
            )
            _atomic_write_json(
                run_dir / f"round_{round_number}.json",
                record.model_dump(mode="json"),
            )
            summary.rounds.append(record)
            previous_results = train_results
            persist_summary()
            current_round = None
            current_patch = None
            current_results = []
            _emit(on_progress, actual_run_id, round_number, "round_saved")

            if unavailable:
                summary.status = "error"
                summary.stop_reason = "target unavailable after request retries"
                persist_summary()
                _emit(
                    on_progress,
                    actual_run_id,
                    round_number,
                    "run_stopped",
                    reason=summary.stop_reason,
                )
                return summary
            if record.train_asr == 0.0:
                summary.stop_reason = "training ASR reached 0.0"
                break

        summary.status = "ok"
        if summary.stop_reason is None:
            summary.stop_reason = "maximum rounds completed"
        holdout_report = create_holdout_report(actual_run_id, run_dir)
        _atomic_write_json(
            run_dir / "holdout_report.json",
            holdout_report.model_dump(mode="json"),
        )
        persist_summary()
        warning = (
            holdout_report.generalization_gap > GENERALIZATION_GAP_THRESHOLD
        )
        _emit(
            on_progress,
            actual_run_id,
            summary.rounds[-1].round,
            "holdout_report",
            baseline_holdout_asr=holdout_report.baseline_holdout_asr,
            final_holdout_asr=holdout_report.final_holdout_asr,
            generalization_gap=holdout_report.generalization_gap,
            memorization_warning=warning,
        )
        return summary
    except asyncio.CancelledError:
        save_incomplete_round()
        summary.status = "cancelled"
        summary.stop_reason = "run cancelled"
        persist_summary()
        raise
    except Exception:
        save_incomplete_round()
        summary.status = "error"
        summary.stop_reason = "run failed; see the raised exception"
        persist_summary()
        raise
