# Nasiko integration research notes

These notes record facts verified in the read-only sibling checkout at
`../nasiko`. No Nasiko source files were changed. The installed CLI help and
live local deployment and gateway calls were also verified.

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
- On Windows Docker Desktop, a host-native server can report healthy while
  failing to proxy to agents at Docker-private IPs. The live test reproduced a
  502 from that topology. The source-built server container was instead attached
  to the same `nasiko` Docker network as the agents; its proxy calls then
  succeeded. The source Dockerfile and full Compose definition support running
  the server as a container on that network.
  Sources: `../nasiko/server/Dockerfile`,
  `../nasiko/docker-compose.yml`,
  `../nasiko/server/src/agent_proxy.rs`.

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
  `../nasiko/cli/src/commands/agents.rs`,
  `../nasiko/docs/A2A_PROTOCOL.md` (Overview and Nasiko Architecture Mapping).
- The agent-proxy routes require control-plane authentication, and the CLI
  sends its active session token as an HTTP Bearer token. `nasiko ps` prints a
  trailing slash for root agent paths; the chat command removes trailing
  slashes before sending. `core/nasiko_client.py` mirrors that root-path
  normalization and accepts the token explicitly as `auth_token`; it never
  reads the CLI credential file or an environment variable implicitly.
  Sources: `../nasiko/server/src/lib.rs` (agent-proxy auth layer),
  `../nasiko/cli/src/commands/chat.rs`,
  `../nasiko/cli/src/commands/agents.rs`.
- The documented A2A binding is JSON-RPC 2.0 over HTTP(S), with
  `Content-Type: application/json` and `A2A-Version: 1.0`; the protocol guide
  shows `SendMessage` requests with message text in `params.message.parts`.
  Sources: `../nasiko/docs/A2A_PROTOCOL.md` (Transport & Wire Format,
  Request Format, and Operations).

## A2A protocol decision for this project

There is a protocol-version inconsistency in the checked-in material. The
README says a deployed agent must speak A2A v1.0, and `docs/A2A_PROTOCOL.md`
documents `A2A-Version: 1.0`; however, the checked-in
`agents/currency-agent/AgentCard.json` declares `protocolVersion: "0.2.9"`,
and the lifecycle guide uses the same legacy example. The current server
source defines the A2A version as `1.0` in `types/src/a2a.rs`, and the checked
in assistant agent uses `a2a-sdk[http-server]==1.1.0` in
`agents/assistant-agent/pyproject.toml`. Following the current server protocol
and assistant example, this project uses A2A 1.0 request headers, wire
messages, target runtime cards, and static `AgentCard.json` files. This is a
compatibility decision based on the current implementation, not a claim that
the legacy currency-agent card has been migrated.

## Task 12 implementation and verification status

- `core/nasiko_client.py` sends the documented JSON-RPC `SendMessage` request
  with `A2A-Version: 1.0` and an optional explicit Bearer token. It requires
  callers to provide the complete endpoint URL and restricts it to localhost
  or a loopback IP; do not derive or guess a proxy path. For deployed agents,
  use the complete endpoint reported by `nasiko ps`. Nasiko prints a trailing
  slash for a root proxy route, so the client removes that slash to match the
  canonical path used by `nasiko chat`.
- `targets/calendar_assistant/` and `targets/memo_assistant/` contain static
  A2A 1.0 cards, Dockerfiles, standalone dependency manifests, and deterministic
  A2A services under `src/`. Each returns its existing benign fixture for an
  exact safe request and a safe fallback otherwise; neither service exposes
  its prompt canary.
- Offline tests exercise the actual A2A service routes with an in-process
  ASGI transport and call them through `NasikoClient`. Live verification also
  validated, deployed, and called both targets through the authenticated local
  Nasiko gateway. Each returned its benign fixture and the safe fallback for a
  request containing its planted fake canary; neither response disclosed the
  canary.
- This Windows verification built the server from `../nasiko/server/Dockerfile`
  and ran it on the same Docker network as the deployed agents. The native
  host-server variant could not reach the agent containers' private network
  addresses, even though the health and service-status checks passed.

The command syntax was checked with `nasiko --help`, `nasiko deploy --help`,
`nasiko chat --help`, and the matching source in
`../nasiko/cli/src/main.rs`, `../nasiko/cli/src/lib.rs`, and
`../nasiko/docs/CLI_DESIGN.md`.
