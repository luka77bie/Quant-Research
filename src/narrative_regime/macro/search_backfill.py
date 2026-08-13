from __future__ import annotations

import hashlib
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

from narrative_regime.macro.discovery import classify_release_title

NBS_SEARCH_URL = "https://api.so-gov.cn/query/s"
BACKFILL_COLUMNS = {
    "record_id",
    "source_family",
    "period",
    "title",
    "source_url",
    "index_url",
    "candidate_count",
    "discovery_status",
}
SEED_COLUMNS = {
    "record_id",
    "title",
    "source_url",
    "discovery_method",
    "timing_precision",
}


class NbsSearchBackfill:
    """Backfill NBS catalog gaps through exact-title official site search."""

    def __init__(
        self,
        *,
        attempts: int = 3,
        max_pages: int = 5,
        base_delay_seconds: float = 1.0,
        timeout_seconds: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        session: requests.Session | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        if max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        self.attempts = attempts
        self.max_pages = max_pages
        self.base_delay_seconds = base_delay_seconds
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep
        self.session = session or requests.Session()

    def backfill(
        self, catalog: pd.DataFrame, *, response_dir: Path
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
        validate_backfill_catalog(catalog)
        response_dir.mkdir(parents=True, exist_ok=True)
        updated = catalog.copy()
        _ensure_provenance_columns(updated)
        audit_rows = []
        targets = updated[
            updated["source_family"].isin({"nbs_pmi", "nbs_cpi"})
            & updated["discovery_status"].eq("missing")
        ]
        for index, row in targets.iterrows():
            record_id = str(row["record_id"])
            query = build_search_query(str(row["source_family"]), str(row["period"]))
            response_paths: list[Path] = []
            error = ""
            matches_by_url: dict[str, dict[str, str]] = {}
            try:
                for page in range(1, self.max_pages + 1):
                    legacy_path = response_dir / f"{record_id}.json"
                    response_path = response_dir / f"{record_id}_p{page:02d}.json"
                    read_path = (
                        legacy_path
                        if page == 1 and legacy_path.exists()
                        else response_path
                    )
                    if read_path.exists():
                        payload = json.loads(read_path.read_text(encoding="utf-8"))
                    else:
                        payload = self._search(query, page=page)
                        response_path.write_text(
                            json.dumps(payload, ensure_ascii=False, sort_keys=True)
                            + "\n",
                            encoding="utf-8",
                        )
                        read_path = response_path
                    response_paths.append(read_path)
                    page_matches = parse_search_matches(
                        payload,
                        source_family=str(row["source_family"]),
                        period=str(row["period"]),
                    )
                    matches_by_url.update(
                        {str(match["source_url"]): match for match in page_matches}
                    )
                matches = list(matches_by_url.values())
            except (RuntimeError, TypeError, ValueError) as exc:
                matches = []
                error = f"{type(exc).__name__}: {exc}"
            if error:
                status = "request_failed"
            elif len(matches) == 1:
                status = "backfilled"
                match = matches[0]
                updated.loc[index, ["title", "source_url", "index_url"]] = [
                    match["title"],
                    match["source_url"],
                    NBS_SEARCH_URL,
                ]
                updated.loc[index, "discovery_method"] = "nbs_official_title_search"
                updated.loc[index, "timing_precision"] = "pending_article_validation"
                updated.loc[index, "candidate_count"] = 1
                updated.loc[index, "discovery_status"] = status
            elif len(matches) > 1:
                status = "duplicate"
                updated.loc[index, "candidate_count"] = len(matches)
                updated.loc[index, "discovery_status"] = status
            else:
                status = "not_found"
            audit_rows.append(
                {
                    "record_id": record_id,
                    "source_family": row["source_family"],
                    "period": row["period"],
                    "query": query,
                    "matching_candidates": len(matches),
                    "backfill_status": status,
                    "matched_urls": " | ".join(
                        str(match["source_url"]) for match in matches
                    ),
                    "searched_pages": len(response_paths),
                    "response_sha256": " | ".join(
                        hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in response_paths
                    ),
                    "error": error,
                }
            )
        audit = pd.DataFrame(
            audit_rows,
            columns=[
                "record_id",
                "source_family",
                "period",
                "query",
                "matching_candidates",
                "backfill_status",
                "matched_urls",
                "searched_pages",
                "response_sha256",
                "error",
            ],
        )
        counts = audit["backfill_status"].value_counts().to_dict()
        family_summary = coverage_by_family(updated)
        gate = all(
            values["coverage"] >= 0.95 and values["duplicate"] == 0
            for values in family_summary.values()
        )
        summary: dict[str, object] = {
            "target_records": len(targets),
            "backfill_status_counts": {
                status: int(count) for status, count in counts.items()
            },
            "source_families": family_summary,
            "etf_returns_read": False,
            "regime_thresholds_constructed": False,
            "search_backfill_gate": "pass" if gate else "blocked",
        }
        return updated, audit, summary

    def _search(self, query: str, *, page: int) -> dict[str, object]:
        errors = []
        form = {
            "siteCode": "bm36000002",
            "tab": "all",
            "qt": query,
            "page": str(page),
            "pageSize": "20",
            "sort": "relevance",
            "keyPlace": "1",
        }
        headers = {"User-Agent": "Luka-Quant-Research-Lab/0.1 catalog-backfill"}
        for attempt in range(1, self.attempts + 1):
            try:
                response = self.session.post(
                    NBS_SEARCH_URL,
                    data=form,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
                response.raise_for_status()
                payload = response.json()
                if payload.get("ok") is not True:
                    raise ValueError(f"official search rejected request: {payload}")
                if not isinstance(payload.get("resultDocs"), list):
                    raise ValueError("official search resultDocs is not a list")
                return payload
            except Exception as exc:  # per-query failure remains resumable
                errors.append(f"attempt {attempt}: {type(exc).__name__}: {exc}")
                if attempt < self.attempts:
                    self.sleep(self.base_delay_seconds * 2 ** (attempt - 1))
        raise RuntimeError(" | ".join(errors))


def validate_backfill_catalog(catalog: pd.DataFrame) -> None:
    missing = sorted(BACKFILL_COLUMNS - set(catalog.columns))
    if missing:
        raise ValueError(f"macro catalog missing columns: {', '.join(missing)}")
    if catalog["record_id"].duplicated().any():
        raise ValueError("macro catalog contains duplicate record IDs")


def build_search_query(source_family: str, period: str) -> str:
    parsed = pd.Period(period, freq="M")
    if source_family == "nbs_pmi":
        return f"{parsed.year}年{parsed.month}月中国采购经理指数运行情况"
    if source_family == "nbs_cpi":
        return f"{parsed.year}年{parsed.month}月份居民消费价格"
    raise ValueError(f"unsupported backfill source family: {source_family}")


def parse_search_matches(
    payload: dict[str, object], *, source_family: str, period: str
) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    for result in payload.get("resultDocs", []):
        if not isinstance(result, dict) or not isinstance(result.get("data"), dict):
            continue
        data = result["data"]
        title = _plain_title(str(data.get("titleO") or ""))
        url = str(data.get("url") or "")
        host = (urlparse(url).hostname or "").lower()
        classified = classify_release_title(title)
        official_host = host == "stats.gov.cn" or host.endswith(".stats.gov.cn")
        if not official_host or classified != (source_family, period):
            continue
        if "/sj/zxfb/" not in url:
            continue
        unique[url] = {"title": title, "source_url": url}
    return list(unique.values())


def coverage_by_family(catalog: pd.DataFrame) -> dict[str, dict[str, object]]:
    summary = {}
    for family, selected in catalog.groupby("source_family", sort=True):
        discovered = selected["discovery_status"].isin(
            {"discovered", "backfilled", "seeded_pending_article_validation"}
        )
        summary[str(family)] = {
            "expected": len(selected),
            "ready": int(discovered.sum()),
            "missing": int((~discovered).sum()),
            "duplicate": int(selected["discovery_status"].eq("duplicate").sum()),
            "coverage": float(discovered.mean()),
        }
    return summary


def apply_reviewed_seeds(
    catalog: pd.DataFrame, seeds: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    validate_backfill_catalog(catalog)
    missing_columns = sorted(SEED_COLUMNS - set(seeds.columns))
    if missing_columns:
        raise ValueError(
            f"macro seed file missing columns: {', '.join(missing_columns)}"
        )
    if seeds["record_id"].duplicated().any():
        raise ValueError("macro seed file contains duplicate record IDs")

    updated = catalog.copy()
    _ensure_provenance_columns(updated)
    audit_rows = []
    catalog_ids = set(updated["record_id"])
    for seed in seeds.to_dict("records"):
        record_id = str(seed["record_id"])
        issues = []
        if record_id not in catalog_ids:
            issues.append("record ID not found in catalog")
            target = None
        else:
            target = updated[updated["record_id"].eq(record_id)].iloc[0]
            classified = classify_release_title(str(seed["title"]))
            if classified != (target["source_family"], target["period"]):
                issues.append("title does not match catalog family and period")
            if target["discovery_status"] not in {"missing", "not_found"}:
                issues.append("catalog row is not missing")
        url = str(seed["source_url"])
        host = (urlparse(url).hostname or "").lower()
        official_host = host == "stats.gov.cn" or host.endswith(".stats.gov.cn")
        allowed_path = "/sj/zxfb/" in url or "/xxgk/sjfb/zxfb2020/" in url
        if not official_host or not allowed_path:
            issues.append("source URL is not an allowed NBS release page")
        if seed["timing_precision"] not in {"minute", "date"}:
            issues.append("timing precision must be minute or date")
        if target is not None and not issues:
            index = updated["record_id"].eq(record_id)
            updated.loc[index, ["title", "source_url"]] = [
                seed["title"],
                seed["source_url"],
            ]
            updated.loc[index, "index_url"] = ""
            updated.loc[index, "discovery_method"] = seed["discovery_method"]
            updated.loc[index, "timing_precision"] = seed["timing_precision"]
            updated.loc[index, "candidate_count"] = 1
            updated.loc[index, "discovery_status"] = (
                "seeded_pending_article_validation"
            )
        audit_rows.append(
            {
                "record_id": record_id,
                "timing_precision": seed["timing_precision"],
                "seed_status": "accepted" if not issues else "blocked",
                "issues": "; ".join(issues),
            }
        )
    audit = pd.DataFrame(audit_rows)
    family_summary = coverage_by_family(updated)
    gate = bool(len(audit)) and audit["seed_status"].eq("accepted").all() and all(
        values["coverage"] >= 0.95 and values["duplicate"] == 0
        for values in family_summary.values()
    )
    summary: dict[str, object] = {
        "seed_records": len(audit),
        "accepted_seeds": int(audit["seed_status"].eq("accepted").sum()),
        "blocked_seeds": int(audit["seed_status"].eq("blocked").sum()),
        "date_only_seeds": int(audit["timing_precision"].eq("date").sum()),
        "source_families": family_summary,
        "etf_returns_read": False,
        "regime_thresholds_constructed": False,
        "source_catalog_gate": "pass_pending_article_validation" if gate else "blocked",
    }
    return updated, audit, summary


def _plain_title(title: str) -> str:
    return re.sub(r"<[^>]+>", "", title).strip()


def _ensure_provenance_columns(catalog: pd.DataFrame) -> None:
    if "discovery_method" not in catalog:
        catalog["discovery_method"] = catalog["discovery_status"].map(
            {
                "discovered": "official_index",
                "backfilled": "nbs_official_title_search",
            }
        ).fillna("")
    if "timing_precision" not in catalog:
        catalog["timing_precision"] = "pending_article_validation"
