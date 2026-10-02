---
name: cli-and-api-wrapper
description: How the Typer CLI and FastAPI wrapper both call the same run_loop core, including run_id polling and CI exit codes. Use when writing cli/, api/, redteam commands, run endpoints, progress output, or --fail-above.
---

# CLI and API Wrapper

Both entry points are thin. They parse input, call `core.loop.run_loop`, and format output. No attack, judge, or defender logic lives here.

## CLI (cli/main.py, Typer)
- `redteam run --target <name> --rounds 3 [--fail-above 0.10]`
- `redteam report --run latest` (or a run id)
- `redteam attacks list [--split train|holdout]`
- Install with `pip install -e .` so `redteam` works from any folder (entry point in pyproject.toml).
- `run` prints one live line per step using the `on_progress` callback, e.g. `Round 1: train ASR 60% -> patching -> holdout ASR 55%`.
- With `--fail-above X`, exit code 1 if the final holdout ASR is above X, else 0. Without it, exit 0 unless an error happened.

## API (api/app.py, FastAPI)
- `POST /runs` body `{"target": "...", "rounds": 3}` starts the loop in the background and returns `{"run_id": "..."}` immediately.
- `GET /runs/{run_id}` returns status (`running`, `done`, `error`) and the latest progress.
- `GET /runs/{run_id}/report` returns `summary.json`.
- Do not hold a request open while the loop runs.
- The request and response shape Nasiko expects for agents is NOT assumed. Follow `docs/nasiko-notes.md`, and ask me if it's missing.

## Rules
- Validate inputs with pydantic. Unknown target returns a clear error.
- Cap `rounds` at 10.
- Run state lives in `runs/<run_id>/`. The API reads the same files the CLI reads.

## Tests
- CLI: use Typer's test runner with a fake loop, check output and exit codes.
- API: use FastAPI's test client, check start, poll, and report.
- Both must run offline.

## Working style
- If a command name, flag, or endpoint is unclear, ask me before adding it. Don't assume.