from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from narrative_regime.cli import (
    _select_universe_symbols,
    main,
)


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


def test_macro_evidence_cli_writes_complete_artifacts(tmp_path: Path) -> None:
    content = (
        '<html><meta charset="utf-8"><body>2021/12/31 09:00'
        "制造业采购经理指数（PMI）为50.3%</body></html>"
    ).encode()
    raw = tmp_path / "data/raw/macro_release_pages"
    raw.mkdir(parents=True)
    page = raw / "pmi.html"
    page.write_bytes(content)
    page.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "record_id": "pmi",
                "source_url": "https://www.stats.gov.cn/pmi.html",
                "retrieved_at": "2026-01-01T00:00:00+00:00",
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ),
        encoding="utf-8",
    )
    catalog = tmp_path / "catalog.csv"
    pd.DataFrame(
        [{
            "record_id": "pmi",
            "dimension": "growth",
            "period": "2021-12",
            "release_at": "2021-12-31T09:00:00+08:00",
            "source_url": "https://www.stats.gov.cn/pmi.html",
            "strict_point_in_time_status": "provisional_no_snapshot",
        }]
    ).to_csv(catalog, index=False)
    evidence = tmp_path / "evidence.csv"
    pd.DataFrame(
        [{
            "record_id": "pmi",
            "expected_page_sha256": hashlib.sha256(content).hexdigest(),
            "release_evidence_text": "2021/12/31 09:00",
            "release_evidence_precision": "minute",
            "value_evidence_text": "制造业采购经理指数（PMI）为50.3%",
        }]
    ).to_csv(evidence, index=False)
    output = tmp_path / "outputs/evidence"

    result = main(
        [
            "macro-evidence-audit",
            "--catalog",
            str(catalog),
            "--evidence",
            str(evidence),
            "--root",
            str(tmp_path),
            "--output-dir",
            str(output),
        ]
    )

    assert result == 0
    assert (output / "macro_evidence_audit.csv").exists()
    assert (output / "macro_evidence_summary.json").exists()
    assert (output / "macro_evidence_run_manifest.json").exists()
