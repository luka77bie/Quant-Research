from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd

PROTOCOLS = ("delay_24h", "delay_48h", "next_month")
MARKET_TIMEZONE = "Asia/Shanghai"
SESSION_OPEN_HOUR = 9
SESSION_OPEN_MINUTE = 30


@dataclass(frozen=True)
class TimingJoinResult:
    schedule: pd.DataFrame
    calendar: pd.DataFrame
    summary: dict[str, object]


def build_timing_joins(
    features: pd.DataFrame,
    market_calendar: pd.DataFrame,
    *,
    reference_symbol: str = "510300",
) -> TimingJoinResult:
    """Map narrative features to audited market sessions under frozen delays."""
    _validate_features(features)
    sessions = _reference_sessions(market_calendar, reference_symbol)
    prepared = features.copy()
    prepared["published_at"] = pd.to_datetime(prepared["published_at"], utc=True)
    prepared["available_at"] = pd.to_datetime(prepared["available_at"], utc=True)
    prepared["period_end"] = pd.to_datetime(prepared["period_end"])
    prepared = prepared.sort_values("period_end").reset_index(drop=True)

    if prepared["available_at"].lt(prepared["published_at"]).any():
        raise ValueError("available_at must not precede published_at")
    if prepared["record_id"].duplicated().any():
        raise ValueError("features contain duplicate record_id values")

    schedule_rows = []
    for protocol in PROTOCOLS:
        previous_activation: pd.Timestamp | None = None
        for record in prepared.to_dict("records"):
            effective_at = _effective_at(record, protocol, sessions)
            eligible = sessions.loc[sessions["session_open_at"].ge(effective_at)]
            if eligible.empty:
                raise ValueError(
                    f"no reference session after {protocol} effective time for "
                    f"{record['record_id']}"
                )
            activation = eligible.iloc[0]
            activation_open = activation["session_open_at"]
            if (
                previous_activation is not None
                and activation_open <= previous_activation
            ):
                raise ValueError(f"non-increasing {protocol} activation schedule")
            schedule_rows.append(
                {
                    "protocol": protocol,
                    "record_id": record["record_id"],
                    "period_end": record["period_end"].date().isoformat(),
                    "published_at": record["published_at"],
                    "available_at": record["available_at"],
                    "effective_at": effective_at,
                    "activation_date": activation["date"].date().isoformat(),
                    "activation_open_at": activation_open,
                    "effective_to_activation_hours": (
                        activation_open - effective_at
                    ).total_seconds()
                    / 3600,
                    "point_in_time_status": record["point_in_time_status"],
                }
            )
            previous_activation = activation_open

    schedule = pd.DataFrame(schedule_rows)
    calendar = _build_asof_calendar(prepared, schedule, sessions)
    violations = _lookahead_violations(calendar)
    if violations:
        raise ValueError(f"timing calendar contains {violations} lookahead violations")
    summary = {
        "protocols": list(PROTOCOLS),
        "feature_records": len(prepared),
        "schedule_records": len(schedule),
        "reference_sessions": len(sessions),
        "calendar_records": len(calendar),
        "lookahead_violations": violations,
        "pre_feature_sessions": {
            protocol: int(
                calendar.loc[
                    calendar["protocol"].eq(protocol), "record_id"
                ].isna().sum()
            )
            for protocol in PROTOCOLS
        },
        "timing_gate": "pass",
        "price_values_used": False,
        "return_data_used": False,
        "research_use": "exploratory_only",
    }
    return TimingJoinResult(schedule, calendar, summary)


def _effective_at(
    record: dict[str, object],
    protocol: str,
    sessions: pd.DataFrame,
) -> pd.Timestamp:
    published_at = pd.Timestamp(record["published_at"])
    available_at = pd.Timestamp(record["available_at"])
    if protocol == "delay_24h":
        return available_at
    if protocol == "delay_48h":
        return published_at + timedelta(hours=48)
    if protocol == "next_month":
        available_local = available_at.tz_convert(MARKET_TIMEZONE)
        next_period = available_local.tz_localize(None).to_period("M") + 1
        session_local = sessions["session_open_at"].dt.tz_convert(MARKET_TIMEZONE)
        session_period = session_local.dt.tz_localize(None).dt.to_period("M")
        candidates = sessions.loc[
            session_period.eq(next_period), "session_open_at"
        ]
        if candidates.empty:
            raise ValueError(
                f"no reference session in month after available_at for "
                f"{record['record_id']}"
            )
        return candidates.iloc[0]
    raise AssertionError(f"unknown protocol: {protocol}")


def _reference_sessions(
    market_calendar: pd.DataFrame, reference_symbol: str
) -> pd.DataFrame:
    required = {"date", "symbol"}
    missing = sorted(required - set(market_calendar.columns))
    if missing:
        raise ValueError("market calendar missing columns: " + ", ".join(missing))
    selected = market_calendar.loc[
        market_calendar["symbol"].astype(str).eq(reference_symbol), ["date"]
    ].copy()
    if selected.empty:
        raise ValueError(f"reference symbol not found: {reference_symbol}")
    selected["date"] = pd.to_datetime(selected["date"])
    if selected["date"].duplicated().any():
        raise ValueError("reference calendar contains duplicate dates")
    selected = selected.sort_values("date").reset_index(drop=True)
    local_open = (
        selected["date"]
        + timedelta(hours=SESSION_OPEN_HOUR, minutes=SESSION_OPEN_MINUTE)
    ).dt.tz_localize(MARKET_TIMEZONE)
    selected["session_open_at"] = local_open.dt.tz_convert("UTC")
    return selected


def _build_asof_calendar(
    features: pd.DataFrame,
    schedule: pd.DataFrame,
    sessions: pd.DataFrame,
) -> pd.DataFrame:
    feature_columns = [
        column
        for column in features.columns
        if column not in {"period_end", "published_at", "available_at"}
    ]
    feature_values = features[feature_columns]
    protocol_frames = []
    for protocol in PROTOCOLS:
        activations = schedule.loc[
            schedule["protocol"].eq(protocol),
            [
                "record_id",
                "period_end",
                "published_at",
                "available_at",
                "effective_at",
                "activation_date",
                "activation_open_at",
            ],
        ].merge(feature_values, on="record_id", validate="one_to_one")
        frame = pd.merge_asof(
            sessions,
            activations.sort_values("activation_open_at"),
            left_on="session_open_at",
            right_on="activation_open_at",
            direction="backward",
            allow_exact_matches=True,
        )
        frame.insert(0, "protocol", protocol)
        frame["feature_available"] = frame["record_id"].notna()
        frame["feature_age_sessions"] = (
            frame.groupby("record_id", dropna=True).cumcount().where(
                frame["feature_available"]
            )
        )
        protocol_frames.append(frame)
    return pd.concat(protocol_frames, ignore_index=True)


def _lookahead_violations(calendar: pd.DataFrame) -> int:
    exposed = calendar.loc[calendar["feature_available"]]
    return int(
        exposed["session_open_at"].lt(exposed["activation_open_at"]).sum()
        + exposed["activation_open_at"].lt(exposed["effective_at"]).sum()
    )


def _validate_features(features: pd.DataFrame) -> None:
    required = {
        "record_id",
        "period_end",
        "published_at",
        "available_at",
        "point_in_time_status",
    }
    missing = sorted(required - set(features.columns))
    if missing:
        raise ValueError("features missing columns: " + ", ".join(missing))
    if features.empty:
        raise ValueError("features must contain at least one record")
