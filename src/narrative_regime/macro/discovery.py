from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

DEFAULT_INDEX_URLS = {
    "nbs": "https://www.stats.gov.cn/sj/zxfb/index.html",
    "pbc": "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html",
}
SOURCE_FAMILIES = ("nbs_pmi", "nbs_cpi", "pbc_m2")


@dataclass(frozen=True)
class IndexPage:
    source: str
    page_number: int
    url: str
    content: bytes
    error: str = ""


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._title = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        values = dict(attrs)
        self._href = values.get("href")
        self._title = values.get("title") or ""
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._href is None:
            return
        title = self._title.strip() or " ".join(self._text).strip()
        self.links.append((self._href, re.sub(r"\s+", "", title)))
        self._href = None
        self._title = ""
        self._text = []


class MacroCatalogDiscovery:
    """Enumerate official index pages without reading market outcomes."""

    def __init__(
        self,
        *,
        attempts: int = 3,
        base_delay_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        session: requests.Session | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self.attempts = attempts
        self.base_delay_seconds = base_delay_seconds
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep
        self.session = session or requests.Session()

    def fetch_indexes(self, index_urls: dict[str, str]) -> list[IndexPage]:
        pages: list[IndexPage] = []
        for source in ("nbs", "pbc"):
            seed_url = index_urls[source]
            seed = self._fetch(seed_url)
            page_count = extract_page_count(seed, source=source)
            pages.append(IndexPage(source, 1, seed_url, seed))
            for page_number in range(2, page_count + 1):
                url = index_page_url(seed_url, source, page_number)
                try:
                    content = self._fetch(url)
                    pages.append(IndexPage(source, page_number, url, content))
                except RuntimeError as exc:
                    pages.append(IndexPage(source, page_number, url, b"", str(exc)))
        return pages

    def _fetch(self, url: str) -> bytes:
        errors: list[str] = []
        headers = {"User-Agent": "Luka-Quant-Research-Lab/0.1 catalog-discovery"}
        for attempt in range(1, self.attempts + 1):
            try:
                response = self.session.get(
                    url, timeout=self.timeout_seconds, headers=headers
                )
                response.raise_for_status()
                if b"<html" not in response.content[:4096].lower():
                    raise ValueError("response does not contain an HTML document")
                return response.content
            except Exception as exc:  # page-level failure remains explicit
                errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
                if attempt < self.attempts:
                    self.sleep(self.base_delay_seconds * 2 ** (attempt - 1))
        raise RuntimeError(f"index fetch failed for {url}: {' | '.join(errors)}")


def extract_page_count(content: bytes, *, source: str) -> int:
    text = content.decode("utf-8", errors="replace")
    if source == "nbs":
        match = re.search(r"createPageHTML\((\d+),", text)
    elif source == "pbc":
        match = re.search(r'totalpage="(\d+)"', text)
    else:
        raise ValueError(f"unsupported index source: {source}")
    if not match:
        raise ValueError(f"page count not found for {source}")
    return int(match.group(1))


def index_page_url(seed_url: str, source: str, page_number: int) -> str:
    if page_number < 1:
        raise ValueError("page_number must be positive")
    if page_number == 1:
        return seed_url
    if source == "nbs":
        return urljoin(seed_url, f"index_{page_number - 1}.html")
    if source == "pbc":
        return urljoin(seed_url, f"11871-{page_number}.html")
    raise ValueError(f"unsupported index source: {source}")


def parse_index_page(page: IndexPage) -> list[dict[str, object]]:
    parser = _LinkParser()
    parser.feed(page.content.decode("utf-8", errors="replace"))
    unique: dict[tuple[str, str], dict[str, object]] = {}
    for href, title in parser.links:
        classified = classify_release_title(title)
        if classified is None:
            continue
        family, period = classified
        url = urljoin(page.url, href)
        unique[(family, url)] = {
            "source_family": family,
            "period": period,
            "title": title,
            "source_url": url,
            "index_url": page.url,
            "index_page": page.page_number,
        }
    return list(unique.values())


def classify_release_title(title: str) -> tuple[str, str] | None:
    pmi = re.search(r"(20\d{2})年(\d{1,2})月中国采购经理指数运行情况", title)
    if pmi:
        return "nbs_pmi", _period(*pmi.groups())
    cpi = re.search(r"(20\d{2})年(\d{1,2})月份居民消费价格", title)
    if cpi:
        return "nbs_cpi", _period(*cpi.groups())
    m2 = re.fullmatch(
        r"(20\d{2})年(?:(\d{1,2})月|(一季度|上半年|前三季度))?金融统计数据报告",
        title,
    )
    if m2:
        year, month, aggregate = m2.groups()
        mapped_month = month or {"一季度": "3", "上半年": "6", "前三季度": "9"}.get(
            aggregate, "12"
        )
        return "pbc_m2", _period(year, mapped_month)
    return None


def build_coverage_catalog(
    pages: list[IndexPage], *, start: str, end: str
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    expected_periods = pd.period_range(start, end, freq="M").astype(str).tolist()
    candidates = pd.DataFrame(row for page in pages for row in parse_index_page(page))
    if candidates.empty:
        candidates = pd.DataFrame(
            columns=[
                "source_family",
                "period",
                "title",
                "source_url",
                "index_url",
                "index_page",
            ]
        )
    candidates = candidates[
        candidates["period"].between(expected_periods[0], expected_periods[-1])
    ].drop_duplicates()
    candidates = candidates.sort_values(
        ["source_family", "period", "source_url"]
    ).reset_index(drop=True)

    rows: list[dict[str, object]] = []
    for family in SOURCE_FAMILIES:
        family_rows = candidates[candidates["source_family"].eq(family)]
        for period in expected_periods:
            matches = family_rows[family_rows["period"].eq(period)]
            status = "missing"
            if len(matches) == 1:
                status = "discovered"
            elif len(matches) > 1:
                status = "duplicate"
            first = matches.iloc[0] if len(matches) else None
            rows.append(
                {
                    "record_id": f"{family}_{period.replace('-', '_')}",
                    "source_family": family,
                    "period": period,
                    "title": "" if first is None else first["title"],
                    "source_url": "" if first is None else first["source_url"],
                    "index_url": "" if first is None else first["index_url"],
                    "candidate_count": len(matches),
                    "discovery_status": status,
                }
            )
    catalog = pd.DataFrame(rows)
    family_summary: dict[str, dict[str, object]] = {}
    for family in SOURCE_FAMILIES:
        selected = catalog[catalog["source_family"].eq(family)]
        discovered = int(selected["discovery_status"].eq("discovered").sum())
        family_summary[family] = {
            "expected": len(selected),
            "discovered": discovered,
            "missing": int(selected["discovery_status"].eq("missing").sum()),
            "duplicate": int(selected["discovery_status"].eq("duplicate").sum()),
            "coverage": discovered / len(selected),
        }
    gate = not any(page.error for page in pages) and all(
        values["coverage"] >= 0.95 and values["duplicate"] == 0
        for values in family_summary.values()
    )
    summary: dict[str, object] = {
        "period_start": expected_periods[0],
        "period_end": expected_periods[-1],
        "index_pages_archived": len(pages),
        "index_pages_failed": sum(bool(page.error) for page in pages),
        "failed_index_urls": [page.url for page in pages if page.error],
        "candidate_records": len(candidates),
        "source_families": family_summary,
        "etf_returns_read": False,
        "regime_thresholds_constructed": False,
        "catalog_discovery_gate": "pass" if gate else "blocked",
    }
    return catalog, candidates, summary


def archive_index_pages(pages: list[IndexPage], output_dir: Path) -> list[Path]:
    archive_dir = output_dir / "index_pages"
    archive_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    ledger = []
    for page in pages:
        path = archive_dir / f"{page.source}_{page.page_number:03d}.html"
        path.write_bytes(page.content)
        paths.append(path)
        ledger.append(
            {
                "source": page.source,
                "page_number": page.page_number,
                "index_url": page.url,
                "sha256": hashlib.sha256(page.content).hexdigest(),
                "bytes": len(page.content),
                "fetch_status": "failed" if page.error else "ready",
                "error": page.error,
            }
        )
    ledger_path = output_dir / "macro_index_page_ledger.csv"
    pd.DataFrame(ledger).to_csv(ledger_path, index=False)
    return [*paths, ledger_path]


def _period(year: str, month: str) -> str:
    number = int(month)
    if not 1 <= number <= 12:
        raise ValueError(f"invalid release month: {month}")
    return f"{year}-{number:02d}"
