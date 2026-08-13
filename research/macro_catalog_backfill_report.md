# Macro Catalog Search Backfill Audit v0.1

## Decision

The 2018-2025 source catalog passes the pre-specified 95% coverage gate for all
three families. Proceed to article retrieval and body-level validation. Do not
construct transformations, regime states, or ETF joins yet.

## Discovery Cascade

The catalog uses three explicitly separated discovery methods:

1. Official column indexes supplied 53/96 NBS PMI, 53/96 NBS CPI, and 95/96
   PBOC M2 records.
2. Month-specific NBS official-site title search supplied 72 unique records.
   Queries were limited to title search, filtered to official domains and
   exact family-period matches, and cached per query for resumability.
3. Fourteen residual NBS records were located as reviewed search candidates and
   registered in a separate seed ledger. Their acceptance status remains
   `seeded_pending_article_validation`, not parser-verified.

## Result

| Source family | Catalog URLs | Expected | Coverage | Remaining gap |
| --- | ---: | ---: | ---: | --- |
| NBS manufacturing PMI | 96 | 96 | 100.00% | None |
| NBS CPI YoY | 96 | 96 | 100.00% | None |
| PBOC M2 YoY | 95 | 96 | 98.96% | January 2025 |

The exact-title search recovered 72 of 86 index gaps. Searching five result
pages did not recover the remaining 14, so the system did not silently weaken
the title or domain filters. Reviewed official candidates were added through a
versioned seed contract instead.

## Evidence Precision

Twelve reviewed seeds point to migrated NBS data-release pages with displayed
minute timestamps. Two point to NBS information-disclosure mirrors and expose
only a document date:

- April 2020 PMI.
- November 2019 CPI.

These remain `date` precision. They must not be promoted to minute precision
unless a separate official release page or contemporaneous snapshot is found.

## Remaining Risk

- A discovered URL is not yet a validated observation.
- Live official pages are not contemporaneous historical snapshots.
- Search ranking is mutable; committed catalog and seed ledgers preserve this
  run's accepted candidates, while local JSON responses preserve retrieval
  details.
- January 2025 national M2 has no accepted original PBOC page. The gap remains
  explicit because regional PBOC reports are not substitutes for national M2.

No ETF return was read and no regime threshold was constructed.

## Next Gate

1. Download all 287 catalog pages with per-record retry and resume behavior.
2. Verify official domain, page title, statistical period, release timing, and
   deterministic headline value extraction.
3. Keep date-only evidence explicit and report every parser failure.
4. Require at least 95% article-ready coverage for every family.
5. Freeze release-lag and transformation rules only after that gate passes.
