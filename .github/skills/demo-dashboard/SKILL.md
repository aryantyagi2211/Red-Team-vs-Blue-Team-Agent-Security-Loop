---
name: demo-dashboard
description: Builds the demo dashboard that charts ASR per round and shows before/after prompt diffs. Use when working on dashboard/, charts, summary.json display, sample demo data, or the final presentation view.
---

# Demo Dashboard

The dashboard exists for the demo. It must be simple, fast, and never blank.

## What it shows
- Line chart: train ASR and holdout ASR per round (round 0 is the baseline).
- Utility pass rate per round, so judges see the agent still works.
- ASR by category, baseline vs final.
- Before/after system prompt diff for the selected target and round.
- A headline card: baseline holdout ASR -> final holdout ASR.

## How
- One static HTML page plus a small JS file, served by the existing FastAPI app. No build step, no big framework.
- Reads `runs/<run_id>/summary.json` and `runs/diffs/*.diff` through simple API routes.
- Use one chart library, loaded from a local copy in `dashboard/vendor/` so it works without internet.
- Poll the run status while a run is in progress so the chart fills live.

## Demo safety
- Keep a recorded real run in `dashboard/sample_run/`. If a live run fails, the dashboard loads that one and clearly labels it "recorded run".
- Never show fake numbers as live results.

## Rules
- Clean, readable, large fonts, high contrast. It will be shown on a projector.
- Handle missing files and half-finished runs without errors.

## Working style
- If a layout choice or data shape is unclear, ask me before building. Don't assume.