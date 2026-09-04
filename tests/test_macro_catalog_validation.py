from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from narrative_regime.macro.catalog_validation import (
    MacroMonthlyArchive,
    _release_is_plausible,
    audit_monthly_catalog,
    monthly_cache_path,
)


def _catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "record_id": "nbs_pmi_2021_12",
                "source_family": "nbs_pmi",
                "period": "2021-12",
                "title": "2021年12月中国采购经理指数运行情况",
                "source_url": "https://www.stats.gov.cn/pmi.html",
                "discovery_status": "discovered",
                "timing_precision": "pending_article_validation",
            },
            {
                "record_id": "nbs_cpi_2021_12",
                "source_family": "nbs_cpi",
                "period": "2021-12",
                "title": "2021年12月份居民消费价格同比上涨1.5%",
                "source_url": "https://www.stats.gov.cn/cpi.html",
                "discovery_status": "discovered",
                "timing_precision": "pending_article_validation",
            },
            {
                "record_id": "pbc_m2_2021_12",
                "source_family": "pbc_m2",
                "period": "2021-12",
                "title": "2021年金融统计数据报告",
                "source_url": "https://www.pbc.gov.cn/m2.html",
                "discovery_status": "discovered",
                "timing_precision": "pending_article_validation",
            },
        ]
    )


def _pages() -> dict[str, bytes]:
    return {
        "nbs_pmi_2021_12": _html(
            "2021年12月中国采购经理指数运行情况",
            "2021/12/31 09:00 制造业采购经理指数（PMI）为50.3%",
        ),
        "nbs_cpi_2021_12": _html(
            "2021年12月份居民消费价格同比上涨1.5%",
            "2022/01/12 09:30 全国居民消费价格同比上涨1.5%",
        ),
        "pbc_m2_2021_12": _html(
            "2021年金融统计数据报告",
            (
                "文章来源：2022-01-12 16:00:27 "
                "广义货币(M2)余额238.29万亿元，同比增长9.0%"
            ),
        ),
    }


def _html(title: str, body: str) -> bytes:
    return (
        f'<html><meta charset="utf-8"><title>{title}</title>'
        f"<body>{title}{body}</body></html>"
    ).encode()


def _write_cache(root: Path, record_id: str, url: str, content: bytes) -> None:
    page = monthly_cache_path(root, record_id)
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_bytes(content)
    page.with_suffix(".meta.json").write_text(
        json.dumps(
            {
                "record_id": record_id,
                "source_url": url,
                "retrieved_at": "2026-01-01T00:00:00+00:00",
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        ),
        encoding="utf-8",
    )


class _Response:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _Session:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.calls = 0

    def get(self, *_args: object, **_kwargs: object) -> _Response:
        self.calls += 1
        return _Response(self.content)


def test_full_catalog_audit_passes_only_when_each_family_is_ready(
    tmp_path: Path,
) -> None:
    catalog = _catalog()
    for row in catalog.to_dict("records"):
        _write_cache(
            tmp_path,
            row["record_id"],
            row["source_url"],
            _pages()[row["record_id"]],
        )

    audit, summary = audit_monthly_catalog(tmp_path, catalog)

    assert audit["article_status"].eq("ready").all()
    assert summary["article_validation_gate"] == "pass"
    assert summary["etf_returns_read"] is False


def test_missing_cache_blocks_only_affected_record_and_family(tmp_path: Path) -> None:
    catalog = _catalog()
    for row in catalog.iloc[:2].to_dict("records"):
        _write_cache(
            tmp_path,
            row["record_id"],
            row["source_url"],
            _pages()[row["record_id"]],
        )

    audit, summary = audit_monthly_catalog(tmp_path, catalog)

    assert audit["article_status"].tolist() == ["ready", "ready", "blocked"]
    assert summary["article_validation_gate"] == "blocked"
    assert summary["source_families"]["pbc_m2"]["pages_cached"] == 0


def test_fetch_resumes_from_checksum_valid_cache(tmp_path: Path) -> None:
    catalog = _catalog().iloc[:1]
    row = catalog.iloc[0].to_dict()
    content = _pages()[row["record_id"]]
    session = _Session(content)
    archive = MacroMonthlyArchive(tmp_path, session=session, sleep=lambda _: None)

    first = archive.fetch_catalog(catalog)
    second = archive.fetch_catalog(catalog)

    assert first.iloc[0]["status"] == "downloaded"
    assert second.iloc[0]["status"] == "cached"
    assert session.calls == 1


def test_fetch_rejects_unknown_selective_record(tmp_path: Path) -> None:
    archive = MacroMonthlyArchive(tmp_path, sleep=lambda _: None)

    with pytest.raises(ValueError, match="unknown monthly macro record IDs"):
        archive.fetch_catalog(_catalog(), record_ids=["unknown"])


def test_release_window_allows_pre_holiday_month_end_release() -> None:
    assert _release_is_plausible(
        pd.Timestamp("2025-01-27T09:30:00+08:00"), "2025-01"
    )
