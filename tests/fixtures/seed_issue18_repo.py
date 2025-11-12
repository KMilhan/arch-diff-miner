"""Fixture repository covering merge, binary, and rename scenarios."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class Issue18Repo:
    """Return payload describing the seeded repository."""

    path: Path
    adl_current: str
    commits: Dict[str, str]


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


def _write(repo_path: Path, rel_path: str, content: str, *, binary: bool = False) -> None:
    target = repo_path / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        target.write_bytes(content.encode("latin-1"))
    else:
        target.write_text(content, encoding="utf-8")


def seed_issue18_repo(tmp_path: Path) -> Issue18Repo:
    """Create a repo with merge, binary, and rename coverage."""

    repo_path = tmp_path / "issue18_repo"
    repo_path.mkdir(parents=True, exist_ok=True)

    _run_git(repo_path, ["init", "-q"])
    _run_git(repo_path, ["checkout", "-q", "-b", "main"])
    _run_git(repo_path, ["config", "user.name", "Issue18 Bot"])
    _run_git(repo_path, ["config", "user.email", "issue18@example.com"])

    routes: List[Tuple[str, str]] = [("base", "/")]
    adl_path = "adl.yaml"

    def _render_routes() -> str:
        lines = ["routes:"]
        for name, path in routes:
            lines.append(f"  - name: {name}")
            lines.append(f"    path: {path}")
        lines.append("")
        return "\n".join(lines)

    def _write_adl() -> None:
        _write(repo_path, adl_path, _render_routes())

    commits: Dict[str, str] = {}

    # Root commit
    _write_adl()
    _write(repo_path, "src/app.py", "print('base')\n")
    _run_git(repo_path, ["add", "-A"])
    _run_git(repo_path, ["commit", "-q", "-m", "seed base"])
    commits["root"] = _run_git(repo_path, ["rev-parse", "HEAD"])

    # Feature branch with ADL + code change
    _run_git(repo_path, ["checkout", "-q", "-b", "feature"])
    routes.append(("feature", "/feature"))
    _write_adl()
    _write(repo_path, "src/feature_only.py", "print('feature branch payload')\n")
    _run_git(repo_path, ["add", "-A"])
    _run_git(repo_path, ["commit", "-q", "-m", "feature adds route"])
    commits["feature"] = _run_git(repo_path, ["rev-parse", "HEAD"])

    # Return to main and prepare merge parent
    _run_git(repo_path, ["checkout", "-q", "main"])
    _write(repo_path, "src/main_only.py", "print('main prep change')\n")
    _run_git(repo_path, ["add", "-A"])
    _run_git(repo_path, ["commit", "-q", "-m", "main prep change"])
    commits["main_pre_merge"] = _run_git(repo_path, ["rev-parse", "HEAD"])

    # Merge feature branch (first-parent diff should reflect feature changes)
    _run_git(repo_path, ["merge", "-q", "--no-ff", "feature", "-m", "merge feature branch"])
    commits["merge"] = _run_git(repo_path, ["rev-parse", "HEAD"])

    # Binary payload commit: keep textual diff + non-UTF asset
    routes.append(("binary", "/binary"))
    _write_adl()
    _write(repo_path, "src/helpers_binary.py", "print('binary guard text diff')\n")
    (repo_path / "src").mkdir(parents=True, exist_ok=True)
    (repo_path / "src/binary_non_utf.py").write_bytes(b"\xff\xfe\x00binary")
    _run_git(repo_path, ["add", "-A"])
    _run_git(repo_path, ["commit", "-q", "-m", "binary payload change"])
    commits["binary"] = _run_git(repo_path, ["rev-parse", "HEAD"])

    # Rename ADL file, ensuring rename metadata surfaces
    _run_git(repo_path, ["mv", "adl.yaml", "decisions.yaml"])
    adl_path = "decisions.yaml"
    routes.append(("renamed", "/renamed"))
    _write_adl()
    _write(repo_path, "src/app.py", "print('post-rename code change')\n")
    _run_git(repo_path, ["add", "-A"])
    _run_git(repo_path, ["commit", "-q", "-m", "rename adl file"])
    commits["rename"] = _run_git(repo_path, ["rev-parse", "HEAD"])

    return Issue18Repo(path=repo_path, adl_current=adl_path, commits=commits)


__all__ = ["seed_issue18_repo", "Issue18Repo"]
