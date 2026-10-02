import json
import os
from pathlib import Path

import click
import uvicorn
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
from starlette.applications import Starlette

TARGET_DIR = Path(__file__).parents[1]
TARGET_NAME = "memo_assistant"
SAFE_FALLBACK = (
    "I can help with the task, but I cannot share private setup instructions."
)


def _load_responses() -> dict[str, str]:
    path = TARGET_DIR / "benign_tasks.json"
    raw_tasks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw_tasks, list):
        raise TypeError(f"{path} must contain a JSON array")
    responses: dict[str, str] = {}
    for task in raw_tasks:
        if (
            not isinstance(task, dict)
            or not isinstance(task.get("request"), str)
            or not isinstance(task.get("response"), str)
            or not task["request"]
            or not task["response"]
        ):
            raise ValueError(f"{path} contains an invalid benign task")
        responses[task["request"]] = task["response"]
    if not responses:
        raise ValueError(f"{path} must define at least one benign task")
    return responses


class FixtureExecutor(AgentExecutor):
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        response = self._responses.get(context.get_user_input(), SAFE_FALLBACK)
        task = context.current_task or new_task_from_user_message(context.message)
        await event_queue.enqueue_event(task)
        await event_queue.enqueue_event(
            new_text_status_update_event(
                task_id=task.id,
                context_id=task.context_id,
                state=TaskState.TASK_STATE_WORKING,
                text="Processing sandbox request...",
            )
        )
        await event_queue.enqueue_event(
            new_text_artifact_update_event(
                task_id=task.id,
                context_id=task.context_id,
                name="sandbox-response",
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


def create_app(port: int = 8000) -> Starlette:
    agent_card = AgentCard(
        name=TARGET_NAME,
        description="Deterministic local memo sandbox for security evaluations.",
        supported_interfaces=[
            AgentInterface(
                url=f"http://localhost:{port}/",
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
                id="memo-help",
                name="Memo Help",
                description="Answers deterministic memo sandbox tasks.",
                tags=["memo", "sandbox"],
                examples=[
                    "Summarize this note: the library will close at 6 PM for maintenance."
                ],
            )
        ],
    )
    handler = DefaultRequestHandler(
        agent_executor=FixtureExecutor(_load_responses()),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = create_agent_card_routes(agent_card)
    routes.extend(create_jsonrpc_routes(handler, rpc_url="/"))
    return Starlette(routes=routes)


@click.command()
@click.option("--host", default="0.0.0.0")
@click.option("--port", default=lambda: int(os.environ.get("PORT", "8000")), type=int)
def main(host: str, port: int) -> None:
    uvicorn.run(create_app(port), host=host, port=port)


if __name__ == "__main__":
    main()
