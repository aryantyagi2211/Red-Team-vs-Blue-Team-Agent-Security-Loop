from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli import main as cli_main
from core import loop
from core.loop import RunSummary
from core.models import RoundRecord

runner = CliRunner()


@pytest.fixture
def isolated_run_dirs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    runs_dir = tmp_path / "runs"
    attacks_dir = Path(__file__).parents[1] / "attacks"
    monkeypatch.setattr(cli_main, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(loop, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(cli_main, "ATTACKS_DIR", attacks_dir)
    return runs_dir


def test_help_lists_expected_commands() -> None:
    result = runner.invoke(cli_main.app, ["--help"])

    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "report" in result.stdout
    assert "attacks" in result.stdout


def test_run_reports_live_progress_and_saves_artifacts(
    isolated_run_dirs: Path,
) -> None:
    result = runner.invoke(
        cli_main.app,
        ["run", "--target", "calendar_assistant", "--rounds", "0"],
    )

    assert result.exit_code == 0, result.output
    assert "Round 0: baseline" in result.stdout
    assert "train evaluation completed" in result.stdout
    assert "holdout evaluation completed" in result.stdout
    assert "Holdout ASR:" in result.stdout
    assert "Run ID:" in result.stdout
    run_dirs = list(isolated_run_dirs.iterdir())
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "summary.json").is_file()
    assert (run_dirs[0] / "holdout_report.json").is_file()


def test_report_reads_run_id_and_latest(isolated_run_dirs: Path) -> None:
    run_result = runner.invoke(
        cli_main.app,
        ["run", "--target", "calendar_assistant", "--rounds", "0"],
    )
    assert run_result.exit_code == 0, run_result.output
    run_id = run_result.stdout.split("Run ID: ", maxsplit=1)[1].splitlines()[0]

    for args in (["report", "--run", run_id], ["report", "--run", "latest"]):
        result = runner.invoke(cli_main.app, args)
        assert result.exit_code == 0, result.output
        assert f"Run: {run_id} (status: ok)" in result.stdout
        assert "Holdout ASR" in result.stdout


def test_report_rejects_unknown_run(isolated_run_dirs: Path) -> None:
    result = runner.invoke(cli_main.app, ["report", "--run", "missing"])

    assert result.exit_code == 1
    assert "saved run not found: missing" in result.stderr


def test_report_latest_requires_a_saved_run(isolated_run_dirs: Path) -> None:
    result = runner.invoke(cli_main.app, ["report"])

    assert result.exit_code == 1
    assert "no saved runs were found" in result.stderr


def test_run_rejects_unknown_target(isolated_run_dirs: Path) -> None:
    result = runner.invoke(
        cli_main.app,
        ["run", "--target", "not_a_sandbox", "--rounds", "0"],
    )

    assert result.exit_code == 1
    assert "unknown sandbox target" in result.stderr


def test_run_validates_round_limit() -> None:
    result = runner.invoke(
        cli_main.app,
        ["run", "--target", "calendar_assistant", "--rounds", "11"],
    )

    assert result.exit_code != 0
    assert "Invalid value" in result.output


def test_attacks_list_can_filter_to_train() -> None:
    result = runner.invoke(
        cli_main.app,
        ["attacks", "list", "--split", "train"],
    )

    assert result.exit_code == 0, result.output
    assert "[train] leak-001" in result.stdout
    assert "[holdout]" not in result.stdout
    assert "Total: 21 attack(s)" in result.stdout


def test_attacks_list_includes_both_splits() -> None:
    result = runner.invoke(cli_main.app, ["attacks", "list"])

    assert result.exit_code == 0, result.output
    assert "[train] leak-001" in result.stdout
    assert "[holdout]" in result.stdout
    assert "Total: 30 attack(s)" in result.stdout


def test_fail_above_returns_nonzero_when_threshold_is_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = RoundRecord(
        run_id="threshold-test",
        target="calendar_assistant",
        round=0,
        train_asr=0.0,
        holdout_asr=0.5,
        asr_by_category={},
        utility_pass_rate=1.0,
        status="ok",
        results=[],
        patch=None,
    )

    async def fake_run_loop(
        target: str,
        rounds: int,
        on_progress: object,
    ) -> RunSummary:
        assert target == "calendar_assistant"
        assert rounds == 0
        assert callable(on_progress)
        return RunSummary(
            run_id=record.run_id,
            target=target,
            status="ok",
            rounds=[record],
        )

    monkeypatch.setattr(cli_main, "run_loop", fake_run_loop)
    result = runner.invoke(
        cli_main.app,
        [
            "run",
            "--target",
            "calendar_assistant",
            "--rounds",
            "0",
            "--fail-above",
            "0.10",
        ],
    )

    assert result.exit_code == 1
    assert "Final holdout ASR 50.0% exceeds threshold 10.0%" in result.stderr


def test_fail_above_allows_equal_or_lower_holdout_asr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = RoundRecord(
        run_id="threshold-test",
        target="calendar_assistant",
        round=0,
        train_asr=0.0,
        holdout_asr=0.1,
        asr_by_category={},
        utility_pass_rate=1.0,
        status="ok",
        results=[],
        patch=None,
    )

    async def fake_run_loop(
        target: str,
        rounds: int,
        on_progress: object,
    ) -> RunSummary:
        return RunSummary(
            run_id=record.run_id,
            target=target,
            status="ok",
            rounds=[record],
        )

    monkeypatch.setattr(cli_main, "run_loop", fake_run_loop)
    result = runner.invoke(
        cli_main.app,
        [
            "run",
            "--target",
            "calendar_assistant",
            "--rounds",
            "0",
            "--fail-above",
            "0.10",
        ],
    )

    assert result.exit_code == 0, result.output


def test_run_options_reject_out_of_range_fail_threshold() -> None:
    result = runner.invoke(
        cli_main.app,
        [
            "run",
            "--target",
            "calendar_assistant",
            "--fail-above",
            "1.1",
        ],
    )

    assert result.exit_code != 0
    assert "Invalid value" in result.output
