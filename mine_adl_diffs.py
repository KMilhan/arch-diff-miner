"""
mine_adl_diffs.py

Scans a Git repository to find commits where the ADL file was changed.
It then extracts a training data tuple:
(intent, code_diffs, adl_diff)

This script is the "first shovel" for our 1-stage "LLM Translator"
by creating the "Diff-to-Diff" training dataset.

Requirements:
  uv sync  # installs pygit2 via pyproject deps
"""
import json
import logging
from pathlib import Path
from typing import List, Tuple, Optional

import pygit2

# --- Configuration ---
# Set these paths to match your local environment
REPO_PATH = "../spam-bootstrapper"  # Path to your 8,000-line Python package
ADL_FILE_PATH = "adl.yaml"
CODE_FILE_EXTENSIONS = ('.py',)  # We only care about Python file diffs

# --- Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Type alias for our training data structure
# (Commit Message, List[Python File Diffs], Adl Yaml Diff)
DiffDataPair = Tuple[str, List[str], str]


def _patch_to_text(patch: pygit2.Patch) -> str:
    """Convert a pygit2 patch to its textual diff representation."""
    text = getattr(patch, "text", None)
    return text if isinstance(text, str) else ""


def _discover_repository(repo_path: str) -> Optional[pygit2.Repository]:
    """Locate and open a Git repository starting from repo_path."""
    try:
        git_dir = pygit2.discover_repository(repo_path)
    except (KeyError, pygit2.GitError):
        git_dir = None

    if not git_dir:
        logger.error(f"Error: Path '{repo_path}' is not inside a Git repository.")
        return None

    try:
        return pygit2.Repository(git_dir)
    except pygit2.GitError as error:
        logger.error(f"Error opening repository at '{repo_path}': {error}")
        return None


def _single_file_diff(
    parent_tree: pygit2.Tree,
    current_tree: pygit2.Tree,
    target_path: str,
) -> str:
    """Return the textual diff for a single file path."""
    try:
        diff = parent_tree.diff(
            current_tree,
            paths=[target_path],
            context_lines=3,
            interhunk_lines=1,
        )
    except pygit2.GitError as error:
        logger.error(f"Could not diff {target_path}: {error}")
        return ""

    for patch in diff:
        patch_text = _patch_to_text(patch)
        if patch_text:
            return patch_text
    return ""


def _collect_code_diffs(
    parent_tree: pygit2.Tree,
    current_tree: pygit2.Tree,
    adl_file: str,
) -> List[str]:
    """Gather diff text for code files that changed in the commit."""
    try:
        diff = parent_tree.diff(
            current_tree,
            context_lines=3,
            interhunk_lines=1,
        )
    except pygit2.GitError as error:
        logger.error(f"Could not compute code diffs: {error}")
        return []

    code_diffs: List[str] = []
    for patch in diff:
        path = patch.delta.new_file.path or patch.delta.old_file.path
        if not path or path == adl_file or not path.endswith(CODE_FILE_EXTENSIONS):
            continue

        patch_text = _patch_to_text(patch)
        if patch_text:
            code_diffs.append(patch_text)
    return code_diffs


def mine_repository(
    repo_path: str,
    adl_file: str,
) -> List[DiffDataPair]:
    """
    Mines a repository to extract (Intent, Code Diff, ADL Diff) pairs.

    This iterates through all commits that modified the target ADL file
    and creates a diff against their parent.

    Args:
        repo_path: The file system path to the Git repository.
        adl_file: The relative path to the ADL file within the repo.

    Returns:
        A list of DiffDataPair tuples, ready for training.
    """
    logger.info(f"Opening repository at: {repo_path}")
    repo = _discover_repository(repo_path)
    if repo is None:
        return []

    try:
        head_id = repo.head.target
    except pygit2.GitError:
        logger.error(f"Repository '{repo_path}' has no HEAD.")
        return []

    walker = repo.walk(head_id, pygit2.GIT_SORT_TOPOLOGICAL)
    walker.simplify_first_parent()

    logger.info(f"Scanning for commits that changed: {adl_file}")

    training_data: List[DiffDataPair] = []
    adl_commit_count = 0

    for target_commit in walker:
        # We need a parent to create a diff. Skip the root commit.
        if not target_commit.parents:
            commit_id = str(target_commit.id)
            logger.info(
                f"Skipping root commit {commit_id} (no parent).",
            )
            continue

        # Get the parent commit (the "Before" state, x_k)
        parent_commit = target_commit.parents[0]
        commit_id = str(target_commit.id)
        parent_id = str(parent_commit.id)
        logger.info(
            f"Processing Target Commit (After): {commit_id}",
        )
        logger.info(
            f"           Parent Commit (Before): {parent_id}",
        )

        # 1. Get the 'Intent' (X2) from the target commit message
        intent_x2 = target_commit.message

        # 2. Get the 'ADL Diff' (Y)
        parent_tree = parent_commit.tree
        current_tree = target_commit.tree
        adl_diff_y = _single_file_diff(parent_tree, current_tree, adl_file)

        if not adl_diff_y:
            continue
        adl_commit_count += 1

        # 3. Get the 'Code Diffs' (X1)
        code_diffs_x1 = _collect_code_diffs(parent_tree, current_tree, adl_file)

        # We only save data if there was an *actual* change
        # in either the ADL or the code.
        if code_diffs_x1 or adl_diff_y:
            data_pair: DiffDataPair = (intent_x2, code_diffs_x1, adl_diff_y)
            training_data.append(data_pair)
            logger.info(
                f"  -> SUCCESS: Found {len(code_diffs_x1)} code diffs "
                f"and 1 ADL diff.",
            )
        else:
            logger.info("  -> SKIPPED: No meaningful diffs found.")

    if not adl_commit_count:
        logger.warning(f"No commits found that modified '{adl_file}'.")
    logger.info(
        f"Mining complete. Extracted {len(training_data)} training pairs.",
    )
    return training_data


def main():
    """Main function to run the diff mining process."""
    
    # Ensure the path is correct
    repo_dir = Path(REPO_PATH).expanduser()
    adl_file_rel_path = ADL_FILE_PATH
    
    training_pairs = mine_repository(
        repo_path=str(repo_dir),
        adl_file=adl_file_rel_path,
    )
    
    if training_pairs:
        logger.info("-" * 40)
        logger.info("Example of the first training pair extracted:")
        
        intent, code_diffs, adl_diff = training_pairs[0]
        
        logger.info(f"\nINTENT (X2):\n{intent}\n")
        
        logger.info(f"CODE DIFFS (X1) - ({len(code_diffs)} files):")
        if code_diffs:
            logger.info(f"--- Diff for first code file ---\n{code_diffs[0]}\n")
        else:
            logger.info("  (No code diffs in this commit)\n")
        
        logger.info(f"ADL DIFF (Y):\n{adl_diff}\n")
        logger.info("-" * 40)

        # Here you would save this data to a file (e.g., JSON, Parquet)
        # for the LLM Finetuning step.
        # Example:
        with open("training_dataset.json", "w") as f:
             json.dump(training_pairs, f, indent=2)


if __name__ == "__main__":
    main()
    
