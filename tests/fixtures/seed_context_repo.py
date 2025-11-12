"""Deterministic on-disk Git repo for context-stats integration tests."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List


@dataclass(frozen=True)
class FileHistory:
    """Metadata describing the history we seeded for a single file."""

    churn_count: int
    unique_authors: int
    last_modified: datetime
    authors: frozenset[str]


@dataclass(frozen=True)
class SeededContextRepo:
    """Return payload for tests needing repo path and expectations."""

    path: Path
    head_sha: str
    window_since: datetime
    window_until: datetime
    files: Dict[str, FileHistory]


def _run_git(repo_path: Path, args: List[str], env: Dict[str, str] | None = None) -> str:
    base_env = os.environ.copy()
    if env:
        base_env.update(env)
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
        text=True,
        env=base_env,
    )
    return result.stdout.strip()


def _write(repo_path: Path, rel_path: str, content: str) -> None:
    target = repo_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def seed_context_repo(tmp_path: Path) -> SeededContextRepo:
    """Create a miniature repository with predictable commit history."""

    repo_path = tmp_path / "context_repo"
    repo_path.mkdir(parents=True, exist_ok=True)

    _run_git(repo_path, ["init", "-q"])
    _run_git(repo_path, ["config", "user.name", "Context Bot"])
    _run_git(repo_path, ["config", "user.email", "bot@example.com"])

    base_time = datetime(2024, 1, 1, 8, tzinfo=timezone.utc)
    timeline = [
        {
            "offset": 0,
            "author": ("Ada Lovelace", "ada@example.com"),
            "files": {
                "src/service.py": "print('svc v1')\n",
                "src/helpers.py": "HELPERS = ['seed']\n",
            },
            "message": "seed files",
        },
        {
            "offset": 3,
            "author": ("Grace Hopper", "grace@example.com"),
            "files": {
                "src/service.py": "print('svc v2 from grace')\n",
            },
            "message": "grace tweaks service",
        },
        {
            "offset": 7,
            "author": ("Ada Lovelace", "ada@example.com"),
            "files": {
                "src/helpers.py": "HELPERS = ['seed', 'ada']\n",
            },
            "message": "ada extends helpers",
        },
        {
            "offset": 10,
            "author": ("Barbara Liskov", "barbara@example.com"),
            "files": {
                "src/helpers.py": "HELPERS = ['seed', 'ada', 'barbara']\n",
            },
            "message": "barbara patches helpers",
        },
    ]

    history: Dict[str, Dict[str, object]] = {}
    head_sha = ""

    for entry in timeline:
        commit_time = base_time + timedelta(days=entry["offset"])
        author_name, author_email = entry["author"]
        for rel_path, contents in entry["files"].items():
            _write(repo_path, rel_path, contents)

        env = {
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
            "GIT_AUTHOR_DATE": commit_time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "GIT_COMMITTER_DATE": commit_time.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        }

        _run_git(repo_path, ["add", "-A"])
        _run_git(repo_path, ["commit", "-q", "-m", entry["message"]], env=env)
        head_sha = _run_git(repo_path, ["rev-parse", "HEAD"])

        for rel_path in entry["files"].keys():
            tracked = history.setdefault(
                rel_path,
                {"churn": 0, "authors": set(), "last_modified": commit_time},
            )
            tracked["churn"] = int(tracked["churn"]) + 1
            tracked["authors"].add(author_email.lower())
            tracked["last_modified"] = commit_time

    file_histories = {
        path: FileHistory(
            churn_count=int(meta["churn"]),
            unique_authors=len(meta["authors"]),
            last_modified=meta["last_modified"],
            authors=frozenset(meta["authors"]),
        )
        for path, meta in history.items()
    }

    window_since = base_time - timedelta(days=1)
    window_until = base_time + timedelta(days=12)

    return SeededContextRepo(
        path=repo_path,
        head_sha=head_sha,
        window_since=window_since,
        window_until=window_until,
        files=file_histories,
    )


__all__ = ["seed_context_repo", "SeededContextRepo", "FileHistory"]
