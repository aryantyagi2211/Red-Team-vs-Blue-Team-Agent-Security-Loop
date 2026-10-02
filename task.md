# Implementation checklist

Complete one task at a time. After each task, run its tests, review changes using the `code-review` skill, address High findings, update this checklist and the project documentation, check staged content for secrets, commit as `task <n>: <short title>`, then run `bash scripts/push.sh`. Stop after each task and wait for the user to say "next".

1. [x] **Scaffold**
   - **Goal:** Set up Python project metadata, the planned package directories, and a README skeleton.
   - **Files touched:** `pyproject.toml`, `README.md`, `.gitignore`, package `__init__.py` files, `.gitkeep` placeholders, `tests/test_scaffold.py`, and `project.md`.
   - **How to test:** Run `python -m pip install -e ".[dev]"` and `python -m pytest`.
   - **Done when:** The package installs, all planned directories exist, scaffold tests pass, and the README describes the project and current status.
   - **Completion note:** Scaffolded the Python package and planned directories; editable install succeeded on Python 3.14.2, all 6 smoke tests passed, and Ruff passed.

2. [x] **Models**
   - **Goal:** Define typed `Attack`, `AttackResult`, `Patch`, and `RoundRecord` data models.
   - **Files touched:** `core/models.py`, `tests/test_models.py`.
   - **How to test:** Run `python -m pytest tests/test_models.py`.
   - **Done when:** Model fields and validation behavior are covered by passing tests.
   - **Completion note:** Added the four Pydantic models, typed attack category/split/status values, deterministic success-check validation, bounded ASR/utility rates, and offline validation tests.

3. [x] **Attack library**
   - **Goal:** Draft training and holdout attack sets using the attack-library skill, with fake canaries only.
   - **Files touched:** `attacks/train.json`, `attacks/holdout.json`, `tests/test_attack_library.py`.
   - **How to test:** Run `python -m pytest tests/test_attack_library.py`.
   - **Done when:** Both JSON sets validate against the attack model and holdout cases are distinct from training cases.
   - **Completion note:** Added 30 manually drafted attacks (21 train, 9 holdout) across all four categories; model validation, split, ID, canary-check, and Jaccard overlap tests pass.

4. [x] **Deterministic judge**
   - **Goal:** Score attack results deterministically using planted fake canaries and forbidden behaviors.
   - **Files touched:** `core/judge.py`, `tests/test_judge.py`.
   - **How to test:** Run `python -m pytest tests/test_judge.py`.
   - **Done when:** Tests cover successful and unsuccessful outcomes without relying on an LLM judge.
   - **Completion note:** Added normalized, case-insensitive canary and forbidden-phrase matching plus split and category ASR reporting; all judge tests pass offline.

5. [x] **Sandbox targets**
   - **Goal:** Add locally controlled sandbox agents with fake canaries and benign tasks.
   - **Files touched:** `targets/`, `tests/test_targets.py`.
   - **How to test:** Run `python -m pytest tests/test_targets.py`.
   - **Done when:** Target fixtures respond to benign tasks and contain only fake canaries and data.
   - **Completion note:** Added two local deterministic sandbox targets with distinct prompt canaries, three benign tasks each, safe fallback responses, and offline utility/canary tests.

6. [x] **Attacker runner**
   - **Goal:** Run attack cases against a fake client without contacting external systems.
   - **Files touched:** `core/attacker.py`, `tests/test_attacker.py`.
   - **How to test:** Run `python -m pytest tests/test_attacker.py`.
   - **Done when:** Fake-client tests verify attack requests and collected results.
   - **Completion note:** Added an async attack runner and local fake sandbox client; tests cover request order, deterministic scoring, expected target errors, and propagation of unexpected failures.

7. [x] **Defender and patcher**
   - **Goal:** Apply logged prompt/config diffs, defend targets, and support rollback.
   - **Files touched:** `core/defender.py`, `tests/test_defender.py`.
   - **How to test:** Run `python -m pytest tests/test_defender.py`.
   - **Done when:** Tests verify patch application, change logging, and restoration after rollback.
   - **Completion note:** Added deterministic training-only prompt hardening, required prompt-aware utility evaluator injection, rollback, and run-scoped non-overwriting snapshots/diffs; 11 focused tests, all 66 suite tests, and Ruff passed.

8. [x] **Loop orchestrator**
   - **Goal:** Implement attack, score, defend, and re-attack rounds with per-round ASR records.
   - **Files touched:** `core/loop.py`, `tests/test_loop.py`.
   - **How to test:** Run `python -m pytest tests/test_loop.py`.
   - **Done when:** Fake-target tests verify the round sequence, ASR calculation, and JSON run records.
   - **Completion note:** Added baseline plus up to 10 patch rounds, isolated train-only defender input, train/holdout scoring, capped concurrency and retries, progress callbacks, atomic round/summary records, and cancellation/error persistence; 15 focused tests pass.

9. [ ] **Holdout evaluation**
   - **Goal:** Evaluate the defended target against unseen holdout attacks and report holdout ASR.
   - **Files touched:** `core/holdout.py`, `tests/test_holdout.py`.
   - **How to test:** Run `python -m pytest tests/test_holdout.py`.
   - **Done when:** Tests confirm the holdout set is evaluated separately and its ASR is reported.

10. [ ] **CLI**
    - **Goal:** Add Typer commands for running evaluations and reporting saved runs through the shared core.
    - **Files touched:** `cli/`, `pyproject.toml`, `tests/test_cli.py`, `README.md`.
    - **How to test:** Run `python -m pytest tests/test_cli.py` and check the CLI help output.
    - **Done when:** Run and report commands call the shared core and have passing CLI tests.

11. [ ] **Nasiko notes**
    - **Goal:** Read `../nasiko` and write factual integration notes; ask the user to confirm before any Nasiko-specific implementation.
    - **Files touched:** `docs/nasiko-notes.md`.
    - **How to test:** Review each note against source files in `../nasiko`; no code test applies.
    - **Done when:** Notes cite verified repository facts and the user has been asked to confirm before task 12.

12. [ ] **Nasiko client and deploy targets**
    - **Goal:** After user confirmation, implement a Nasiko client and deploy sandbox targets using verified interfaces only.
    - **Files touched:** `core/`, `targets/`, `tests/`, and relevant dependency/configuration files.
    - **How to test:** Run targeted client and deployment tests against the documented local sandbox.
    - **Done when:** Integration behavior is verified without invented endpoints, flags, or config keys.

13. [ ] **API wrapper**
    - **Goal:** Expose the shared loop through FastAPI, including asynchronous run IDs and polling, and deploy the red-team agent.
    - **Files touched:** `api/`, `tests/`, `pyproject.toml`, and deployment configuration.
    - **How to test:** Run targeted API tests with a fake client and verify run creation and polling.
    - **Done when:** API tests pass and the deployed agent invokes the same core loop as the CLI.

14. [ ] **Dashboard and sample run**
    - **Goal:** Add a dashboard and record a sample sandbox run.
    - **Files touched:** `dashboard/`, `runs/`, `tests/`, `README.md`.
    - **How to test:** Run dashboard tests and verify the sample run loads locally.
    - **Done when:** The dashboard displays recorded round and holdout metrics from a fake-canary run.

15. [ ] **Project review and demo**
    - **Goal:** Review the complete project, write the demo script, and finalize the README.
    - **Files touched:** `docs/demo-script.md`, `README.md`, and any files required for fixes from review.
    - **How to test:** Run the full test suite and follow the demo script end to end.
    - **Done when:** The project review is complete, the README reflects verified behavior, and the demo is reproducible.
