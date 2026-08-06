# Tencent Provider Qualification v0.1

## Decision

Tencent's adjusted K-line endpoint is accepted as the primary convenience
source for the frozen ETF baseline. It is not treated as an authoritative
licensed archive.

## Independent Overlap

The 2018-01-02 to 2026-07-31 `510300` comparison against the previously
validated AKShare-Eastmoney cache produced:

| Check | Result |
| --- | ---: |
| Rows per provider | 2,081 |
| Left-only / right-only dates | 0 / 0 |
| Adjusted-close MAE | 0.0000024 |
| Daily-return MAE | 0.00000023 |
| Daily-return correlation | 0.99999986 |
| Median volume ratio | 1.0 |

The reproducible `nrea compare-providers` command blocks qualification when
dates, returns, or volume units differ beyond committed thresholds.

## Corporate Actions

The Tencent series correctly keeps `510500` continuous across its official
2022-08-26 share split. Sina's current adjustment payload contains a transient
one-day factor at that boundary and would create false offsetting jumps if used
without repair. Sina therefore remains coverage evidence only.

## Operational Controls

- Each symbol is fetched in calendar-year chunks below the endpoint row cap.
- Caches merge by date, so a refresh cannot erase previously valid rows.
- Provider caches never splice automatically.
- Broad coverage checks run at download time; the exact reference-calendar
  audit remains mandatory before baseline execution.
