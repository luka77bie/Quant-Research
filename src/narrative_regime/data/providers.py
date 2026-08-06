from __future__ import annotations

from datetime import date, timedelta
from typing import Any

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


class TencentProvider:
    name = "tencent"
    endpoint = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

    def __init__(self, session: Any | None = None) -> None:
        self._session = session

    def fetch(self, request: FetchRequest) -> pd.DataFrame:
        if self._session is None:
            try:
                import requests
            except ImportError as exc:
                raise RuntimeError(
                    "requests is not installed; install the 'tencent' extra"
                ) from exc
            session = requests.Session()
        else:
            session = self._session

        market_symbol = _to_tencent_symbol(request.symbol)
        frames = [
            self._fetch_chunk(session, market_symbol, start, end)
            for start, end in _year_chunks(request.start, request.end)
        ]
        usable = [frame for frame in frames if not frame.empty]
        if not usable:
            raise ValueError(f"Tencent returned no rows for {request.symbol}")
        return normalize_market_frame(pd.concat(usable, ignore_index=True))

    def _fetch_chunk(
        self,
        session: Any,
        market_symbol: str,
        start: date,
        end: date,
    ) -> pd.DataFrame:
        parameter = (
            f"{market_symbol},day,{start.isoformat()},{end.isoformat()},640,qfq"
        )
        response = session.get(
            self.endpoint,
            params={"param": parameter},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            raise RuntimeError(
                f"Tencent API error {payload.get('code')}: {payload.get('msg', '')}"
            )
        security_data = payload.get("data", {}).get(market_symbol)
        if not isinstance(security_data, dict):
            raise ValueError(f"Tencent response missing {market_symbol}")
        rows = security_data.get("qfqday") or security_data.get("day") or []
        if not rows:
            return pd.DataFrame()
        if any(len(row) < 6 for row in rows):
            raise ValueError("Tencent returned an unexpected daily row shape")
        return pd.DataFrame(
            [row[:6] for row in rows],
            columns=["date", "open", "close", "high", "low", "volume"],
        ).assign(amount=pd.NA)


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


def _to_tencent_symbol(symbol: str) -> str:
    if symbol.startswith(("sh", "sz")) and len(symbol) == 8:
        return symbol
    if not symbol.isdigit() or len(symbol) != 6:
        raise ValueError(f"cannot map symbol to Tencent: {symbol}")
    prefix = "sh" if symbol.startswith(("5", "6")) else "sz"
    return f"{prefix}{symbol}"


def _year_chunks(start: date, end: date) -> list[tuple[date, date]]:
    chunks = []
    chunk_start = start
    while chunk_start <= end:
        chunk_end = min(date(chunk_start.year, 12, 31), end)
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end + timedelta(days=1)
    return chunks


def build_providers(
    names: list[str],
) -> list[AkshareProvider | TencentProvider | YahooProvider]:
    registry = {
        "akshare": AkshareProvider,
        "tencent": TencentProvider,
        "yahoo": YahooProvider,
    }
    unknown = sorted(set(names) - set(registry))
    if unknown:
        raise ValueError(f"unknown providers: {', '.join(unknown)}")
    return [registry[name]() for name in names]
