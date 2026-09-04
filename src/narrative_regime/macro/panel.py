from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from narrative_regime.macro.discovery import SOURCE_FAMILIES

LEDGER_COLUMNS = {
    "record_id",
    "source_family",
    "period",
    "release_at",
    "release_timing_precision",
    "headline_value",
    "article_status",
}


@dataclass(frozen=True)
class MacroPanelResult:
    panel: pd.DataFrame
    state_counts: pd.DataFrame
    summary: dict[str, object]


def build_macro_panel(
    ledger: pd.DataFrame, protocol: dict[str, object]
) -> MacroPanelResult:
    """Build a return-blind chronology from validated publication records."""
    _validate_protocol(protocol)
    records = _validate_ledger(ledger, protocol)
    sample = protocol["sample"]
    periods = pd.period_range(
        str(sample["start_period"]), str(sample["end_period"]), freq="M"
    ).astype(str)
    panel = pd.DataFrame({"period": periods})

    family_prefixes = {
        "nbs_pmi": "pmi",
        "nbs_cpi": "cpi_yoy",
        "pbc_m2": "m2_yoy",
    }
    for family, prefix in family_prefixes.items():
        selected = records.loc[
            records["source_family"].eq(family),
            [
                "period",
                "record_id",
                "headline_value",
                "release_at",
                "release_timing_precision",
                "article_status",
            ],
        ].copy()
        selected["available_after"] = selected.apply(_available_after, axis=1)
        selected = selected.rename(
            columns={
                "record_id": f"{prefix}_record_id",
                "headline_value": prefix,
                "release_at": f"{prefix}_release_at",
                "release_timing_precision": f"{prefix}_timing_precision",
                "article_status": f"{prefix}_article_status",
                "available_after": f"{prefix}_available_after",
            }
        )
        panel = panel.merge(selected, on="period", how="left", validate="one_to_one")

    ready_columns = [
        "pmi_article_status",
        "cpi_yoy_article_status",
        "m2_yoy_article_status",
    ]
    panel["panel_ready"] = panel[ready_columns].eq("ready").all(axis=1)
    available_columns = [
        "pmi_available_after",
        "cpi_yoy_available_after",
        "m2_yoy_available_after",
    ]
    panel["panel_available_after"] = panel[available_columns].max(axis=1)

    panel["growth_state"] = panel["pmi"].map(_growth_state)
    panel["cpi_yoy_change_3m"] = panel["cpi_yoy"].diff(3)
    panel["inflation_state"] = panel["cpi_yoy_change_3m"].map(
        lambda value: _direction_state(value, "falling", "stable", "rising")
    )
    panel["m2_yoy_change_3m"] = panel["m2_yoy"].diff(3)
    panel["liquidity_state"] = panel["m2_yoy_change_3m"].map(
        lambda value: _direction_state(
            value, "decelerating", "stable", "accelerating"
        )
    )
    panel.loc[~panel["panel_ready"], "panel_available_after"] = pd.NaT

    state_counts = _state_counts(panel, int(protocol["minimum_state_observations"]))
    dimensions = {}
    for dimension in ("growth", "inflation", "liquidity"):
        selected = state_counts[state_counts["dimension"].eq(dimension)]
        dimensions[dimension] = {
            "observed_states": int(len(selected)),
            "reportable_states": int(selected["reportable"].sum()),
            "counts": {
                str(row["state"]): int(row["observations"])
                for row in selected.to_dict("records")
            },
        }
    gate = all(item["reportable_states"] >= 2 for item in dimensions.values())
    summary: dict[str, object] = {
        "expected_periods": len(panel),
        "panel_ready_periods": int(panel["panel_ready"].sum()),
        "panel_incomplete_periods": int((~panel["panel_ready"]).sum()),
        "dimensions": dimensions,
        "minimum_state_observations": int(protocol["minimum_state_observations"]),
        "combined_states_constructed": False,
        "etf_returns_read": False,
        "macro_panel_gate": "pass" if gate else "blocked",
    }
    return MacroPanelResult(panel=panel, state_counts=state_counts, summary=summary)


def _validate_protocol(protocol: dict[str, object]) -> None:
    if protocol.get("protocol_version") != 1:
        raise ValueError("unsupported macro regime protocol version")
    if protocol.get("combined_states_permitted") is not False:
        raise ValueError("combined states must remain disabled at this stage")
    if protocol.get("etf_returns_permitted") is not False:
        raise ValueError("ETF returns must remain disabled at this stage")
    if int(protocol.get("minimum_state_observations", 0)) < 1:
        raise ValueError("minimum_state_observations must be positive")
    dimensions = protocol.get("dimensions")
    if not isinstance(dimensions, dict):
        raise ValueError("protocol dimensions are required")
    families = {
        str(spec.get("source_family"))
        for spec in dimensions.values()
        if isinstance(spec, dict)
    }
    if families != set(SOURCE_FAMILIES):
        raise ValueError("protocol must use exactly the three registered families")


def _validate_ledger(
    ledger: pd.DataFrame, protocol: dict[str, object]
) -> pd.DataFrame:
    missing = sorted(LEDGER_COLUMNS - set(ledger.columns))
    if missing:
        raise ValueError(f"macro article ledger missing columns: {', '.join(missing)}")
    records = ledger.copy()
    if records["record_id"].duplicated().any():
        raise ValueError("macro article ledger contains duplicate record IDs")
    if records.duplicated(["source_family", "period"]).any():
        raise ValueError("macro article ledger contains duplicate family periods")
    if set(records["source_family"]) != set(SOURCE_FAMILIES):
        raise ValueError("macro article ledger source families are incomplete")
    expected_missing = set(protocol["sample"]["expected_missing_record_ids"])
    observed_missing = set(
        records.loc[records["article_status"].ne("ready"), "record_id"]
    )
    if observed_missing != expected_missing:
        raise ValueError("article ledger missing records differ from frozen protocol")
    records["headline_value"] = pd.to_numeric(
        records["headline_value"], errors="coerce"
    )
    invalid_values = records["article_status"].eq("ready") & records[
        "headline_value"
    ].isna()
    if invalid_values.any():
        raise ValueError("article-ready ledger records must have numeric values")
    return records


def _available_after(row: pd.Series) -> pd.Timestamp:
    if row["article_status"] != "ready":
        return pd.NaT
    precision = row["release_timing_precision"]
    if precision == "minute":
        return pd.to_datetime(row["release_at"], utc=True, errors="raise")
    if precision == "date":
        local_date = pd.Timestamp(row["release_at"]).tz_localize("Asia/Shanghai")
        return (local_date + pd.Timedelta(days=1)).tz_convert("UTC")
    raise ValueError(f"unsupported release timing precision: {precision}")


def _growth_state(value: float) -> str | None:
    if pd.isna(value):
        return None
    if value < 50:
        return "contraction"
    if value > 50:
        return "expansion"
    return "neutral"


def _direction_state(
    value: float, negative: str, zero: str, positive: str
) -> str | None:
    if pd.isna(value):
        return None
    if value < 0:
        return negative
    if value > 0:
        return positive
    return zero


def _state_counts(panel: pd.DataFrame, minimum: int) -> pd.DataFrame:
    rows = []
    for dimension in ("growth", "inflation", "liquidity"):
        states = panel[f"{dimension}_state"].where(panel["panel_ready"])
        counts = states.value_counts()
        run_ids = states.ne(states.shift()).cumsum()
        runs = (
            pd.DataFrame({"state": states, "run_id": run_ids})
            .dropna(subset=["state"])
            .groupby(["state", "run_id"], as_index=False)
            .size()
        )
        for state, observations in counts.items():
            state_runs = runs.loc[runs["state"].eq(state), "size"]
            rows.append(
                {
                    "dimension": dimension,
                    "state": state,
                    "observations": int(observations),
                    "episodes": int(len(state_runs)),
                    "median_episode_months": float(state_runs.median()),
                    "maximum_episode_months": int(state_runs.max()),
                    "minimum_observations": minimum,
                    "reportable": int(observations) >= minimum,
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["dimension", "state"], ignore_index=True
    )
