from collections.abc import Iterable, Mapping
from typing import Protocol

from core.judge import score_attack
from core.models import Attack, AttackResult
from targets.sandbox import SandboxTarget


class TargetRequestError(Exception):
    """An expected failure while sending a request to a target agent."""


class AttackClient(Protocol):
    async def send(self, target: str, payload: str) -> str:
        """Send one attack payload to the named target and return its response."""


class FakeSandboxClient:
    def __init__(self, targets: Mapping[str, SandboxTarget]) -> None:
        self._targets = dict(targets)

    async def send(self, target: str, payload: str) -> str:
        try:
            sandbox = self._targets[target]
        except KeyError as exc:
            raise TargetRequestError(f"unknown sandbox target: {target}") from exc
        return sandbox.respond(payload)


async def run_attacks(
    target: str,
    attacks: Iterable[Attack],
    client: AttackClient,
    canary: str,
) -> list[AttackResult]:
    results = []
    for attack in attacks:
        try:
            response = await client.send(target, attack.payload)
        except TargetRequestError as exc:
            results.append(score_attack(attack, "", canary, error=str(exc)))
        else:
            results.append(score_attack(attack, response, canary))
    return results
