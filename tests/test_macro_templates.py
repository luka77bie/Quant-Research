from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from narrative_regime.macro.templates import (
    audit_template_drift,
    extract_macro_release,
)


def _html(timestamp: str, body: str) -> bytes:
    return f'<html><meta charset="utf-8"><body>{timestamp}{body}</body></html>'.encode()


def test_extracts_nbs_pmi_release() -> None:
    result = extract_macro_release(
        _html("2021/12/31 09:00", "制造业采购经理指数（PMI）为50.3%"),
        source_family="nbs_pmi",
    )

    assert result.release_at == pd.Timestamp("2021-12-31 01:00:00Z")
    assert result.value == 50.3


def test_extracts_negative_nbs_cpi_release() -> None:
    result = extract_macro_release(
        _html("2025/01/09 09:30", "全国居民消费价格同比下降0.2%"),
        source_family="nbs_cpi",
    )

    assert result.value == -0.2


def test_extracts_flat_nbs_cpi_release() -> None:
    result = extract_macro_release(
        _html("2025/01/09 09:30", "全国居民消费价格同比持平"),
        source_family="nbs_cpi",
    )

    assert result.value == 0.0


def test_extracts_pbc_m2_release() -> None:
    result = extract_macro_release(
        _html(
            "文章来源：2021-06-10 16:00:27",
            "5月末，广义货币(M2)余额227.55万亿元，同比增长8.3%",
        ),
        source_family="pbc_m2",
    )

    assert result.release_at == pd.Timestamp("2021-06-10 08:00:27Z")
    assert result.value == 8.3


def test_rejects_unknown_source_family() -> None:
    with pytest.raises(ValueError, match="unsupported macro source family"):
        extract_macro_release(b"<html></html>", source_family="unknown")


def test_template_gate_requires_three_ready_anchors_per_family(tmp_path: Path) -> None:
    rows = []
    cache = tmp_path / "data/raw/macro_release_pages"
    cache.mkdir(parents=True)
    specs = {
        "nbs_pmi": ("2021/12/31 09:00", "制造业采购经理指数（PMI）为50.3%", 50.3),
        "nbs_cpi": ("2022/01/12 09:30", "全国居民消费价格同比上涨1.5%", 1.5),
        "pbc_m2": (
            "文章来源：2021-06-10 16:00:27",
            "5月末，广义货币(M2)余额227.55万亿元，同比增长8.3%",
            8.3,
        ),
    }
    releases = {
        "nbs_pmi": "2021-12-31T09:00:00+08:00",
        "nbs_cpi": "2022-01-12T09:30:00+08:00",
        "pbc_m2": "2021-06-10T16:00:27+08:00",
    }
    for family, (timestamp, body, value) in specs.items():
        for anchor in range(3):
            record_id = f"{family}_{anchor}"
            (cache / f"{record_id}.html").write_bytes(_html(timestamp, body))
            rows.append(
                {
                    "record_id": record_id,
                    "source_family": family,
                    "anchor_year": 2018 + anchor,
                    "release_at": releases[family],
                    "value": value,
                }
            )

    _, summary = audit_template_drift(tmp_path, pd.DataFrame(rows))

    assert summary["template_drift_gate"] == "pass"
