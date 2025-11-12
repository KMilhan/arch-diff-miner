# Repository Guidelines

## Project Structure & Module Organization
- `main.py` – lightweight entry point used for smoke-testing interpreter wiring.
- `mine_adl_diffs.py` – core miner that walks a target repo, gathers `(intent, code_diffs, adl_diff)` tuples, and persists them to `training_dataset.json`.
- `training_dataset.json` – generated output; keep large snapshots out of git or prune before committing.
- `pyproject.toml` / `uv.lock` – Python 3.14 project definition and locked dependencies (currently only `gitpython`).
Keep helper scripts beside the miner so paths stay relative; place any future tests in `tests/` mirroring module names (`tests/test_mine_adl_diffs.py`).

## Build, Test, and Development Commands
- `uv sync` – installs the locked environment; prefer this over bare `pip` so everyone targets Python 3.14.
- `uv run python main.py` – ensures the entry point and logging stack still execute after edits.
- `uv run python mine_adl_diffs.py` – mines diffs using the `REPO_PATH` pointing at your local ADL source repo and refreshes `training_dataset.json`.
- `uv run pytest` – placeholder command once tests exist; fail fast if any dataset validators are added under `tests/`.
Set `REPO_PATH` and `ADL_FILE_PATH` via env vars when scripting (`REPO_PATH=~/code/spam uv run python mine_adl_diffs.py`).

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indentation, type hints, and module-level constants in `UPPER_SNAKE_CASE` (see `REPO_PATH`). Favor pure functions that accept explicit paths, and always wrap user messages with `logging` instead of `print` inside the miner. Keep docstrings in Google-style sentences describing inputs/outputs.

## Testing Guidelines
Create tests under `tests/` using `pytest`, naming files `test_*.py` and functions `test_<behavior>()`. When fixtures need repositories, mock GitPython objects rather than cloning live repos. Before committing, run `uv run pytest` and manually inspect the first tuple in `training_dataset.json` to confirm intents/diffs align with expectations.

## Commit & Pull Request Guidelines
The repo currently lacks history, so adopt Conventional Commits (`feat:`, `fix:`, `chore:`) to ease changelog generation. Keep commits focused (script edit + dataset sample at most). Pull requests should include: purpose summary, reproduction steps (`uv run ...`), sample diff tuple output, and mention of any external repo snapshots; attach screenshots only if you introduce UI/diagram artifacts.

## Security & Configuration Tips
Never point `REPO_PATH` at private repos without confirming access controls, since diffs may surface sensitive intent text. Avoid committing raw customer data; if anonymization is required, filter before writing `training_dataset.json`. Store long-running repo paths in `.envrc` or shell exports rather than hard-coding secrets inside scripts.
