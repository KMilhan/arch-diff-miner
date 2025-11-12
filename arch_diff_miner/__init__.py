"""Arch Diff Miner package."""
from importlib.metadata import version

from .cli import (
    DEFAULT_ADL_FILE,
    DEFAULT_CODE_EXTENSIONS,
    DEFAULT_CONTEXT_DAYS,
    DEFAULT_OUTPUT_PATH,
    MineConfig,
    TrainingSample,
    app,
    main,
    mine,
    mine_repository,
)
from .context import collect_context_stats

__all__ = [
    "DEFAULT_ADL_FILE",
    "DEFAULT_CODE_EXTENSIONS",
    "DEFAULT_CONTEXT_DAYS",
    "DEFAULT_OUTPUT_PATH",
    "MineConfig",
    "TrainingSample",
    "app",
    "collect_context_stats",
    "main",
    "mine",
    "mine_repository",
]

try:
    __version__ = version("arch-diff-miner")
except Exception:  # pragma: no cover - local dev fallback
    __version__ = "0.0.0"
