# Data Gate Status: 2026-09-04

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
- The full Study 02 catalog caches and validates all 287 available official
  articles. PMI passes 96/96, CPI passes 96/96, and M2 passes 95/96. The missing
  January 2025 national M2 source remains explicit.

## Current Macro Gate

The full current-page article-validation gate passes. All 287 available pages
have matching record IDs, URLs, and checksums; their titles, statistical months,
release timing, and headline values validate. Two records retain date-only
timing rather than fabricated intraday precision. January 2025 national M2 is
the sole source gap and is not filled from a regional or retrospective series.

All records remain `provisional_no_snapshot`: current official pages support a
publication-time reconstruction but do not prove that page contents are
unchanged historical vintages. The next permitted task is to freeze macro
transformations, availability rules, and release lags without ETF outcomes.
That contract and return-blind panel now pass their audit: 95/96 months are
complete, the January 2025 M2 gap is not filled, and each dimension has two
reportable states with at least eight observations. ETF payoff joins remain
prohibited until the payoff-atlas comparison and reporting protocol is frozen.

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
