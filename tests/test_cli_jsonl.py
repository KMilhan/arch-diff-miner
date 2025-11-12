"""End-to-end tests for the arch_diff_miner CLI."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .conftest import parse_jsonl


def run_cli(repo_path: Path, adl_file: str, extra_args: list[str] | None = None) -> list[dict]:
    cmd = [
        "uv",
        "run",
        "python",
        "-m",
        "arch_diff_miner",
        "mine",
        "--repo",
        str(repo_path),
        "--adl-file",
        adl_file,
    ]
    if extra_args:
        cmd.extend(extra_args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return parse_jsonl(result.stdout)


def test_root_commit_skipped(sample_repo):
    records = run_cli(
        sample_repo["path"],
        sample_repo["adl_current"],
        extra_args=["--code-exts", ".py"],
    )
    commit_hashes = {record["commit"]["hash"] for record in records}
    assert sample_repo["commits"]["root"] not in commit_hashes


def test_required_keys_present(sample_repo):
    records = run_cli(
        sample_repo["path"],
        sample_repo["adl_current"],
        extra_args=["--code-exts", ".py", ".md"],
    )
    assert records, "Expected at least one JSONL record"
    record = records[0]
    assert set(record.keys()) >= {"commit", "intent", "adl_diff", "code_diffs", "metadata"}
    commit = record["commit"]
    assert {
        "hash",
        "parent_hash",
        "authored_at",
        "committed_at",
        "author",
        "is_merge",
    } <= set(commit.keys())
    assert isinstance(record["code_diffs"], list) and record["code_diffs"], "code diffs should not be empty"
    assert record["adl_diff"]["hunks"], "ADL hunks should be populated"


def test_merge_commit_marked(sample_repo):
    records = run_cli(sample_repo["path"], sample_repo["adl_current"], extra_args=None)
    merge_hash = sample_repo["commits"]["merge"]
    merge_record = next(r for r in records if r["commit"]["hash"] == merge_hash)
    assert merge_record["commit"]["is_merge"] is True


def test_rename_is_tracked(sample_repo):
    records = run_cli(
        sample_repo["path"],
        sample_repo["adl_current"],
        extra_args=["--code-exts", ".py", "--code-exts", ".rs"],
    )
    rename_hash = sample_repo["commits"]["rename"]
    rename_record = next(r for r in records if r["commit"]["hash"] == rename_hash)
    adl_diff = rename_record["adl_diff"]
    assert adl_diff["path"].endswith("decisions.yaml")
    assert adl_diff.get("previous_path") == "adl.yaml"


def test_adl_only_commit_filtered(sample_repo):
    records = run_cli(sample_repo["path"], sample_repo["adl_current"], extra_args=None)
    filtered_hashes = {record["commit"]["hash"] for record in records}
    assert sample_repo["commits"]["adl_only"] not in filtered_hashes
