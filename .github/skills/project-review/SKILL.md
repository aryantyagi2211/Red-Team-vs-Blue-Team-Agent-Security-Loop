---
name: project-review
description: Checks the whole project end to end to confirm everything works before the demo. Use when asked to review the project, run a final check, verify the demo, or after the last task.
---

# Project Review

Run this after the final task and again right before the demo. Write the result to `PROJECT_REVIEW.md` as a pass/fail table.

## Checks
- Tests: the full test suite passes offline.
- Fresh setup: following the README from scratch works (install, run).
- CLI: `redteam run --target <name> --rounds 3` completes and saves `runs/<run_id>/`.
- API: start a run, poll it, and fetch the report.
- Nasiko: targets and the red-team agent are deployed and callable, matching `docs/nasiko-notes.md`.
- Results: baseline holdout ASR vs final holdout ASR, utility pass rate, generalization gap.
- Isolation: confirm by test and by reading code that holdout never reaches the defender.
- Dashboard: loads with a live run and with `sample_run`.
- Repo hygiene: `.env` and secrets not committed, `.gitignore` correct, no leftover debug files.
- Docs: `README.md`, `project.md`, and `task.md` are accurate and every task is ticked or has a note.
- Demo: a 2-minute demo script exists in `docs/demo-script.md` and every step in it works.

## Output
- A table of check, status, and notes. List what's broken, ordered by how badly it hurts the demo.
- Do not hide failures. If a check can't run, mark it "not verified" and say why.

## Working style
- If you can't tell whether something passes, say so and ask me. Don't assume.