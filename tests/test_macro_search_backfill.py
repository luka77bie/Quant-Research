from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from narrative_regime.macro.search_backfill import (
    NbsSearchBackfill,
    apply_reviewed_seeds,
    build_search_query,
    parse_search_matches,
)


def _result(title: str, url: str) -> dict[str, object]:
    return {"data": {"titleO": title, "url": url, "docDate": "2018-01-31"}}


def _catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "record_id": "nbs_pmi_2018_01",
                "source_family": "nbs_pmi",
                "period": "2018-01",
                "title": "",
                "source_url": "",
                "index_url": "",
                "candidate_count": "0",
                "discovery_status": "missing",
            },
            {
                "record_id": "nbs_cpi_2018_01",
                "source_family": "nbs_cpi",
                "period": "2018-01",
                "title": "existing",
                "source_url": "https://www.stats.gov.cn/existing.html",
                "index_url": "https://www.stats.gov.cn/index.html",
                "candidate_count": "1",
                "discovery_status": "discovered",
            },
            {
                "record_id": "pbc_m2_2018_01",
                "source_family": "pbc_m2",
                "period": "2018-01",
                "title": "m2",
                "source_url": "https://www.pbc.gov.cn/m2.html",
                "index_url": "https://www.pbc.gov.cn/index.html",
                "candidate_count": "1",
                "discovery_status": "discovered",
            },
        ]
    )


def test_builds_period_specific_search_queries() -> None:
    assert (
        build_search_query("nbs_pmi", "2018-01")
        == "2018年1月中国采购经理指数运行情况"
    )
    assert build_search_query("nbs_cpi", "2018-01") == "2018年1月份居民消费价格"
    with pytest.raises(ValueError, match="unsupported"):
        build_search_query("pbc_m2", "2018-01")


def test_filters_to_exact_official_release_match() -> None:
    payload = {
        "resultDocs": [
            _result(
                "2018年1月<em>中国采购经理指数</em>运行情况",
                "https://www.stats.gov.cn/sj/zxfb/202302/release.html",
            ),
            _result(
                "2018年1月中国采购经理指数运行情况",
                "https://weibo.com/not-official",
            ),
            _result(
                "2018年2月中国采购经理指数运行情况",
                "https://www.stats.gov.cn/sj/zxfb/202302/wrong-period.html",
            ),
            _result(
                "2018年1月中国采购经理指数运行情况",
                "https://www.stats.gov.cn/sj/sjjd/202302/interpretation.html",
            ),
        ]
    }

    matches = parse_search_matches(
        payload, source_family="nbs_pmi", period="2018-01"
    )

    assert matches == [
        {
            "title": "2018年1月中国采购经理指数运行情况",
            "source_url": "https://www.stats.gov.cn/sj/zxfb/202302/release.html",
        }
    ]


class _Backfill(NbsSearchBackfill):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__(attempts=1, max_pages=1)
        self.payload = payload
        self.queries: list[str] = []

    def _search(self, query: str, *, page: int) -> dict[str, object]:
        self.queries.append(query)
        assert page == 1
        return self.payload


def test_backfills_only_missing_nbs_rows(tmp_path: Path) -> None:
    payload = {
        "ok": True,
        "resultDocs": [
            _result(
                "2018年1月中国采购经理指数运行情况",
                "https://www.stats.gov.cn/sj/zxfb/202302/pmi.html",
            )
        ],
    }
    backfill = _Backfill(payload)

    updated, audit, summary = backfill.backfill(
        _catalog(), response_dir=tmp_path / "responses"
    )

    target = updated[updated["record_id"].eq("nbs_pmi_2018_01")].iloc[0]
    assert target["discovery_status"] == "backfilled"
    assert target["source_url"].endswith("pmi.html")
    assert target["discovery_method"] == "nbs_official_title_search"
    assert len(audit) == 1
    assert audit.iloc[0]["backfill_status"] == "backfilled"
    assert summary["etf_returns_read"] is False
    assert backfill.queries == ["2018年1月中国采购经理指数运行情况"]


def test_duplicate_exact_matches_remain_blocked(tmp_path: Path) -> None:
    payload = {
        "ok": True,
        "resultDocs": [
            _result(
                "2018年1月中国采购经理指数运行情况",
                "https://www.stats.gov.cn/sj/zxfb/202302/a.html",
            ),
            _result(
                "2018年1月中国采购经理指数运行情况",
                "https://www.stats.gov.cn/sj/zxfb/202302/b.html",
            ),
        ],
    }

    updated, audit, _ = _Backfill(payload).backfill(
        _catalog(), response_dir=tmp_path / "responses"
    )

    target = updated[updated["record_id"].eq("nbs_pmi_2018_01")].iloc[0]
    assert target["discovery_status"] == "duplicate"
    assert int(target["candidate_count"]) == 2
    assert audit.iloc[0]["backfill_status"] == "duplicate"


def test_completed_catalog_is_a_no_op(tmp_path: Path) -> None:
    catalog = _catalog()
    catalog.loc[
        catalog["record_id"].eq("nbs_pmi_2018_01"), "discovery_status"
    ] = "backfilled"

    updated, audit, summary = _Backfill({}).backfill(
        catalog, response_dir=tmp_path / "responses"
    )

    assert updated["source_url"].tolist() == catalog["source_url"].tolist()
    assert audit.empty
    assert summary["target_records"] == 0


def test_applies_reviewed_seed_pending_article_validation() -> None:
    catalog = _catalog()
    seeds = pd.DataFrame(
        [
            {
                "record_id": "nbs_pmi_2018_01",
                "title": "2018年1月中国采购经理指数运行情况",
                "source_url": "https://www.stats.gov.cn/sj/zxfb/202302/pmi.html",
                "discovery_method": "reviewed_search",
                "timing_precision": "minute",
            }
        ]
    )

    updated, audit, summary = apply_reviewed_seeds(catalog, seeds)

    target = updated[updated["record_id"].eq("nbs_pmi_2018_01")].iloc[0]
    assert target["discovery_status"] == "seeded_pending_article_validation"
    assert target["index_url"] == ""
    assert target["discovery_method"] == "reviewed_search"
    assert target["timing_precision"] == "minute"
    assert audit.iloc[0]["seed_status"] == "accepted"
    assert summary["accepted_seeds"] == 1


def test_rejects_seed_with_wrong_period() -> None:
    seeds = pd.DataFrame(
        [
            {
                "record_id": "nbs_pmi_2018_01",
                "title": "2018年2月中国采购经理指数运行情况",
                "source_url": "https://www.stats.gov.cn/sj/zxfb/202302/pmi.html",
                "discovery_method": "reviewed_search",
                "timing_precision": "minute",
            }
        ]
    )

    _, audit, summary = apply_reviewed_seeds(_catalog(), seeds)

    assert audit.iloc[0]["seed_status"] == "blocked"
    assert summary["source_catalog_gate"] == "blocked"
