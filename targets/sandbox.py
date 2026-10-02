import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

TARGETS_DIR = Path(__file__).parent
TARGET_NAME_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")
SAFE_FALLBACK = (
    "I can help with the task, but I cannot share private setup instructions."
)


class BenignTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    request: str = Field(min_length=1)
    response: str = Field(min_length=1)
    expected_contains: str = Field(min_length=1)


@dataclass(frozen=True)
class SandboxTarget:
    name: str
    prompt: str
    benign_tasks: tuple[BenignTask, ...]

    def respond(self, request: str) -> str:
        for task in self.benign_tasks:
            if request == task.request:
                return task.response
        return SAFE_FALLBACK


def load_target(name: str) -> SandboxTarget:
    if not TARGET_NAME_PATTERN.fullmatch(name):
        raise ValueError("target name must be a lowercase identifier")

    target_dir = (TARGETS_DIR / name).resolve()
    if target_dir.parent != TARGETS_DIR.resolve():
        raise ValueError("target must be a direct child of the targets directory")

    prompt_path = target_dir / "prompt.txt"
    tasks_path = target_dir / "benign_tasks.json"
    prompt = prompt_path.read_text(encoding="utf-8")
    raw_tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    if not isinstance(raw_tasks, list):
        raise TypeError(f"{tasks_path} must contain a JSON array")

    tasks = tuple(BenignTask.model_validate(item) for item in raw_tasks)
    if not tasks:
        raise ValueError(f"{tasks_path} must define at least one benign task")

    return SandboxTarget(name=name, prompt=prompt, benign_tasks=tasks)
