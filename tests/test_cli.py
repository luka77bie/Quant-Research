from __future__ import annotations

import pandas as pd
import pytest

from narrative_regime.cli import _select_universe_symbols


def _universe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["510300", "510500", "512100"],
            "available_from": ["2012-05-28", "2013-03-15", "2016-11-04"],
        }
    )


def test_select_symbols_preserves_universe_order() -> None:
    selected = _select_universe_symbols(_universe(), "512100, 510300")

    assert selected["symbol"].tolist() == ["510300", "512100"]


@pytest.mark.parametrize("argument", ["", "  ", ","])
def test_select_symbols_rejects_empty_argument(argument: str) -> None:
    with pytest.raises(ValueError, match="at least one"):
        _select_universe_symbols(_universe(), argument)


def test_select_symbols_rejects_unknown_symbol() -> None:
    with pytest.raises(ValueError, match="999999"):
        _select_universe_symbols(_universe(), "510300,999999")


def test_select_symbols_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        _select_universe_symbols(_universe(), "510300,510300")
