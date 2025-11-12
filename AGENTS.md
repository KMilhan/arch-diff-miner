# Repository Guidelines

## Project Structure & Module Organization
- `main.py` – lightweight entry point used for smoke-testing interpreter wiring.
- `mine_adl_diffs.py` – core miner that walks a target repo, gathers `(intent, code_diffs, adl_diff)` tuples, and persists them to `training_dataset.json`.
- `training_dataset.json` – generated output; keep large snapshots out of git or prune before committing.
- `pyproject.toml` / `uv.lock` – Python 3.14 project definition and locked dependencies (currently `pygit2` + friends).
Keep helper scripts beside the miner so paths stay relative; place any future tests in `tests/` mirroring module names (`tests/test_mine_adl_diffs.py`).

## Task Tracking & Workflow
- Manage every change through GitHub Issues by using the `gh` CLI so the task history stays visible.
- Limit issue activity to `https://github.com/KMilhan/arch-diff-miner`; avoid opening or editing issues outside this repo for routine work.
- Reference the active issue number in your notes and close or update it with `gh issue comment|close` immediately after pushing the corresponding commit.
- Capture upstream/downstream dependencies in each issue description when they are known, and link related work with sub-issues so reviewers can see sequencing at a glance.

## Build, Test, and Development Commands
- Run everything through `uv` to stay on the locked Python 3.14 freethreaded (no-GIL) toolchain; skip ad-hoc `pip` or system `python` invocations, and install the interpreter with `uv python install 3.14+freethreaded` when needed.
- `uv sync` – installs the locked environment; prefer this over bare `pip` so everyone targets Python 3.14.
- `uv run python main.py` – ensures the entry point and logging stack still execute after edits.
- `uv run python mine_adl_diffs.py` – mines diffs using the `REPO_PATH` pointing at your local ADL source repo and refreshes `training_dataset.json`.
- `uv run pytest` – placeholder command once tests exist; fail fast if any dataset validators are added under `tests/`.
Set `REPO_PATH` and `ADL_FILE_PATH` via env vars when scripting (`REPO_PATH=~/code/spam uv run python mine_adl_diffs.py`).

## Coding Style & Naming Conventions
- Treat PEP 8/PEP 257 guidance as mandatory: 4-space indentation, type hints, and `UPPER_SNAKE_CASE` module-level constants (see `REPO_PATH`).
- Favor pure functions that accept explicit paths, and always wrap user messages with `logging` instead of `print` inside the miner.
- Keep docstrings in Google-style sentences describing inputs/outputs.

## Testing Guidelines
Create tests under `tests/` using `pytest`, naming files `test_*.py` and functions `test_<behavior>()`. When fixtures need repositories, mock GitPython objects rather than cloning live repos. Before committing, run `uv run pytest` and manually inspect the first tuple in `training_dataset.json` to confirm intents/diffs align with expectations.

## Commit & Pull Request Guidelines
- Keep each commit atomic; pair script edits with dataset snapshots only when they cannot be separated.
- Format commit messages as a colon-style emoji followed by an imperative title (e.g., `:memo: Document workflow`), then `git push` immediately.
- Because commits lack closing keywords, finish the related GitHub Issue by commenting with the commit link or by running `gh issue close` once the push succeeds.
- Pull requests should include: purpose summary, reproduction steps (`uv run ...`), sample diff tuple output, and mention of any external repo snapshots; attach screenshots only if you introduce UI/diagram artifacts.

## Security & Configuration Tips
Never point `REPO_PATH` at private repos without confirming access controls, since diffs may surface sensitive intent text. Avoid committing raw customer data; if anonymization is required, filter before writing `training_dataset.json`. Store long-running repo paths in `.envrc` or shell exports rather than hard-coding secrets inside scripts.
