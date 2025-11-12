# Repository Guidelines

## Project Structure & Module Organization
- `arch_diff_miner/` – Typer CLI package housing the miner logic (`cli.py`, `__init__.py`, `__main__.py`).
- `pyproject.toml` / `uv.lock` – Python 3.14 project definition and locked dependencies (currently `pygit2`, `typer`, and transitive helpers).
- Keep helper scripts beside the miner so paths stay relative; place any future tests in `tests/` mirroring module names (`tests/test_mine_adl_diffs.py`).

## Task Tracking & Workflow
- Manage every change through GitHub Issues by using the `gh` CLI so the task history stays visible.
- Limit issue activity to `https://github.com/KMilhan/arch-diff-miner`; avoid opening or editing issues outside this repo for routine work.
- Reference the active issue number in your notes and close or update it with `gh issue comment|close` immediately after pushing the corresponding commit.
- Capture upstream/downstream dependencies in each issue description when they are known, and link related work with sub-issues so reviewers can see sequencing at a glance.

## Build, Test, and Development Commands
- Run everything through `uv` to stay on the locked Python 3.14 freethreaded (no-GIL) toolchain; skip ad-hoc `pip` or system `python` invocations, and install the interpreter with `uv python install 3.14+freethreaded` when needed.
- `uv sync` – installs the locked environment; prefer this over bare `pip` so everyone targets Python 3.14.
- `uv run python -m arch_diff_miner mine --repo-path "$REPO_PATH" --adl-file <adl.yaml> --code-ext .py --output training_dataset.json` – mines diffs using the repo you pass via CLI (or the `REPO_PATH` env var Typer picks up) and refreshes `training_dataset.json`. Example: `REPO_PATH=/path/to/adl uv run python -m arch_diff_miner mine --repo-path "$REPO_PATH" --output training_dataset.json`.
- `uv run python -m arch_diff_miner --help` – inspect the Typer CLI and available options.
- `uv run pytest` – placeholder command once tests exist; fail fast if any dataset validators are added under `tests/`.

## Coding Style & Naming Conventions
- Treat PEP 8, 257, 621, 517, 518 guidance as mandatory
- Keep docstrings in Google-style sentences describing inputs/outputs.

## Testing Guidelines
Create tests under `tests/` using `pytest`, naming files `test_*.py` and functions `test_<behavior>()`. 

## Commit & Pull Request Guidelines
- Keep each commit atomic; pair code edits with dataset snapshots only when they cannot be separated.
- Format commit messages as a colon-style emoji followed by an imperative title (e.g., `:memo: Document workflow`), then `git push` immediately.
- Because commits lack closing keywords, finish the related GitHub Issue by commenting with the commit link or by running `gh issue close` once the push succeeds.
- Pull requests should include: purpose summary, reproduction steps (`uv run ...`), sample diff tuple output, and mention of any external repo snapshots; attach screenshots only if you introduce UI/diagram artifacts.
