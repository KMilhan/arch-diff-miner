"""Unit tests for context statistics collection."""
from __future__ import annotations

from pathlib import Path

import pygit2
import pytest

from arch_diff_miner.context import collect_context_stats
from tests.fixtures.seed_context_repo import seed_context_repo


def _open_repo(path: Path) -> pygit2.Repository:
    return pygit2.Repository(str(path / ".git"))


def test_collect_context_stats_matches_seeded_history(tmp_path: Path) -> None:
    """Verify churn, authors, and recency per file and aggregate totals."""

    seeded = seed_context_repo(tmp_path)
    repo = _open_repo(seeded.path)
    parent_commit = repo.revparse_single("HEAD")

    tracked_files = list(seeded.files.keys())
    per_file, aggregate = collect_context_stats(
        repo=repo,
        parent_commit=parent_commit,
        files=tracked_files,
        since_dt=seeded.window_since,
        until_dt=seeded.window_until,
    )

    assert list(per_file.keys()) == tracked_files

    union_authors = set()
    freshest_days = []
    for path, expected in seeded.files.items():
        stats = per_file[path]
        assert stats["churn_count"] == expected.churn_count
        assert stats["unique_authors"] == expected.unique_authors
        expected_days = (seeded.window_until - expected.last_modified).total_seconds() / 86400
        assert stats["last_modified_days_ago"] == pytest.approx(expected_days)
        assert stats["top_authors"], "top authors list must not be empty when churn > 0"
        union_authors.update(expected.authors)
        freshest_days.append(expected_days)

    assert aggregate["total_commits"] == sum(item.churn_count for item in seeded.files.values())
    assert aggregate["total_unique_authors"] == len(union_authors)
    assert aggregate["most_recent_change_days_ago"] == pytest.approx(min(freshest_days))


def test_collect_context_stats_handles_missing_files(tmp_path: Path) -> None:
    """Unknown files should yield zeroed stats without crashing."""

    seeded = seed_context_repo(tmp_path)
    repo = _open_repo(seeded.path)
    parent_commit = repo.revparse_single("HEAD")

    per_file, aggregate = collect_context_stats(
        repo=repo,
        parent_commit=parent_commit,
        files=["nonexistent/file.py"],
        since_dt=seeded.window_since,
        until_dt=seeded.window_until,
    )

    stats = per_file["nonexistent/file.py"]
    assert stats["churn_count"] == 0
    assert stats["unique_authors"] == 0
    assert stats["last_modified_days_ago"] == 0.0
    assert stats["top_authors"] == []

    assert aggregate["total_commits"] == 0
    assert aggregate["total_unique_authors"] == 0
    assert aggregate["most_recent_change_days_ago"] == 0.0
