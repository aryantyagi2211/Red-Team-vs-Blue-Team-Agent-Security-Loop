---
description: Project context, working style, and rules for the Red-Team vs Blue-Team loop on Nasiko
applyTo: "**"
---

# Project: Red-Team vs Blue-Team Loop for Nasiko

## Working style (important)
- Don't assume anything. If a requirement, file path, API, or Nasiko behavior is unclear, stop and ask me before writing code.
- Never invent Nasiko endpoints, config keys, or CLI flags. Read the repo/docs first, or ask me.
- If there are multiple ways to do something, give the options in 2-3 lines and ask which one I want.
- If something fails, tell me what you know and what you don't. Don't silently guess fixes.
- Ask one clear question at a time.

## What we're building
An autonomous security loop on top of Nasiko (AI agent control plane).
- Attacker agent: probes every registered agent with prompt-injection and data-leak attacks.
- Defender agent: reads failed-defense results and hardens agent system prompts and gateway rules.
- Judge/scorer: deterministically decides whether each attack succeeded.
- Loop: attack -> score -> defend -> re-attack. Track attack success rate (ASR) per round.
- Hold out a separate set of unseen attacks and report ASR on them too, so we can show the defender isn't just memorizing.
- Demo goal: ASR visibly drops (e.g. ~60% -> ~5%) across rounds, shown on a simple dashboard.

## Entry points
- One core module with a function like `run_loop(target, rounds)`.
- CLI (Typer) wraps it: `redteam run --target <agent> --rounds 3`, `redteam report --run latest`.
- A FastAPI wrapper exposes it as a Nasiko agent. Long runs return a `run_id` and are polled via `GET /runs/{run_id}`.
- CLI and API must call the same core code. No duplicated logic.

## Stack
- Python 3.11, FastAPI, Typer, async/await, pydantic models for all data shapes.
- Nasiko agents are A2A-style services registered in the Nasiko registry; the router picks agents.
- Docker for running targets. Keep everything runnable with one command.

## Rules for generated code
- Working demo beats polish. This is a one-day hackathon: prefer simple, readable code.
- Small functions, type hints, no unused abstractions.
- Every attack is a pydantic `Attack` object (id, category, payload, success_check).
- Success checks must be deterministic: use canary strings planted in target system prompts
  (e.g. SECRET-CANARY-1234). An attack succeeds if the canary or forbidden behaviour appears.
- Store every round as JSON in `runs/round_<n>.json` (attacks, results, ASR, defender changes).
- Defender changes must be applied as diffs to prompt/config files and logged.
- Never hardcode API keys. Read from environment variables via `.env` (gitignored).

## Safety scope
- Only attack agents we deploy ourselves in our own local Nasiko sandbox.
- Use fake secrets and canary tokens only. Never real credentials or real user data.
- Do not write attacks aimed at external systems or third-party services.

## Workflow
- Make small commits. After each feature, give a one-line way to test it.
- When unsure about Nasiko's API, read the repo docs/code first instead of guessing endpoints.