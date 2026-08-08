from __future__ import annotations

import math
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import pandas as pd

EXPECTED_DIMENSIONS = {"growth", "inflation", "liquidity"}
EXPECTED_RECORDS_PER_DIMENSION = 4
MINIMUM_ORIGINAL_RELEASE_PAGES = 10
ALLOWED_RECORD_TYPES = {
    "original_release_page",
    "official_retrospective_confirmation",
}


@dataclass(frozen=True)
class MacroPilotResult:
    audit: pd.DataFrame
    summary: dict[str, object]


def audit_macro_release_pilot(catalog: pd.DataFrame) -> MacroPilotResult:
    """Audit a return-blind pilot catalog of official macro releases."""
    _validate_columns(catalog)
    if catalog["record_id"].duplicated().any():
        raise ValueError("macro pilot contains duplicate record IDs")
    if catalog.duplicated(["dimension", "series_id", "period"]).any():
        raise ValueError("macro pilot contains duplicate series periods")

    rows = []
    for record in catalog.fillna("").to_dict("records"):
        period_valid = bool(re.fullmatch(r"\d{4}-\d{2}", str(record["period"])))
        release_at = pd.to_datetime(record["release_at"], errors="coerce", utc=True)
        release_after_period = False
        if period_valid and pd.notna(release_at):
            period_end = pd.Period(str(record["period"]), freq="M").end_time
            release_after_period = release_at.tz_convert("Asia/Shanghai").tz_localize(
                None
            ) >= period_end.floor("D")
        source_url = str(record["source_url"])
        hostname = (urlparse(source_url).hostname or "").lower()
        official_domain = _is_official_domain(hostname)
        value = pd.to_numeric(record["value"], errors="coerce")
        value_valid = bool(pd.notna(value) and math.isfinite(float(value)))
        record_type_valid = record["source_record_type"] in ALLOWED_RECORD_TYPES
        revision_status_present = bool(str(record["revision_status"]).strip())
        review_ready = record["review_status"] == "publication_record_ready"
        strict_verified = (
            bool(str(record["historical_snapshot_url"]).strip())
            and record["strict_point_in_time_status"] == "verified_snapshot"
        )
        checks = {
            "period_valid": period_valid,
            "release_timestamp_valid": bool(pd.notna(release_at)),
            "release_after_period": release_after_period,
            "official_domain": official_domain,
            "record_type_valid": record_type_valid,
            "value_valid": value_valid,
            "revision_status_present": revision_status_present,
            "review_ready": review_ready,
        }
        rows.append(
            {
                **record,
                **checks,
                "strict_point_in_time_verified": strict_verified,
                "audit_status": "ready" if all(checks.values()) else "blocked",
                "failure_reasons": ";".join(
                    key for key, passed in checks.items() if not passed
                ),
            }
        )

    audit = pd.DataFrame(rows)
    dimension_counts = {
        dimension: int(count)
        for dimension, count in audit["dimension"].value_counts().items()
    }
    original_pages = int(
        audit["source_record_type"].eq("original_release_page").sum()
    )
    ready_records = int(audit["audit_status"].eq("ready").sum())
    expected_total = len(EXPECTED_DIMENSIONS) * EXPECTED_RECORDS_PER_DIMENSION
    dimension_gate = set(dimension_counts) == EXPECTED_DIMENSIONS and all(
        dimension_counts[dimension] == EXPECTED_RECORDS_PER_DIMENSION
        for dimension in EXPECTED_DIMENSIONS
    )
    summary = {
        "expected_records": expected_total,
        "catalog_records": len(audit),
        "ready_records": ready_records,
        "blocked_records": int(len(audit) - ready_records),
        "dimension_counts": dimension_counts,
        "original_release_pages": original_pages,
        "official_retrospective_confirmations": int(
            audit["source_record_type"]
            .eq("official_retrospective_confirmation")
            .sum()
        ),
        "strict_point_in_time_verified_records": int(
            audit["strict_point_in_time_verified"].sum()
        ),
        "etf_returns_read": False,
        "regime_thresholds_constructed": False,
        "portfolio_constructed": False,
    }
    summary["macro_release_pilot_gate"] = (
        "pass_publication_record_only"
        if len(audit) == expected_total
        and ready_records == expected_total
        and dimension_gate
        and original_pages >= MINIMUM_ORIGINAL_RELEASE_PAGES
        else "blocked"
    )
    return MacroPilotResult(audit=audit, summary=summary)


def _is_official_domain(hostname: str) -> bool:
    return hostname == "stats.gov.cn" or hostname.endswith(".stats.gov.cn") or (
        hostname == "pbc.gov.cn" or hostname.endswith(".pbc.gov.cn")
    )


def _validate_columns(catalog: pd.DataFrame) -> None:
    required = {
        "record_id",
        "dimension",
        "series_id",
        "series_name",
        "period",
        "release_at",
        "source_url",
        "source_record_type",
        "value",
        "unit",
        "seasonal_adjustment",
        "release_value_status",
        "revision_status",
        "historical_snapshot_url",
        "strict_point_in_time_status",
        "review_status",
    }
    missing = sorted(required - set(catalog.columns))
    if missing:
        raise ValueError(f"macro pilot missing columns: {', '.join(missing)}")
