"""Utilities to maintain an error ledger for ATAS exports."""

from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

LEDGER_PATH = Path("data/raw/atas/error_ledger.csv")
LEDGER_FIELDS = [
    "event_type",
    "start_utc",
    "end_utc",
    "batch_id",
    "details",
    "file_hash",
]


@dataclass
class LedgerEntry:
    """Single ledger record capturing data continuity incidents."""

    event_type: str
    start_utc: datetime
    end_utc: datetime
    batch_id: str
    details: str
    file_hash: str = ""

    def as_row(self) -> dict[str, str]:
        record = asdict(self)
        record["start_utc"] = self.start_utc.replace(microsecond=0).isoformat()
        record["end_utc"] = self.end_utc.replace(microsecond=0).isoformat()
        return record


def append_entries(entries: Iterable[LedgerEntry], ledger_path: Optional[Path] = None) -> Path:
    """Append entries to the ledger, creating the file when required."""

    path = ledger_path or LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        if not exists:
            writer.writeheader()
        for entry in entries:
            writer.writerow(entry.as_row())
    return path


__all__ = ["LedgerEntry", "append_entries", "LEDGER_PATH"]

