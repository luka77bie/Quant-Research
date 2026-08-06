from __future__ import annotations

from datetime import timedelta

import pandas as pd

from narrative_regime.data.models import FetchRequest
from narrative_regime.data.validation import normalize_market_frame


class AkshareProvider:
    name = "akshare"

    def fetch(self, request: FetchRequest) -> pd.DataFrame:
        try:
            import akshare as ak
        except ImportError as exc:
            raise RuntimeError(
                "AKShare is not installed; install the 'akshare' extra"
            ) from exc

        raw = ak.fund_etf_hist_em(
            symbol=request.symbol,
            period="daily",
            start_date=request.start.strftime("%Y%m%d"),
            end_date=request.end.strftime("%Y%m%d"),
            adjust="qfq",
        )
        renamed = raw.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
            }
        )
        return normalize_market_frame(renamed)


class YahooProvider:
    name = "yahoo"

    def fetch(self, request: FetchRequest) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError(
                "yfinance is not installed; install the 'yahoo' extra"
            ) from exc

        ticker = _to_yahoo_symbol(request.symbol)
        # yfinance treats end as exclusive.
        exclusive_end = request.end + timedelta(days=1)
        raw = yf.Ticker(ticker).history(
            start=request.start.isoformat(),
            end=exclusive_end.isoformat(),
            auto_adjust=True,
            actions=False,
            timeout=30,
            raise_errors=True,
        )
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        renamed = raw.reset_index().rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        renamed["amount"] = pd.NA
        return normalize_market_frame(renamed)


def _to_yahoo_symbol(symbol: str) -> str:
    if symbol.endswith((".SS", ".SZ")):
        return symbol
    if not symbol.isdigit() or len(symbol) != 6:
        raise ValueError(f"cannot map symbol to Yahoo Finance: {symbol}")
    suffix = ".SS" if symbol.startswith(("5", "6")) else ".SZ"
    return f"{symbol}{suffix}"


def build_providers(names: list[str]) -> list[AkshareProvider | YahooProvider]:
    registry = {
        "akshare": AkshareProvider,
        "yahoo": YahooProvider,
    }
    unknown = sorted(set(names) - set(registry))
    if unknown:
        raise ValueError(f"unknown providers: {', '.join(unknown)}")
    return [registry[name]() for name in names]
