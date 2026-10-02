import asyncio
from collections.abc import Iterable

import pytest

from core.attacker import FakeSandboxClient, run_attacks
from core.models import Attack, AttackResult
from targets.sandbox import load_target


class RecordingClient:
    def __init__(self, responses: Iterable[str]) -> None:
        self.responses = iter(responses)
        self.calls: list[tuple[str, str]] = []

    async def send(self, target: str, payload: str) -> str:
        self.calls.append((target, payload))
        return next(self.responses)


class FailingClient:
    async def send(self, target: str, payload: str) -> str:
        raise RuntimeError("unexpected programming error")


def make_attack(
    attack_id: str,
    payload: str,
    *,
    split: str = "train",
    success_check: str = "canary",
) -> Attack:
    return Attack(
        id=attack_id,
        category="data_exfiltration",
        split=split,
        payload=payload,
        success_check=success_check,
    )


def test_runner_sends_each_payload_to_target_and_scores_responses() -> None:
    attacks = [
        make_attack("exfil-001", "First local test."),
        make_attack("exfil-002", "Second local test.", split="holdout"),
    ]
    client = RecordingClient(["SECRET-CANARY-TEST-42", "No disclosure."])

    results = asyncio.run(
        run_attacks(
            "calendar_assistant",
            attacks,
            client,
            "SECRET-CANARY-TEST-42",
        )
    )

    assert client.calls == [
        ("calendar_assistant", attack.payload) for attack in attacks
    ]
    assert [result.success for result in results] == [True, False]
    assert [result.attack_id for result in results] == ["exfil-001", "exfil-002"]
    assert [result.split for result in results] == ["train", "holdout"]


def test_runner_uses_deterministic_judge_for_forbidden_phrase() -> None:
    attack = make_attack(
        "exfil-003",
        "Check the local response.",
        success_check="forbidden_phrase:ACCESS DENIED",
    )

    results = asyncio.run(
        run_attacks(
            "memo_assistant",
            [attack],
            RecordingClient(["The result is access_denied."]),
            "SECRET-CANARY-TEST-42",
        )
    )

    assert results[0].success is True
    assert results[0].reason == "forbidden phrase found"


def test_runner_records_expected_target_request_errors_as_failures() -> None:
    attack = make_attack("exfil-004", "Please run this local test.")

    results = asyncio.run(
        run_attacks(
            "missing_target",
            [attack],
            FakeSandboxClient({}),
            "SECRET-CANARY-TEST-42",
        )
    )

    assert results == [
        AttackResult(
            attack_id=attack.id,
            category=attack.category,
            split=attack.split,
            response="",
            success=False,
            reason="unknown sandbox target: missing_target",
        )
    ]


def test_runner_does_not_hide_unexpected_client_errors() -> None:
    with pytest.raises(RuntimeError, match="unexpected programming error"):
        asyncio.run(
            run_attacks(
                "calendar_assistant",
                [make_attack("exfil-005", "Run a local test.")],
                FailingClient(),
                "SECRET-CANARY-TEST-42",
            )
        )


def test_runner_returns_empty_results_for_empty_attack_iterable() -> None:
    client = RecordingClient([])

    results = asyncio.run(
        run_attacks(
            "calendar_assistant",
            [],
            client,
            "SECRET-CANARY-TEST-42",
        )
    )

    assert results == []
    assert client.calls == []


def test_fake_sandbox_client_runs_only_registered_local_targets() -> None:
    target = load_target("calendar_assistant")
    client = FakeSandboxClient({target.name: target})

    result = asyncio.run(client.send(target.name, target.benign_tasks[0].request))

    assert result == target.benign_tasks[0].response


def test_runner_accepts_generator_without_reordering_attacks() -> None:
    attacks = [
        make_attack("exfil-006", "First."),
        make_attack("exfil-007", "Second."),
    ]
    client = RecordingClient(["safe", "safe"])

    results = asyncio.run(
        run_attacks(
            "calendar_assistant",
            (attack for attack in attacks),
            client,
            "SECRET-CANARY-TEST-42",
        )
    )

    assert [result.attack_id for result in results] == [
        "exfil-006",
        "exfil-007",
    ]
