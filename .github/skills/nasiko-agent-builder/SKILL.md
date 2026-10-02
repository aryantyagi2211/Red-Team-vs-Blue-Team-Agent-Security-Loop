---
name: nasiko-agent-builder
description: How to build, register, and deploy agents in Nasiko using the real repo as the source of truth. Use when creating target agents, wrapping the red-team loop as a Nasiko agent, deploying, registering, or calling agents through the Nasiko gateway or CLI.
---

# Nasiko Agent Builder

Nasiko is cloned at `../nasiko`. It is read-only. Never edit it.

## Rule zero: read first, never guess
- Before writing any Nasiko-related code, read `../nasiko` README, docs, CLI help, and the example agents.
- Never invent endpoints, request/response formats, config keys, agent manifest fields, or CLI flags.
- Write what you found into `docs/nasiko-notes.md`, with the file path in the repo for every fact (setup commands, agent structure, how to register, how to deploy, how to call through the gateway).
- If the repo doesn't answer something, stop and ask me.

## Building agents
- Copy the structure of an existing example agent from the repo. Change only what we need.
- Target agents live in `targets/<name>/`, each with: `prompt.txt` (live system prompt), a planted fake canary, `benign_tasks.json`, and whatever Nasiko needs to register it.
- The red-team loop gets wrapped as one more Nasiko agent in `api/`. It calls the same `core.loop.run_loop`.

## Order of work
1. Get Nasiko running locally using the documented commands. Record them in the notes.
2. Deploy one hand-written dummy agent and call it through the gateway.
3. Only after step 2 works, deploy our target agents.
4. Only after targets work, deploy the red-team agent.

## Calling agents
- Use the exact request format found in the repo. Put it in one function `core/nasiko_client.py` so only one file knows the format.
- Handle timeouts and errors. Max 2 retries per call.
- Offline fallback: keep a fake client for tests so nothing needs Nasiko running.

## Working style
- If Nasiko behavior, ports, auth, or formats are unclear, ask me before coding. Don't assume.