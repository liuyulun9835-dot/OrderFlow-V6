"""Centralised random seeding helpers used across entrypoints."""

from __future__ import annotations

import os
import random
from typing import Optional

import numpy as np


def seed_all(seed: Optional[int] = None) -> int:
    """Seed Python, numpy and hash-based generators.

    Parameters
    ----------
    seed:
        Optional seed to use. When ``None`` a deterministic seed is derived
        from ``PYTHONHASHSEED`` or falls back to ``42``.

    Returns
    -------
    int
        The seed value applied to all generators.
    """

    if seed is None:
        env_seed = os.environ.get("PYTHONHASHSEED")
        if env_seed is not None and env_seed.isdigit():
            seed = int(env_seed)
        else:
            seed = 42

    random.seed(seed)
    np.random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    return seed

