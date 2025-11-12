#!/usr/bin/env bash
# Girokmoji release note helper. See README for usage.
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash scripts/release_notes.sh [FROM [TO]] | [FROM..TO]
Generate girokmoji release notes between two git refs.

Examples:
  bash scripts/release_notes.sh             # last tag -> HEAD (requires tags)
  bash scripts/release_notes.sh v0.3.0 HEAD
  bash scripts/release_notes.sh v0.3.0..HEAD

Environment overrides:
  PROJECT_NAME  Override project display name (defaults to repo basename)
  REPO_DIR      Path to repo (defaults to git rev-parse --show-toplevel)
  RELEASE_DATE  YYYY-MM-DD string (defaults to current UTC date)
USAGE
}

if [[ "$#" -gt 2 ]]; then
  usage >&2
  exit 1
fi

repo_dir=${REPO_DIR:-$(git rev-parse --show-toplevel)}
project_name=${PROJECT_NAME:-$(basename "$repo_dir")}
release_date=${RELEASE_DATE:-$(date -u +%F)}

if [[ -z "$project_name" || -z "$repo_dir" ]]; then
  echo "error: unable to resolve repo metadata" >&2
  exit 1
fi

from_ref=""
to_ref=""

if [[ $# -gt 0 ]]; then
  if [[ "$1" == *".."* && "$#" -eq 1 ]]; then
    from_ref=${1%%..*}
    to_ref=${1##*..}
  else
    from_ref=$1
    to_ref=${2:-}
  fi
fi

to_ref=${to_ref:-HEAD}

if [[ -z "$from_ref" ]]; then
  if ! from_ref=$(git -C "$repo_dir" describe --tags --abbrev=0 "$to_ref" 2>/dev/null); then
    echo "error: no git tags found; pass explicit FROM/TO or FROM..TO" >&2
    usage >&2
    exit 1
  fi
fi

if [[ -z "$from_ref" ]]; then
  echo "error: missing FROM ref" >&2
  exit 1
fi

if [[ -z "$to_ref" ]]; then
  echo "error: missing TO ref" >&2
  exit 1
fi

if ! git -C "$repo_dir" rev-parse "$from_ref" >/dev/null 2>&1; then
  echo "error: unknown FROM ref '$from_ref'" >&2
  exit 1
fi

if ! git -C "$repo_dir" rev-parse "$to_ref" >/dev/null 2>&1; then
  echo "error: unknown TO ref '$to_ref'" >&2
  exit 1
fi

echo "Generating girokmoji release notes for $project_name: $from_ref -> $to_ref" >&2
uvx --from "girokmoji@latest" \
  girokmoji generate "$project_name" "$release_date" "$repo_dir" "$from_ref" "$to_ref" --range auto
