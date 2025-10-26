#!/usr/bin/env python3
"""Initialise standard data directory structure."""

from __future__ import annotations

from pathlib import Path

DIRECTORIES = [
    Path("data/raw/atas/bar"),
    Path("data/raw/atas/tick"),
    Path("data/exchange/example_symbol"),
    Path("data/meta"),
    Path("data/processed"),
    Path("logs"),
    Path("results"),
]


def ensure_gitkeep(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    gitkeep = directory / ".gitkeep"
    gitkeep.touch()


def main() -> None:
    for directory in DIRECTORIES:
        ensure_gitkeep(directory)
    print("Initialized:", " ".join(str(d) for d in DIRECTORIES))


if __name__ == "__main__":
    main()
