# Narrative Timing Protocol Report v0.1

## Decision

The timing gate passes for all reports and protocols. The resulting daily
feature calendars may be used for pre-specified descriptive market analysis.
They remain exploratory because every source document is point-in-time
provisional.

## Frozen Protocols

All timestamps are compared in UTC after defining session opens at 09:30 in
`Asia/Shanghai`. Trading dates come only from the audited `510300` reference
calendar; price and return values are not read.

- `delay_24h`: use the catalog-derived `available_at`, currently publication
  plus 24 hours, then activate at the first session open on or after that time.
- `delay_48h`: use publication plus 48 hours, then activate at the first session
  open on or after that time.
- `next_month`: activate at the first reference session in the calendar month
  after the local `available_at` month.

For each protocol, a backward as-of join carries only the latest activated
report. Sessions before the first activation remain explicitly unavailable.

## Audit Result

| Check | Result |
| --- | ---: |
| Feature records | 32 |
| Timing protocols | 3 |
| Activation records | 96 |
| Reference sessions | 2,081 |
| Protocol-session rows | 6,243 |
| Lookahead violations | 0 |
| Price values used | No |
| Return data used | No |

The 24-hour and 48-hour rules activate on the same date for 20 of 32 reports.
For the remaining reports, 48-hour activation is one day later in eight cases,
three days later in three cases, and eight days later once because of the 2021
Lunar New Year closure. The largest effective-time-to-session wait is about
231 hours for 2023 Q4 under the 24-hour rule because of the 2024 holiday closure.

Activation ranges are 2018-05-14 through 2026-02-12 for 24 hours,
2018-05-14 through 2026-02-13 for 48 hours, and 2018-06-01 through 2026-03-02
for next month.

## Next Gate

1. Audit feature missingness, persistence, distribution, and cross-feature
   correlation under the frozen calendars.
2. Pre-specify descriptive forward windows and market controls before computing
   any feature-return relationship.
3. Report all frozen features and all three timing protocols; do not select a
   preferred delay from observed performance.
4. Keep this stage separate from portfolio construction and MOM60 integration.
