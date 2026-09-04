from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

from narrative_regime.macro.archive import extract_visible_text
from narrative_regime.macro.discovery import SOURCE_FAMILIES, classify_release_title
from narrative_regime.macro.templates import (
    extract_macro_release,
    extract_macro_value,
)

CATALOG_COLUMNS = {
    "record_id",
    "source_family",
    "period",
    "title",
    "source_url",
    "discovery_status",
    "timing_precision",
}
MINIMUM_FAMILY_COVERAGE = 0.95
EARLIEST_RELEASE_DAYS_BEFORE_MONTH_END = 7
LATEST_RELEASE_DAYS_AFTER_MONTH_END = 60


class MacroMonthlyArchive:
    """Cache full-catalog official macro pages one record at a time."""

    def __init__(
        self,
        root: Path,
        *,
        attempts: int = 3,
        base_delay_seconds: float = 2.0,
        timeout_seconds: float = 30.0,
        inter_record_delay_seconds: float = 0.0,
        sleep: Callable[[float], None] = time.sleep,
        session: requests.Session | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        if inter_record_delay_seconds < 0:
            raise ValueError("inter-record delay must not be negative")
        self.root = root
        self.attempts = attempts
        self.base_delay_seconds = base_delay_seconds
        self.timeout_seconds = timeout_seconds
        self.inter_record_delay_seconds = inter_record_delay_seconds
        self.sleep = sleep
        self.session = session or requests.Session()

    def fetch_catalog(
        self,
        catalog: pd.DataFrame,
        *,
        record_ids: Iterable[str] | None = None,
        refresh: bool = False,
    ) -> pd.DataFrame:
        records = validate_monthly_catalog(catalog)
        selected = _select_records(records, record_ids)
        rows = []
        for index, record in enumerate(selected):
            rows.append(self.fetch_one(record, refresh=refresh))
            if index < len(selected) - 1 and self.inter_record_delay_seconds:
                self.sleep(self.inter_record_delay_seconds)
        return pd.DataFrame(rows, columns=_fetch_columns())

    def fetch_one(
        self, record: dict[str, str], *, refresh: bool = False
    ) -> dict[str, object]:
        source_url = record["source_url"].strip()
        if not source_url:
            return _fetch_result(record, "missing_source")
        cache_path = monthly_cache_path(self.root, record["record_id"])
        if not refresh and _cache_valid(cache_path, source_url):
            metadata = json.loads(
                cache_path.with_suffix(".meta.json").read_text(encoding="utf-8")
            )
            return _fetch_result(record, "cached", cache_path, metadata=metadata)

        errors = []
        headers = {
            "User-Agent": "Luka-Quant-Research-Lab/0.1 monthly-macro-archive"
        }
        for attempt in range(1, self.attempts + 1):
            try:
                response = self.session.get(
                    source_url,
                    timeout=self.timeout_seconds,
                    headers=headers,
                )
                response.raise_for_status()
                content = response.content
                if b"<html" not in content[:8192].lower():
                    raise ValueError("response does not contain an HTML document")
                metadata = _write_cache(cache_path, content, record)
                return _fetch_result(
                    record, "downloaded", cache_path, metadata=metadata
                )
            except Exception as exc:  # failures stay local to the record
                errors.append(
                    f"attempt {attempt}/{self.attempts}: "
                    f"{type(exc).__name__}: {exc}"
                )
                if attempt < self.attempts:
                    self.sleep(self.base_delay_seconds * 2 ** (attempt - 1))
        return _fetch_result(record, "failed", error=" | ".join(errors))


def validate_monthly_catalog(catalog: pd.DataFrame) -> list[dict[str, str]]:
    missing = sorted(CATALOG_COLUMNS - set(catalog.columns))
    if missing:
        raise ValueError(f"monthly macro catalog missing columns: {', '.join(missing)}")
    if catalog["record_id"].duplicated().any():
        raise ValueError("monthly macro catalog contains duplicate record IDs")
    if catalog.duplicated(["source_family", "period"]).any():
        raise ValueError("monthly macro catalog contains duplicate family periods")

    records = catalog.fillna("").astype(str).to_dict("records")
    for record in records:
        family = record["source_family"]
        period = record["period"]
        source_url = record["source_url"].strip()
        if family not in SOURCE_FAMILIES:
            raise ValueError(f"unsupported macro source family: {family}")
        if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", period):
            raise ValueError(f"invalid monthly macro period: {period}")
        if source_url:
            hostname = (urlparse(source_url).hostname or "").lower()
            if not _is_official_domain(hostname):
                raise ValueError(f"macro source domain is not allowed: {hostname}")
            if not record["title"].strip():
                raise ValueError(
                    "catalog title must not be blank when source URL exists"
                )
            if record["discovery_status"] == "missing":
                raise ValueError("missing catalog record must not contain a source URL")
        elif record["discovery_status"] != "missing":
            raise ValueError(
                "catalog record without a source URL must be marked missing"
            )
        if record["timing_precision"] not in {
            "minute",
            "date",
            "pending_article_validation",
        }:
            raise ValueError("invalid timing_precision")
    return records


def audit_monthly_catalog(
    root: Path, catalog: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, object]]:
    records = validate_monthly_catalog(catalog)
    rows = [_audit_one(root, record) for record in records]
    audit = pd.DataFrame(rows)
    family_summary: dict[str, dict[str, object]] = {}
    for family in SOURCE_FAMILIES:
        selected = audit[audit["source_family"].eq(family)]
        ready = int(selected["article_status"].eq("ready").sum())
        expected = len(selected)
        family_summary[family] = {
            "expected_records": expected,
            "source_urls": int(selected["source_url"].ne("").sum()),
            "pages_cached": int(selected["page_cached"].sum()),
            "title_verified": int(selected["title_verified"].sum()),
            "period_verified": int(selected["period_verified"].sum()),
            "release_timing_verified": int(
                selected["release_timing_verified"].sum()
            ),
            "headline_value_verified": int(
                selected["headline_value_verified"].sum()
            ),
            "article_ready": ready,
            "article_ready_coverage": ready / expected if expected else 0.0,
        }
    gate = all(
        values["article_ready_coverage"] >= MINIMUM_FAMILY_COVERAGE
        for values in family_summary.values()
    )
    summary: dict[str, object] = {
        "catalog_records": len(audit),
        "source_urls": int(audit["source_url"].ne("").sum()),
        "pages_cached": int(audit["page_cached"].sum()),
        "article_ready_records": int(audit["article_status"].eq("ready").sum()),
        "article_blocked_records": int(
            audit["article_status"].eq("blocked").sum()
        ),
        "missing_source_records": int(
            audit["article_status"].eq("missing_source").sum()
        ),
        "source_families": family_summary,
        "minimum_family_coverage": MINIMUM_FAMILY_COVERAGE,
        "etf_returns_read": False,
        "regime_thresholds_constructed": False,
        "article_validation_gate": "pass" if gate else "blocked",
    }
    return audit, summary


def build_article_evidence_ledger(audit: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "record_id",
        "source_family",
        "period",
        "source_url",
        "retrieved_at",
        "page_sha256",
        "release_at",
        "release_timing_precision",
        "headline_value",
        "strict_point_in_time_status",
        "article_status",
    ]
    ledger = audit.loc[:, columns].copy()
    ledger["strict_point_in_time_status"] = "provisional_no_snapshot"
    return ledger


def summarize_fetch(results: pd.DataFrame) -> dict[str, object]:
    counts = results["status"].value_counts().to_dict()
    failures = int(counts.get("failed", 0))
    return {
        "selected_records": len(results),
        "status_counts": {key: int(value) for key, value in counts.items()},
        "network_failures": failures,
        "missing_source_records": int(counts.get("missing_source", 0)),
        "etf_returns_read": False,
        "regime_thresholds_constructed": False,
        "monthly_catalog_fetch_gate": "pass" if failures == 0 else "blocked",
    }


def monthly_cache_path(root: Path, record_id: str) -> Path:
    return root / "data" / "raw" / "macro_monthly_pages" / f"{record_id}.html"


def _audit_one(root: Path, record: dict[str, str]) -> dict[str, object]:
    base = {
        "record_id": record["record_id"],
        "source_family": record["source_family"],
        "period": record["period"],
        "catalog_title": record["title"],
        "source_url": record["source_url"],
        "discovery_status": record["discovery_status"],
        "page_cached": False,
        "retrieved_at": "",
        "page_sha256": "",
        "title_verified": False,
        "period_verified": False,
        "release_at": "",
        "release_timing_precision": "",
        "release_timing_verified": False,
        "headline_value": float("nan"),
        "headline_value_verified": False,
        "strict_point_in_time_status": "provisional_no_snapshot",
        "article_status": "blocked",
        "issues": "",
    }
    if not record["source_url"].strip():
        base["article_status"] = "missing_source"
        base["issues"] = "source URL missing"
        return base

    issues: list[str] = []
    cache_path = monthly_cache_path(root, record["record_id"])
    metadata_path = cache_path.with_suffix(".meta.json")
    if not cache_path.exists() or not metadata_path.exists():
        issues.append("page or metadata missing")
    else:
        try:
            content = cache_path.read_bytes()
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            observed = hashlib.sha256(content).hexdigest()
            base["page_cached"] = True
            base["retrieved_at"] = metadata.get("retrieved_at", "")
            base["page_sha256"] = observed
            if metadata.get("sha256") != observed:
                issues.append("checksum mismatch")
            if metadata.get("record_id") != record["record_id"]:
                issues.append("record ID mismatch")
            if metadata.get("source_url") != record["source_url"]:
                issues.append("source URL mismatch")

            text = extract_visible_text(content)
            base["title_verified"] = _normalize(record["title"]) in text
            if not base["title_verified"]:
                issues.append("catalog title not found in page")
            classified = classify_release_title(record["title"])
            base["period_verified"] = classified == (
                record["source_family"],
                record["period"],
            )
            if not base["period_verified"]:
                issues.append("catalog title does not match family and period")

            try:
                extracted = extract_macro_release(
                    content, source_family=record["source_family"]
                )
                base["release_at"] = extracted.release_at.isoformat()
                base["release_timing_precision"] = "minute"
                base["release_timing_verified"] = _release_is_plausible(
                    extracted.release_at, record["period"]
                )
                base["headline_value"] = extracted.value
                base["headline_value_verified"] = True
            except ValueError as exc:
                try:
                    base["headline_value"] = extract_macro_value(
                        content, source_family=record["source_family"]
                    )
                    base["headline_value_verified"] = True
                except ValueError as value_exc:
                    issues.append(f"value extraction failed: {value_exc}")
                if record["timing_precision"] == "date":
                    date_only = _extract_plausible_date(text, record["period"])
                    if date_only:
                        base["release_at"] = date_only
                        base["release_timing_precision"] = "date"
                        base["release_timing_verified"] = True
                    else:
                        issues.append("date-only release evidence not found")
                else:
                    issues.append(f"release extraction failed: {exc}")
            if not base["release_timing_verified"]:
                issues.append("release timing is outside the allowed period window")
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            issues.append(f"invalid page or metadata: {type(exc).__name__}: {exc}")

    ready_checks = [
        base["page_cached"],
        base["title_verified"],
        base["period_verified"],
        base["release_timing_verified"],
        base["headline_value_verified"],
    ]
    if all(ready_checks) and not issues:
        base["article_status"] = "ready"
    base["issues"] = "; ".join(dict.fromkeys(issues))
    return base


def _release_is_plausible(release_at: pd.Timestamp, period: str) -> bool:
    period_value = pd.Period(period, freq="M")
    earliest = period_value.end_time.tz_localize("Asia/Shanghai") - pd.Timedelta(
        days=EARLIEST_RELEASE_DAYS_BEFORE_MONTH_END
    )
    latest = period_value.end_time.tz_localize("Asia/Shanghai") + pd.Timedelta(
        days=LATEST_RELEASE_DAYS_AFTER_MONTH_END
    )
    local_release = release_at.tz_convert("Asia/Shanghai")
    return earliest <= local_release <= latest


def _extract_plausible_date(text: str, period: str) -> str:
    candidates: set[pd.Timestamp] = set()
    for year, month, day in re.findall(
        r"(20\d{2})(?:年|[-/])(\d{1,2})(?:月|[-/])(\d{1,2})日?", text
    ):
        try:
            candidates.add(pd.Timestamp(year=int(year), month=int(month), day=int(day)))
        except ValueError:
            continue
    period_value = pd.Period(period, freq="M")
    earliest = period_value.end_time.normalize() - pd.Timedelta(
        days=EARLIEST_RELEASE_DAYS_BEFORE_MONTH_END
    )
    latest = period_value.end_time.normalize() + pd.Timedelta(
        days=LATEST_RELEASE_DAYS_AFTER_MONTH_END
    )
    plausible = sorted(item for item in candidates if earliest <= item <= latest)
    return plausible[0].date().isoformat() if plausible else ""


def _select_records(
    records: list[dict[str, str]], record_ids: Iterable[str] | None
) -> list[dict[str, str]]:
    if record_ids is None:
        return records
    requested = [str(record_id).strip() for record_id in record_ids]
    if not requested or any(not item for item in requested):
        raise ValueError("record IDs must contain at least one non-empty value")
    if len(requested) != len(set(requested)):
        raise ValueError("record IDs contain duplicates")
    known = {record["record_id"] for record in records}
    unknown = sorted(set(requested) - known)
    if unknown:
        raise ValueError(f"unknown monthly macro record IDs: {', '.join(unknown)}")
    selected = set(requested)
    return [record for record in records if record["record_id"] in selected]


def _write_cache(
    cache_path: Path, content: bytes, record: dict[str, str]
) -> dict[str, object]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    sha256 = hashlib.sha256(content).hexdigest()
    with tempfile.NamedTemporaryFile(dir=cache_path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    os.replace(temporary, cache_path)
    metadata = {
        "record_id": record["record_id"],
        "source_url": record["source_url"],
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "bytes": len(content),
        "sha256": sha256,
    }
    metadata_path = cache_path.with_suffix(".meta.json")
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=cache_path.parent, delete=False
    ) as handle:
        temporary_metadata = Path(handle.name)
        json.dump(metadata, handle, ensure_ascii=True, indent=2)
        handle.write("\n")
    os.replace(temporary_metadata, metadata_path)
    return metadata


def _cache_valid(cache_path: Path, source_url: str) -> bool:
    metadata_path = cache_path.with_suffix(".meta.json")
    if not cache_path.exists() or not metadata_path.exists():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        observed = hashlib.sha256(cache_path.read_bytes()).hexdigest()
        return (
            metadata["source_url"] == source_url
            and metadata["sha256"] == observed
        )
    except (KeyError, OSError, json.JSONDecodeError):
        return False


def _fetch_result(
    record: dict[str, str],
    status: str,
    cache_path: Path | None = None,
    *,
    metadata: dict[str, object] | None = None,
    error: str = "",
) -> dict[str, object]:
    return {
        "record_id": record["record_id"],
        "source_family": record["source_family"],
        "period": record["period"],
        "source_url": record["source_url"],
        "status": status,
        "cache_path": str(cache_path) if cache_path else "",
        "retrieved_at": (metadata or {}).get("retrieved_at", ""),
        "sha256": (metadata or {}).get("sha256", ""),
        "bytes": (metadata or {}).get("bytes", 0),
        "error": error,
    }


def _fetch_columns() -> list[str]:
    return [
        "record_id",
        "source_family",
        "period",
        "source_url",
        "status",
        "cache_path",
        "retrieved_at",
        "sha256",
        "bytes",
        "error",
    ]


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("\u3000", "")


def _is_official_domain(hostname: str) -> bool:
    return hostname == "stats.gov.cn" or hostname.endswith(".stats.gov.cn") or (
        hostname == "pbc.gov.cn" or hostname.endswith(".pbc.gov.cn")
    )
