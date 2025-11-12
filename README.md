# Arch Diff Miner

Arch Diff Miner is a Python 3.14 freethreaded (no-GIL) command-line tool that mines architecture decision logs (ADLs) for training data. Powered by `pygit2`/libgit2 and a Typer CLI packaged under `arch_diff_miner`, it walks a target repository and streams `(intent, code_diffs, adl_diff)` tuples as JSONL to stdout (or a file when `--output` is provided).

## Why a CLI?
- **Headless-first.** Runs anywhere Git is available, making it easy to integrate into scripts or CI jobs.
- **Fast despite Python.** pygit2/libgit2 diff streaming, minimal allocations, and the GIL-free CPython 3.14 runtime keep runtimes competitive with compiled tooling.
- **Deterministic outputs.** With `uv` pinning dependencies, identical inputs yield identical dataset artifacts.

## Quick Start
0. Ensure the interpreter is installed: `uv python install 3.14+freethreaded`.
1. Install dependencies once: `uv sync`.
2. Stream JSONL to stdout (space-delimited extensions):
   ```bash
   uv run python -m arch_diff_miner mine \
     --repo /path/to/repo \
     --adl-file adl.yaml \
     --code-exts .py .rs \
     --context-days 90
   ```
3. Same command using repeated flags, but writing to a file:
   ```bash
   uv run python -m arch_diff_miner mine \
     --repo /path/to/repo \
     --adl-file adl.yaml \
     --code-exts .py --code-exts .rs \
     --context-days 90 \
     --output training_dataset.jsonl
   ```
4. Inspect CLI help: `uv run python -m arch_diff_miner --help`. *(Tip: `--context-days` defaults to 90, so omitting it keeps the same context window.)*

## CLI Options
- `--repo` / `$REPO_PATH` (required) — Absolute path to the Git repository being mined.
- `--adl-file` / `$ADL_FILE_PATH` (default `adl.yaml`) — ADL file relative to the repo root.
- `--code-exts` (space-delimited or repeatable, default `.py`) — Additional code extensions to capture alongside the ADL diff.
- `--output` / `$TRAINING_DATASET_PATH` (default stdout) — Optional destination JSON file; omit to stream to the console.
- `--context-days` (default `90`) — Look-back window, in days, used to compute per-file churn/author stats for the `context_signals` block. Values below 1 are rejected.
- `--context-days` (default `90`) — Look-back window, in days, for computing context signals; values below 1 are rejected.

> ADL path matching currently uses an exact, case-insensitive comparison. Glob-style patterns are on the roadmap, but for now provide a single, concrete path like `architectures/adl.yaml`.
- Run `uv run python -m arch_diff_miner --help` to view the full Typer help text.

### Release Notes (girokmoji)
- Last tag → HEAD: `bash scripts/release_notes.sh > RELEASE_NOTES.md` (requires at least one tag).
- Explicit ranges:
  - Separate args: `bash scripts/release_notes.sh FROM TO` (e.g., `v0.3.0 HEAD`).
  - Git range: `bash scripts/release_notes.sh FROM..TO` (e.g., `v0.3.0..HEAD`).
- The script shells out to `uvx --from "girokmoji@latest"` on demand, so no global install is required.
- Troubleshooting (no tags): either pass two refs explicitly—`bash scripts/release_notes.sh $(git rev-list --max-parents=0 HEAD) HEAD`—or create an initial tag such as `git tag -a v0.0.0 -m "Initial"` before rerunning.

## Key Commands
- Stream to stdout: `uv run python -m arch_diff_miner mine --repo $REPO_PATH --adl-file adl.yaml --code-exts .py .rs --context-days 90`
- Write JSONL to disk: `uv run python -m arch_diff_miner mine --repo $REPO_PATH --adl-file adl.yaml --context-days 90 --output training_dataset.jsonl`
- Run tests: `uv run pytest`

## Output Format (JSONL)
- Each line is one self-contained JSON object (no enclosing array) so you can pipe results into downstream tooling.
- When `--output` is omitted the miner streams to stdout; otherwise it writes UTF-8 JSONL to the provided path.

Example record (truncated):

```json
{
  "commit": {
    "hash": "0bff65a6fb3b0b7bfbc6f5cb9f947f1f22dc5678",
    "parent_hash": "9a2b3a4c5d6e7f8091a2b3c4d5e6f708192a3b4c",
    "authored_at": "2025-11-12T07:58:10Z",
    "committed_at": "2025-11-12T08:03:41Z",
    "author": {"name": "KMilhan", "email": "milhan@example.com"},
    "committer": {"name": "KMilhan", "email": "milhan@example.com"},
    "is_merge": false
  },
  "intent": {
    "message": "ADL: add Loki logging stack",
    "source": {"type": "commit_message"}
  },
  "adl_diff": {
    "path": "architectures/decisions.yaml",
    "previous_path": "adl.yaml",
    "status": "renamed",
    "hunks": [
      {
        "header": "@@ -10,3 +10,8 @@",
        "added": ["+  - id: dep-loki", "+    description: Loki log store"],
        "removed": ["-  - id: dep-syslog"],
        "context": ["   title: Observability"]
      }
    ],
    "stats": {"additions": 2, "deletions": 1}
  },
  "code_diffs": [
    {
      "path": "svc/logging/config.py",
      "status": "modified",
      "extension": ".py",
      "language": null,
      "hunks": [
        "@@ -1,3 +1,6 @@",
        " import logging",
        "+LOKI_URL = 'http://loki:3100'"
      ],
      "stats": {"additions": 2, "deletions": 0}
    }
  ],
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
  },
  "metadata": {
    "dataset_version": "adl-diff-miner-schema-v2.0",
    "generated_at": "2025-11-12T08:04:05Z"
  }
}
```

## Contributing
Follow the workflow in `AGENTS.md`: file a GitHub Issue, keep commits atomic with colon-style emoji + imperative titles, and push immediately after each change. Always prefer `uv` over ad-hoc `pip`, and stick to PEP 8 + PEP 257.
