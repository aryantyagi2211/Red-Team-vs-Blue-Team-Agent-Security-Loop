# Red-Team vs Blue-Team Loop for Nasiko

A local, controlled security-evaluation project that tests only sandbox agents we deploy ourselves. The loop will use deterministic fake-canary checks to score prompt-injection and data-leak probes, apply defensive prompt or gateway changes, and track round and holdout attack success rates.

## Current status

The Python package, four core Pydantic models, deterministic judge, two local sandbox targets, and async attacker runner are implemented. The deterministic defender builds general prompt hardening rules from successful training categories only, applies prompt changes with run-scoped snapshots and diffs, and rolls back when an injected utility evaluator fails. The sandbox responder is fixture-based and does not interpret prompts, so patch application requires an explicit utility evaluator rather than claiming that its canned responses measure prompt behavior. The 30 manually drafted attacks are split between training and holdout libraries (21/9). Offline tests cover models, attack separation, deterministic scoring, ASR reporting, target utility, attack execution, defender patching, artifact preservation, and rollback. The loop, CLI, API, and dashboard are not implemented yet. Nasiko-specific implementation is gated on verified repository research and user confirmation in task 11.

## Requirements

- Python 3.11 or newer

## Set up and test

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

The CLI and evaluation loop are not runnable yet; they will be added in later tasks. Defender patch applications require a run identifier and a utility-check callback that evaluates the updated target.

## Safety scope

All probes are limited to locally deployed sandbox agents and fake canary values. Do not use real credentials, real user data, or targets outside the local sandbox.
