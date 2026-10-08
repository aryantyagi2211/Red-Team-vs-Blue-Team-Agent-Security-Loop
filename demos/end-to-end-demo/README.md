# Red-Team Loop End-to-End Demo

This demo exercises the real `redteam` evaluation loop against two deterministic
HTTP agents stored here. The agents bind only to `127.0.0.1`; they use fake
canaries and canned benign tasks, with no model API, credentials, external
targets, or real data.

The demo intentionally simulates vulnerable agents: before hardening, their
deterministic behavior returns the fake canary for prompt-injection-style
requests. The red-team loop evaluates the project's existing train and holdout
attacks; its blue-team defender adds a general instruction-boundary rule to the
agent's prompt files; then the loop retests attacks and benign tasks. These
results demonstrate the control flow and are **not live LLM or Nasiko results**.

## Run the end-to-end test

From PowerShell, install the project from the repository root if you have not
already:

```powershell
python -m pip install -e ".[dev]"
```

Then run both demo agents and the evaluation harness from this folder:

```powershell
cd demos\end-to-end-demo
..\..\.venv\Scripts\python.exe .\run_demo.py
```

The runner starts the local agent service on `127.0.0.1:8766`, checks health,
runs the real red-team/blue-team loop against `calendar_assistant` and
`memo_assistant`, prints metrics, redacts fake-canary responses in the saved
JSON records, and stops the service. It resets each selected prompt to its
pristine `prompt.initial.txt` before starting that target's run. The successful
blue-team patch remains in `prompt.txt` afterward so you can inspect it.

Expected outcome for both agents:

| Stage | Train ASR | Holdout ASR | Utility |
|---|---:|---:|---:|
| Baseline | 100% | 78% (7/9 attacks) | 100% |
| After the blue-team prompt patch | 0% | 0% | 100% |

Attack cases, round reports, holdout report, prompt snapshots, and patch diffs
are saved in `<repository-root>\runs\<run_id>\`. The run records appear in the
main project's local dashboard at
[http://127.0.0.1:8765/dashboard/](http://127.0.0.1:8765/dashboard/) if that
dashboard server is running; otherwise start the API from a separate terminal:

```powershell
cd ..\..
.\.venv\Scripts\python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8765
```

Select the completed run for either demo target to see the ASR/utility chart
and prompt diff. Do not use **Start local run** in that dashboard to repeat
this external-agent test; its start button invokes the main project's default
fixture client. Repeat the end-to-end HTTP-agent test with `run_demo.py`.

## Inspect and reset

- Agent source: `demo_agents.py`
- Agent prompts and benign tasks: `agents\calendar_assistant\` and
  `agents\memo_assistant\`
- Loop integration and assertions: `run_demo.py`
- The demo includes copies of the source attack splits under `attacks\`; the
  main project checks their fixed-split hashes as usual.
- `prompt.initial.txt` is the clean prompt; `prompt.txt` shows the latest
  prompt after hardening. A new demo run automatically restores the clean
  prompt first.
- Only generated local run artifacts under the main project's ignored `runs\`
  directory need manual cleanup.

## What this demonstrates

1. **Attack:** the real project runner sends training and held-out payloads to
   local HTTP agents and deterministically scores fake-canary disclosure.
2. **Harden:** the real defender uses only successful training results to
   build and apply a prompt patch to the selected external agent's prompt file.
3. **Measure:** the loop retests train and holdout attacks, checks benign task
   utility before accepting a patch, and saves ASR, utility, generalization,
   and diff artifacts.

This is a controlled integration test of the project's loop and patch
mechanism, not a security certification or a test of real model behavior.
