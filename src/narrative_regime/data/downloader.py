from __future__ import annotations

import hashlib
import json
import os
import random
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from narrative_regime.data.models import (
    FetchRequest,
    FetchResult,
    MarketDataProvider,
)
from narrative_regime.data.validation import (
    market_frame_coverage_issues,
    normalize_market_frame,
)


class DownloadManager:
    def __init__(
        self,
        root: Path,
        providers: Iterable[MarketDataProvider],
        *,
        attempts: int = 3,
        base_delay_seconds: float = 2.0,
        inter_symbol_delay_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        self.root = root
        self.providers = list(providers)
        if not self.providers:
            raise ValueError("at least one provider is required")
        self.attempts = attempts
        self.base_delay_seconds = base_delay_seconds
        self.inter_symbol_delay_seconds = inter_symbol_delay_seconds
        self.sleep = sleep

    def download_many(
        self,
        requests: Iterable[FetchRequest],
        *,
        refresh: bool = False,
    ) -> list[FetchResult]:
        results = []
        for index, request in enumerate(requests):
            if index:
                self.sleep(self.inter_symbol_delay_seconds)
            results.append(self.download_one(request, refresh=refresh))
        return results

    def download_one(
        self,
        request: FetchRequest,
        *,
        refresh: bool = False,
    ) -> FetchResult:
        errors: list[str] = []
        partial_results: list[FetchResult] = []
        for provider in self.providers:
            cache_path = self._cache_path(provider.name, request.symbol)
            if not refresh and self._cache_covers(cache_path, request):
                result = FetchResult(
                    symbol=request.symbol,
                    provider=provider.name,
                    status="cached",
                    rows=self._row_count(cache_path),
                    cache_path=cache_path,
                )
                self._append_result(result, request)
                return result

            for attempt in range(1, self.attempts + 1):
                try:
                    fresh = provider.fetch(request)
                    combined = self._merge_with_cache(cache_path, fresh)
                    coverage_issues = market_frame_coverage_issues(
                        combined,
                        expected_start=request.start,
                        expected_end=request.end,
                    )
                    cache_status = "partial" if coverage_issues else "validated"
                    self._write_cache(
                        cache_path,
                        combined,
                        request,
                        provider.name,
                        status=cache_status,
                        coverage_issues=coverage_issues,
                    )
                    result = FetchResult(
                        symbol=request.symbol,
                        provider=provider.name,
                        status="partial" if coverage_issues else "downloaded",
                        rows=len(combined),
                        cache_path=cache_path,
                        coverage_issues=coverage_issues,
                    )
                    self._append_attempt(
                        request=request,
                        provider=provider.name,
                        attempt=attempt,
                        status=result.status,
                        rows=len(combined),
                        coverage_issues=coverage_issues,
                    )
                    if not coverage_issues:
                        self._append_result(result, request)
                        return result

                    partial_results.append(result)
                    errors.append(
                        f"{provider.name} returned partial history: "
                        + "; ".join(coverage_issues)
                    )
                    break
                except Exception as exc:  # provider failures must not abort the batch
                    message = (
                        f"{provider.name} attempt {attempt}/{self.attempts}: "
                        f"{type(exc).__name__}: {exc}"
                    )
                    errors.append(message)
                    self._append_attempt(
                        request=request,
                        provider=provider.name,
                        attempt=attempt,
                        status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                    if attempt < self.attempts:
                        delay = self.base_delay_seconds * (2 ** (attempt - 1))
                        self.sleep(delay + random.uniform(0, delay * 0.1))

        if partial_results:
            best = max(partial_results, key=lambda item: item.rows)
            result = FetchResult(
                symbol=best.symbol,
                provider=best.provider,
                status="partial",
                rows=best.rows,
                cache_path=best.cache_path,
                error=" | ".join(errors),
                coverage_issues=best.coverage_issues,
            )
            self._append_result(result, request)
            return result

        result = FetchResult(
            symbol=request.symbol,
            provider="none",
            status="failed",
            rows=0,
            cache_path=None,
            error=" | ".join(errors),
        )
        self._append_result(result, request)
        return result

    def _cache_path(self, provider: str, symbol: str) -> Path:
        return self.root / "data" / "raw" / provider / f"{symbol}.csv"

    @staticmethod
    def _metadata_path(cache_path: Path) -> Path:
        return cache_path.with_suffix(".meta.json")

    def _cache_covers(self, cache_path: Path, request: FetchRequest) -> bool:
        metadata_path = self._metadata_path(cache_path)
        if not cache_path.exists() or not metadata_path.exists():
            return False
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            return (
                metadata["requested_start"] <= request.start.isoformat()
                and metadata["requested_end"] >= request.end.isoformat()
                and metadata["status"] == "validated"
                and metadata["sha256"] == _sha256(cache_path)
            )
        except (KeyError, json.JSONDecodeError, OSError):
            return False

    @staticmethod
    def _row_count(cache_path: Path) -> int:
        return max(sum(1 for _ in cache_path.open(encoding="utf-8")) - 1, 0)

    @staticmethod
    def _merge_with_cache(cache_path: Path, fresh: pd.DataFrame) -> pd.DataFrame:
        frames = [fresh]
        if cache_path.exists():
            frames.insert(0, pd.read_csv(cache_path))
        return normalize_market_frame(pd.concat(frames, ignore_index=True))

    def _write_cache(
        self,
        cache_path: Path,
        frame: pd.DataFrame,
        request: FetchRequest,
        provider: str,
        *,
        status: str,
        coverage_issues: tuple[str, ...],
    ) -> None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".csv",
            dir=cache_path.parent,
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            frame.to_csv(handle, index=False, date_format="%Y-%m-%d")
        os.replace(temporary_path, cache_path)

        metadata = {
            "provider": provider,
            "symbol": request.symbol,
            "requested_start": request.start.isoformat(),
            "requested_end": request.end.isoformat(),
            "observed_start": frame["date"].min().date().isoformat(),
            "observed_end": frame["date"].max().date().isoformat(),
            "rows": len(frame),
            "sha256": _sha256(cache_path),
            "status": status,
            "coverage_issues": list(coverage_issues),
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
        metadata_path = self._metadata_path(cache_path)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".json",
            dir=cache_path.parent,
            delete=False,
        ) as handle:
            temporary_metadata = Path(handle.name)
            json.dump(metadata, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
        os.replace(temporary_metadata, metadata_path)

    def _append_attempt(
        self,
        *,
        request: FetchRequest,
        provider: str,
        attempt: int,
        status: str,
        rows: int = 0,
        error: str | None = None,
        coverage_issues: tuple[str, ...] = (),
    ) -> None:
        self._append_manifest_record(
            {
                "event": "provider_attempt",
                "request": self._request_record(request),
                "provider": provider,
                "attempt": attempt,
                "status": status,
                "rows": rows,
                "error": error,
                "coverage_issues": list(coverage_issues),
            }
        )

    def _append_result(self, result: FetchResult, request: FetchRequest) -> None:
        result_record = asdict(result)
        result_record["cache_path"] = (
            str(result.cache_path) if result.cache_path else None
        )
        result_record["coverage_issues"] = list(result.coverage_issues)
        self._append_manifest_record(
            {
                "event": "symbol_result",
                "request": self._request_record(request),
                "result": result_record,
            }
        )

    @staticmethod
    def _request_record(request: FetchRequest) -> dict[str, str]:
        return {
            "symbol": request.symbol,
            "start": request.start.isoformat(),
            "end": request.end.isoformat(),
        }

    def _append_manifest_record(self, record: dict[str, object]) -> None:
        manifest_path = self.root / "data" / "manifests" / "downloads.jsonl"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            **record,
        }
        with manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
