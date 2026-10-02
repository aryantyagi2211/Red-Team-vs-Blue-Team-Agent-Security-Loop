import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from core import defender, loop
from core.holdout import (
    GENERALIZATION_GAP_THRESHOLD,
    HoldoutReport,
    check_train_holdout_overlap,
    create_holdout_report,
    format_holdout_report,
    holdout_asr_by_category,
    load_fixed_splits,
    save_split_hashes,
)
from core.models import Attack, AttackResult, RoundRecord
from targets import sandbox


def make_attack(
    attack_id: str,
    split: str,
    payload: str,
    category: str = "data_exfiltration",
) -> Attack:
    return Attack(
        id=attack_id,
        category=category,
        split=split,
        payload=payload,
        success_check="canary",
    )


def make_result(
    attack_id: str,
    split: str,
    category: str,
    success: bool,
) -> AttackResult:
    return AttackResult(
        attack_id=attack_id,
        category=category,
        split=split,
        response="safe response",
        success=success,
        reason="no match",
    )


def write_sets(
    directory: Path,
    train: list[Attack],
    holdout: list[Attack],
) -> tuple[Path, Path]:
    directory.mkdir()
    train_path = directory / "train.json"
    holdout_path = directory / "holdout.json"
    train_path.write_text(
        json.dumps([attack.model_dump() for attack in train]),
        encoding="utf-8",
    )
    holdout_path.write_text(
        json.dumps([attack.model_dump() for attack in holdout]),
        encoding="utf-8",
    )
    return train_path, holdout_path


def write_round(
    run_dir: Path,
    round_number: int,
    train_asr: float,
    holdout_asr: float,
    results: list[AttackResult],
) -> None:
    record = RoundRecord(
        run_id="report-run",
        target="calendar_assistant",
        round=round_number,
        train_asr=train_asr,
        holdout_asr=holdout_asr,
        asr_by_category={},
        holdout_asr_by_category=holdout_asr_by_category(results),
        utility_pass_rate=1.0,
        status="ok",
        results=results,
        patch=None,
    )
    (run_dir / f"round_{round_number}.json").write_text(
        record.model_dump_json(),
        encoding="utf-8",
    )


def test_run_hashes_are_saved_and_detect_split_changes(tmp_path: Path) -> None:
    train_path, holdout_path = write_sets(
        tmp_path / "attacks",
        [make_attack("train-1", "train", "train words")],
        [make_attack("holdout-1", "holdout", "holdout words")],
    )
    runs_dir = tmp_path / "runs"
    hashes = save_split_hashes(
        "stable-run",
        train_path,
        holdout_path,
        runs_dir,
    )

    hash_file = runs_dir / "stable-run" / "split_hash.txt"
    assert hashes == {
        "train": hashlib.sha256(train_path.read_bytes()).hexdigest(),
        "holdout": hashlib.sha256(holdout_path.read_bytes()).hexdigest(),
    }
    assert hash_file.read_text(encoding="utf-8").splitlines() == [
        f"{hashes['train']}  train.json",
        f"{hashes['holdout']}  holdout.json",
    ]
    assert (
        save_split_hashes(
            "stable-run",
            train_path,
            holdout_path,
            runs_dir,
        )
        == hashes
    )

    holdout_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="split files changed"):
        save_split_hashes("stable-run", train_path, holdout_path, runs_dir)


def test_splits_cannot_be_initialized_after_round_records_exist(
    tmp_path: Path,
) -> None:
    train_path, holdout_path = write_sets(
        tmp_path / "attacks",
        [make_attack("train-1", "train", "train words")],
        [make_attack("holdout-1", "holdout", "holdout words")],
    )
    run_dir = tmp_path / "runs" / "finished"
    run_dir.mkdir(parents=True)
    (run_dir / "round_0.json").touch()

    with pytest.raises(FileExistsError, match="no attack split hashes"):
        save_split_hashes("finished", train_path, holdout_path, tmp_path / "runs")


def test_overlap_check_flags_only_jaccard_above_threshold() -> None:
    train = [make_attack("train-1", "train", "a b c d")]
    at_threshold = [make_attack("holdout-1", "holdout", "a b c e")]
    above_threshold = [make_attack("holdout-2", "holdout", "a b c")]

    assert check_train_holdout_overlap(train, at_threshold) == []
    flagged = check_train_holdout_overlap(train, above_threshold)
    assert flagged == [("train-1", "holdout-2", 0.75)]


def test_fixed_split_loader_validates_splits_and_rejects_overlap(
    tmp_path: Path,
) -> None:
    attack_dir = tmp_path / "attacks"
    write_sets(
        attack_dir,
        [make_attack("train-1", "train", "calendar appointments and reminders")],
        [make_attack("holdout-1", "holdout", "calendar appointments and reminders")],
    )

    with pytest.raises(ValueError, match="overlap exceeds 0.60"):
        load_fixed_splits(
            "overlap-run",
            attack_dir,
            tmp_path / "runs",
        )

    assert (tmp_path / "runs" / "overlap-run" / "split_hash.txt").exists()


def test_holdout_category_asr_uses_only_holdout_results() -> None:
    results = [
        make_result("train-1", "train", "data_exfiltration", True),
        make_result("holdout-1", "holdout", "data_exfiltration", True),
        make_result("holdout-2", "holdout", "data_exfiltration", False),
        make_result("holdout-3", "holdout", "prompt_leak", True),
    ]

    assert holdout_asr_by_category(results) == {
        "data_exfiltration": 0.5,
        "prompt_leak": 1.0,
    }


@pytest.mark.parametrize(
    ("gap", "warning"),
    [
        (GENERALIZATION_GAP_THRESHOLD, False),
        (GENERALIZATION_GAP_THRESHOLD + 0.001, True),
        (GENERALIZATION_GAP_THRESHOLD - 0.001, False),
    ],
)
def test_report_memorization_warning_uses_strict_gap_threshold(
    tmp_path: Path,
    gap: float,
    warning: bool,
) -> None:
    run_dir = tmp_path / "report-run"
    run_dir.mkdir()
    baseline_results = [
        make_result("base-train", "train", "data_exfiltration", True),
        make_result("base-holdout", "holdout", "data_exfiltration", True),
    ]
    final_results = [
        make_result("final-train", "train", "data_exfiltration", False),
        make_result("final-holdout", "holdout", "data_exfiltration", gap > 0),
        make_result("final-holdout-prompt", "holdout", "prompt_leak", True),
    ]
    write_round(run_dir, 0, 1.0, 1.0, baseline_results)
    final_train_asr = 0.0 if gap > 0 else 0.2
    final_holdout_asr = final_train_asr + gap
    write_round(run_dir, 1, final_train_asr, final_holdout_asr, final_results)

    report = create_holdout_report("report-run", run_dir)

    assert report.baseline_holdout_asr == 1.0
    assert report.final_holdout_asr == final_holdout_asr
    assert report.generalization_gap == pytest.approx(gap)
    assert report.memorization_warning is warning


def test_report_format_includes_headline_pair_categories_and_warning() -> None:
    report = HoldoutReport(
        run_id="demo-run",
        baseline_holdout_asr=0.6,
        final_holdout_asr=0.3,
        holdout_asr_by_category={"prompt_leak": 0.25},
        generalization_gap=0.2,
        memorization_warning=True,
    )

    formatted = format_holdout_report(report)

    assert "Baseline holdout ASR: 0.600" in formatted
    assert "Final holdout ASR: 0.300" in formatted
    assert "prompt_leak: 0.250" in formatted
    assert "WARNING:" in formatted


def test_holdout_run_persists_split_hashes_and_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_name = "calendar_assistant"
    target_dir = tmp_path / "targets" / target_name
    target_dir.mkdir(parents=True)
    source_dir = sandbox.TARGETS_DIR / target_name
    for filename in ("prompt.txt", "benign_tasks.json"):
        (target_dir / filename).write_text(
            (source_dir / filename).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    run_dir = tmp_path / "runs"
    monkeypatch.setattr(sandbox, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(defender, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(defender, "RUNS_DIR", run_dir)
    monkeypatch.setattr(loop, "RUNS_DIR", run_dir)

    class SafeClient:
        async def send(self, target: str, payload: str) -> str:
            return "No private setup is disclosed."

    summary = asyncio.run(
        loop.run_loop(
            target_name,
            rounds=0,
            run_id="integrated-holdout",
            client=SafeClient(),
        )
    )

    saved = run_dir / "integrated-holdout"
    hashes = (saved / "split_hash.txt").read_text(encoding="utf-8")
    report = json.loads((saved / "holdout_report.json").read_text(encoding="utf-8"))
    assert "train.json" in hashes and "holdout.json" in hashes
    assert report["baseline_holdout_asr"] == summary.rounds[0].holdout_asr
    assert report["final_holdout_asr"] == summary.rounds[0].holdout_asr


def test_loop_detects_attack_file_changes_before_round_record_is_saved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target_name = "calendar_assistant"
    target_dir = tmp_path / "targets" / target_name
    target_dir.mkdir(parents=True)
    source_dir = sandbox.TARGETS_DIR / target_name
    for filename in ("prompt.txt", "benign_tasks.json"):
        (target_dir / filename).write_text(
            (source_dir / filename).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    attack_dir = tmp_path / "attacks"
    _train_path, holdout_path = write_sets(
        attack_dir,
        [make_attack("train-1", "train", "summarize the calendar appointments")],
        [make_attack("holdout-1", "holdout", "describe a recipe ingredient list")],
    )
    run_dir = tmp_path / "runs"
    monkeypatch.setattr(sandbox, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(defender, "TARGETS_DIR", tmp_path / "targets")
    monkeypatch.setattr(loop, "ATTACKS_DIR", attack_dir)
    monkeypatch.setattr(loop, "RUNS_DIR", run_dir)
    monkeypatch.setattr(defender, "RUNS_DIR", run_dir)
    monkeypatch.setattr(loop, "RETRY_DELAY_SECONDS", 0)

    class MutatingClient:
        changed = False

        async def send(self, target: str, payload: str) -> str:
            if not self.changed:
                self.changed = True
                holdout_path.write_text(
                    json.dumps(
                        [
                            make_attack(
                                "holdout-1",
                                "holdout",
                                "modified evaluation request",
                            ).model_dump()
                        ]
                    ),
                    encoding="utf-8",
                )
            return "No private setup is disclosed."

    with pytest.raises(ValueError, match="split files changed"):
        asyncio.run(
            loop.run_loop(
                target_name,
                rounds=0,
                run_id="changed-holdout",
                client=MutatingClient(),
            )
        )

    saved = run_dir / "changed-holdout"
    assert (saved / "split_hash.txt").exists()
    partial_round = json.loads(
        (saved / "round_0.json").read_text(encoding="utf-8")
    )
    assert partial_round["status"] == "error"
    assert partial_round["results"]
    assert json.loads((saved / "summary.json").read_text(encoding="utf-8"))[
        "status"
    ] == "error"
