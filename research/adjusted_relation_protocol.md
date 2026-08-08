# Adjusted Narrative-Market Relation Protocol v0.1

## Evidence Status

This protocol is frozen after the unadjusted descriptive relationships were
observed at commit `e321acd`. The adjusted results are therefore exploratory,
not untouched confirmatory evidence. They may test whether raw relationships
survive fixed controls, but they cannot retroactively validate a discovered
feature, timing rule, or horizon.

## Question

Does one pre-specified primary policy-language feature retain an association
with a forward ETF asset-group outcome after controlling for document length,
lagged MOM60, lagged 20-session volatility, and persistent differences between
asset groups?

## Specification Grid

Every combination of 11 primary features, three timing protocols, and three
forward windows is reported. No feature, delay, or horizon may be selected from
the results. Each model contains one narrative feature because 31 to 32 events
cannot support a high-dimensional narrative regression.

Continuous variables, including the outcome, are standardized within each
complete model sample using sample standard deviations. A level feature uses
section character count as its measurement control. A quarter-over-quarter
change feature uses section character-count change.

## Models

The primary model pools six equal-weight asset-group outcomes and includes
asset-group fixed effects. Uncertainty is CR1 cluster-robust by `record_id`, the
quarterly report event. This prevents six asset groups exposed to the same text
from being counted as six independent narrative observations.

Secondary models report one coefficient per asset group without p-values. A
separate event-level model relates the same feature and controls to
cross-sectional return dispersion; it uses pre-specified Bartlett Newey-West
lags of zero for 5- and 20-session outcomes and one for 60-session outcomes.

Models require at least 24 event clusters or events. Rank deficiency, a design
condition number above 1,000, a predictor standard deviation at or below
`1e-12`, or absolute feature-control correlation above 0.95 produces a visible
exclusion rather than a silent estimate.

## Multiplicity and Interpretation

Benjamini-Hochberg q-values are computed separately across all 99 primary pooled
tests and all 99 dispersion tests. The 10% FDR value is a reference threshold,
not a trading rule. Asset-group secondary coefficients receive no p-values.

A result may be called a candidate incremental relation only when the pooled
q-value is at most 0.10, the pooled coefficient has one sign across all three
timing rules for the same feature and horizon, and no numerical gate fails.
Candidate status still does not permit portfolio construction. Independent data
or a genuinely future sample is required.

## Stop Conditions

- Do not add controls, remove controls, or alter covariance rules after results.
- Do not replace a failed feature with an audit-only raw count or novelty view.
- Do not present nominal p-values without the frozen q-value family.
- Do not proceed to a narrative portfolio from this sample.
- Strict point-in-time claims remain blocked by unresolved historical PDF
  identity, regardless of adjusted significance.
