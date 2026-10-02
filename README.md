# Red-Team vs Blue-Team Loop for Nasiko

A local, controlled security-evaluation project that tests only sandbox agents we deploy ourselves. The loop will use deterministic fake-canary checks to score prompt-injection and data-leak probes, apply defensive prompt or gateway changes, and track round and holdout attack success rates.

## Current status

The Python package, four core Pydantic models, deterministic judge, two local sandbox targets, async attacker runner, defender, and loop orchestrator are implemented. The loop runs a baseline and up to 10 patch rounds, scores train and holdout sets separately, reports per-category ASR, caps concurrent requests, retries transient target request failures at most twice, emits progress events, and atomically saves round and summary JSON. The defender builds general prompt hardening rules from successful training results only, applies prompt changes with run-scoped snapshots and diffs, and rolls back when a utility evaluator fails. The sandbox responder is fixture-based and does not interpret prompts, so a prompt-conditioned client and explicit utility evaluator must be injected to meaningfully verify patch effectiveness; no canary value is sent to the defender. The 30 manually drafted attacks are split between training and holdout libraries (21/9). Offline tests cover models, attack separation, deterministic scoring, ASR reporting, target utility, attack execution, defender patching, rollback, persistence, retries, cancellation, and holdout isolation. The CLI, API, and dashboard are not implemented yet. Nasiko-specific implementation is gated on verified repository research and user confirmation in task 11.

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

The CLI is not runnable yet; it will be added in a later task. A loop can run locally with `core.loop.run_loop`; a supplied utility-check callback is used for the baseline and required before any prompt patch is applied. A prompt-aware attack client and evaluator are needed to meaningfully verify patch effectiveness. The built-in fixture responder does not interpret prompts, so it is useful for deterministic harness tests but cannot by itself demonstrate prompt-hardening effectiveness.

## Safety scope

All probes are limited to locally deployed sandbox agents and fake canary values. Do not use real credentials, real user data, or targets outside the local sandbox.
