# Nasiko integration research notes

These notes record facts verified in the read-only sibling checkout at
`../nasiko`. No Nasiko source files were changed. Nasiko CLI help could not be
executed because `cargo` is not installed in this environment; command syntax
below was cross-checked against the repository README, CLI design document, and
CLI source.

## Running Nasiko locally

- The documented Windows Docker setup is to copy `.env.example` to `.env`,
  configure the documented local settings, then run `docker compose up -d`.
  The Compose stack starts the server with Postgres, Redis, RustFS, and the
  observability services. It is stopped with `docker compose down`.
  Sources: `../nasiko/README.md` (Quick Start and Windows setup),
  `../nasiko/docker-compose.yml`.
- A separate source-development path uses Rust and `just`: start infrastructure
  with `just infra`, configure `server/.env` from `server/.env.example`, and run
  `just dev` (or `just run`). The README gives the server address as
  `http://localhost:8080`.
  Source: `../nasiko/README.md` (Developer / Rust setup).
- For agent development without a cluster, `nasiko run` builds and starts an
  agent locally, defaulting to port 8000. The lifecycle guide then uses
  `nasiko chat http://localhost:8000 "What can you do?"` to call it.
  Source: `../nasiko/docs/AGENT_LIFECYCLE.md` (Prerequisites, Phase 2: Test).
- For a local control plane, the lifecycle guide documents `nasiko up`,
  `nasiko deploy .`, `nasiko ps`, and `nasiko down`.
  Source: `../nasiko/docs/AGENT_LIFECYCLE.md` (Local cluster workflow).

## Agent project structure and example

- The documented agent project contains `AgentCard.json`, `Dockerfile`, and
  agent source; deployment creates `.nasiko/agent.json` as a local binding to
  the deployed agent ID. The guide says not to edit the generated binding and
  to ignore it in Git.
  Source: `../nasiko/docs/AGENT_LIFECYCLE.md` (Project Structure).
- The checked-in Python example is `agents/currency-agent/`. It implements an
  A2A executor, creates an agent card, serves the card and JSON-RPC routes with
  Starlette, and starts Uvicorn. Its Dockerfile uses Python 3.13, installs the
  project package, and runs `main.py` on port 8000.
  Sources: `../nasiko/agents/currency-agent/main.py`,
  `../nasiko/agents/currency-agent/AgentCard.json`,
  `../nasiko/agents/currency-agent/Dockerfile`.
- The lifecycle guide says `nasiko validate` checks the agent directory,
  `AgentCard.json`, and `Dockerfile`.
  Source: `../nasiko/docs/AGENT_LIFECYCLE.md` (Phase 1: Create).

## Registration, deployment, and calling

- The deployment workflow requires a connected cluster; the README's example
  connects to `http://localhost:8080` and authenticates before scaffolding and
  deploying. The lifecycle guide documents `nasiko deploy .` for a source
  directory and states it builds, pushes, registers or updates, deploys, and
  writes `.nasiko/agent.json`. `nasiko ps` lists deployed agents.
  Sources: `../nasiko/README.md` (Deploying your own agents),
  `../nasiko/docs/AGENT_LIFECYCLE.md` (Phase 3: Deploy and Phase 4: Operate),
  `../nasiko/cli/src/commands/deploy.rs`.
- The documented chat CLI accepts a deployed agent name or UUID, a direct A2A
  URL, or the active cluster's orchestrator. The CLI design gives
  `nasiko chat my-agent "hi"` as a name-resolved call and
  `nasiko chat http://localhost:8000 "hello"` as a direct local-agent call.
  Sources: `../nasiko/docs/CLI_DESIGN.md` (How `chat` Works),
  `../nasiko/cli/src/lib.rs` (Chat arguments).
- The CLI implementation documents the control-plane orchestrator endpoint as
  `/api/orchestrator/a2a` and the deployed-agent proxy as
  `/api/agents/{id}{transport_path}`; it says the latter path is printed by
  `nasiko ps` and comes from the agent card. Nasiko describes the server as the
  sole ingress and says inter-agent calls are proxied through it; there is no
  separate gateway service.
  Sources: `../nasiko/cli/src/commands/chat.rs`,
  `../nasiko/docs/A2A_PROTOCOL.md` (Overview and Nasiko Architecture Mapping).
- The documented A2A binding is JSON-RPC 2.0 over HTTP(S), with
  `Content-Type: application/json` and `A2A-Version: 1.0`; the protocol guide
  shows `SendMessage` requests with message text in `params.message.parts`.
  Sources: `../nasiko/docs/A2A_PROTOCOL.md` (Transport & Wire Format,
  Request Format, and Operations).

## Open question before integration

There is a protocol-version inconsistency in the checked-in material. The
README says a deployed agent must speak A2A v1.0, and `docs/A2A_PROTOCOL.md`
documents `A2A-Version: 1.0`; however, the checked-in
`agents/currency-agent/AgentCard.json` declares `protocolVersion: "0.2.9"`.
The lifecycle guide's AgentCard description also gives `0.2.9` as an example.
The current source checkout does not resolve whether those example values are
legacy or accepted. Confirm the version/compatibility requirement before
implementing a Nasiko target or client.

The CLI help command (`cargo run --manifest-path cli/Cargo.toml -- --help`)
was attempted but could not run because Cargo is unavailable. The command
surface was instead inspected in `../nasiko/cli/src/main.rs`,
`../nasiko/cli/src/lib.rs`, and `../nasiko/docs/CLI_DESIGN.md`.
