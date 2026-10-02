# Red-Team vs Blue-Team Loop for Nasiko

A local, controlled security-evaluation project that tests only sandbox agents we deploy ourselves. The loop will use deterministic fake-canary checks to score prompt-injection and data-leak probes, apply defensive prompt or gateway changes, and track round and holdout attack success rates.

## Current status

The Python package, core Pydantic models, deterministic judge, two local sandbox targets, async attacker runner, defender, loop orchestrator, holdout evaluator, and Typer CLI are implemented. The loop runs a baseline and up to 10 patch rounds, scores train and holdout sets separately, reports train/category and holdout/category ASR, caps concurrent requests, retries transient target request failures at most twice, emits progress events, and atomically saves round and summary JSON. The holdout evaluator freezes SHA-256 hashes of both attack files per run, rejects train/holdout payload overlap above 60%, and saves a baseline/final holdout comparison plus a generalization-gap warning when holdout ASR exceeds train ASR by more than 0.15. The defender builds general prompt hardening rules from successful training results only, applies prompt changes with run-scoped snapshots and diffs, and rolls back when a utility evaluator fails. The sandbox responder is fixture-based and does not interpret prompts, so a prompt-conditioned client and explicit utility evaluator must be injected to meaningfully verify patch effectiveness; no canary value is sent to the defender. The 30 manually drafted attacks are split between training and holdout libraries (21/9). Offline tests cover models, attack separation, deterministic scoring, target utility, attack execution, defender patching, rollback, persistence, retries, cancellation, holdout isolation, and CLI behavior. The API and dashboard are not implemented yet. Nasiko-specific implementation is gated on verified repository research and user confirmation in task 11.

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

Install the package in editable mode to use the CLI:

```powershell
python -m pip install -e .
redteam attacks list --split train
redteam run --target calendar_assistant --rounds 3 --fail-above 0.10
redteam report --run latest
```

The CLI uses the local fixture responder by default and runs offline. A loop can also run locally with `core.loop.run_loop`; a supplied utility-check callback is used for the baseline and required before any prompt patch is applied. A prompt-aware attack client and evaluator are needed to meaningfully verify patch effectiveness. The built-in fixture responder does not interpret prompts, so it is useful for deterministic harness tests but cannot by itself demonstrate prompt-hardening effectiveness.

## Safety scope

All probes are limited to locally deployed sandbox agents and fake canary values. Do not use real credentials, real user data, or targets outside the local sandbox.
