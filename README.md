# Red-Team vs Blue-Team Loop for Nasiko

A local, controlled security-evaluation project that tests only sandbox agents we deploy ourselves. The loop will use deterministic fake-canary checks to score prompt-injection and data-leak probes, apply defensive prompt or gateway changes, and track round and holdout attack success rates.

## Current status

The repository is scaffolded. The Python package installs and its six scaffold smoke tests pass on Python 3.14.2; Ruff reports no issues. Models, attack data, the judge, sandbox targets, the loop, CLI, API, and dashboard are not implemented yet. Nasiko-specific implementation is gated on the verified repository research and user confirmation in task 11.

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

The CLI and evaluation loop are not runnable yet; they will be added in later tasks.

## Safety scope

All probes are limited to locally deployed sandbox agents and fake canary values. Do not use real credentials, real user data, or targets outside the local sandbox.
