# China Macro Release Feasibility Pilot v0.1

## Decision

Continue to cross-year source-template testing, but do not construct macro
regimes yet. The pilot passes at publication-record and current-page evidence
levels and remains provisional for strict point-in-time use.

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
| Pages archived with locked SHA-256 on 2026-08-13 | 12 |
| Release evidence verified from visible page text | 12 |
| Value evidence verified from visible page text | 12 |
| Minute-precision release evidence | 11 |
| Date-precision release evidence | 1 |
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

The March 2023 M2 retrospective confirmation states that the original release
occurred on April 11 but does not establish an intraday time. The catalog now
uses 23:59:59 China time as a conservative end-of-day availability timestamp,
rather than the previously reconstructed 16:30 value.

## Current-Page Evidence Audit

The follow-on archive stores each current official HTML page atomically with its
retrieval timestamp, byte count, URL, and SHA-256. A committed evidence ledger
locks the observed checksum and exact visible-text fragments supporting the
release date or time and headline value. The audit rejects changed bytes,
missing metadata, unlocked checksums, unapproved domains, or missing evidence
text. All 12 records pass this current-page gate.

This result detects future changes relative to the 2026-08-13 retrieval. It does
not prove that the page was unchanged between its displayed release date and
retrieval.

## Next Gate

The cross-year source-template gate is now complete; see
[`macro_template_drift_report.md`](macro_template_drift_report.md). The next gate
is a complete 2018-2025 monthly official-release catalog, followed by frozen
transformations and release-lag conventions before any ETF outcome join.

## Reproduction

Run the pilot and evidence commands using the root README instructions. Outputs
include row-level audits, summaries, and checksum manifests.
