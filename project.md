# Project

Red-Team vs Blue-Team Loop for Nasiko is a local, controlled security-evaluation project that runs deterministic prompt-injection and data-leak probes against sandbox agents we deploy ourselves, scores outcomes using fake canary strings, and iteratively hardens agent prompts or gateway rules while tracking attack success rates and holdout performance.

## Repository structure

This tree reflects the project files currently present; planned paths will be added here as their tasks create them.

```text
redteam/
├── .git/                            # Git metadata for this repository
├── .gitattributes                   # Keep shell scripts on LF line endings
├── .gitignore                       # Python, environment, virtualenv, and run-output exclusions
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
├── api/                             # FastAPI wrapper package (implementation pending)
│   └── __init__.py                  # Python package marker
├── attacks/                         # Training and holdout attack-library data
│   ├── holdout.json                 # Unseen evaluation attack drafts
│   ├── train.json                   # Training attack drafts
│   └── __init__.py                  # Python package marker
├── cli/                             # Typer command-line interface package (implementation pending)
│   └── __init__.py                  # Python package marker
├── core/                            # Core models, scoring, runners, and loop (implementation pending)
│   ├── __init__.py                  # Python package marker
│   ├── attacker.py                  # Async runner and local fake sandbox client
│   ├── judge.py                     # Deterministic string scoring and split/category ASR
│   └── models.py                    # Typed Pydantic attack, result, patch, and round models
├── dashboard/                       # Evaluation dashboard (implementation pending)
│   └── .gitkeep                     # Placeholder until dashboard files are added
├── docs/                            # Integration notes and demonstration documentation
│   └── .gitkeep                     # Placeholder until documentation is added
├── git_remote.txt                   # User-managed Git remote placeholder; no remote configured yet
├── project.md                       # Project description and current repository structure
├── pyproject.toml                   # Python project metadata and dependencies
├── README.md                        # Current capabilities, setup instructions, and status
├── runs/                            # Local JSON run records; contents are gitignored
│   └── .gitkeep                     # Placeholder for the ignored run-output directory
├── scripts/                         # Repository utility scripts
│   └── push.sh                      # Push helper that reads the configured remote placeholder
├── targets/                         # Locally controlled, deterministic sandbox agents
│   ├── calendar_assistant/          # Fake-calendar target with a unique fake canary and utility tasks
│   │   ├── benign_tasks.json        # Safe calendar requests and expected response checks
│   │   └── prompt.txt               # Private sandbox prompt containing its fake canary
│   ├── memo_assistant/              # Fake-memo target with a unique fake canary and utility tasks
│   │   ├── benign_tasks.json        # Safe memo requests and expected response checks
│   │   └── prompt.txt               # Private sandbox prompt containing its fake canary
│   ├── __init__.py                  # Sandbox targets package
│   └── sandbox.py                   # Safe local target loader and deterministic responder
├── task.md                          # Ordered implementation checklist and task status
└── tests/                           # Automated project tests
    ├── test_attack_library.py       # Split, category, ID, and holdout overlap checks
    ├── test_attacker.py             # Fake-client attack execution and result collection
    ├── test_judge.py                # Deterministic scoring and ASR behavior
    ├── test_models.py               # Model fields and validation behavior
    ├── test_targets.py              # Sandbox utility and canary isolation checks
    └── test_scaffold.py             # Package import and Python version smoke tests
```
