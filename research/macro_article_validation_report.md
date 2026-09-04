# Study 02 Full Monthly Article Validation

## Decision

Pass the current-page article-validation gate and proceed to a frozen macro data
contract. Do not join ETF returns yet.

## Result

The catalog contains 288 expected family-month records from January 2018
through December 2025. All 287 available official pages downloaded successfully
with per-record metadata and SHA-256 checksums.

| Source family | Expected | Article-ready | Coverage |
| --- | ---: | ---: | ---: |
| NBS manufacturing PMI | 96 | 96 | 100.00% |
| NBS CPI YoY | 96 | 96 | 100.00% |
| PBOC M2 YoY | 96 | 95 | 98.96% |

Every available page passes five checks: cache integrity, title, statistical
month, release timing, and headline value. The sole missing record is January
2025 national M2. It is not replaced by a regional series or inferred value.

## Timing precision

Of the 287 article-ready records, 285 have minute-level publication timing. The
April 2020 PMI and November 2019 CPI records retain date-only precision. A later
market join must treat those observations as available only after the recorded
date ends.

The official January 2025 PMI release occurred on 27 January ahead of the Spring
Festival holiday. The release plausibility window now allows publication up to
seven days before month-end. This correction was made during return-blind data
validation and is explicitly tested.

## Research limits

The pages were retrieved on 4 September 2026. They are current official pages,
not contemporaneously archived snapshots from each historical release date.
The committed evidence ledger therefore labels every record
`provisional_no_snapshot`. This supports a clearly labelled publication-time
reconstruction, not a strict vintage-data claim.

No ETF returns were read, no regime thresholds were constructed, and no
portfolio was created during this stage.

## Next gate

1. Freeze one transformation and state rule for growth, inflation, and
   liquidity.
2. Freeze availability handling for minute-level, date-only, and missing data.
3. Build the monthly macro panel from the committed evidence ledger.
4. Audit missingness, state counts, persistence, and chronology without returns.
5. Permit an ETF payoff atlas only after that return-blind panel passes.
