from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class FetchRequest:
    symbol: str
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("start must be on or before end")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")


@dataclass(frozen=True)
class FetchResult:
    symbol: str
    provider: str
    status: str
    rows: int
    cache_path: Path | None
    error: str | None = None
    coverage_issues: tuple[str, ...] = ()


class MarketDataProvider(Protocol):
    name: str

    def fetch(self, request: FetchRequest) -> pd.DataFrame:
        """Return daily data with canonical columns."""
