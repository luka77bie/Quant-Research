import sys
from datetime import date
from types import SimpleNamespace

import pytest

from narrative_regime.data.models import FetchRequest
from narrative_regime.data.providers import (
    YahooProvider,
    _to_yahoo_symbol,
    build_providers,
)


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [
        ("510300", "510300.SS"),
        ("159915", "159915.SZ"),
        ("510300.SS", "510300.SS"),
    ],
)
def test_to_yahoo_symbol(symbol: str, expected: str) -> None:
    assert _to_yahoo_symbol(symbol) == expected


def test_build_providers_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="unknown providers"):
        build_providers(["unknown"])


def test_yahoo_provider_propagates_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTicker:
        def history(self, **kwargs: object) -> object:
            assert kwargs["raise_errors"] is True
            raise RuntimeError("Too Many Requests")

    fake_yfinance = SimpleNamespace(Ticker=lambda _: FakeTicker())
    monkeypatch.setitem(sys.modules, "yfinance", fake_yfinance)

    with pytest.raises(RuntimeError, match="Too Many Requests"):
        YahooProvider().fetch(
            FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
        )
