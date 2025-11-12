"""Arch Diff Miner CLI.

This module exposes a Typer-powered command that walks a Git repository,
locates commits touching a target ADL file, and emits `(intent, code_diffs,
adl_diff)` tuples into a JSON dataset for downstream fine-tuning.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import pygit2
import typer

# --- Logging & CLI wiring ----------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = typer.Typer(
    add_completion=False,
    help=(
        "Mine architecture decision log (ADL) commits and export training "
        "tuples by leveraging pygit2."
    ),
)

# --- Constants ----------------------------------------------------------------
DiffDataPair = Tuple[str, List[str], str]
DEFAULT_ADL_FILE = "adl.yaml"
DEFAULT_CODE_EXTENSIONS = (".py",)
DEFAULT_OUTPUT_PATH = Path("training_dataset.json")


# --- Helper functions ---------------------------------------------------------
def _normalize_rel_path(value: str) -> str:
    """Normalize repository-relative file paths for libgit2 comparisons."""
    normalized = value.replace("\\", "/").lstrip("./")
    return normalized or DEFAULT_ADL_FILE


def _normalize_extensions(exts: Sequence[str]) -> Tuple[str, ...]:
    """Ensure extensions start with a dot and compare case-insensitively."""
    cleaned: List[str] = []
    for ext in exts:
        candidate = ext.strip()
        if not candidate:
            continue
        if not candidate.startswith('.'):
            candidate = f".{candidate}"
        cleaned.append(candidate.lower())
    return tuple(dict.fromkeys(cleaned)) or DEFAULT_CODE_EXTENSIONS


def _discover_repository(repo_path: Path) -> Optional[pygit2.Repository]:
    """Locate and open a Git repository starting from repo_path."""
    try:
        git_dir = pygit2.discover_repository(str(repo_path))
    except (KeyError, pygit2.GitError):
        git_dir = None

    if not git_dir:
        logger.error("Error: Path '%s' is not inside a Git repository.", repo_path)
        return None

    try:
        return pygit2.Repository(git_dir)
    except pygit2.GitError as error:
        logger.error("Error opening repository at '%s': %s", repo_path, error)
        return None


def _patch_text(patch: pygit2.Patch) -> str:
    """Extract textual diff content from a pygit2 Patch."""
    text = getattr(patch, "text", None)
    return text if isinstance(text, str) else ""


def _single_file_diff(
    repo: pygit2.Repository,
    parent_tree: pygit2.Tree,
    current_tree: pygit2.Tree,
    target_path: str,
) -> str:
    """Return the textual diff for a single file path."""
    try:
        diff = repo.diff(
            parent_tree,
            current_tree,
            paths=[target_path],
            context_lines=3,
            interhunk_lines=1,
        )
    except pygit2.GitError as error:
        logger.error("Could not diff %s: %s", target_path, error)
        return ""

    for patch in diff:
        patch_text = _patch_text(patch)
        if patch_text:
            return patch_text
    return ""


def _collect_code_diffs(
    repo: pygit2.Repository,
    parent_tree: pygit2.Tree,
    current_tree: pygit2.Tree,
    adl_file: str,
    code_extensions: Sequence[str],
) -> List[str]:
    """Gather diff text for code files that changed in the commit."""
    try:
        diff = repo.diff(
            parent_tree,
            current_tree,
            context_lines=3,
            interhunk_lines=1,
        )
    except pygit2.GitError as error:
        logger.error("Could not compute code diffs: %s", error)
        return []

    adl_path = adl_file.lower()
    code_diffs: List[str] = []

    for patch in diff:
        path = patch.delta.new_file.path or patch.delta.old_file.path
        if not path:
            continue

        normalized_path = path.lower()
        if normalized_path == adl_path:
            continue
        if not any(normalized_path.endswith(ext) for ext in code_extensions):
            continue

        patch_text = _patch_text(patch)
        if patch_text:
            code_diffs.append(patch_text)

    return code_diffs


def _log_sample(training_pairs: List[DiffDataPair]) -> None:
    """Log the first tuple for quick inspection."""
    if not training_pairs:
        return

    intent, code_diffs, adl_diff = training_pairs[0]
    logger.info("-" * 40)
    logger.info("Example of the first training pair extracted:")
    logger.info("\nINTENT (X2):\n%s\n", intent)
    logger.info("CODE DIFFS (X1) - (%s files):", len(code_diffs))
    if code_diffs:
        logger.info("--- Diff for first code file ---\n%s\n", code_diffs[0])
    else:
        logger.info("  (No code diffs in this commit)\n")
    logger.info("ADL DIFF (Y):\n%s\n", adl_diff)
    logger.info("-" * 40)


def _write_training_dataset(
    output_path: Path,
    training_pairs: List[DiffDataPair],
) -> Path:
    """Persist the training tuples to disk and return the resolved path."""
    resolved = output_path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(
        json.dumps(training_pairs, indent=2),
        encoding="utf-8",
    )
    return resolved


# --- Core mining logic --------------------------------------------------------
def mine_repository(
    repo_path: Path,
    adl_file: str,
    code_extensions: Sequence[str],
) -> List[DiffDataPair]:
    """Extract `(intent, code_diffs, adl_diff)` tuples from repo history."""
    logger.info("Opening repository at: %s", repo_path)
    repo = _discover_repository(repo_path)
    if repo is None:
        return []

    try:
        head_id = repo.head.target
    except pygit2.GitError:
        logger.error("Repository '%s' has no HEAD.", repo_path)
        return []

    walker = repo.walk(head_id, pygit2.GIT_SORT_TOPOLOGICAL)
    walker.simplify_first_parent()

    normalized_adl_path = _normalize_rel_path(adl_file)
    normalized_exts = _normalize_extensions(code_extensions)

    logger.info("Scanning for commits that changed: %s", normalized_adl_path)

    training_data: List[DiffDataPair] = []
    adl_commit_count = 0

    for target_commit in walker:
        if not target_commit.parents:
            commit_id = str(target_commit.id)
            logger.info("Skipping root commit %s (no parent).", commit_id)
            continue

        parent_commit = target_commit.parents[0]
        commit_id = str(target_commit.id)
        parent_id = str(parent_commit.id)
        logger.info("Processing Target Commit (After): %s", commit_id)
        logger.info("           Parent Commit (Before): %s", parent_id)

        parent_tree = parent_commit.tree
        current_tree = target_commit.tree

        adl_diff_y = _single_file_diff(
            repo,
            parent_tree,
            current_tree,
            normalized_adl_path,
        )

        if not adl_diff_y:
            continue
        adl_commit_count += 1

        code_diffs_x1 = _collect_code_diffs(
            repo,
            parent_tree,
            current_tree,
            normalized_adl_path,
            normalized_exts,
        )

        intent_x2 = target_commit.message

        data_pair: DiffDataPair = (intent_x2, code_diffs_x1, adl_diff_y)
        training_data.append(data_pair)
        logger.info(
            "  -> SUCCESS: Found %s code diffs and 1 ADL diff.",
            len(code_diffs_x1),
        )

    if not adl_commit_count:
        logger.warning("No commits found that modified '%s'.", normalized_adl_path)

    logger.info(
        "Mining complete. Extracted %s training pairs.",
        len(training_data),
    )
    return training_data


# --- Typer command ------------------------------------------------------------
@app.command()
def mine(
    repo_path: Path = typer.Option(
        ...,
        "--repo-path",
        envvar="REPO_PATH",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Path to the Git repository containing the ADL file.",
    ),
    adl_file: str = typer.Option(
        DEFAULT_ADL_FILE,
        "--adl-file",
        envvar="ADL_FILE_PATH",
        help="Path to the ADL file relative to the repo root.",
        show_default=True,
    ),
    output_path: Path = typer.Option(
        DEFAULT_OUTPUT_PATH,
        "--output",
        "-o",
        envvar="TRAINING_DATASET_PATH",
        help="Where to write the JSON dataset.",
        show_default=True,
    ),
    code_extensions: List[str] = typer.Option(
        list(DEFAULT_CODE_EXTENSIONS),
        "--code-ext",
        "-c",
        help="Repeat for additional file extensions to include (e.g., --code-ext .py --code-ext .rs).",
        show_default=True,
    ),
) -> None:
    """Mine ADL-related commits and persist the resulting dataset."""
    normalized_exts = _normalize_extensions(code_extensions)
    training_pairs = mine_repository(
        repo_path=repo_path,
        adl_file=adl_file,
        code_extensions=normalized_exts,
    )

    if not training_pairs:
        logger.warning("No training pairs were found; dataset not written.")
        raise typer.Exit(code=1)

    destination = _write_training_dataset(output_path, training_pairs)
    logger.info(
        "Saved %s training pairs to %s",
        len(training_pairs),
        destination,
    )
    _log_sample(training_pairs)


def main() -> None:
    """Entry point for tooling that still expects a callable main."""
    app()


if __name__ == "__main__":
    main()
