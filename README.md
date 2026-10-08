# Red-Team vs Blue-Team Loop for Nasiko

A local, controlled security-evaluation project that tests only sandbox agents we deploy ourselves. The loop uses deterministic fake-canary checks to score prompt-injection and data-leak probes, apply defensive prompt changes, and track round and holdout attack success rates.

## Current status

The Python package, core Pydantic models, deterministic judge, two local sandbox targets, async attacker runner, defender, loop orchestrator, holdout evaluator, Typer CLI, FastAPI wrapper, A2A red-team agent, and local dashboard are implemented. The loop runs a baseline and up to 10 patch rounds, scores train and holdout sets separately, reports train/category and holdout/category ASR, caps concurrent requests, retries transient target request failures at most twice, emits progress events, and atomically saves round and summary JSON. The holdout evaluator freezes SHA-256 hashes of both attack files per run, rejects train/holdout payload overlap above 60%, and saves a baseline/final holdout comparison plus a generalization-gap warning when holdout ASR exceeds train ASR by more than 0.15. The defender builds general prompt hardening rules from successful training results only, applies prompt changes with run-scoped snapshots and diffs, and rolls back when a utility evaluator fails. The sandbox responder is fixture-based and does not interpret prompts, so a prompt-conditioned client and explicit utility evaluator must be injected to meaningfully verify patch effectiveness; no canary value is sent to the defender. The 30 manually drafted attacks are split between training and holdout libraries (21/9). The full offline suite passes (143 tests), and the final project review and reproducible demo have been completed. A separate end-to-end integration demo at [demos/end-to-end-demo/README.md](demos/end-to-end-demo/README.md) exercises the real loop against two deterministic local HTTP agents; it measured holdout ASR 77.8% → 0% with 100% benign utility, and is explicitly not a live LLM/Nasiko result. Both Nasiko sandbox targets have also been live-tested through the authenticated local gateway with benign requests and fake-canary non-disclosure probes. The deployed red-team agent's A2A start and authenticated status/report polling have been verified, but its default client remains the offline deterministic fixture, not a live target client. The dashboard is served at `/dashboard/`, plots train/holdout ASR and utility by round, compares holdout ASR by category, polls local runs, and displays canary-redacted prompt diffs. Its recorded fixture sample is simulated, not a live Nasiko result. See [docs/nasiko-notes.md](docs/nasiko-notes.md) and [docs/demo-script.md](docs/demo-script.md).

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

Run the REST API locally:

```powershell
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Start a run with `POST /runs` and JSON `{"target":"calendar_assistant","rounds":0}`.
The API returns HTTP 202 with a `run_id`; poll `GET /runs/{run_id}` and read
`GET /runs/{run_id}/report`. The deployed A2A agent accepts the same JSON object
as text in an A2A 1.0 `SendMessage` request and replies with the run ID. The API
and agent both call `core.loop.run_loop`; by default it uses the local
deterministic fixture client. Build the Nasiko image from the repository root
and deploy the tagged image:

```powershell
docker build -f api/Dockerfile -t nasiko-redteam-agent:0.1.0 .
nasiko deploy nasiko-redteam-agent:0.1.0 --name redteam-agent --port 8000 --version 0.1.0 --yes
```

The image excludes `.env`, local Nasiko bindings, generated `runs/` records, and tests.

### Dashboard

With the API running, open [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/).
The page lists saved local runs, starts a local fixture evaluation, and polls
its metrics as rounds finish. It uses a vendored Chart.js bundle, so charts do
not require an internet connection. The included `sample-calendar-hardening`
record is labeled **RECORDED RUN**: it was generated using a deterministic,
prompt-aware fake client to demonstrate a baseline and patched round. It is
not a live Nasiko target result. The dashboard API returns aggregate metrics
only; fake canaries are redacted from prompt diffs, and attack payloads and
target responses are not shown.

For a reproducible two-minute walkthrough, including the distinction between
the recorded simulation and local fixture runs, follow
[docs/demo-script.md](docs/demo-script.md). The final validation evidence and
known integration caveats are described above and in the demo and Nasiko
integration notes.

The CLI uses the local fixture responder by default and runs offline. A loop can also run locally with `core.loop.run_loop`; a supplied utility-check callback is used for the baseline and required before any prompt patch is applied. A prompt-aware attack client and evaluator are needed to meaningfully verify patch effectiveness. The built-in fixture responder does not interpret prompts, so it is useful for deterministic harness tests but cannot by itself demonstrate prompt-hardening effectiveness.

### Nasiko A2A targets

Both sandbox targets include an A2A 1.0 service, static agent card, and Docker build context. Offline tests exercise each service in-process; live validation also confirmed both deployed targets return their benign fixtures and do not disclose their planted fake canaries through the Nasiko gateway. Use the complete local proxy endpoint shown by `nasiko ps` and pass the active bearer token explicitly as `auth_token` when constructing a `NasikoClient`; never hardcode or print it. The client rejects non-loopback URLs and canonicalizes Nasiko's root proxy URL to the path form used by the Nasiko chat CLI. On Windows, the control plane must share the Docker agent network to proxy to deployed targets; see `docs/nasiko-notes.md`.

## Safety scope

All probes are limited to locally deployed sandbox agents and fake canary values. Do not use real credentials, real user data, or targets outside the local sandbox.
