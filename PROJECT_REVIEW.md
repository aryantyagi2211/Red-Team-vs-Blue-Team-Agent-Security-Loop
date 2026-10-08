# Final project review

Review performed 2026-10-09 against the repository project-review checklist.
The project is a local controlled red-team harness, not an AI model or defense
connected to the deployed Nasiko targets by default.

| Check | Status | Notes |
|---|---|---|
| Full offline tests | PASS | Clean virtual environment: 143 passed. Upstream Starlette/httpx and A2A protobuf deprecation warnings remain. |
| Fresh setup | PASS | Created `.venv` and installed the documented editable project with development dependencies. |
| CLI | PASS | Installed `redteam run --target calendar_assistant --rounds 3` and `redteam report --run latest` completed and saved a run. Default fixture yielded 0% baseline ASR and 100% utility. |
| API | PASS | Started a run, polled it to completion, fetched its report, and retrieved dashboard metrics. |
| Nasiko deployment and calls | PASS | `nasiko ps` reported both sandbox targets and the red-team agent running. Benign calls to calendar and memo targets passed. Started a red-team A2A run and polled status/report through the authenticated local Nasiko proxy with the project client. The `nasiko chat --agent redteam-agent <JSON>` CLI attempt returned an input-validation error; the direct A2A client path passed. |
| Recorded evaluation results | PASS | Recorded deterministic prompt-aware sample: holdout ASR 100% baseline → 0% final, utility 100%, generalization gap 0%. Clearly labeled as a fixture simulation, not live Nasiko results. |
| Holdout isolation | PASS | Code passes only prior train results to `train_failure_categories`; a test asserts holdout results are rejected before defender input. |
| Dashboard | PASS | Browser check loaded the sample and live local run; charts rendered at desktop and mobile widths. Built container served the page, sample API, and vendored chart. |
| Repository hygiene | PASS | `.env`, `.nasiko`, run records, and Python environments are ignored; no credentials or local bindings are tracked. |
| Documentation and tree | PASS | README, `project.md`, `task.md`, and the demo script describe the local fixture behavior and distinguish simulated sample metrics from deployed-agent calls. |
| Two-minute demo | PASS | Follow [docs/demo-script.md](./docs/demo-script.md); its CLI, dashboard, and optional benign target calls were exercised. |

## Review notes

- `python -m pytest`: 143 passed.
- Ruff lint (`ruff check .`): passed. A repository-wide `ruff format --check .`
  reported 17 existing files as unformatted; these files are outside the
  documentation-only Task 15 changes, so no unrelated reformatting was applied.
- The deployed red-team agent uses the offline fixture client by default; it
  does not attack the separately deployed Nasiko targets. The optional Nasiko
  demo step is only a benign target connectivity check.
- The dashboard does not display individual attack payloads or target
  responses. Prompt diffs are served with fake canary strings redacted.
