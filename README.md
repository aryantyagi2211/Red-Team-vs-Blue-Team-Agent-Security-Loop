# Red-Team vs Blue-Team Loop for Nasiko

A local, controlled security-evaluation project that tests only sandbox agents we deploy ourselves. The loop will use deterministic fake-canary checks to score prompt-injection and data-leak probes, apply defensive prompt or gateway changes, and track round and holdout attack success rates.

## Current status

The Python package is scaffolded, the four core Pydantic models and deterministic judge are implemented, and two local sandbox targets with unique fake canaries and benign tasks are available. An async attacker runner sends attacks through a fake local client and scores responses. The 30 manually drafted attacks are split between training and holdout libraries (21/9). Offline tests cover models, attack split separation, deterministic scoring, ASR reporting, target utility, and attack execution; the loop, CLI, API, and dashboard are not implemented yet. Nasiko-specific implementation is gated on the verified repository research and user confirmation in task 11.

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
