"""Compatibility layer exposing QA validation modules under the legacy path."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType

_TARGET = 'QA_validation'

__all__: list[str] = []


def __getattr__(name: str) -> ModuleType:
    module = importlib.import_module(f'{_TARGET}.{name}')
    sys.modules[f'{__name__}.{name}'] = module
    return module


def __dir__() -> list[str]:
    return sorted(set(__all__))
