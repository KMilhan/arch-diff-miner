"""Verify JSONL emission includes context_signals per v2.0 schema."""
from __future__ import annotations

import json
from pathlib import Path

from arch_diff_miner.cli import MineConfig, mine_repository
from arch_diff_miner.jsonl_writer import write_jsonl_dataset
from tests.fixtures.seed_context_repo import seed_context_repo


def _mine_single_record(tmp_path: Path) -> dict[str, object]:
    repo_info = seed_context_repo(tmp_path)
    config = MineConfig(
        repo_path=repo_info.path,
        adl_file="adl.yaml",
        code_extensions=(".py",),
        context_days=30,
    )
    samples = mine_repository(config)
    assert samples, "seeded repo should yield at least one training pair"

    output_path = tmp_path / "dataset.jsonl"
    write_jsonl_dataset(samples, output_path)
    with output_path.open(encoding="utf-8") as handle:
        line = handle.readline().strip()
    assert line, "JSONL output should contain at least one record"
    return json.loads(line)


def test_context_signals_matches_golden(tmp_path: Path) -> None:
    record = _mine_single_record(tmp_path)
    context_signals = record.get("context_signals")
    assert context_signals, "context_signals block must be present in v2.0 output"

    golden_path = Path(__file__).parent / "golden" / "context_signals_seed_repo.json"
    golden = json.loads(golden_path.read_text(encoding="utf-8"))

    # Dynamic hash only needs to be a string; everything else should match the schema.
    assert isinstance(context_signals.get("analysis_parent_hash"), str)
    assert context_signals.get("analysis_timespan_days") == golden["analysis_timespan_days"]
    assert context_signals.get("files_analyzed") == golden["files_analyzed"]
    assert context_signals.get("aggregate_stats") == golden["aggregate_stats"]
    assert context_signals.get("per_file_stats") == golden["per_file_stats"]

    assert record.get("metadata", {}).get("dataset_version") == "adl-diff-miner-schema-v2.0"
    assert "context_stats" not in record
