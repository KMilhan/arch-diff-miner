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
- Stream JSONL to stdout: `uv run python -m arch_diff_miner mine --repo "$REPO_PATH" --adl-file <adl.yaml> --code-exts .py .rs`.
- Write JSONL to disk: `uv run python -m arch_diff_miner mine --repo "$REPO_PATH" --adl-file <adl.yaml> --code-exts .py --code-exts .rs --output training_dataset.jsonl`.
- `uv run python -m arch_diff_miner --help` – inspect the Typer CLI and available options.
- `uv run pytest` – placeholder command once tests exist; fail fast if any dataset validators are added under `tests/`.

## Coding Style & Naming Conventions
- Treat PEP 8, 257, 621, 517, 518 guidance as mandatory
- Keep docstrings in Google-style sentences describing inputs/outputs.

## Testing Guidelines
Create tests under `tests/` using `pytest`, naming files `test_*.py` and functions `test_<behavior>()`. 

## Commit & Pull Request Guidelines
- Keep each commit atomic; pair code edits with dataset snapshots only when they cannot be separated.
- **Subject format:** `:<emoji>:` + imperative verb phrase. Examples: `:sparkles: Stream JSONL output`, `:broom: Ignore release artifacts`, `:memo: Clarify CLI defaults`. Always push right after committing.
- Include a short body describing *why* and *what* (reference issue numbers or dataset filenames when helpful).
- Handy template: ``git commit -m ":sparkles: Implement X" -m "why: …; what: …" && git push``
- Because commits lack closing keywords, finish the related GitHub Issue by commenting with the commit link or by running `gh issue close` once the push succeeds.
- Pull requests should include: purpose summary, reproduction steps (`uv run ...`), sample diff tuple output, and mention of any external repo snapshots; attach screenshots only if you introduce UI/diagram artifacts.

## Issue-Driven Workflow Loop
1. **Pick an issue** – Prefer open `status:ready` issues (then `priority:high`), scoped to `https://github.com/KMilhan/arch-diff-miner`.
2. **Start work** – `gh issue edit <n> --add-label "status:in-progress" --remove-label "status:ready"` and comment with a brief plan.
3. **Implement** – Make a single logical change, commit with the `:<emoji>:` format + explanatory body, push immediately.
4. **Update the issue** – Comment with the commit SHA/URL, then close it (`gh issue close <n> -c "Done in <sha>"`).
5. **Repeat as needed** – If more work remains, pick the next ready issue; otherwise stop.

> Tip: If you need a dry run, say “preview start” in notes and list the intended issue/steps before editing labels.
