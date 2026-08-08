# Descriptive Narrative-Market Relation Report v0.1

## Decision

The frozen computation gate passes. The evidence gate does not support feature
selection, a predictive claim, or an ETF strategy. Most primary-feature signs
change across timing and horizon choices, while every source document remains a
provisional publication-time reconstruction.

## Frozen Scope

- Events: 32 quarterly PBOC reports from 2018 through 2025.
- Timing: 24-hour delay, 48-hour delay, and first session of the next month.
- Outcomes: 5, 20, and 60 `510300` reference-session forward returns.
- Universe: 18 dynamically eligible ETFs in six asset groups.
- Features: all 19 frozen numeric diagnostics; 11 have primary roles.
- Estimators: unadjusted Pearson and Spearman correlation.
- Prohibited: inference, delay or feature selection, portfolio construction,
  and strict point-in-time claims.

Forward returns begin at the activation-session close and end at the close of
the Nth later reference session. MOM60 and annualized 20-session volatility use
data ending at the previous reference-session close. They are saved with the
panel for audit, not used in the raw correlations.

## Coverage Audit

| Item | Result |
| --- | ---: |
| Planned symbol-window rows | 5,184 |
| Usable rows | 4,874 |
| Excluded rows | 310 |
| Pre-listing exclusions | 270 |
| Insufficient control history | 36 |
| Non-tradable activation endpoint | 3 |
| Non-tradable end endpoint | 1 |
| Control-date lookahead violations | 0 |

Every planned combination has either an outcome or a named exclusion. There is
no silent row loss. Usable counts per timing-window cell range from 541 to 542
of 576.

## Sensitivity Result

For each primary feature, sign stability was checked across all nine timing and
horizon combinations. Only 27 of 198 symbol-feature groups, 12 of 66
asset-group-feature groups, and 2 of 11 dispersion-feature groups retain one
Spearman sign throughout.

Across the nine specifications, median asset-group Spearman coefficients for a
primary feature range from -0.370 to 0.294. The corresponding ranges are -0.378
to 0.416 at symbol level and -0.206 to 0.177 for cross-sectional dispersion.
These ranges describe the full reporting surface; they are not invitations to
select the endpoints.

The 24- and 48-hour protocols are relatively similar: the median absolute
difference in asset-group Spearman correlation is 0.028 across primary
feature-window-group cells. The 24-hour versus next-month median difference is
0.115. Thus the broader timing assumption matters materially even though an
extra 24 hours is often absorbed by a weekend or holiday.

## Interpretation

The small event count, overlapping forward windows, sparse language categories,
dynamic ETF histories, and large number of reported relationships make isolated
coefficients unreliable. Uniform sign is also only a sensitivity diagnostic;
the nine estimates share events and are not independent confirmations.

This stage answers an engineering and falsification question: the frozen joins
can be executed reproducibly without hidden exclusions or control lookahead.
It does not show that policy language predicts returns or adds value beyond
MOM60.

## Stop and Next Gate

Do not build a narrative portfolio from these outputs. Before any adjusted
analysis, freeze its unit of observation, control formula, covariance treatment,
multiplicity policy, and decision threshold. Because the raw outcomes are now
observed, an adjusted specification cannot be presented as untouched
confirmatory evidence. Strict historical modeling remains blocked until PDF
version identity is independently supported or the claim is kept explicitly
exploratory.

## Reproduction

Run the `nrea market-relations` command documented in the repository README.
The output directory contains the complete audit, usable panel, asset-group and
dispersion outcomes, three relationship tables, a summary, and a checksum run
manifest.
