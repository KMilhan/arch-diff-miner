# Arch Diff Miner

Arch Diff Miner is a Python 3.14 freethreaded (no-GIL) command-line tool that mines architecture decision logs (ADLs) for training data. Powered by `pygit2`/libgit2 and a Typer CLI packaged under `arch_diff_miner`, it walks a target repository, captures `(intent, code_diffs, adl_diff)` tuples, and emits them into `training_dataset.json` for downstream fine-tuning pipelines.

## Why a CLI?
- **Headless-first.** Runs anywhere Git is available, making it easy to integrate into scripts or CI jobs.
- **Fast despite Python.** pygit2/libgit2 diff streaming, minimal allocations, and the GIL-free CPython 3.14 runtime keep runtimes competitive with compiled tooling.
- **Deterministic outputs.** With `uv` pinning dependencies, identical inputs yield identical dataset artifacts.

## Quick Start
0. Ensure the interpreter is installed: `uv python install 3.14+freethreaded`.
1. Install dependencies once: `uv sync`.
2. Export the source repo path (or pass `--repo-path` on the CLI): `export REPO_PATH=/path/to/adl-source`.
3. Generate tuples with Typer: `uv run python -m arch_diff_miner mine --adl-file adl.yaml --output training_dataset.json`.
4. Smoke-test the entry point: `uv run python main.py`.

## CLI Options
- `--repo-path` / `$REPO_PATH` (required) — Absolute path to the Git repository being mined.
- `--adl-file` / `$ADL_FILE_PATH` (default `adl.yaml`) — ADL file relative to the repo root.
- `--output` / `$TRAINING_DATASET_PATH` (default `training_dataset.json`) — Destination JSON file.
- `--code-ext` (repeatable, default `.py`) — Additional code extensions to capture alongside the ADL diff.
- Run `uv run python -m arch_diff_miner --help` to view the full Typer help text.

## Key Commands
- `uv run python -m arch_diff_miner mine` — Mines diffs using `REPO_PATH` (and optional `ADL_FILE_PATH`) and refreshes `training_dataset.json`.
- `uv run python main.py` — Lightweight check that logging and CLI wiring still work.
- `uv run pytest` — Placeholder; run once tests land under `tests/`.

## Contributing
Follow the workflow in `AGENTS.md`: file a GitHub Issue, keep commits atomic with colon-style emoji + imperative titles, and push immediately after each change. Always prefer `uv` over ad-hoc `pip`, and stick to PEP 8 + PEP 257.
