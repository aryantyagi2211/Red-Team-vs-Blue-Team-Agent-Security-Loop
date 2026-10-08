# Two-minute demo: Red-Team vs Blue-Team Loop

## Before presenting

From the repository root, prepare the local environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

In a first PowerShell window, start the local API and dashboard:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/dashboard/` in a browser. The dashboard and its
vendored chart library run locally and do not require internet access.

## Presentation (about two minutes)

### 0:00–0:20 — Set the safety boundary

**Say:** “This demo only evaluates the calendar and memo agents we run in our
local sandbox. It uses fake canaries; no third-party targets, real secrets, or
user data are involved.”

### 0:20–0:45 — Run the offline CLI harness

In a second PowerShell window, run:

```powershell
.\.venv\Scripts\Activate.ps1
redteam run --target calendar_assistant --rounds 3
redteam report --run latest
```

The default local client is a deterministic safe fixture. It should complete
the baseline with train ASR 0%, holdout ASR 0%, and utility 100%. It stops
without patching because there are no successful attacks to learn from. This
demonstrates the harness and saved report, not a live model defense.

### 0:45–1:20 — Show the recorded hardening example

In the dashboard’s **Evaluation run** selector, choose
`RECORDED · Calendar assistant · sample-calendar-hardening`.

Point out the holdout ASR headline (100% baseline → 0% final), the round-by-round
train/holdout and utility chart, and the holdout category comparison. Expand
`calendar_assistant_round1.diff` to show the general defensive prompt rule.
The dashboard redacts fake canaries from the diff.

**Say:** “RECORDED RUN is a deterministic prompt-aware fixture simulation, not
a live Nasiko result. The chart is backed by the checked-in sample artifacts;
it is labeled so these results cannot be mistaken for a live evaluation.”

### 1:20–1:45 — Start a live local dashboard run

Select **Start local run** for `Calendar assistant`, leaving patch rounds at
3. Show the run status and chart update as the API reports progress. With the
default safe fixture, this run normally ends at the zero-ASR baseline and does
not create a prompt patch. Its metrics are from this local run and are kept
separate from the recorded example.

### 1:45–2:00 — Optional deployed-target smoke test

If the local Nasiko cluster is already running, call a benign task on a
deployed sandbox agent:

```powershell
nasiko chat --agent calendar_assistant "What weekday is two days after Monday?"
```

Expected response: “Two days after Monday is Wednesday.” This is a benign
connectivity check; the dashboard’s default run client does not target deployed
Nasiko agents. Do not describe the local fixture run or recorded sample as
results from a deployed target.

## Expected artifacts and cleanup

- CLI run records are written below `runs/` and are ignored by Git.
- The checked-in, canary-redacted sample is in `dashboard/sample_run/`.
- Stop Uvicorn with `Ctrl+C`. No remote service or credential is needed for the
  local CLI/API/dashboard demo.
