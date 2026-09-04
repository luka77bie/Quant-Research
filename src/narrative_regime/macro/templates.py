from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from narrative_regime.macro.archive import extract_visible_text


@dataclass(frozen=True)
class ExtractedMacroRelease:
    release_at: pd.Timestamp
    value: float


def extract_macro_release(
    content: bytes, *, source_family: str
) -> ExtractedMacroRelease:
    """Extract release time and headline value using one rule per source family."""
    text = extract_visible_text(content)
    if source_family == "nbs_pmi":
        release_at = _extract_nbs_release_at(text)
    elif source_family == "nbs_cpi":
        release_at = _extract_nbs_release_at(text)
    elif source_family == "pbc_m2":
        release_at = _extract_pbc_release_at(text)
    else:
        raise ValueError(f"unsupported macro source family: {source_family}")
    value = _extract_macro_value(text, source_family=source_family)
    return ExtractedMacroRelease(release_at=release_at, value=value)


def extract_macro_value(content: bytes, *, source_family: str) -> float:
    """Extract the registered headline value without requiring release time."""
    return _extract_macro_value(
        extract_visible_text(content), source_family=source_family
    )


def _extract_macro_value(text: str, *, source_family: str) -> float:
    if source_family == "nbs_pmi":
        return _extract_float(
            text,
            r"(?:中国)?制造业采购经理指数（PMI）为(\d+(?:\.\d+)?)%",
            "manufacturing PMI",
        )
    if source_family == "nbs_cpi":
        match = re.search(
            r"全国居民消费价格同比(上涨|下降)(\d+(?:\.\d+)?)%", text
        )
        if "全国居民消费价格同比持平" in text:
            return 0.0
        if match:
            direction, magnitude = match.groups()
            return float(magnitude) * (-1 if direction == "下降" else 1)
        raise ValueError("CPI headline value not found")
    if source_family == "pbc_m2":
        return _extract_float(
            text,
            (
                r"广义货币[（(]M2[）)]余额\d+(?:\.\d+)?万亿元[,，]"
                r"同比增长(\d+(?:\.\d+)?)%"
            ),
            "M2 YoY",
        )
    raise ValueError(f"unsupported macro source family: {source_family}")


def audit_template_drift(
    root: Path, catalog: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, object]]:
    required = {
        "record_id",
        "source_family",
        "anchor_year",
        "release_at",
        "value",
    }
    missing = sorted(required - set(catalog.columns))
    if missing:
        raise ValueError(
            f"template drift catalog missing columns: {', '.join(missing)}"
        )
    if catalog["record_id"].duplicated().any():
        raise ValueError("template drift catalog contains duplicate record IDs")

    rows = []
    for record in catalog.to_dict("records"):
        cache_path = (
            root
            / "data"
            / "raw"
            / "macro_release_pages"
            / f"{record['record_id']}.html"
        )
        issues: list[str] = []
        extracted_at = pd.NaT
        extracted_value = float("nan")
        try:
            extracted = extract_macro_release(
                cache_path.read_bytes(), source_family=str(record["source_family"])
            )
            extracted_at = extracted.release_at
            extracted_value = extracted.value
            expected_at = pd.to_datetime(record["release_at"], errors="raise", utc=True)
            if extracted_at != expected_at:
                issues.append("release timestamp mismatch")
            expected_value = float(record["value"])
            if abs(extracted_value - expected_value) > 1e-12:
                issues.append("headline value mismatch")
        except (OSError, TypeError, ValueError) as exc:
            issues.append(f"extraction failed: {type(exc).__name__}: {exc}")
        rows.append(
            {
                "record_id": record["record_id"],
                "source_family": record["source_family"],
                "anchor_year": int(record["anchor_year"]),
                "expected_release_at": record["release_at"],
                "extracted_release_at": extracted_at,
                "expected_value": float(record["value"]),
                "extracted_value": extracted_value,
                "template_status": "ready" if not issues else "blocked",
                "issues": "; ".join(issues),
            }
        )
    audit = pd.DataFrame(rows)
    ready_rows = audit["template_status"].eq("ready")
    family_counts = {
        family: int(count)
        for family, count in audit.loc[ready_rows, "source_family"]
        .value_counts()
        .items()
    }
    ready = int(ready_rows.sum())
    required_families = {"nbs_pmi", "nbs_cpi", "pbc_m2"}
    gate = (
        len(audit) == 9
        and ready == 9
        and set(family_counts) == required_families
        and all(family_counts[family] == 3 for family in required_families)
    )
    summary = {
        "catalog_records": len(audit),
        "template_ready_records": ready,
        "template_blocked_records": int(len(audit) - ready),
        "ready_records_by_source_family": family_counts,
        "etf_returns_read": False,
        "regime_thresholds_constructed": False,
        "template_drift_gate": "pass" if gate else "blocked",
    }
    return audit, summary


def _extract_nbs_release_at(text: str) -> pd.Timestamp:
    match = re.search(r"(20\d{2})[/-](\d{2})[/-](\d{2})(\d{2}):(\d{2})", text)
    if not match:
        raise ValueError("NBS release timestamp not found")
    year, month, day, hour, minute = match.groups()
    return pd.Timestamp(
        f"{year}-{month}-{day}T{hour}:{minute}:00+08:00"
    ).tz_convert("UTC")


def _extract_pbc_release_at(text: str) -> pd.Timestamp:
    match = re.search(
        r"文章来源：(20\d{2})-(\d{2})-(\d{2})(\d{2}):(\d{2}):(\d{2})", text
    )
    if not match:
        raise ValueError("PBOC release timestamp not found")
    year, month, day, hour, minute, second = match.groups()
    return pd.Timestamp(
        f"{year}-{month}-{day}T{hour}:{minute}:{second}+08:00"
    ).tz_convert("UTC")


def _extract_float(text: str, pattern: str, label: str) -> float:
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"{label} headline value not found")
    return float(match.group(1))
