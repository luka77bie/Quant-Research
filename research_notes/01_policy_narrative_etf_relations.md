# Research Note 01: Do PBOC Policy Narratives Explain ETF Returns?

## Decision in One Sentence

Stop before portfolio construction: the full adjusted grid produces zero
narrative candidates after small-sample uncertainty and multiplicity correction.

## Why This Matters

Policy reports may reveal changes in accommodation, restraint, risk control,
exchange-rate stability, and structural support before those changes are fully
reflected across equity, bond, commodity, sector, and overseas ETFs. If that
information survives momentum and volatility controls, it could improve a
systematic ETF research process. If it does not, a strategy researcher should
avoid adding a fragile text layer to an adequate momentum baseline.

## Data and Timing

The study audits 18 ETFs on a dynamic listing-date universe from 2018 through
July 2026. Tencent qfq histories pass a strict `510300` reference-calendar
audit, including explicit verified no-trade dates. Thirty-two official PBOC
quarterly reports from 2018 through 2025 are checksum-locked and parsed with one
deterministic policy-section rule.

All report files remain publication-time reconstructions because matching
historical snapshots have not been established. Results therefore cannot be
called a strict point-in-time backtest. Three pre-specified activation rules use
24-hour, 48-hour, and next-month delays.

## Measurement and Method

A return-blind literal lexicon creates 19 diagnostics. Eleven non-redundant
primary features enter the adjusted stage. The full grid covers three timing
rules and 5-, 20-, and 60-session outcomes.

Each primary model includes one narrative feature, the matching document-length
control, lagged MOM60, lagged 20-session volatility, and asset-group fixed
effects. Uncertainty is clustered by the quarterly report event. All 99 pooled
tests are adjusted together with Benjamini-Hochberg q-values; no feature,
timing, or horizon is selected after inspection.

## Results

The market-relation audit accounts for all 5,184 planned
event-timing-window-ETF combinations. It retains 4,874 outcomes and gives each
of 310 exclusions a named reason. No lagged control uses activation-day or
future information.

All 99 pooled models, 594 asset-group descriptive models, and 99 dispersion
models pass their numerical gates. No pooled or dispersion q-value is at or
below 0.10. The closest pooled result has standardized beta -0.262 and nominal
p-value 0.00102, but its q-value is 0.10099 and therefore fails the frozen
threshold. Its magnitude is also much smaller under the 24- and 48-hour timing
rules than under next-month activation.

## Portfolio Interpretation

The pipeline can measure policy language reproducibly, but this sample does not
justify choosing a narrative feature or building a narrative-aware ETF
portfolio. The appropriate decision is to retain frozen MOM60 as the benchmark
and stop reusing these 32 reports for model selection.

The broader question of whether a validated narrative signal works only in
certain macro regimes remains unanswered. The study stops before conditional
interactions because fitting them after weak unconditional evidence would add a
large post-selection surface to an already small sample.

## What This Study Demonstrates

- Resumable multi-provider data engineering with visible failures.
- Dynamic ETF eligibility and suspension-aware calendar auditing.
- Official-document provenance, deterministic text parsing, and delay controls.
- Frozen benchmarks, complete specification reporting, clustered uncertainty,
  and multiplicity correction.
- A willingness to reject an attractive idea when evidence is insufficient.

## Next Independent Test

Build a return-blind China macro-regime chronology from timestamped growth,
inflation, and liquidity data, then study ETF-group payoffs without tuning
another narrative rule on the exhausted report sample.

## Reproduction

Commands, configs, manifests, and technical reports are linked from the root
README. The formal adjusted run is tied to clean implementation commit
`7ebd9b2`; the final report records the protocol amendment and stop decision.

## Interview Summary

I tested whether PBOC policy language adds information beyond ETF momentum and
market controls. The hardest problem was not modeling but point-in-time document
and ETF data provenance. I froze 11 features, three delays, and three horizons
instead of choosing the best result. No adjusted relationship survived the
complete multiplicity correction, with the closest q-value at 0.10099. I
therefore stopped the narrative strategy and moved the next study to an
independent, return-blind macro-regime design.
