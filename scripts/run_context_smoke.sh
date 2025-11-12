#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/arch-diff-smoke.XXXXXX")
KEEP_WORK=${ARCH_DIFF_SMOKE_KEEP:-}

cleanup() {
  if [[ -z "$KEEP_WORK" ]]; then
    rm -rf "$WORK_DIR"
  else
    echo "Leaving working files under $WORK_DIR"
  fi
}
trap cleanup EXIT

echo "🏗  Seeding deterministic fixture repo..."
SEED_ROOT="$WORK_DIR/fixture"
mkdir -p "$SEED_ROOT"
ARCH_DIFF_SMOKE_REPO_PATH=$(ARCH_DIFF_SMOKE_SEED_ROOT="$SEED_ROOT" uv run python - <<'PY'
import os
from pathlib import Path
from tests.fixtures.seed_context_repo import seed_context_repo

root = Path(os.environ["ARCH_DIFF_SMOKE_SEED_ROOT"])
repo = seed_context_repo(root)
print(repo.path)
PY
)

if [[ -z "$ARCH_DIFF_SMOKE_REPO_PATH" ]]; then
  echo "Failed to seed fixture repo" >&2
  exit 1
fi

OUTPUT_PATH="$WORK_DIR/dataset.jsonl"
echo "🚀 Mining dataset with context signals..."
uv run python -m arch_diff_miner mine \
  --repo "$ARCH_DIFF_SMOKE_REPO_PATH" \
  --adl-file adl.yaml \
  --code-exts .py \
  --context-days 90 \
  --output "$OUTPUT_PATH"

echo "📊 First record context_signals summary:"
ARCH_DIFF_SMOKE_DATASET="$OUTPUT_PATH" uv run python - <<'PY'
import json
import os
from pathlib import Path

dataset = Path(os.environ["ARCH_DIFF_SMOKE_DATASET"])
lines = [line for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
if not lines:
    raise SystemExit("dataset is empty")
record = json.loads(lines[0])
cs = record.get("context_signals", {})
summary = {
    "files_analyzed": cs.get("files_analyzed"),
    "aggregate_stats": cs.get("aggregate_stats"),
    "per_file_stats": cs.get("per_file_stats", [])[:1],
}
print(json.dumps(summary, indent=2))
PY

echo "📝 JSONL written to: $OUTPUT_PATH"
echo "(Set ARCH_DIFF_SMOKE_KEEP=1 to inspect the working directory.)"
