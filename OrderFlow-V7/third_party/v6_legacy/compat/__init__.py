"""Compat layer for transitional import paths."""
# flake8: noqa
from __future__ import annotations

# Deprecated import aliases — keep for 2 minor versions.
try:
    from data.alignment.merge_to_features import *  # noqa: F401,F403
except Exception:  # pragma: no cover
    pass

try:
    from data.alignment.sessions import *  # noqa: F401,F403
except Exception:  # pragma: no cover
    pass

try:
    from data.preprocessing.fetch_kline import *  # noqa: F401,F403
except Exception:  # pragma: no cover
    pass

try:
    from data.calibration.calibration import *  # noqa: F401,F403
except Exception:  # pragma: no cover
    pass

try:
    from decision.engine import *  # noqa: F401,F403
except Exception:  # pragma: no cover
    pass
