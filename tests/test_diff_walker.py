"""Tests covering merge handling, binary diffs, and renames."""
from __future__ import annotations

import logging
from pathlib import Path

from arch_diff_miner.cli import MineConfig, mine_repository
from tests.fixtures.seed_issue18_repo import seed_issue18_repo, Issue18Repo


def _mine_records(tmp_path: Path, adl_file: str = "adl.yaml") -> tuple[Issue18Repo, list[dict[str, object]]]:
    repo_info = seed_issue18_repo(tmp_path)
    config = MineConfig(
        repo_path=repo_info.path,
        adl_file=adl_file,
        code_extensions=(".py",),
        context_days=30,
    )
    records = mine_repository(config)
    return repo_info, records


def _record(records: list[dict[str, object]], message: str) -> dict[str, object]:
    for rec in records:
        if rec.get("intent_message") == message:
            return rec
    raise AssertionError(f"record with message '{message}' not found")


def test_merge_commit_uses_first_parent(tmp_path: Path) -> None:
    repo, records = _mine_records(tmp_path)
    merge = _record(records, "merge feature branch")

    assert merge["is_merge"] is True
    assert merge["parent_hash"] == repo.commits["main_pre_merge"]
    assert {diff["path"] for diff in merge["code_diffs"]} == {"src/feature_only.py"}


def test_binary_diff_skipped_and_logged(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.WARNING, logger="arch_diff_miner.cli")
    repo, records = _mine_records(tmp_path)
    binary = _record(records, "binary payload change")

    assert "binary" in repo.commits
    assert all(diff["path"] != "src/binary_non_utf.py" for diff in binary["code_diffs"])
    assert {diff["path"] for diff in binary["code_diffs"]} == {"src/helpers_binary.py"}


def test_adl_rename_previous_path(tmp_path: Path) -> None:
    _, records = _mine_records(tmp_path, adl_file="decisions.yaml")
    rename = _record(records, "rename adl file")

    adl_diff = rename["adl_diff"]
    assert adl_diff["path"] == "decisions.yaml"
    assert adl_diff["previous_path"] == "adl.yaml"
