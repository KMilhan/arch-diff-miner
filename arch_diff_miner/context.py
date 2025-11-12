"""Context mining utilities for per-file Git statistics."""
from __future__ import annotations

import logging
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, MutableMapping, Sequence, Tuple

import pygit2

logger = logging.getLogger(__name__)

PerFileStat = Dict[str, object]
AggregateStats = Dict[str, object]
PerFileStats = Dict[str, PerFileStat]

SECONDS_PER_DAY = 86_400


def _normalize_path(path: str) -> str:
    """Normalize repository-relative paths for libgit2 comparisons."""

    if not path:
        return ""
    normalized = path.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.strip()


def _ensure_utc(dt: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _commit_datetime(commit: pygit2.Commit) -> datetime:
    """Return the committer timestamp for a commit in UTC."""

    offset_minutes = getattr(commit, "commit_time_offset", 0)
    tz = timezone.utc if offset_minutes == 0 else timezone(timedelta(minutes=offset_minutes))
    return datetime.fromtimestamp(commit.commit_time, tz).astimezone(timezone.utc)


def _days_between(later: datetime, earlier: datetime | None) -> float:
    """Return fractional days between timestamps, defaulting to 0.0."""

    if earlier is None:
        return 0.0
    seconds = max((later - earlier).total_seconds(), 0.0)
    return seconds / SECONDS_PER_DAY


def _touch_matches(delta: pygit2.DiffDelta, targets: Dict[str, str]) -> Iterable[str]:
    """Yield canonical targets touched by the provided delta."""

    seen: set[str] = set()
    for candidate in (delta.new_file.path, delta.old_file.path):
        cleaned = _normalize_path(candidate or "")
        if not cleaned:
            continue
        canonical = targets.get(cleaned.lower())
        if canonical and canonical not in seen:
            seen.add(canonical)
            yield canonical


def collect_context_stats(
    repo: pygit2.Repository,
    parent_commit: pygit2.Commit,
    files: Sequence[str],
    since_dt: datetime,
    until_dt: datetime,
) -> Tuple[PerFileStats, AggregateStats]:
    """Compute churn, authors, and recency metrics per file.

    Args:
        repo: Open pygit2 repository.
        parent_commit: Commit whose ancestry should be inspected (first parent).
        files: Iterable of repository-relative file paths to track.
        since_dt: Inclusive lower bound for commit timestamps.
        until_dt: Inclusive upper bound for commit timestamps.

    Returns:
        Tuple of per-file stats (OrderedDict keyed by normalized path) and
        dataset-level aggregate statistics.
    """

    canonical: List[str] = []
    lookup: Dict[str, str] = {}
    for path in files:
        cleaned = _normalize_path(path)
        if not cleaned:
            continue
        lower = cleaned.lower()
        if lower in lookup:
            continue
        lookup[lower] = cleaned
        canonical.append(cleaned)

    if not canonical:
        return OrderedDict(), {"total_commits": 0, "total_unique_authors": 0, "most_recent_change_days_ago": 0.0}

    since_utc = _ensure_utc(since_dt)
    until_utc = _ensure_utc(until_dt)
    if since_utc > until_utc:
        raise ValueError("since_dt must be less than or equal to until_dt")

    churn_counts: MutableMapping[str, int] = OrderedDict((path, 0) for path in canonical)
    author_sets: Dict[str, set[str]] = {path: set() for path in canonical}
    author_freq: Dict[str, MutableMapping[str, int]] = {
        path: defaultdict(int) for path in canonical
    }
    last_touched: Dict[str, datetime | None] = {path: None for path in canonical}

    empty_tree = repo[repo.TreeBuilder().write()]

    walker = repo.walk(parent_commit.id, pygit2.GIT_SORT_TIME)
    walker.simplify_first_parent()

    for commit in walker:
        commit_dt = _commit_datetime(commit)
        if commit_dt > until_utc:
            continue
        if commit_dt < since_utc:
            break
        parent_tree = commit.parents[0].tree if commit.parents else empty_tree
        try:
            diff = repo.diff(parent_tree, commit.tree)
        except pygit2.GitError as error:  # pragma: no cover - defensive
            # Context stats should not prevent dataset creation; warn and continue.
            repo_path = getattr(repo, "path", "<repo>")
            logger.warning("Context diff failed in %s: %s", repo_path, error)
            continue

        try:
            diff.find_similar()
        except AttributeError:  # pragma: no cover - older pygit2
            pass

        for patch in diff:
            touched = list(_touch_matches(patch.delta, lookup))
            if not touched:
                continue

            author = commit.author
            identity = (author.email or author.name or "").strip().lower() or "unknown"

            for path in touched:
                churn_counts[path] += 1
                author_sets[path].add(identity)
                author_freq[path][identity] += 1
                previous = last_touched[path]
                if previous is None or commit_dt > previous:
                    last_touched[path] = commit_dt

    per_file: PerFileStats = OrderedDict()
    all_authors: set[str] = set()
    freshest: List[float] = []

    for path in canonical:
        churn = churn_counts[path]
        unique = len(author_sets[path])
        last_days = _days_between(until_utc, last_touched[path])
        if churn:
            freshest.append(last_days)
            all_authors.update(author_sets[path])

        sorted_authors = sorted(
            author_freq[path].items(), key=lambda item: (-item[1], item[0])
        )
        top_authors = [email for email, _ in sorted_authors[:3]]

        per_file[path] = {
            "churn_count": churn,
            "unique_authors": unique,
            "last_modified_days_ago": last_days,
            "top_authors": top_authors,
        }

    aggregate: AggregateStats = {
        "total_commits": sum(churn_counts.values()),
        "total_unique_authors": len(all_authors),
        "most_recent_change_days_ago": min(freshest) if freshest else 0.0,
    }

    return per_file, aggregate


__all__ = ["collect_context_stats"]
