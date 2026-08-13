from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from collections.abc import Callable
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

EVIDENCE_COLUMNS = {
    "record_id",
    "expected_page_sha256",
    "release_evidence_text",
    "release_evidence_precision",
    "value_evidence_text",
}


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


class MacroEvidenceArchive:
    """Cache current official HTML pages with retrieval provenance."""

    def __init__(
        self,
        root: Path,
        *,
        attempts: int = 3,
        base_delay_seconds: float = 2.0,
        timeout_seconds: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        session: requests.Session | None = None,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self.root = root
        self.attempts = attempts
        self.base_delay_seconds = base_delay_seconds
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep
        self.session = session or requests.Session()

    def fetch_catalog(
        self,
        catalog: pd.DataFrame,
        evidence: pd.DataFrame,
        *,
        refresh: bool = False,
    ) -> pd.DataFrame:
        records = validate_evidence_contract(catalog, evidence)
        return pd.DataFrame(
            [self.fetch_one(record, refresh=refresh) for record in records]
        )

    def fetch_one(
        self, record: dict[str, object], *, refresh: bool = False
    ) -> dict[str, object]:
        cache_path = _cache_path(self.root, str(record["record_id"]))
        expected = str(record["expected_page_sha256"]).strip()
        if not refresh and _cache_valid(
            cache_path, str(record["source_url"]), expected
        ):
            metadata = json.loads(
                cache_path.with_suffix(".meta.json").read_text(encoding="utf-8")
            )
            return _fetch_result(record, "cached", cache_path, metadata=metadata)

        errors = []
        headers = {
            "User-Agent": "Luka-Quant-Research-Lab/0.1 evidence-archive"
        }
        for attempt in range(1, self.attempts + 1):
            try:
                response = self.session.get(
                    str(record["source_url"]),
                    timeout=self.timeout_seconds,
                    headers=headers,
                )
                response.raise_for_status()
                content = response.content
                if b"<html" not in content[:4096].lower():
                    raise ValueError("response does not contain an HTML document")
                observed = hashlib.sha256(content).hexdigest()
                if expected and observed != expected:
                    raise ValueError("download checksum differs from locked evidence")
                metadata = _write_cache(cache_path, content, record, observed)
                return _fetch_result(
                    record, "downloaded", cache_path, metadata=metadata
                )
            except Exception as exc:  # per-record network failures remain visible
                errors.append(
                    f"attempt {attempt}/{self.attempts}: "
                    f"{type(exc).__name__}: {exc}"
                )
                if attempt < self.attempts:
                    self.sleep(self.base_delay_seconds * (2 ** (attempt - 1)))
        return _fetch_result(record, "failed", None, error=" | ".join(errors))


def validate_evidence_contract(
    catalog: pd.DataFrame, evidence: pd.DataFrame
) -> list[dict[str, object]]:
    missing = sorted(EVIDENCE_COLUMNS - set(evidence.columns))
    if missing:
        raise ValueError(f"macro evidence missing columns: {', '.join(missing)}")
    if evidence["record_id"].duplicated().any():
        raise ValueError("macro evidence contains duplicate record IDs")
    catalog_ids = set(catalog["record_id"].astype(str))
    evidence_ids = set(evidence["record_id"].astype(str))
    if catalog_ids != evidence_ids:
        raise ValueError("macro catalog and evidence record IDs must match")
    merged = catalog.merge(evidence, on="record_id", validate="one_to_one")
    for row in merged.to_dict("records"):
        hostname = (urlparse(str(row["source_url"])).hostname or "").lower()
        if not _is_official_domain(hostname):
            raise ValueError(f"macro source domain is not allowed: {hostname}")
        expected = str(row["expected_page_sha256"]).strip()
        if expected and not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("expected_page_sha256 must be blank or lowercase SHA-256")
        if not str(row["release_evidence_text"]).strip():
            raise ValueError("release_evidence_text must not be blank")
        if row["release_evidence_precision"] not in {"minute", "date"}:
            raise ValueError("release_evidence_precision must be minute or date")
        if not str(row["value_evidence_text"]).strip():
            raise ValueError("value_evidence_text must not be blank")
    return merged.to_dict("records")


def audit_macro_evidence(
    root: Path, catalog: pd.DataFrame, evidence: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, object]]:
    records = validate_evidence_contract(catalog, evidence)
    rows = []
    for record in records:
        cache_path = _cache_path(root, str(record["record_id"]))
        metadata_path = cache_path.with_suffix(".meta.json")
        issues: list[str] = []
        metadata: dict[str, object] = {}
        release_verified = False
        value_verified = False
        expected = str(record["expected_page_sha256"]).strip()
        if not expected:
            issues.append("page checksum is not locked")
        if not cache_path.exists() or not metadata_path.exists():
            issues.append("page or metadata missing")
        else:
            try:
                content = cache_path.read_bytes()
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                observed = hashlib.sha256(content).hexdigest()
                if metadata.get("sha256") != observed:
                    issues.append("checksum mismatch")
                if expected and observed != expected:
                    issues.append("checksum differs from locked evidence")
                if metadata.get("source_url") != record["source_url"]:
                    issues.append("source URL mismatch")
                if metadata.get("record_id") != record["record_id"]:
                    issues.append("record ID mismatch")
                retrieved = pd.to_datetime(
                    metadata.get("retrieved_at"), errors="raise", utc=True
                )
                release = pd.to_datetime(record["release_at"], errors="raise", utc=True)
                if retrieved < release:
                    issues.append("retrieved_at precedes release_at")
                visible_text = extract_visible_text(content)
                release_verified = _contains_evidence(
                    visible_text, str(record["release_evidence_text"])
                )
                value_verified = _contains_evidence(
                    visible_text, str(record["value_evidence_text"])
                )
                if not release_verified:
                    issues.append("release evidence text not found")
                if not value_verified:
                    issues.append("value evidence text not found")
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                issues.append("invalid page or metadata")
        rows.append(
            {
                "record_id": record["record_id"],
                "dimension": record["dimension"],
                "period": record["period"],
                "retrieved_at": metadata.get("retrieved_at", ""),
                "sha256": metadata.get("sha256", ""),
                "release_evidence_verified": release_verified,
                "release_evidence_precision": record[
                    "release_evidence_precision"
                ],
                "value_evidence_verified": value_verified,
                "current_page_status": "ready" if not issues else "blocked",
                "strict_point_in_time_status": record["strict_point_in_time_status"],
                "issues": "; ".join(dict.fromkeys(issues)),
            }
        )
    audit = pd.DataFrame(rows)
    ready = int(audit["current_page_status"].eq("ready").sum())
    summary = {
        "catalog_records": len(audit),
        "current_pages_ready": ready,
        "current_pages_blocked": int(len(audit) - ready),
        "release_evidence_verified": int(
            audit["release_evidence_verified"].sum()
        ),
        "minute_precision_release_evidence": int(
            (
                audit["release_evidence_verified"]
                & audit["release_evidence_precision"].eq("minute")
            ).sum()
        ),
        "date_precision_release_evidence": int(
            (
                audit["release_evidence_verified"]
                & audit["release_evidence_precision"].eq("date")
            ).sum()
        ),
        "value_evidence_verified": int(audit["value_evidence_verified"].sum()),
        "strict_point_in_time_verified": int(
            audit["strict_point_in_time_status"].eq("verified_snapshot").sum()
        ),
        "etf_returns_read": False,
        "regime_thresholds_constructed": False,
        "macro_evidence_gate": (
            "pass_current_page_evidence_only"
            if len(audit) == 12 and ready == 12
            else "blocked"
        ),
    }
    return audit, summary


def extract_visible_text(content: bytes) -> str:
    encoding = _detect_encoding(content)
    html = content.decode(encoding, errors="replace")
    parser = _VisibleTextParser()
    parser.feed(html)
    return _normalize_text(" ".join(parser.parts))


def _contains_evidence(visible_text: str, evidence: str) -> bool:
    return _normalize_text(evidence) in visible_text


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("\u3000", "")


def _detect_encoding(content: bytes) -> str:
    prefix = content[:8192]
    match = re.search(br"charset\s*=\s*['\"]?([a-zA-Z0-9_-]+)", prefix, re.I)
    if match:
        encoding = match.group(1).decode("ascii", errors="ignore").lower()
        if encoding in {"gb2312", "gbk"}:
            return "gb18030"
        if encoding:
            return encoding
    return "utf-8"


def _write_cache(
    cache_path: Path,
    content: bytes,
    record: dict[str, object],
    sha256: str,
) -> dict[str, object]:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
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


def _cache_valid(cache_path: Path, source_url: str, expected: str) -> bool:
    metadata_path = cache_path.with_suffix(".meta.json")
    if not cache_path.exists() or not metadata_path.exists():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        observed = hashlib.sha256(cache_path.read_bytes()).hexdigest()
        return (
            metadata["source_url"] == source_url
            and metadata["sha256"] == observed
            and (not expected or expected == observed)
        )
    except (KeyError, OSError, json.JSONDecodeError):
        return False


def _cache_path(root: Path, record_id: str) -> Path:
    return root / "data" / "raw" / "macro_release_pages" / f"{record_id}.html"


def _is_official_domain(hostname: str) -> bool:
    return hostname == "stats.gov.cn" or hostname.endswith(".stats.gov.cn") or (
        hostname == "pbc.gov.cn" or hostname.endswith(".pbc.gov.cn")
    )


def _fetch_result(
    record: dict[str, object],
    status: str,
    cache_path: Path | None,
    *,
    metadata: dict[str, object] | None = None,
    error: str = "",
) -> dict[str, object]:
    return {
        "record_id": record["record_id"],
        "status": status,
        "cache_path": str(cache_path) if cache_path else "",
        "retrieved_at": (metadata or {}).get("retrieved_at", ""),
        "sha256": (metadata or {}).get("sha256", ""),
        "bytes": (metadata or {}).get("bytes", 0),
        "error": error,
    }
