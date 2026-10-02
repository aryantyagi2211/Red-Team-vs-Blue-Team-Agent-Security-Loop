from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

AttackCategory = Literal[
    "prompt_leak",
    "instruction_override",
    "indirect_injection",
    "data_exfiltration",
]
AttackSplit = Literal["train", "holdout"]


class Attack(BaseModel):
    id: str
    category: AttackCategory
    split: AttackSplit
    payload: str
    success_check: str

    @field_validator("success_check")
    @classmethod
    def validate_success_check(cls, value: str) -> str:
        if value == "canary":
            return value
        prefix = "forbidden_phrase:"
        if value.startswith(prefix) and value[len(prefix) :].strip():
            return value
        raise ValueError(
            "success_check must be 'canary' or 'forbidden_phrase:<text>'"
        )


class AttackResult(BaseModel):
    attack_id: str
    category: str
    split: str
    response: str
    success: bool
    reason: str


class Patch(BaseModel):
    target: str
    round: int
    old_prompt: str
    new_prompt: str
    rationale: str
    gateway_rules: list[str] = Field(default_factory=list)


class RoundRecord(BaseModel):
    run_id: str
    target: str
    round: int
    train_asr: float = Field(ge=0.0, le=1.0)
    holdout_asr: float = Field(ge=0.0, le=1.0)
    asr_by_category: dict[str, Annotated[float, Field(ge=0.0, le=1.0)]]
    holdout_asr_by_category: dict[
        str, Annotated[float, Field(ge=0.0, le=1.0)]
    ] = Field(default_factory=dict)
    utility_pass_rate: float = Field(ge=0.0, le=1.0)
    status: Literal["ok", "rolled_back", "error"]
    results: list[AttackResult]
    patch: Patch | None
