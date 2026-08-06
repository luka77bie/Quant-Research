import pytest

from narrative_regime.data.providers import _to_yahoo_symbol, build_providers


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

