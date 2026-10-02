---
name: holdout-eval
description: Keeps the train/holdout attack split clean and reports generalization so the ASR improvement is believable. Use when working on attacks/holdout.json, train vs holdout ASR, memorization checks, split overlap, or evaluation reports.
---

# Holdout Eval

Holdout attacks measure whether the defender really improved or just memorized the train attacks.

## Rules
- The split is fixed after the first run. Save a hash of both files in `runs/<run_id>/split_hash.txt` and fail loudly if the hash changes mid-run.
- Holdout attacks and results never reach the defender, the patch rationale, or any prompt. Never tune anything on holdout.
- Holdout wording and style must differ from train. Add a check that flags any holdout attack whose word overlap with a train attack is above 60% (simple Jaccard on word sets). Flagged attacks need my review.

## Reporting
- Every round reports train ASR, holdout ASR, and holdout ASR per category.
- Generalization gap = holdout ASR minus train ASR. If the gap is above 0.15 after the final round, print a warning that the defender may be memorizing.
- The final report shows the baseline holdout ASR next to the final holdout ASR. That pair is the headline number.

## Tests (tests/test_holdout.py)
- Hash changes are detected.
- Overlap check flags near-duplicate attacks and passes distinct ones.
- Gap warning triggers above the threshold and not below.
- Holdout data never appears in the defender input.

## Working style
- If a threshold or split rule is unclear, ask me before changing it. Don't assume.