# Project

Red-Team vs Blue-Team Loop for Nasiko is a local, controlled security-evaluation project that runs deterministic prompt-injection and data-leak probes against sandbox agents we deploy ourselves, scores outcomes using fake canary strings, and iteratively hardens agent prompts or gateway rules while tracking attack success rates and holdout performance.

The local Python loop, CLI, REST API, Nasiko A2A 1.0 client and red-team agent, two deployable fixture targets, and evaluation dashboard are implemented. Both target agents have been validated, deployed, and called through the local Nasiko gateway; benign responses and fake-canary non-disclosure were verified offline and live. The red-team agent is deployed and its A2A run start and REST status/report flow were verified through Nasiko. The dashboard reads aggregate round and holdout metrics, polls local runs, shows category and utility charts, and redacts canary values in prompt diffs. Its committed sample is explicitly labeled as a recorded deterministic fixture simulation, not a live Nasiko result. The API and agent use the deterministic fixture client by default. Task 15 is complete; the fresh-environment full suite passed all 143 tests. See `PROJECT_REVIEW.md` for validation evidence and `docs/demo-script.md` for the reproducible demo.

## Repository structure

This tree reflects the project files currently present; planned paths will be added here as their tasks create them.

```text
redteam/
├── .git/                            # Git metadata for this repository
├── .gitattributes                   # Keep shell scripts on LF line endings
├── .gitignore                       # Python, environment, virtualenv, and run-output exclusions
├── .dockerignore                    # Exclude secrets, local bindings, runs, and tests from images
├── .github/                         # Repository guidance and task-specific skills
│   ├── instructions/                # Project-wide development instructions
│   │   └── intruction.instructions.md # Available project instructions (filename as found)
│   └── skills/                      # Task-specific implementation and review guidance
│       ├── attack-library/SKILL.md  # Guidance for authoring the attack library
│       ├── cli-and-api-wrapper/SKILL.md # Guidance for CLI and API work
│       ├── code-review/SKILL.md     # Project code-review procedure
│       ├── defender-patcher/SKILL.md # Guidance for defender and patcher work
│       ├── demo-dashboard/SKILL.md  # Guidance for dashboard and sample runs
│       ├── deterministic-judge/SKILL.md # Guidance for deterministic scoring
│       ├── holdout-eval/SKILL.md    # Guidance for holdout evaluation
│       ├── loop-orchestrator/SKILL.md # Guidance for loop orchestration
│       ├── nasiko-agent-builder/SKILL.md # Guidance for Nasiko-specific work
│       └── project-review/SKILL.md # Guidance for final project review
├── api/                             # FastAPI run API, A2A red-team agent, and deployable image
│   ├── __init__.py                  # API package description
│   ├── app.py                       # Async run lifecycle, dashboard metrics, static page, and A2A executor
│   └── Dockerfile                   # Container image for local Nasiko deployment
├── attacks/                         # Training and holdout attack-library data
│   ├── holdout.json                 # Unseen evaluation attack drafts
│   ├── train.json                   # Training attack drafts
│   └── __init__.py                  # Python package marker
├── cli/                             # Typer commands for local runs, reports, and attack listing
│   ├── __init__.py                  # Python package marker
│   └── main.py                      # Thin CLI wrapper around core loop and saved artifacts
├── core/                            # Core models, scoring, defense, runners, and loop
│   ├── __init__.py                  # Python package marker
│   ├── attacker.py                  # Async runner and local fake sandbox client
│   ├── defender.py                  # Training-only prompt hardening, run-scoped logs, and rollback
│   ├── holdout.py                   # Split hashes, overlap checks, holdout metrics, and gap report
│   ├── judge.py                     # Deterministic string scoring and split/category ASR
│   ├── loop.py                      # Baseline/patch rounds, progress, retries, and JSON run persistence
│   ├── models.py                    # Typed Pydantic attack, result, patch, and round models
│   └── nasiko_client.py             # Local-only A2A 1.0 client with explicit proxy authentication
├── dashboard/                       # Local evaluation dashboard, offline chart, and recorded fixture sample
│   ├── app.js                       # Run selection/start, polling, safe metrics, and charts
│   ├── index.html                   # Dashboard page and evaluation controls
│   ├── sample_run/                  # Recorded deterministic prompt-aware fixture evaluation
│   │   ├── diffs/                   # Fake-canary-redacted prompt patch diffs
│   │   │   └── calendar_assistant_round1.diff # Added defensive prompt rule
│   │   ├── holdout_report.json      # Baseline/final holdout comparison and gap metrics
│   │   └── summary.json             # Redacted round metrics and recorded run metadata
│   ├── styles.css                   # High-contrast responsive projector-friendly styles
│   └── vendor/                      # Offline chart library and its license
│       ├── chart.umd.min.js         # Locally served Chart.js 4.4.8 bundle
│       └── LICENSE.md               # Chart.js MIT license
├── docs/                            # Verified Nasiko integration notes and demo documentation
│   ├── .gitkeep                     # Existing documentation-directory placeholder
│   ├── demo-script.md               # Reproducible, safety-scoped two-minute project demo
│   └── nasiko-notes.md              # Facts checked against the read-only sibling Nasiko repo
├── git_remote.txt                   # User-managed Git remote URL placeholder
├── project.md                       # Project description and current repository structure
├── PROJECT_REVIEW.md                # Final pass/fail checklist with validation evidence
├── pyproject.toml                   # Python project metadata and dependencies
├── README.md                        # Current capabilities, setup instructions, and status
├── runs/                            # Local round/summary JSON and run-scoped prompt snapshots/diffs (gitignored)
│   └── .gitkeep                     # Placeholder for the ignored run-output directory
├── scripts/                         # Repository utility scripts
│   └── push.sh                      # Push helper that reads the configured remote placeholder
├── targets/                         # Locally controlled, deterministic sandbox agents
│   ├── __init__.py                  # Sandbox targets package
│   ├── sandbox.py                   # Safe local target loader and deterministic responder
│   ├── calendar_assistant/          # Fake-calendar A2A fixture target and deploy context
│   │   ├── .dockerignore            # Exclude Python bytecode from the Docker context
│   │   ├── .nasiko/                 # Nasiko-generated deployment metadata (gitignored)
│   │   │   └── agent.json           # Local binding to the deployed agent
│   │   ├── AgentCard.json           # A2A 1.0 card for Nasiko validation/deployment
│   │   ├── Dockerfile               # Container build for the calendar service
│   │   ├── benign_tasks.json        # Safe calendar requests and expected response checks
│   │   ├── prompt.txt               # Private sandbox prompt containing its fake canary
│   │   ├── pyproject.toml           # Standalone target runtime dependencies
│   │   └── src/
│   │       └── main.py              # Deterministic A2A service implementation
│   └── memo_assistant/              # Fake-memo A2A fixture target and deploy context
│       ├── .dockerignore            # Exclude Python bytecode from the Docker context
│       ├── .nasiko/                 # Nasiko-generated deployment metadata (gitignored)
│       │   └── agent.json           # Local binding to the deployed agent
│       ├── AgentCard.json           # A2A 1.0 card for Nasiko validation/deployment
│       ├── Dockerfile               # Container build for the memo service
│       ├── benign_tasks.json        # Safe memo requests and expected response checks
│       ├── prompt.txt               # Private sandbox prompt containing its fake canary
│       ├── pyproject.toml           # Standalone target runtime dependencies
│       └── src/
│           └── main.py              # Deterministic A2A service implementation
├── task.md                          # Ordered implementation checklist and task status
└── tests/                           # Automated project tests
    ├── test_api.py                  # REST run lifecycle, validation, reports, and A2A invocation
    ├── test_dashboard.py             # Static assets, metric safety, sample run, and diff redaction
    ├── test_attack_library.py       # Split, category, ID, and holdout overlap checks
    ├── test_attacker.py             # Fake-client attack execution and result collection
    ├── test_cli.py                  # CLI run, report, attack listing, and exit-code behavior
    ├── test_defender.py             # Patch application, utility evaluation, rollback, and artifact safety
    ├── test_holdout.py              # Split integrity, overlap, per-category ASR, and gap warnings
    ├── test_judge.py                # Deterministic scoring and ASR behavior
    ├── test_loop.py                 # Round flow, ASR, rollback, persistence, retries, and cancellation
    ├── test_models.py               # Model fields and validation behavior
    ├── test_nasiko_client.py        # A2A request format, endpoint guards, and errors
    ├── test_nasiko_targets.py       # Offline client/target integration and deployment metadata
    ├── test_targets.py              # Sandbox utility and canary isolation checks
    └── test_scaffold.py             # Package import and Python version smoke tests
```
