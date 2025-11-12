# Arch Diff Miner v2.0.0

## Highlights
- Added `--context-days` (default 90) so operators can tune how far back the miner looks when computing history-aware stats.
- Implemented the per-file context miner (`collect_context_stats`) and golden-backed tests to keep churn/author metrics stable.
- Emitted the new `context_signals` block alongside existing fields and bumped `metadata.dataset_version` to `adl-diff-miner-schema-v2.0` for downstream consumers.
- Documented the v2.0 schema/CLI behavior and added README examples plus release-friendly fixtures.

## Upgrade Notes
- The JSONL schema is additive; existing `commit/intention/adl_diff/code_diffs` fields remain byte-compatible. Consumers should read the `context_signals` object (parent hash, files analyzed, aggregate stats, per-file stats list) and tolerate unknown fields for future expansion.
- The seeded integration tests (`tests/test_jsonl_emission.py`) rely on the deterministic fixture under `tests/fixtures`, so regenerate goldens only when the schema changes.

## Example CLI
```bash
uv run python -m arch_diff_miner mine \
  --repo /path/to/repo \
  --adl-file adl.yaml \
  --code-exts .py --code-exts .rs \
  --context-days 90 \
  --output training_dataset_v2.jsonl
```

## Context Signals Snippet
```json
{
  "context_signals": {
    "analysis_parent_hash": "<parent-sha>",
    "analysis_timespan_days": 90,
    "files_analyzed": ["svc/logging/config.py"],
    "aggregate_stats": {
      "total_commits": 9,
      "total_unique_authors": 3,
      "most_recent_change_days_ago": 2.5
    },
    "per_file_stats": [
      {
        "path": "svc/logging/config.py",
        "churn_count": 6,
        "unique_authors": 3,
        "last_modified_days_ago": 2.5,
        "top_authors": ["dev@example.com", "mlops-bot@example.com"]
      }
    ]
  }
}
```
