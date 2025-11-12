# Arch Diff Miner

Arch Diff Miner is a Python 3.14 freethreaded (no-GIL) command-line tool that mines architecture decision logs (ADLs) for training data. It walks a target repository, captures `(intent, code_diffs, adl_diff)` tuples, and emits them into `training_dataset.json` for downstream fine-tuning pipelines.

## Why a CLI?
- **Headless-first.** Runs anywhere Git is available, making it easy to integrate into scripts or CI jobs.
- **Fast despite Python.** GitPython streaming, minimal allocations, and the GIL-free CPython 3.14 runtime keep runtimes competitive with compiled tooling.
- **Deterministic outputs.** With `uv` pinning dependencies, identical inputs yield identical dataset artifacts.

## Quick Start
0. Ensure the interpreter is installed: `uv python install 3.14+freethreaded`.
1. Install dependencies once: `uv sync`.
2. Export the source repo path: `export REPO_PATH=/path/to/adl-source`.
3. Generate tuples: `uv run python mine_adl_diffs.py`.
4. Smoke-test the entry point: `uv run python main.py`.

## Key Commands
- `uv run python mine_adl_diffs.py` — Mines diffs using `REPO_PATH` (and optional `ADL_FILE_PATH`) and refreshes `training_dataset.json`.
- `uv run python main.py` — Lightweight check that logging and CLI wiring still work.
- `uv run pytest` — Placeholder; run once tests land under `tests/`.

## Contributing
Follow the workflow in `AGENTS.md`: file a GitHub Issue, keep commits atomic with colon-style emoji + imperative titles, and push immediately after each change. Always prefer `uv` over ad-hoc `pip`, and stick to PEP 8 + PEP 257.
