import json
import re
from pathlib import Path

import pytest

from core.models import Attack, AttackCategory

ATTACKS_DIR = Path(__file__).parents[1] / "attacks"
EXPECTED_CATEGORIES: set[AttackCategory] = {
    "prompt_leak",
    "instruction_override",
    "indirect_injection",
    "data_exfiltration",
}
ID_PREFIXES: dict[AttackCategory, str] = {
    "prompt_leak": "leak-",
    "instruction_override": "override-",
    "indirect_injection": "indirect-",
    "data_exfiltration": "exfil-",
}


def load_attacks(filename: str) -> list[Attack]:
    raw_attacks = json.loads((ATTACKS_DIR / filename).read_text(encoding="utf-8"))
    assert isinstance(raw_attacks, list)
    return [Attack.model_validate(item) for item in raw_attacks]


def words(text: str) -> set[str]:
    return set(re.findall(r"\b\w+\b", text.lower()))


@pytest.fixture(scope="module")
def attack_sets() -> tuple[list[Attack], list[Attack]]:
    return load_attacks("train.json"), load_attacks("holdout.json")


def test_attack_library_has_target_size_and_approximate_split(
    attack_sets: tuple[list[Attack], list[Attack]],
) -> None:
    train, holdout = attack_sets

    assert len(train) + len(holdout) == 30
    assert len(train) == 21
    assert len(holdout) == 9


def test_attacks_use_all_categories_and_match_their_file_split(
    attack_sets: tuple[list[Attack], list[Attack]],
) -> None:
    train, holdout = attack_sets

    assert {attack.category for attack in train + holdout} == EXPECTED_CATEGORIES
    assert all(attack.split == "train" for attack in train)
    assert all(attack.split == "holdout" for attack in holdout)


def test_attack_ids_are_unique_and_category_prefixed(
    attack_sets: tuple[list[Attack], list[Attack]],
) -> None:
    attacks = attack_sets[0] + attack_sets[1]
    ids = [attack.id for attack in attacks]

    assert len(ids) == len(set(ids))
    assert all(attack.id.startswith(ID_PREFIXES[attack.category]) for attack in attacks)


def test_all_attacks_use_deterministic_canary_checks_and_nonempty_payloads(
    attack_sets: tuple[list[Attack], list[Attack]],
) -> None:
    attacks = attack_sets[0] + attack_sets[1]

    assert all(attack.success_check == "canary" for attack in attacks)
    assert all(attack.payload.strip() for attack in attacks)


def test_holdout_payloads_are_not_near_duplicates_of_training_payloads(
    attack_sets: tuple[list[Attack], list[Attack]],
) -> None:
    train, holdout = attack_sets
    train_words = [words(attack.payload) for attack in train]

    for held_out in holdout:
        held_out_words = words(held_out.payload)
        assert held_out_words
        assert all(
            len(held_out_words & training_words)
            / len(held_out_words | training_words)
            <= 0.6
            for training_words in train_words
        ), f"{held_out.id} overlaps substantially with a training payload"
