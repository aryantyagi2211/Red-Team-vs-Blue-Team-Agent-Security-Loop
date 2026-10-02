---
name: loop-orchestrator
description: Runs the attack, score, defend, re-attack rounds and saves each round to runs/. Use when writing or editing loop.py, run_loop, round logic, stop conditions, progress callbacks, run IDs, or runs/round_<n>.json output.
---

# Loop Orchestrator

One core function runs the whole red-team loop. The CLI and the API both call it. No loop logic anywhere else.

## Entry point (core/loop.py)

```python
async def run_loop(target: str, rounds: int = 3, run_id: str | None = None,
                   on_progress: Callable[[dict], None] | None = None) -> RunSummary:
    ...
```

- `on_progress` is called after every step so the CLI can print live updates and the API can store status for polling. The loop never prints directly.
- If `run_id` is None, generate one (timestamp plus short random suffix).

## Round flow
- **Round 0 (baseline):** run all train and holdout attacks against the untouched target. Save as `round_0.json`. No defender step.
- **Rounds 1..N:**
  1. Run the defender on the failed **train** attacks from the previous round and apply the patch (see defender-patcher skill).
  2. Run the utility check. If it fails, roll back and mark the round as `rolled_back`.
  3. Re-run all train attacks and all holdout attacks against the patched target.
  4. Judge every result (see deterministic-judge skill) and compute ASR for train, holdout, and per category.
  5. Save the round and emit progress.
- Holdout attacks are run and scored every round, but their results never go to the defender.

## Stop conditions
- Stop after `rounds` rounds, or early if train ASR is 0.0 for the current round.
- Never loop forever. Enforce a max of 10 rounds even if the caller asks for more.
- If the target agent is unreachable, stop and report the error. Don't retry endlessly: at most 2 retries per attack with a short delay.

## Output files
Save to `runs/<run_id>/round_<n>.json` and `runs/<run_id>/summary.json`.

```python
class RoundRecord(BaseModel):
    run_id: str
    target: str
    round: int
    train_asr: float
    holdout_asr: float
    asr_by_category: dict[str, float]
    utility_pass_rate: float
    status: Literal["ok", "rolled_back", "error"]
    results: list[AttackResult]
    patch: Patch | None
```

`summary.json` has the ASR and utility numbers for every round, so the dashboard and `redteam report` can read one file.

## Rules
- Attacks run with a concurrency limit (default 5) so we don't overload the target or the model API.
- Save each round to disk as soon as it finishes, so a crash keeps earlier rounds.
- Write files atomically (write to a temp file, then rename).
- The same inputs should give comparable results. Set any model temperature to 0 for target, judge-adjacent, and defender calls unless I say otherwise, and log the model name used.
- Use async with a clean cancel: if the run is cancelled, mark the status and save what exists.

## Tests (tests/test_loop.py)
Use fake target and fake defender so tests run offline:
- baseline round runs with no patch
- ASR drops after a patch that fixes a failing attack
- early stop when train ASR reaches 0
- rolled-back round is recorded with status `rolled_back`
- holdout results never appear in the defender's input
- progress callback gets called in order
- a crash mid-run leaves earlier round files intact

## Working style
- If round order, stop rule, file format, or concurrency is unclear, ask me before changing it. Don't assume.