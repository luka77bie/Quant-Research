from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from narrative_regime.data.validation import (
    market_frame_coverage_issues,
    normalize_market_frame,
)

AUDIT_COLUMNS = [
    "symbol",
    "provider",
    "audit_status",
    "metadata_status",
    "rows",
    "observed_start",
    "observed_end",
    "checksum_ok",
    "issues",
]


def audit_provider_cache(
    root: Path,
    provider: str,
    symbols: list[str],
) -> pd.DataFrame:
    """Audit one provider cache without downloading or repairing data."""
    records = [_audit_symbol(root, provider, symbol) for symbol in symbols]
    return pd.DataFrame(records, columns=AUDIT_COLUMNS)


def _audit_symbol(root: Path, provider: str, symbol: str) -> dict[str, object]:
    cache_path = root / "data" / "raw" / provider / f"{symbol}.csv"
    metadata_path = cache_path.with_suffix(".meta.json")
    base: dict[str, object] = {
        "symbol": symbol,
        "provider": provider,
        "audit_status": "missing",
        "metadata_status": "",
        "rows": 0,
        "observed_start": "",
        "observed_end": "",
        "checksum_ok": False,
        "issues": "",
    }
    missing = [
        label
        for label, path in (("cache", cache_path), ("metadata", metadata_path))
        if not path.exists()
    ]
    if missing:
        base["issues"] = f"missing {', '.join(missing)}"
        return base

    issues: list[str] = []
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        base["audit_status"] = "invalid"
        base["issues"] = f"invalid metadata: {type(exc).__name__}: {exc}"
        return base

    base["metadata_status"] = str(metadata.get("status", ""))
    if metadata.get("provider") != provider:
        issues.append("provider differs from metadata")
    if str(metadata.get("symbol", "")) != symbol:
        issues.append("symbol differs from metadata")
    checksum_ok = metadata.get("sha256") == _sha256(cache_path)
    base["checksum_ok"] = checksum_ok
    if not checksum_ok:
        issues.append("checksum mismatch")

    try:
        raw = pd.read_csv(cache_path)
        if "date" in raw:
            parsed_dates = pd.to_datetime(raw["date"], errors="raise")
            if parsed_dates.duplicated().any():
                issues.append("duplicate dates in cache")
        frame = normalize_market_frame(raw)
    except (OSError, ValueError, pd.errors.ParserError) as exc:
        base["audit_status"] = "invalid"
        issues.append(f"invalid cache: {type(exc).__name__}: {exc}")
        base["issues"] = "; ".join(issues)
        return base

    observed_start = frame["date"].min().date().isoformat()
    observed_end = frame["date"].max().date().isoformat()
    base.update(
        rows=len(frame),
        observed_start=observed_start,
        observed_end=observed_end,
    )

    if metadata.get("rows") != len(frame):
        issues.append("row count differs from metadata")
    if metadata.get("observed_start") != observed_start:
        issues.append("observed start differs from metadata")
    if metadata.get("observed_end") != observed_end:
        issues.append("observed end differs from metadata")

    try:
        coverage_issues = market_frame_coverage_issues(
            frame,
            expected_start=pd.Timestamp(metadata["requested_start"]).date(),
            expected_end=pd.Timestamp(metadata["requested_end"]).date(),
        )
        issues.extend(coverage_issues)
    except (KeyError, TypeError, ValueError) as exc:
        issues.append(f"invalid request range in metadata: {exc}")

    metadata_status = metadata.get("status")
    if metadata_status not in {"validated", "partial"}:
        issues.append(f"unexpected metadata status: {metadata_status!r}")
    elif metadata_status == "partial":
        issues.append("metadata marks cache partial")

    if issues:
        base["audit_status"] = (
            "partial" if metadata_status == "partial" and checksum_ok else "invalid"
        )
    else:
        base["audit_status"] = "ready"
    base["issues"] = "; ".join(dict.fromkeys(issues))
    return base


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
