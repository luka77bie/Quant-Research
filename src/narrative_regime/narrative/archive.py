from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

SOURCE_COLUMNS = {
    "source_id",
    "publisher",
    "allowed_domain",
    "document_type",
    "availability_delay_hours",
    "revision_policy",
}
CATALOG_COLUMNS = {
    "record_id",
    "source_id",
    "title",
    "period_end",
    "published_at",
    "publication_time_precision",
    "index_url",
    "document_url",
    "expected_document_sha256",
    "availability_evidence",
    "historical_snapshot_url",
    "historical_snapshot_sha256",
}
RECORD_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]*$")


def validate_catalog(catalog: pd.DataFrame, sources: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize a manually reviewed narrative document catalog."""
    _require_columns(sources, SOURCE_COLUMNS, "source registry")
    _require_columns(catalog, CATALOG_COLUMNS, "narrative catalog")
    if sources["source_id"].duplicated().any():
        raise ValueError("source registry contains duplicate source_id values")
    if catalog["record_id"].duplicated().any():
        raise ValueError("narrative catalog contains duplicate record_id values")
    if catalog["document_url"].duplicated().any():
        raise ValueError("narrative catalog contains duplicate document_url values")
    if not catalog["record_id"].astype(str).str.match(RECORD_ID_PATTERN).all():
        raise ValueError(
            "record_id must contain lowercase letters, digits, and underscores"
        )

    frame = catalog.merge(
        sources,
        on="source_id",
        how="left",
        validate="many_to_one",
        indicator=True,
    )
    if frame["_merge"].ne("both").any():
        unknown = sorted(frame.loc[frame["_merge"].ne("both"), "source_id"].unique())
        raise ValueError(
            f"catalog contains unknown source_id values: {', '.join(unknown)}"
        )
    frame = frame.drop(columns="_merge")
    if frame["document_type"].ne("pdf").any():
        raise ValueError("pilot archive supports only PDF documents")
    if frame["publication_time_precision"].ne("second").any():
        raise ValueError("published_at must have second-level precision")
    if frame["availability_evidence"].ne("official_timestamped_index").any():
        raise ValueError("catalog records require an official timestamped index")
    if not frame["expected_document_sha256"].astype(str).str.fullmatch(
        r"[0-9a-f]{64}"
    ).all():
        raise ValueError("expected_document_sha256 must be a lowercase SHA-256")

    frame["period_end"] = pd.to_datetime(
        frame["period_end"], errors="raise"
    ).dt.normalize()
    frame["published_at"] = pd.to_datetime(
        frame["published_at"], errors="raise", utc=True
    )
    if frame.duplicated(["source_id", "period_end"]).any():
        raise ValueError("catalog contains duplicate source-period records")
    now = pd.Timestamp.now(tz="UTC")
    if (frame["published_at"] > now).any():
        raise ValueError("published_at must not be in the future")
    delays = pd.to_numeric(frame["availability_delay_hours"], errors="raise")
    if (delays < 0).any():
        raise ValueError("availability_delay_hours must not be negative")
    frame["available_at"] = frame["published_at"] + pd.to_timedelta(delays, unit="h")
    if (frame["period_end"].dt.date >= frame["published_at"].dt.date).any():
        raise ValueError("period_end must precede published_at")

    for row in frame.itertuples(index=False):
        _validate_official_url(row.index_url, row.allowed_domain, "index_url")
        _validate_official_url(row.document_url, row.allowed_domain, "document_url")
        snapshot = str(row.historical_snapshot_url).strip()
        if snapshot and snapshot.lower() != "nan":
            _validate_https_url(snapshot, "historical_snapshot_url")
            snapshot_sha256 = str(row.historical_snapshot_sha256).strip()
            if not re.fullmatch(r"[0-9a-f]{64}", snapshot_sha256):
                raise ValueError(
                    "historical_snapshot_sha256 must be a lowercase SHA-256"
                )
    return frame.sort_values(["published_at", "record_id"]).reset_index(drop=True)


class NarrativeArchive:
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
        self, catalog: pd.DataFrame, sources: pd.DataFrame, *, refresh: bool = False
    ) -> pd.DataFrame:
        validated = validate_catalog(catalog, sources)
        results = [
            self.fetch_one(row, refresh=refresh)
            for row in validated.to_dict("records")
        ]
        return pd.DataFrame(results)

    def fetch_one(
        self, record: dict[str, object], *, refresh: bool = False
    ) -> dict[str, object]:
        cache_path = self._cache_path(
            str(record["source_id"]), str(record["record_id"])
        )
        if not refresh and self._cache_valid(
            cache_path,
            str(record["document_url"]),
            str(record["expected_document_sha256"]),
        ):
            metadata = json.loads(
                self._metadata_path(cache_path).read_text(encoding="utf-8")
            )
            return self._result(record, "cached", cache_path, metadata=metadata)

        errors = []
        for attempt in range(1, self.attempts + 1):
            try:
                response = self.session.get(
                    str(record["document_url"]), timeout=self.timeout_seconds
                )
                response.raise_for_status()
                content = response.content
                if not content.startswith(b"%PDF-"):
                    raise ValueError("response is not a PDF document")
                observed_sha256 = hashlib.sha256(content).hexdigest()
                if observed_sha256 != record["expected_document_sha256"]:
                    raise ValueError("download checksum differs from locked catalog")
                metadata = self._write_cache(cache_path, content, record)
                return self._result(record, "downloaded", cache_path, metadata=metadata)
            except Exception as exc:  # network failures remain visible per record
                errors.append(
                    f"attempt {attempt}/{self.attempts}: "
                    f"{type(exc).__name__}: {exc}"
                )
                if attempt < self.attempts:
                    self.sleep(self.base_delay_seconds * (2 ** (attempt - 1)))
        return self._result(record, "failed", None, error=" | ".join(errors))

    def _write_cache(
        self, cache_path: Path, content: bytes, record: dict[str, object]
    ) -> dict[str, object]:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cache_path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
        os.replace(temporary, cache_path)
        metadata = {
            "record_id": record["record_id"],
            "source_id": record["source_id"],
            "document_url": record["document_url"],
            "expected_document_sha256": record["expected_document_sha256"],
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "bytes": len(content),
            "sha256": _sha256(cache_path),
        }
        metadata_path = self._metadata_path(cache_path)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=cache_path.parent, delete=False
        ) as handle:
            temporary_metadata = Path(handle.name)
            json.dump(metadata, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
        os.replace(temporary_metadata, metadata_path)
        return metadata

    def _cache_valid(
        self, cache_path: Path, document_url: str, expected_sha256: str
    ) -> bool:
        metadata_path = self._metadata_path(cache_path)
        if not cache_path.exists() or not metadata_path.exists():
            return False
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            return (
                metadata["document_url"] == document_url
                and metadata["sha256"] == _sha256(cache_path)
                and metadata["sha256"] == expected_sha256
                and cache_path.read_bytes().startswith(b"%PDF-")
            )
        except (KeyError, json.JSONDecodeError, OSError):
            return False

    def _cache_path(self, source_id: str, record_id: str) -> Path:
        return self.root / "data" / "raw" / "narrative" / source_id / f"{record_id}.pdf"

    @staticmethod
    def _metadata_path(cache_path: Path) -> Path:
        return cache_path.with_suffix(".meta.json")

    @staticmethod
    def _result(
        record: dict[str, object],
        status: str,
        cache_path: Path | None,
        *,
        metadata: dict[str, object] | None = None,
        error: str | None = None,
    ) -> dict[str, object]:
        return {
            "record_id": record["record_id"],
            "source_id": record["source_id"],
            "status": status,
            "cache_path": str(cache_path) if cache_path else "",
            "retrieved_at": (metadata or {}).get("retrieved_at", ""),
            "sha256": (metadata or {}).get("sha256", ""),
            "bytes": (metadata or {}).get("bytes", 0),
            "error": error or "",
        }


def audit_archive(
    root: Path, catalog: pd.DataFrame, sources: pd.DataFrame
) -> pd.DataFrame:
    validated = validate_catalog(catalog, sources)
    rows = []
    for record in validated.to_dict("records"):
        cache_path = (
            root
            / "data"
            / "raw"
            / "narrative"
            / str(record["source_id"])
            / f"{record['record_id']}.pdf"
        )
        metadata_path = cache_path.with_suffix(".meta.json")
        issues = []
        metadata: dict[str, object] = {}
        if not cache_path.exists() or not metadata_path.exists():
            issues.append("document or metadata missing")
        else:
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                if metadata.get("sha256") != _sha256(cache_path):
                    issues.append("checksum mismatch")
                if metadata.get("sha256") != record["expected_document_sha256"]:
                    issues.append("checksum differs from locked catalog")
                if metadata.get("document_url") != record["document_url"]:
                    issues.append("document URL mismatch")
                if metadata.get("record_id") != record["record_id"]:
                    issues.append("record ID mismatch")
                if metadata.get("source_id") != record["source_id"]:
                    issues.append("source ID mismatch")
                if not cache_path.read_bytes().startswith(b"%PDF-"):
                    issues.append("invalid PDF signature")
                retrieved = pd.to_datetime(
                    metadata.get("retrieved_at"), errors="raise", utc=True
                )
                if retrieved < record["published_at"]:
                    issues.append("retrieved_at precedes published_at")
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, OSError):
                issues.append("invalid metadata")
        snapshot = str(record["historical_snapshot_url"]).strip()
        has_snapshot = bool(snapshot and snapshot.lower() != "nan")
        snapshot_matches = (
            has_snapshot
            and metadata.get("sha256") == record["historical_snapshot_sha256"]
        )
        status = "ready" if not issues else "blocked"
        rows.append(
            {
                "record_id": record["record_id"],
                "source_id": record["source_id"],
                "period_end": record["period_end"],
                "published_at": record["published_at"],
                "available_at": record["available_at"],
                "retrieved_at": metadata.get("retrieved_at", ""),
                "sha256": metadata.get("sha256", ""),
                "archive_status": status,
                "historical_snapshot": has_snapshot,
                "point_in_time_status": (
                    "verified"
                    if status == "ready" and snapshot_matches
                    else "provisional"
                    if status == "ready"
                    else "blocked"
                ),
                "issues": "; ".join(issues),
            }
        )
    return pd.DataFrame(rows)


def coverage_summary(audit: pd.DataFrame, *, start: str, end: str) -> dict[str, object]:
    expected = pd.date_range(start=start, end=end, freq=pd.offsets.QuarterEnd())
    ready_periods = set(
        pd.to_datetime(audit.loc[audit["archive_status"].eq("ready"), "period_end"])
    )
    missing = [
        date.date().isoformat() for date in expected if date not in ready_periods
    ]
    provisional = int(audit["point_in_time_status"].eq("provisional").sum())
    return {
        "expected_records": len(expected),
        "ready_records": len(expected) - len(missing),
        "coverage_ratio": (
            (len(expected) - len(missing)) / len(expected) if len(expected) else 0.0
        ),
        "missing_period_ends": missing,
        "provisional_records": provisional,
        "verified_point_in_time_records": int(
            audit["point_in_time_status"].eq("verified").sum()
        ),
        "modeling_gate": "pass" if not missing and provisional == 0 else "blocked",
    }


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{name} missing columns: {', '.join(missing)}")


def _validate_official_url(url: str, domain: str, field: str) -> None:
    _validate_https_url(url, field)
    hostname = (urlparse(str(url)).hostname or "").lower()
    allowed = str(domain).lower()
    if hostname != allowed and not hostname.endswith(f".{allowed}"):
        raise ValueError(f"{field} domain is not allowed: {hostname}")


def _validate_https_url(url: str, field: str) -> None:
    parsed = urlparse(str(url))
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(f"{field} must be an HTTPS URL")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
