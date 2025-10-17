"""Compatibility layer for legacy preprocessing imports."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

_TARGET = 'data'

__all__: list[str] = []


def __getattr__(name: str) -> ModuleType:
    module = importlib.import_module(f'{_TARGET}.{name}')
    sys.modules[f'{__name__}.{name}'] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(__all__))
