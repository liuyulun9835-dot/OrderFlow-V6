"""Helper utilities for accessing vendored legacy modules."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional


@lru_cache(maxsize=1)
def _project_root() -> Optional[Path]:
    """Return the repository root that contains the third_party directory."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "third_party").exists():
            return parent
    return None


def ensure_v6_legacy() -> Optional[Path]:
    """Ensure the vendored ``v6_legacy`` package is importable.

    The helper adds the package directory to ``sys.path`` if it is not already
    present and returns the resolved path so callers can reuse it in logs.
    """

    root = _project_root()
    if root is None:
        return None

    legacy_dir = root / "third_party" / "v6_legacy"
    if legacy_dir.exists():
        legacy_path = str(legacy_dir)
        if legacy_path not in sys.path:
            sys.path.insert(0, legacy_path)
        return legacy_dir
    return None


__all__ = ["ensure_v6_legacy"]
