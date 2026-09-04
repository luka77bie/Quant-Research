# Study 02 Monthly Article Validation Protocol

## Purpose

Convert the 2018-2025 official-source catalog into an auditable monthly macro
panel input without reading ETF returns or choosing regime thresholds.

## Registered checks

Every available monthly record must retain its official source URL and a local
checksum. A record is article-ready only when all five checks pass:

1. The cached page and metadata agree with the catalog URL and record ID.
2. The catalog title appears in the visible article text.
3. The title independently classifies to the registered source family and month.
4. The release time is extractable and plausible for the statistical month.
5. The registered headline value is extractable from the article body.

Date-only release timing is accepted only for catalog rows already marked
`date`. It is retained as date precision and is never promoted to a fabricated
intraday timestamp.

The plausibility window runs from seven days before month-end through 60 days
after month-end. The original three-day lower allowance incorrectly blocked the
official January 2025 PMI release published on 27 January ahead of the Spring
Festival holiday. This calendar correction was made during article validation,
before reading ETF returns or constructing any regime threshold.

## Coverage gate

PMI, CPI, and M2 are assessed separately. Each family must reach at least 95%
article-ready coverage. Missing sources, failed downloads, parser failures,
checksum mismatches, and timing failures remain explicit in the audit output.

Passing this gate permits freezing transformation and publication-lag rules. It
does not permit claims about macro regimes or ETF payoffs. Those decisions
belong to later, separately frozen stages.

## Stop conditions

- Stop if any source family remains below 95% after targeted retries and parser
  review.
- Stop if a historical page cannot establish its statistical month or headline
  value.
- Do not substitute a regional M2 release for the missing national series.
- Do not inspect ETF returns to decide which failed records or templates matter.
