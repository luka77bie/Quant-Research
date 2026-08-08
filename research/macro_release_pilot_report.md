# China Macro Release Feasibility Pilot v0.1

## Decision

Continue to a source-archiving gate, but do not construct macro regimes yet.
The pilot passes at publication-record level and remains provisional for strict
point-in-time use.

## Scope

| Dimension | Series | Records | Role |
| --- | --- | ---: | --- |
| Growth | Official manufacturing PMI | 4 | Monthly growth-state candidate |
| Inflation | Official CPI YoY | 4 | Monthly inflation-state candidate |
| Liquidity | Official M2 YoY | 4 | Monthly liquidity-state candidate |

The catalog intentionally reads no ETF return, price, or strategy output. It
tests source feasibility only.

## Gate Result

| Check | Result |
| --- | ---: |
| Expected records | 12 |
| Structurally ready records | 12 |
| Original official release pages | 11 |
| Official retrospective confirmations | 1 |
| Current URLs returning HTTP 200 on 2026-08-08 | 12 |
| Strict historical snapshots | 0 |
| ETF outcomes read | No |
| Regime thresholds constructed | No |

The frozen feasibility threshold requires three dimensions with four records
each and at least 10 original release pages. The observed 11 original pages pass
that threshold.

## Source Findings

NBS manufacturing PMI releases expose a publication timestamp and state that
the published index is seasonally adjusted. The reviewed records cover September
through December 2024 and were released at 09:30 on the final calendar day of
each month.

NBS CPI releases expose a 09:30 publication timestamp and the headline YoY value.
The reviewed September through December 2024 observations were released in the
following month. Their pages give a rounding note but do not state a general
historical revision policy.

PBOC financial-statistics reports expose M2 YoY and state that current-period
data are preliminary, with additional comparable-scope notes. Three reviewed
records use original release pages. The March 2023 value is supported by a later
official PBOC press-conference page that states the original April 11 release;
it is not mislabelled as an original release page.

## Limitation

A current official page with an old publication timestamp is evidence of an
official publication record, not proof that its bytes are unchanged since that
date. No current page is treated as a contemporaneous historical snapshot. The
catalog also records revision policy as unstated where the release page does not
provide one.

## Next Gate

1. Cache all 12 official pages independently and lock retrieval checksums.
2. Extract and verify the displayed release timestamp and headline value.
3. Search for contemporaneous snapshots or independent dated reproductions.
4. Expand to the full 2018-2025 monthly period only if extraction works under
   one deterministic rule per source family.
5. Freeze transformations and regime thresholds before joining ETF outcomes.

## Reproduction

Run `nrea macro-release-pilot` using the root README command. Outputs include a
row-level audit, summary, and clean-commit checksum manifest.
