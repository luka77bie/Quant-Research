import sys
from datetime import date
from types import SimpleNamespace

import pytest

from narrative_regime.data.models import FetchRequest
from narrative_regime.data.providers import (
    TencentProvider,
    YahooProvider,
    _to_tencent_symbol,
    _to_yahoo_symbol,
    _year_chunks,
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


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [("510300", "sh510300"), ("159915", "sz159915"), ("sh510300", "sh510300")],
)
def test_to_tencent_symbol(symbol: str, expected: str) -> None:
    assert _to_tencent_symbol(symbol) == expected


def test_year_chunks_cover_range_without_overlap() -> None:
    chunks = _year_chunks(date(2018, 3, 1), date(2020, 2, 1))

    assert chunks == [
        (date(2018, 3, 1), date(2018, 12, 31)),
        (date(2019, 1, 1), date(2019, 12, 31)),
        (date(2020, 1, 1), date(2020, 2, 1)),
    ]


def test_tencent_provider_pages_and_normalizes() -> None:
    class FakeResponse:
        def __init__(self, rows: list[list[str]]) -> None:
            self.rows = rows

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "code": 0,
                "msg": "",
                "data": {"sh510300": {"qfqday": self.rows}},
            }

    class FakeSession:
        def __init__(self) -> None:
            self.parameters: list[str] = []

        def get(self, *_: object, **kwargs: object) -> FakeResponse:
            parameter = str(kwargs["params"]["param"])  # type: ignore[index]
            self.parameters.append(parameter)
            year = parameter.split(",")[2][:4]
            return FakeResponse(
                [[f"{year}-01-02", "3.0", "3.1", "3.2", "2.9", "100"]]
            )

    session = FakeSession()
    result = TencentProvider(session).fetch(
        FetchRequest("510300", date(2018, 1, 1), date(2021, 12, 31))
    )

    assert len(session.parameters) == 4
    assert result["date"].dt.year.tolist() == [2018, 2019, 2020, 2021]
    assert result["close"].tolist() == [3.1, 3.1, 3.1, 3.1]
    assert result["amount"].isna().all()


def test_tencent_provider_rejects_api_error() -> None:
    class ErrorResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"code": 7, "msg": "throttled", "data": {}}

    session = SimpleNamespace(get=lambda *args, **kwargs: ErrorResponse())

    with pytest.raises(RuntimeError, match="throttled"):
        TencentProvider(session).fetch(
            FetchRequest("510300", date(2024, 1, 1), date(2024, 1, 31))
        )


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
