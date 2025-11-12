"""Helpers for streaming SPEC-compliant JSONL records."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


logger = logging.getLogger(__name__)
DATASET_VERSION = "adl-diff-miner-schema-v2.0"


JsonlRecord = Dict[str, Any]


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_context_signals(raw: Dict[str, Any]) -> Dict[str, Any]:
    files = raw.get("files_analyzed") or []
    deduped_files = list(dict.fromkeys(files))

    aggregate = raw.get("aggregate_stats") or {}
    aggregate_block = {
        "total_commits": int(aggregate.get("total_commits", 0)),
        "total_unique_authors": int(aggregate.get("total_unique_authors", 0)),
        "most_recent_change_days_ago": float(
            aggregate.get("most_recent_change_days_ago", 0.0)
        ),
    }

    per_file_entries: List[Dict[str, Any]] = []
    for entry in raw.get("per_file_stats") or []:
        per_file_entries.append(
            {
                "path": entry.get("path"),
                "churn_count": int(entry.get("churn_count", 0)),
                "unique_authors": int(entry.get("unique_authors", 0)),
                "last_modified_days_ago": float(
                    entry.get("last_modified_days_ago", 0.0)
                ),
                "top_authors": entry.get("top_authors", []),
            }
        )

    return {
        "analysis_parent_hash": raw.get("analysis_parent_hash"),
        "analysis_timespan_days": int(raw.get("analysis_timespan_days", 0)),
        "files_analyzed": deduped_files,
        "aggregate_stats": aggregate_block,
        "per_file_stats": per_file_entries,
    }


def _build_record(sample: Dict[str, Any]) -> Optional[JsonlRecord]:
    adl_diff = sample.get("adl_diff") or {}
    code_diffs = sample.get("code_diffs") or []

    if not adl_diff.get("hunks"):
        logger.info("Skipping sample %s: empty ADL diff.", sample.get("commit_hash"))
        return None
    if not code_diffs:
        logger.info(
            "Skipping sample %s: no qualifying code diffs.", sample.get("commit_hash")
        )
        return None

    filtered_code: List[Dict[str, Any]] = []
    for entry in code_diffs:
        if not entry.get("hunks"):
            continue
        filtered_code.append(
            {
                "path": entry.get("path"),
                "status": entry.get("status", "modified"),
                "extension": entry.get("extension", ""),
                "language": entry.get("language"),
                "hunks": entry.get("hunks", []),
                "stats": entry.get("stats", {"additions": 0, "deletions": 0}),
            }
        )

    if not filtered_code:
        logger.info(
            "Skipping sample %s: code hunks empty after filtering.",
            sample.get("commit_hash"),
        )
        return None

    commit_block: Dict[str, Any] = {
        "hash": sample.get("commit_hash"),
        "parent_hash": sample.get("parent_hash"),
        "authored_at": sample.get("authored_at"),
        "committed_at": sample.get("committed_at"),
        "author": {
            "name": sample.get("author_name", ""),
            "email": sample.get("author_email", ""),
        },
        "is_merge": sample.get("is_merge", False),
    }

    committer_name = sample.get("committer_name")
    committer_email = sample.get("committer_email")
    if committer_name or committer_email:
        commit_block["committer"] = {
            "name": committer_name,
            "email": committer_email,
        }

    adl_block: Dict[str, Any] = {
        "path": adl_diff.get("path"),
        "status": adl_diff.get("status", "modified"),
        "hunks": adl_diff.get("hunks", []),
        "stats": adl_diff.get("stats", {"additions": 0, "deletions": 0}),
    }
    if adl_diff.get("previous_path"):
        adl_block["previous_path"] = adl_diff["previous_path"]

    record: JsonlRecord = {
        "commit": commit_block,
        "intent": {
            "message": sample.get("intent_message", ""),
            "source": {"type": "commit_message"},
        },
        "adl_diff": adl_block,
        "code_diffs": filtered_code,
        "metadata": {
            "dataset_version": DATASET_VERSION,
            "generated_at": _now_utc_iso(),
        },
    }

    context_signals = sample.get("context_signals")
    if context_signals:
        record["context_signals"] = _normalize_context_signals(context_signals)

    return record


def write_jsonl_dataset(
    samples: Iterable[Dict[str, Any]],
    destination: Optional[Path],
) -> int:
    """Stream JSONL records; return count of emitted samples."""
    stream = None
    close_stream = False

    if destination is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        stream = destination.open("w", encoding="utf-8"); close_stream = True

    written = 0
    for sample in samples:
        record = _build_record(sample)
        if record is None:
            continue
        line = json.dumps(record, ensure_ascii=False)
        if stream is None:
            sys.stdout.write(line + "\n")
        else:
            stream.write(line + "\n")
        written += 1

    if close_stream and stream is not None:
        stream.close()

    return written
