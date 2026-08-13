# Data Gate Status: 2026-08-08

## Passed

- Official secondary-market listing dates are verified for all 18 ETFs.
- Tencent produced 18 validated, provider-isolated caches from 2018-01-01
  through 2026-07-31 using calendar-year requests.
- The strict `510300` reference-calendar audit passed for all 18 ETFs.
- Eight dual-source verified no-trade dates are explicit in the exception
  ledger and sample; there are no unverified missing dates.
- The qualified common sample contains 35,372 rows and 18 symbols.
- No selected asset is assumed tradable on a marked no-trade execution date.
- Frozen MOM60 ran from a clean commit at 10, 20, and 30 basis-point costs.
- The predecessor market-attention directionally reproduced for 2022-2023 and
  is frozen as a market-data control rather than narrative evidence.
- All 32 PBOC quarterly reports from 2018 through 2025 download reproducibly
  with locked checksums, exact displayed publication times, retrieval times,
  and conservative 24-hour delayed availability times.
- Deterministic PDF extraction passes for all 32 reports: 1,901 pages and
  1,323,999 non-whitespace characters, with no empty pages or replacement
  characters.
- The deterministic forward-looking policy-section parser passes for all 32
  reports, producing 88,768 non-whitespace characters with no duplicate section
  hashes.
- The frozen non-LLM diagnostic table covers all 32 quarters with 25 literal
  policy terms in five categories and 31 prior-quarter text comparisons. It
  reads no return data and creates no composite score.
- Three timing protocols map all 32 reports to the audited `510300` calendar:
  96 activation records, 6,243 protocol-session rows, and zero lookahead
  violations. No price or return values enter the timing stage.
- Stability diagnostics cover all 19 numeric policy features. All eight missing
  observations are expected first-quarter values; there are no unexpected
  missing values, infinities, or zero-variance features.
- The frozen market-relation audit accounts for all 5,184 planned
  report-protocol-window-symbol combinations. It retains 4,874 usable outcomes,
  logs 310 exclusions, and has zero lagged-control lookahead violations.
- The post-descriptive adjustment grid reports all 99 pooled models, 594
  asset-group coefficients, and 99 dispersion models with no numerical
  exclusions. All 198 multiplicity-adjusted primary and dispersion tests have
  q-values above 0.10.
- The return-blind Study 02 source pilot catalogs 12 official macro publication
  records across manufacturing PMI, CPI YoY, and M2 YoY. Eleven are original
  release pages and one is an official retrospective confirmation; all 12
  current URLs were reachable on 2026-08-08.

## Current Macro Blocker

The Study 02 current-page evidence gate passes. All 12 official pages are cached
locally with retrieval metadata and committed SHA-256 values. Exact normalized
visible-text fragments verify all 12 release-date or timestamp claims and all
12 values. Eleven timestamps have minute precision; the March 2023 M2 record
has date precision only and is conservatively available at end of day.

None of the 12 records has a locked contemporaneous snapshot, so strict
point-in-time status remains provisional. Macro-state construction and ETF
payoff joins remain blocked until full monthly coverage, transformations, and
release-lag rules are frozen.

The cross-year parser test now passes 9 of 9 official anchor pages: NBS PMI and
CPI for 2018, 2021, and 2025, plus PBOC M2 for 2018, 2021, and 2024. Each source
family uses one deterministic release-time and headline-value rule. Full monthly
catalog coverage, contemporaneous snapshots, transformations, and release-lag
rules remain open; ETF outcome joins are still prohibited.

## Previous Provider Failure

Eastmoney completed `510300` but then repeatedly closed connections for other
symbols. Yahoo was rate-limited. Both remain isolated optional fallbacks; neither
is required for the qualified sample.

BaoStock was also tested because it requires no token. It recognized ETF basic
information but returned zero K-line rows for `510300` under unadjusted, forward-
adjusted, and backward-adjusted requests, so it was rejected.

## Current Narrative Blocker

Catalog coverage and extraction quality now pass, but all 32 records remain
provisional because no contemporaneous historical snapshot with a matching
checksum has been established. Wayback requests timed out and exact Common
Crawl index requests returned gateway errors in the current environment; these
results leave snapshot feasibility unresolved and do not prove absence.

The strict point-in-time modeling gate therefore remains blocked. Extracted
text may be used only for a clearly labelled publication-time reconstruction
with signal-delay sensitivity. It may not support a strictly point-in-time
backtest or headline claim.

## Current Modeling Decision

The pre-model descriptive gate passes computationally, but it does not supply a
predictive claim. Only 12 of 66 primary feature-by-asset-group relationships
keep one Spearman sign across all nine delay-window specifications. Portfolio
construction and specification selection remain blocked. The next research
artifact must be frozen before any adjusted analysis and must treat the existing
descriptive outputs as already observed exploratory evidence.

The adjusted stage has now applied that protocol. Its closest pooled result has
`q=0.10099`, above the frozen 0.10 reference threshold; dispersion has minimum
`q=0.39365`. The candidate count is therefore zero. This is a modeling stop, not
a data-pipeline failure.
