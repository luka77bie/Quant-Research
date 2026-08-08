# Adjusted Narrative-Market Relation Report v0.1

## Decision

The computation gate passes and the research gate stops. After fixed controls,
small-sample uncertainty, and multiplicity correction, zero pooled models and
zero dispersion models meet the frozen 10% FDR reference threshold. No feature
is eligible for portfolio construction.

## Provenance

The unadjusted outputs had already been observed before this protocol, so every
adjusted result is labelled post-descriptive exploratory. Protocol v1 omitted
the inference reference distribution. An implementation rehearsal exposed that
gap; its normal-approximation output was rejected. Protocol v2 preserved the
model grid and thresholds but froze conservative Student t reference
distributions before the formal run from clean commit `7ebd9b2`.

## Model Grid

| Model family | Planned | Ready | Excluded |
| --- | ---: | ---: | ---: |
| Pooled asset-group primary | 99 | 99 | 0 |
| Per-asset-group descriptive | 594 | 594 | 0 |
| Cross-sectional dispersion | 99 | 99 | 0 |

The 99 primary specifications are 11 frozen features by three timing protocols
by three forward windows. Each pooled model standardizes its complete sample,
includes the matching text-length control, lagged MOM60, lagged 20-session
volatility, and asset-group fixed effects, and clusters by quarterly report.
Secondary asset-group coefficients intentionally have no p-values.

Numerical gates did not drive the outcome. Pooled condition numbers range from
9.58 to 10.52, the maximum observed absolute feature-control correlation is
0.308, and no model is rank deficient or below the 24-event minimum.

## Multiplicity Result

| Family | Tests | q <= 0.10 | Minimum q |
| --- | ---: | ---: | ---: |
| Pooled asset-group | 99 | 0 | 0.10099 |
| Dispersion | 99 | 0 | 0.39365 |

The closest pooled result uses next-month activation, a 20-session outcome, and
quarter-over-quarter structural-support density change. Its standardized beta
is -0.262, CR1 standard error is 0.072, 95% interval is [-0.409, -0.115],
nominal p-value is 0.00102, and BH q-value is 0.10099. The q-value is above the
frozen threshold and is recorded as a failure, not rounded down.

For the same feature and horizon, pooled coefficients are -0.102 under the
24-hour protocol and -0.071 under the 48-hour protocol, with q-values 0.915 and
0.988. Although all three signs are negative, magnitude and adjusted evidence
depend strongly on the broader next-month timing choice. One of six secondary
asset groups is also slightly positive under next-month activation, so the
pooled direction is not universal.

## Interpretation

The result does not prove the absence of a narrative mechanism. It says this
32-report reconstruction does not provide a multiplicity-adjusted candidate
under the frozen controls and timing sensitivities. The lowest q-value being
close to 0.10 makes the result statistically fragile, not investable.

The protocol amendment is itself a useful failure case: a normal approximation
would have crossed the threshold, while the documented small-sample t convention
does not. That difference is why implementation details must be frozen and
audited before claiming alpha.

## Stop and Next Work

Do not tune a narrative score, choose next-month activation, or construct a
portfolio from this surface. The current sample is exhausted for model
selection. Productive next work is limited to a return-blind macro regime data
layer, independent historical-version evidence, or genuinely future PBOC
reports evaluated under this committed protocol.

## Reproduction

Run `nrea adjusted-relations` using the command in the repository README. The
output directory contains both analysis panels, all three complete model tables,
a summary, and a checksum run manifest tied to the executing commit.
