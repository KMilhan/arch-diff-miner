"""Arch Diff Miner package."""
from importlib.metadata import version

from .cli import (
    DEFAULT_ADL_FILE,
    DEFAULT_CODE_EXTENSIONS,
    DEFAULT_OUTPUT_PATH,
    DiffDataPair,
    app,
    main,
    mine,
    mine_repository,
)

__all__ = [
    "DEFAULT_ADL_FILE",
    "DEFAULT_CODE_EXTENSIONS",
    "DEFAULT_OUTPUT_PATH",
    "DiffDataPair",
    "app",
    "main",
    "mine",
    "mine_repository",
]

try:
    __version__ = version("arch-diff-miner")
except Exception:  # pragma: no cover - local dev fallback
    __version__ = "0.0.0"
