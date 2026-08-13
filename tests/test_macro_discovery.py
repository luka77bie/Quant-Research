from __future__ import annotations

import json

import pytest

from narrative_regime.macro.discovery import (
    IndexPage,
    build_coverage_catalog,
    classify_release_title,
    extract_page_count,
    index_page_url,
    parse_index_page,
)


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("2021年8月中国采购经理指数运行情况", ("nbs_pmi", "2021-08")),
        ("2018年1月份居民消费价格同比上涨1.5%", ("nbs_cpi", "2018-01")),
        ("2025年2月金融统计数据报告", ("pbc_m2", "2025-02")),
        ("2025年一季度金融统计数据报告", ("pbc_m2", "2025-03")),
        ("2025年上半年金融统计数据报告", ("pbc_m2", "2025-06")),
        ("2025年前三季度金融统计数据报告", ("pbc_m2", "2025-09")),
        ("2025年金融统计数据报告", ("pbc_m2", "2025-12")),
    ],
)
def test_classifies_official_release_titles(
    title: str, expected: tuple[str, str]
) -> None:
    assert classify_release_title(title) == expected


def test_rejects_related_but_wrong_pbc_title() -> None:
    assert classify_release_title("2025年2月社会融资规模增量统计数据报告") is None


def test_extracts_each_official_pagination_contract() -> None:
    assert extract_page_count(b"createPageHTML(67, 6,", source="nbs") == 67
    assert extract_page_count(b'totalpage="38"', source="pbc") == 38
    assert (
        index_page_url("https://www.stats.gov.cn/sj/zxfb/index.html", "nbs", 2)
        == "https://www.stats.gov.cn/sj/zxfb/index_1.html"
    )
    assert (
        index_page_url(
            "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html",
            "pbc",
            2,
        )
        == "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/11871-2.html"
    )


def test_nbs_responsive_links_are_deduplicated() -> None:
    link = "./202302/t20230203_1899845.html"
    title = "2018年1月份居民消费价格同比上涨1.5%"
    html = "".join(f'<a href="{link}" title="{title}">{title}</a>' for _ in range(3))
    page = IndexPage(
        "nbs", 1, "https://www.stats.gov.cn/sj/zxfb/index.html", html.encode()
    )

    records = parse_index_page(page)

    assert len(records) == 1
    assert records[0]["period"] == "2018-01"
    assert records[0]["source_url"].endswith("/sj/zxfb/202302/t20230203_1899845.html")


def test_coverage_gate_requires_95_percent_for_every_family() -> None:
    links = []
    for month in range(1, 13):
        links.extend(
            [
                f'<a href="pmi-{month}.html" '
                f'title="2025年{month}月中国采购经理指数运行情况">x</a>',
                f'<a href="cpi-{month}.html" '
                f'title="2025年{month}月份居民消费价格同比持平">x</a>',
            ]
        )
        m2_title = (
            "2025年金融统计数据报告"
            if month == 12
            else f"2025年{month}月金融统计数据报告"
        )
        links.append(f'<a href="m2-{month}.html" title="{m2_title}">x</a>')
    page = IndexPage(
        "nbs", 1, "https://www.stats.gov.cn/index.html", "".join(links).encode()
    )

    catalog, candidates, summary = build_coverage_catalog(
        [page], start="2025-01", end="2025-12"
    )

    assert len(catalog) == 36
    assert len(candidates) == 36
    assert summary["catalog_discovery_gate"] == "pass"
    assert summary["source_families"]["pbc_m2"]["coverage"] == 1.0


def test_duplicate_period_blocks_gate() -> None:
    html = (
        '<a href="a.html" title="2025年1月中国采购经理指数运行情况">a</a>'
        '<a href="b.html" title="2025年1月中国采购经理指数运行情况">b</a>'
    )
    page = IndexPage("nbs", 1, "https://www.stats.gov.cn/index.html", html.encode())

    catalog, _, summary = build_coverage_catalog([page], start="2025-01", end="2025-01")

    pmi = catalog[catalog["source_family"].eq("nbs_pmi")].iloc[0]
    assert pmi["discovery_status"] == "duplicate"
    assert pmi["candidate_count"] == 2
    assert summary["catalog_discovery_gate"] == "blocked"
    json.dumps(summary)


def test_failed_index_page_is_explicit_and_blocks_gate() -> None:
    page = IndexPage(
        "nbs", 2, "https://www.stats.gov.cn/index_1.html", b"", "timeout"
    )

    _, _, summary = build_coverage_catalog([page], start="2025-01", end="2025-01")

    assert summary["index_pages_failed"] == 1
    assert summary["failed_index_urls"] == [page.url]
    assert summary["catalog_discovery_gate"] == "blocked"
