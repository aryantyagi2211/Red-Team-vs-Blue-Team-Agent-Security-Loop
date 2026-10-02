import asyncio
import json
import re
from typing import Literal

import typer

from core.holdout import HoldoutReport, format_holdout_report
from core.loop import ATTACKS_DIR, RUNS_DIR, RunSummary, run_loop
from core.models import Attack

RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")

app = typer.Typer(
    name="redteam",
    help="Run local red-team evaluations against sandbox targets.",
    no_args_is_help=True,
)
attacks_app = typer.Typer(help="Inspect the local attack library.", no_args_is_help=True)
app.add_typer(attacks_app, name="attacks")


def _load_attacks(split: Literal["train", "holdout"] | None) -> list[Attack]:
    splits = (split,) if split is not None else ("train", "holdout")
    attacks: list[Attack] = []
    for item_split in splits:
        path = ATTACKS_DIR / f"{item_split}.json"
        raw_attacks = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw_attacks, list):
            raise TypeError(f"{path} must contain a JSON array")
        split_attacks = [Attack.model_validate(item) for item in raw_attacks]
        if any(attack.split != item_split for attack in split_attacks):
            raise ValueError(f"{path} contains an attack from the wrong split")
        attacks.extend(split_attacks)
    return attacks


def _resolve_run_id(requested_run: str) -> str:
    if requested_run != "latest":
        if not RUN_ID_PATTERN.fullmatch(requested_run):
            raise ValueError("run ID must be a safe alphanumeric identifier or 'latest'")
        return requested_run

    candidates = (
        [
            path
            for path in RUNS_DIR.iterdir()
            if path.is_dir()
            and RUN_ID_PATTERN.fullmatch(path.name)
            and (path / "summary.json").is_file()
        ]
        if RUNS_DIR.exists()
        else []
    )
    if not candidates:
        raise FileNotFoundError("no saved runs were found")
    latest = max(
        candidates,
        key=lambda path: (path.joinpath("summary.json").stat().st_mtime_ns, path.name),
    )
    return latest.name


def _progress(event: dict[str, object]) -> None:
    round_number = event["round"]
    step = event["step"]
    if step == "round_started":
        message = "baseline" if round_number == 0 else "started"
        typer.echo(f"Round {round_number}: {message}")
    elif step == "patch_applied":
        typer.echo(
            f"Round {round_number}: patch applied; "
            f"utility {float(event['utility_pass_rate']):.0%}"
        )
    elif step == "patch_rolled_back":
        typer.echo(
            f"Round {round_number}: patch rolled back; "
            f"utility {float(event['utility_pass_rate']):.0%}"
        )
    elif step in ("train_completed", "holdout_completed"):
        label = "train" if step == "train_completed" else "holdout"
        typer.echo(
            f"Round {round_number}: {label} evaluation completed "
            f"({event['result_count']} attacks)"
        )
    elif step == "round_saved":
        typer.echo(f"Round {round_number}: results saved")
    elif step == "holdout_report":
        typer.echo(
            f"Holdout ASR: {float(event['baseline_holdout_asr']):.1%} -> "
            f"{float(event['final_holdout_asr']):.1%}; "
            f"generalization gap {float(event['generalization_gap']):+.1%}"
        )
        if event["memorization_warning"]:
            typer.echo("Warning: holdout ASR suggests possible memorization.")
    elif step == "run_stopped":
        typer.echo(f"Run stopped: {event['reason']}", err=True)


def _display_saved_run(run_id: str) -> None:
    run_dir = RUNS_DIR / run_id
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"saved run not found: {run_id}")
    summary = RunSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
    typer.echo(f"Run: {summary.run_id} (status: {summary.status})")
    if summary.stop_reason:
        typer.echo(f"Stop reason: {summary.stop_reason}")
    for record in summary.rounds:
        typer.echo(
            f"Round {record.round}: train ASR {record.train_asr:.1%}, "
            f"holdout ASR {record.holdout_asr:.1%}, "
            f"utility {record.utility_pass_rate:.1%} ({record.status})"
        )

    report_path = run_dir / "holdout_report.json"
    if report_path.is_file():
        report = HoldoutReport.model_validate_json(
            report_path.read_text(encoding="utf-8")
        )
        typer.echo(format_holdout_report(report))
    else:
        typer.echo("Holdout report is unavailable for this incomplete run.")


@app.command()
def run(
    target: str = typer.Option(..., "--target", help="Local sandbox target name."),
    rounds: int = typer.Option(
        3,
        "--rounds",
        min=0,
        max=10,
        help="Maximum number of patch rounds (0-10).",
    ),
    fail_above: float | None = typer.Option(
        None,
        "--fail-above",
        min=0.0,
        max=1.0,
        help="Exit with status 1 if final holdout ASR exceeds this rate.",
    ),
) -> None:
    """Run a local evaluation loop against a sandbox target."""
    try:
        summary = asyncio.run(
            run_loop(
                target,
                rounds=rounds,
                on_progress=_progress,
            )
        )
    except (FileNotFoundError, FileExistsError, TypeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Run ID: {summary.run_id}")
    if summary.status != "ok":
        typer.echo(f"Run ended with status {summary.status}: {summary.stop_reason}", err=True)
        raise typer.Exit(code=1)
    if fail_above is not None and summary.rounds[-1].holdout_asr > fail_above:
        typer.echo(
            f"Final holdout ASR {summary.rounds[-1].holdout_asr:.1%} "
            f"exceeds threshold {fail_above:.1%}.",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command()
def report(
    run: str = typer.Option(
        "latest",
        "--run",
        help="Saved run ID or 'latest'.",
    ),
) -> None:
    """Report metrics from a saved run."""
    try:
        _display_saved_run(_resolve_run_id(run))
    except (FileNotFoundError, TypeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc


@attacks_app.command("list")
def list_attacks(
    split: Literal["train", "holdout"] | None = typer.Option(
        None,
        "--split",
        help="Show only this attack split.",
    ),
) -> None:
    """List locally drafted training and holdout attacks."""
    try:
        attacks = _load_attacks(split)
    except (FileNotFoundError, TypeError, ValueError) as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    for attack in attacks:
        typer.echo(
            f"[{attack.split}] {attack.id} ({attack.category})\n"
            f"  {attack.payload}"
        )
    typer.echo(f"Total: {len(attacks)} attack(s)")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
