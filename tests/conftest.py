"""Pytest fixtures for exercising the Arch Diff Miner CLI."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Dict

import pytest


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def _write(repo: Path, rel_path: str, content: str) -> None:
    target = repo / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


@pytest.fixture()
def sample_repo(tmp_path: Path) -> Dict[str, object]:
    """Create a tiny git repo with commits covering traversal edge cases."""

    repo = tmp_path / "repo"
    repo.mkdir(parents=True)

    def git(*args: str) -> str:
        return _run(["git", *args], cwd=repo)

    git("init", "-q")
    git("config", "user.name", "Test User")
    git("config", "user.email", "test@example.com")

    commits: Dict[str, str] = {}

    # Root commit (should be skipped).
    _write(repo, "adl.yaml", "title: ADR 1\nstatus: draft\n")
    _write(repo, "src/app.py", "print('root')\n")
    git("add", "-A")
    git("commit", "-q", "-m", "root")
    commits["root"] = git("rev-parse", "HEAD")

    # ADL + code change.
    _write(repo, "adl.yaml", "title: ADR 1\nstatus: proposed\nnotes: logging\n")
    _write(repo, "src/app.py", "print('adl+code v1')\n")
    git("add", "-A")
    git("commit", "-q", "-m", "adl+code update")
    commits["adl_code"] = git("rev-parse", "HEAD")

    # Feature branch with ADL + code change.
    git("checkout", "-q", "-b", "feature")
    _write(repo, "adl.yaml", "title: ADR 1\nstatus: proposed\nnotes: feature\n")
    _write(repo, "src/feature.py", "print('feature branch')\n")
    git("add", "-A")
    git("commit", "-q", "-m", "feature adl+code")
    commits["feature"] = git("rev-parse", "HEAD")

    # Back to main, make a code-only tweak, then merge feature (introduces merge commit).
    git("checkout", "-q", "main")
    _write(repo, "src/app.py", "print('main pre-merge')\n")
    git("add", "src/app.py")
    git("commit", "-q", "-m", "main pre-merge change")
    git("merge", "-q", "--no-ff", "feature", "-m", "Merge feature branch")
    # Ensure the merge commit includes fresh ADL + code edits relative to the
    # first parent so it becomes a valid sample.
    merged_adl = (repo / "adl.yaml").read_text(encoding="utf-8")
    _write(repo, "adl.yaml", merged_adl + "notes: merged\n")
    _write(repo, "src/app.py", "print('merge commit payload')\n")
    git("add", "-A")
    git("commit", "-q", "--amend", "--no-edit")
    commits["merge"] = git("rev-parse", "HEAD")

    # Rename ADL file and modify code to keep code diff present.
    original_adl = (repo / "adl.yaml").read_text(encoding="utf-8")
    git("mv", "adl.yaml", "decisions.yaml")
    _write(repo, "decisions.yaml", original_adl + "notes: renamed\n")
    _write(repo, "src/app.py", "print('post-rename code change')\n")
    git("add", "-A")
    git("commit", "-q", "-m", "rename adl file")
    commits["rename"] = git("rev-parse", "HEAD")

    # ADL-only change (should be filtered out).
    _write(repo, "decisions.yaml", "title: ADR 1 (renamed)\nstatus: accepted\n")
    git("add", "decisions.yaml")
    git("commit", "-q", "-m", "adl only change")
    commits["adl_only"] = git("rev-parse", "HEAD")

    return {
        "path": repo,
        "adl_current": "decisions.yaml",
        "commits": commits,
    }


def parse_jsonl(stdout: str) -> list[dict[str, object]]:
    """Parse the CLI stdout into JSON objects."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    return [json.loads(line) for line in lines]
