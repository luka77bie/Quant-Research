from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from narrative_regime.data.audit import audit_provider_cache
from narrative_regime.data.validation import normalize_market_frame


@dataclass(frozen=True)
class CommonSampleResult:
    sample: pd.DataFrame
    panel_audit: pd.DataFrame
    cache_audit: pd.DataFrame

    @property
    def ready(self) -> bool:
        return self.panel_audit["status"].isin({"ready", "not_yet_listed"}).all()


def validate_availability_metadata(
    universe: pd.DataFrame,
    sources: pd.DataFrame,
) -> None:
    universe_required = {"symbol", "available_from"}
    source_required = {
        "symbol",
        "listing_date",
        "venue",
        "source",
        "source_url",
        "verified_at",
    }
    universe_missing = sorted(universe_required - set(universe.columns))
    source_missing = sorted(source_required - set(sources.columns))
    if universe_missing:
        raise ValueError(
            f"universe missing availability columns: {', '.join(universe_missing)}"
        )
    if source_missing:
        raise ValueError(
            f"availability sources missing columns: {', '.join(source_missing)}"
        )

    universe_symbols = universe["symbol"].astype(str)
    source_symbols = sources["symbol"].astype(str)
    if universe_symbols.duplicated().any() or source_symbols.duplicated().any():
        raise ValueError("availability inputs contain duplicate symbols")
    if set(universe_symbols) != set(source_symbols):
        missing_sources = sorted(set(universe_symbols) - set(source_symbols))
        unexpected_sources = sorted(set(source_symbols) - set(universe_symbols))
        raise ValueError(
            "availability symbol mismatch: "
            f"missing={','.join(missing_sources) or '-'} "
            f"unexpected={','.join(unexpected_sources) or '-'}"
        )

    universe_dates = pd.Series(
        pd.to_datetime(universe["available_from"], errors="raise").dt.date.to_numpy(),
        index=universe_symbols,
    )
    source_dates = pd.Series(
        pd.to_datetime(sources["listing_date"], errors="raise").dt.date.to_numpy(),
        index=source_symbols,
    )
    mismatches = universe_dates[universe_dates != source_dates]
    if not mismatches.empty:
        raise ValueError(
            "available_from differs from verified listing_date: "
            + ", ".join(mismatches.index)
        )
    if sources[["venue", "source", "source_url", "verified_at"]].isna().any().any():
        raise ValueError("availability source evidence contains missing values")


def build_common_sample(
    *,
    root: Path,
    provider: str,
    universe: pd.DataFrame,
    start: date,
    end: date,
    reference_symbol: str,
) -> CommonSampleResult:
    """Build a dynamic-universe panel on one reference ETF's trading dates."""
    if start > end:
        raise ValueError("start must be on or before end")
    symbols = universe["symbol"].astype(str).tolist()
    if reference_symbol not in symbols:
        raise ValueError("reference symbol is not in the universe")

    cache_audit = audit_provider_cache(root, provider, symbols)
    cache_status = cache_audit.set_index("symbol")["audit_status"]
    if cache_status[reference_symbol] != "ready":
        raise ValueError(
            f"reference symbol cache is not ready: {reference_symbol} "
            f"({cache_status[reference_symbol]})"
        )

    reference = _read_cache(root, provider, reference_symbol)
    reference_dates = pd.DatetimeIndex(
        reference.loc[
            reference["date"].between(pd.Timestamp(start), pd.Timestamp(end)), "date"
        ]
    )
    if reference_dates.empty:
        raise ValueError("reference symbol has no observations in the requested range")

    sample_frames: list[pd.DataFrame] = []
    audit_records: list[dict[str, object]] = []
    for row in universe.to_dict(orient="records"):
        symbol = str(row["symbol"])
        listed = pd.Timestamp(row["available_from"])
        eligible_from = max(pd.Timestamp(start), listed)
        expected_dates = reference_dates[reference_dates >= eligible_from]
        if expected_dates.empty:
            audit_records.append(
                _audit_record(
                    symbol=symbol,
                    available_from=listed,
                    status="not_yet_listed",
                )
            )
            continue

        symbol_cache_status = str(cache_status[symbol])
        if symbol_cache_status != "ready":
            cache_issue = cache_audit.set_index("symbol").loc[symbol, "issues"]
            audit_records.append(
                _audit_record(
                    symbol=symbol,
                    available_from=listed,
                    status=f"cache_{symbol_cache_status}",
                    expected_rows=len(expected_dates),
                    issues=str(cache_issue),
                )
            )
            continue

        frame = _read_cache(root, provider, symbol)
        eligible = frame[
            frame["date"].between(eligible_from, pd.Timestamp(end))
        ].copy()
        actual_dates = pd.DatetimeIndex(eligible["date"])
        missing_dates = expected_dates.difference(actual_dates)
        unexpected_dates = actual_dates.difference(expected_dates)
        issues: list[str] = []
        if not missing_dates.empty:
            issues.append(f"{len(missing_dates)} missing reference trading dates")
        if not unexpected_dates.empty:
            issues.append(f"{len(unexpected_dates)} non-reference trading dates")
        status = "ready" if not issues else "misaligned"
        audit_records.append(
            _audit_record(
                symbol=symbol,
                available_from=listed,
                status=status,
                observed_start=(actual_dates.min() if not actual_dates.empty else None),
                observed_end=(actual_dates.max() if not actual_dates.empty else None),
                expected_rows=len(expected_dates),
                observed_rows=len(actual_dates),
                missing_dates=len(missing_dates),
                unexpected_dates=len(unexpected_dates),
                issues="; ".join(issues),
            )
        )
        if status == "ready":
            eligible.insert(1, "symbol", symbol)
            eligible["asset_group"] = str(row.get("asset_group", ""))
            eligible["source_provider"] = provider
            sample_frames.append(eligible)

    panel_audit = pd.DataFrame(audit_records)
    if not panel_audit["status"].isin({"ready", "not_yet_listed"}).all():
        sample = pd.DataFrame()
    elif not sample_frames:
        sample = pd.DataFrame()
    else:
        sample = pd.concat(sample_frames, ignore_index=True)
        sample = sample.sort_values(["date", "symbol"]).reset_index(drop=True)
    return CommonSampleResult(sample, panel_audit, cache_audit)


def _read_cache(root: Path, provider: str, symbol: str) -> pd.DataFrame:
    path = root / "data" / "raw" / provider / f"{symbol}.csv"
    return normalize_market_frame(pd.read_csv(path))


def _audit_record(
    *,
    symbol: str,
    available_from: pd.Timestamp,
    status: str,
    observed_start: pd.Timestamp | None = None,
    observed_end: pd.Timestamp | None = None,
    expected_rows: int = 0,
    observed_rows: int = 0,
    missing_dates: int = 0,
    unexpected_dates: int = 0,
    issues: str = "",
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "available_from": available_from.date().isoformat(),
        "status": status,
        "observed_start": (
            observed_start.date().isoformat() if observed_start is not None else ""
        ),
        "observed_end": (
            observed_end.date().isoformat() if observed_end is not None else ""
        ),
        "expected_rows": expected_rows,
        "observed_rows": observed_rows,
        "missing_dates": missing_dates,
        "unexpected_dates": unexpected_dates,
        "issues": issues,
    }
