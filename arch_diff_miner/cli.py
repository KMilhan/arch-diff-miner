"""Arch Diff Miner Typer CLI."""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from typing import TypedDict

import pygit2

try:  # pygit2 >= 1.14 provides these enums
    from pygit2 import GIT_DELTA_ADDED, GIT_DELTA_DELETED, GIT_DELTA_MODIFIED, GIT_DELTA_RENAMED
except ImportError:  # pragma: no cover - fallback for older pygit2
    GIT_DELTA_ADDED = 1
    GIT_DELTA_DELETED = 2
    GIT_DELTA_MODIFIED = 3
    GIT_DELTA_RENAMED = 4


import typer

from .jsonl_writer import write_jsonl_dataset
from .context import collect_context_stats


class TrainingSample(TypedDict):
    """Intermediate in-memory sample before JSONL emission."""

    commit_hash: str
    parent_hash: str
    authored_at: str
    committed_at: str
    author_name: str
    author_email: str
    committer_name: Optional[str]
    committer_email: Optional[str]
    is_merge: bool
    intent_message: str
    adl_diff: Dict[str, Any]
    code_diffs: List[Dict[str, Any]]
    context_signals: Dict[str, Any]


@dataclass(frozen=True)
class MineConfig:
    """Runtime settings for a single mining invocation."""

    repo_path: Path
    adl_file: str
    code_extensions: Sequence[str]
    context_days: int


DEFAULT_ADL_FILE = "adl.yaml"
DEFAULT_CODE_EXTENSIONS = (".py",)
DEFAULT_CONTEXT_DAYS = 90
# None indicates stdout per SPEC v1; callers can still supply a file path explicitly.
DEFAULT_OUTPUT_PATH: Optional[Path] = None
CODE_EXTS_FLAG_NAMES = ("--code-exts", "-c")

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


def _expand_code_exts_args(argv: List[str]) -> List[str]:
    """Normalize argv for backwards-compatible commands and code-ext parsing."""

    args = list(argv)
    # Accept legacy `python -m arch_diff_miner mine ...` invocations by dropping
    # the redundant subcommand before Typer parses options.
    if len(args) > 1 and args[1] == "mine":
        args = [args[0], *args[2:]]

    def _split_inline_values(raw: str) -> List[str]:
        values = raw.replace(",", " ").split()
        return values or [raw]

    if len(args) <= 1:
        return args

    expanded = [args[0]]
    i = 1
    while i < len(args):
        token = args[i]
        if token == "--":
            expanded.extend(args[i:])
            break
        if token in CODE_EXTS_FLAG_NAMES:
            expanded.append("--code-exts")
            i += 1
            if i >= len(args):
                break
            expanded.append(args[i])
            i += 1
            while i < len(args):
                lookahead = args[i]
                if lookahead.startswith("-"):
                    break
                expanded.append("--code-exts")
                expanded.append(lookahead)
                i += 1
            continue
        if token.startswith("--code-exts="):
            _, raw_values = token.split("=", 1)
            for value in _split_inline_values(raw_values):
                expanded.append("--code-exts")
                expanded.append(value)
            i += 1
            continue
        if token.startswith("-c="):
            _, raw_values = token.split("=", 1)
            for value in _split_inline_values(raw_values):
                expanded.append("--code-exts")
                expanded.append(value)
            i += 1
            continue
        expanded.append(token)
        i += 1

    return expanded


sys.argv = _expand_code_exts_args(sys.argv)


def _clean_rel_path(value: str) -> str:
    """Normalize repository-relative file paths without applying defaults."""
    return value.replace("\\", "/").lstrip("./") if value else ""


def _normalize_rel_path(value: str) -> str:
    """Normalize repository-relative file paths for libgit2 comparisons."""
    normalized = _clean_rel_path(value)
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


def _validate_context_days(value: int) -> int:
    """Ensure the context-days CLI flag is a positive integer."""
    if value < 1:
        raise typer.BadParameter("--context-days must be >= 1 day to capture history.")
    return value


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


def _patch_text(
    patch: pygit2.Patch,
    path: str,
    kind: str,
) -> str:
    """Extract textual diff content, logging anomalies for ADL/code patches."""
    try:
        text = getattr(patch, "text", None)
    except UnicodeDecodeError as error:
        logger.warning("Unicode decode failed for %s '%s': %s", kind, path, error)
        return ""

    if not isinstance(text, str):
        logger.warning("Binary diff detected for %s '%s'; skipping.", kind, path)
        return ""

    if not text.strip():
        # Blank patches generally mean pure mode/rename changes.
        return ""

    return text


def _delta_status_name(delta_status: int) -> str:
    """Map pygit2 delta status to a human-friendly string."""
    mapping = {
        GIT_DELTA_ADDED: "added",
        GIT_DELTA_DELETED: "deleted",
        GIT_DELTA_MODIFIED: "modified",
        GIT_DELTA_RENAMED: "renamed",
    }
    return mapping.get(delta_status, "unknown")


def _extract_hunks(patch_text: str) -> List[Dict[str, Any]]:
    """Parse unified diff text into structured hunks."""
    if not patch_text:
        return []

    hunks: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None

    for line in patch_text.splitlines():
        if line.startswith("@@"):
            if current:
                hunks.append(current)
            current = {"header": line, "added": [], "removed": [], "context": []}
            continue

        if current is None:
            # Skip diff headers
            continue

        if line.startswith("+"):
            current["added"].append(line[1:])
        elif line.startswith("-"):
            current["removed"].append(line[1:])
        elif line.startswith(" "):
            current["context"].append(line[1:])
        else:
            current["context"].append(line)

    if current:
        hunks.append(current)

    return hunks


def _count_stats_from_text(patch_text: str) -> Dict[str, int]:
    """Return additions/deletions counts for a diff text."""
    adds = 0
    dels = 0
    for line in patch_text.splitlines():
        if line.startswith("@@") or line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("+"):
            adds += 1
        elif line.startswith("-"):
            dels += 1
    return {"additions": adds, "deletions": dels}


def _format_timestamp(signature: pygit2.Signature) -> str:
    """Convert a pygit2 signature timestamp into an ISO-8601 UTC string."""
    tz = timezone(timedelta(minutes=signature.offset))
    dt = datetime.fromtimestamp(signature.time, tz)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _signature_datetime(signature: pygit2.Signature) -> datetime:
    """Return a timezone-aware datetime for additional computations."""

    tz = timezone(timedelta(minutes=signature.offset))
    return datetime.fromtimestamp(signature.time, tz).astimezone(timezone.utc)


class _AdlDiffResult(TypedDict, total=False):
    patch_text: str
    status: str
    current_path: str
    previous_path: Optional[str]
    touched: bool
    hunks: List[Dict[str, Any]]
    stats: Dict[str, int]


def _collect_commit_diffs(
    repo: pygit2.Repository,
    parent_tree: pygit2.Tree,
    current_tree: pygit2.Tree,
    tracked_adl_path: str,
    code_extensions: Sequence[str],
) -> Tuple[_AdlDiffResult, List[Dict[str, Any]]]:
    """Return ADL diff metadata and filtered code diffs for the commit."""
    try:
        diff = repo.diff(
            parent_tree,
            current_tree,
            context_lines=3,
            interhunk_lines=1,
            flags=pygit2.GIT_DIFF_INCLUDE_TYPECHANGE,
        )
    except pygit2.GitError as error:
        logger.error("Could not compute diff for commit: %s", error)
        return {"touched": False}, []

    try:
        diff.find_similar(rename_threshold=60)
    except AttributeError:  # pragma: no cover - older pygit2
        pass

    tracked_lower = tracked_adl_path.lower()
    adl_result: _AdlDiffResult = {"touched": False}
    code_diffs: List[Dict[str, Any]] = []

    for patch in diff:
        delta = patch.delta
        path_new = _clean_rel_path(delta.new_file.path or "")
        path_old = _clean_rel_path(delta.old_file.path or "")
        normalized_new = path_new.lower()
        normalized_old = path_old.lower()

        # Determine if this patch corresponds to the tracked ADL path.
        is_adl_patch = (
            normalized_new == tracked_lower
            or (not path_new and normalized_old == tracked_lower)
            or (
                delta.status == GIT_DELTA_RENAMED
                and normalized_new == tracked_lower
            )
        )

        if is_adl_patch and not adl_result.get("touched"):
            adl_patch_text = _patch_text(patch, path_new or path_old, "ADL")
            adl_result = {
                "patch_text": adl_patch_text,
                "status": _delta_status_name(delta.status),
                "current_path": path_new or path_old,
                "previous_path": path_old if delta.status == GIT_DELTA_RENAMED else None,
                "touched": True,
                "hunks": _extract_hunks(adl_patch_text),
                "stats": _count_stats_from_text(adl_patch_text),
            }
            continue

        # Otherwise, treat as a potential code diff.
        candidate_path = path_new or path_old
        if not candidate_path:
            continue
        normalized_candidate = candidate_path.lower()
        if normalized_candidate == tracked_lower:
            continue
        if not any(normalized_candidate.endswith(ext) for ext in code_extensions):
            continue

        patch_text = _patch_text(patch, candidate_path, "code")
        hunks = _extract_hunks(patch_text)
        if hunks:
            code_diffs.append(
                {
                    "path": candidate_path,
                    "status": _delta_status_name(delta.status),
                    "extension": Path(candidate_path).suffix or "",
                    "language": None,
                    "hunks": hunks,
                    "stats": _count_stats_from_text(patch_text),
                }
            )

    return adl_result, code_diffs


def _log_sample(training_pairs: List[TrainingSample]) -> None:
    """Log the first tuple for quick inspection."""
    if not training_pairs:
        return

    sample = training_pairs[0]
    intent = sample["intent_message"]
    code_diffs = sample["code_diffs"]
    adl_diff = sample["adl_diff"]
    logger.info("-" * 40)
    logger.info("Example of the first training pair extracted:")
    logger.info("\nINTENT (X2):\n%s\n", intent)
    logger.info("CODE DIFFS (X1) - (%s files):", len(code_diffs))
    if code_diffs:
        first_code = code_diffs[0]
        if first_code.get("hunks"):
            code_preview = "\n".join(first_code["hunks"][0]["added"][:20]) or "(context only)"
        else:
            code_preview = "(no hunks)"
        logger.info(
            "--- Diff for first code file (%s) ---\n%s\n",
            first_code["path"],
            code_preview,
        )
    else:
        logger.info("  (No code diffs in this commit)\n")
    adl_hunks = adl_diff.get("hunks", [])
    if adl_hunks:
        adl_preview = "\n".join(adl_hunks[0]["added"]) or "(context only)"
    else:
        adl_preview = "(no hunks)"
    logger.info("ADL DIFF (Y):\n%s\n", adl_preview)
    logger.info("-" * 40)


def _write_training_dataset(
    output_path: Optional[Path],
    training_pairs: List[TrainingSample],
) -> Tuple[Optional[Path], int]:
    """Stream samples to stdout or a destination file as JSONL."""
    destination = output_path.expanduser().resolve() if output_path else None
    written = write_jsonl_dataset(training_pairs, destination)
    return destination, written


def mine_repository(
    config: MineConfig,
) -> List[TrainingSample]:
    """Extract structured samples for commits touching the ADL file."""
    repo_path = config.repo_path
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

    normalized_adl_path = _normalize_rel_path(config.adl_file)
    normalized_exts = _normalize_extensions(config.code_extensions)

    logger.info("Scanning for commits that changed: %s", normalized_adl_path)
    logger.info("Context window (days): %s", config.context_days)

    training_data: List[TrainingSample] = []
    adl_commit_count = 0
    tracked_adl_path = normalized_adl_path

    for target_commit in walker:
        if not target_commit.parents:
            commit_id = str(target_commit.id)
            logger.info("Skipping root commit %s (no parent).", commit_id)
            continue

        parent_commit = target_commit.parents[0]
        commit_id = str(target_commit.id)
        parent_id = str(parent_commit.id)
        is_merge = len(target_commit.parents) > 1
        logger.info("Processing Target Commit (After): %s", commit_id)
        logger.info("           Parent Commit (Before): %s", parent_id)

        parent_tree = parent_commit.tree
        current_tree = target_commit.tree

        adl_result, code_diffs_x1 = _collect_commit_diffs(
            repo,
            parent_tree,
            current_tree,
            tracked_adl_path,
            normalized_exts,
        )

        if adl_result.get("previous_path"):
            tracked_adl_path = _normalize_rel_path(adl_result["previous_path"] or tracked_adl_path)

        if not adl_result.get("touched"):
            continue

        adl_hunks = adl_result.get("hunks", [])
        if not adl_hunks:
            logger.info(
                "  -> SKIP: ADL diff empty or non-textual (status=%s)",
                adl_result.get("status", "unknown"),
            )
            continue

        if not code_diffs_x1:
            logger.info(
                "  -> SKIP: Commit %s touched ADL but has no matching code diffs.",
                commit_id,
            )
            continue

        adl_commit_count += 1

        code_paths = [diff_entry["path"] for diff_entry in code_diffs_x1]
        unique_code_paths = list(dict.fromkeys(code_paths))
        analysis_until = _signature_datetime(parent_commit.committer)
        analysis_since = analysis_until - timedelta(days=config.context_days)
        per_file_stats, aggregate_stats = collect_context_stats(
            repo=repo,
            parent_commit=parent_commit,
            files=unique_code_paths,
            since_dt=analysis_since,
            until_dt=analysis_until,
        )
        per_file_list = [
            {
                "path": path,
                **stats,
            }
            for path, stats in per_file_stats.items()
        ]
        context_signals = {
            "analysis_parent_hash": parent_id,
            "analysis_timespan_days": config.context_days,
            "files_analyzed": unique_code_paths,
            "aggregate_stats": aggregate_stats,
            "per_file_stats": per_file_list,
        }

        intent_x2 = (target_commit.message or "").strip()

        author = target_commit.author
        committer = target_commit.committer

        data_pair: TrainingSample = {
            "commit_hash": commit_id,
            "parent_hash": parent_id,
            "authored_at": _format_timestamp(author),
            "committed_at": _format_timestamp(committer),
            "author_name": author.name or "",
            "author_email": author.email or "",
            "committer_name": committer.name or author.name or "",
            "committer_email": committer.email or author.email or "",
            "is_merge": is_merge,
            "intent_message": intent_x2,
            "adl_diff": {
                "path": adl_result.get("current_path") or tracked_adl_path,
                "previous_path": adl_result.get("previous_path"),
                "status": adl_result.get("status", "modified"),
                "hunks": adl_result.get("hunks", []),
                "stats": adl_result.get("stats", {"additions": 0, "deletions": 0}),
            },
            "code_diffs": code_diffs_x1,
            "context_signals": context_signals,
        }
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


@app.command(name="mine")
def mine(
    repo: Path = typer.Option(
        ...,
        "--repo",
        envvar="REPO_PATH",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        help="Required path to the Git repository containing the ADL file.",
    ),
    adl_file: str = typer.Option(
        DEFAULT_ADL_FILE,
        "--adl-file",
        envvar="ADL_FILE_PATH",
        help="ADL file relative to the repo root (supports glob-style patterns).",
        show_default=True,
    ),
    code_extensions: Optional[List[str]] = typer.Option(
        None,
        "--code-exts",
        "-c",
        help=(
            "Space-delimited or repeated list of code extensions to include "
            "(e.g., --code-exts .py .rs or --code-exts .py --code-exts .rs)."
        ),
        show_default=False,
    ),
    output_path: Optional[Path] = typer.Option(
        DEFAULT_OUTPUT_PATH,
        "--output",
        "-o",
        envvar="TRAINING_DATASET_PATH",
        help="Path to write the JSON dataset (defaults to stdout when omitted).",
        show_default=False,
    ),
    context_days: int = typer.Option(
        DEFAULT_CONTEXT_DAYS,
        "--context-days",
        help=(
            "Number of days to look back from each commit's parent when computing "
            "context signals (values < 1 are rejected)."
        ),
        show_default=True,
        min=1,
    ),
) -> None:
    """Mine ADL-related commits and persist the resulting dataset."""
    validated_context_days = _validate_context_days(context_days)
    selected_code_exts: Sequence[str] = (
        tuple(code_extensions) if code_extensions else DEFAULT_CODE_EXTENSIONS
    )
    config = MineConfig(
        repo_path=repo,
        adl_file=adl_file,
        code_extensions=selected_code_exts,
        context_days=validated_context_days,
    )
    training_pairs = mine_repository(config=config)

    if not training_pairs:
        logger.warning("No training pairs were found; dataset not written.")
        raise typer.Exit(code=1)

    destination, written = _write_training_dataset(output_path, training_pairs)
    target_display = "stdout" if destination is None else str(destination)
    logger.info(
        "Saved %s training pairs to %s",
        written,
        target_display,
    )
    _log_sample(training_pairs)


def main() -> None:
    """Entry point for tooling that expects a callable main."""
    app()
