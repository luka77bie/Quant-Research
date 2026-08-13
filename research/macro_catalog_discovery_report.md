# Macro Monthly Catalog Discovery Audit v0.1

## Decision

Keep Study 02 return-blind and do not construct macro regimes yet. The official
index discovery layer is reproducible, but the complete 2018-2025 catalog gate
is blocked by explicit source gaps.

## Method

The discovery command archives every page exposed by two official indexes:

- National Bureau of Statistics `Data Releases`: 67 static index pages.
- People's Bank of China `Data Interpretation`: 38 paginated index responses.

It classifies exact release-title patterns, maps PBOC quarter, half-year,
three-quarter, and annual titles to March, June, September, and December, and
deduplicates repeated responsive links by official URL. URL dates are never
used as observation periods. The expected grid is frozen at 96 months per
source family from January 2018 through December 2025.

## Result

| Source family | Discovered | Expected | Coverage | Duplicate periods | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| NBS manufacturing PMI | 53 | 96 | 55.21% | 0 | Blocked |
| NBS CPI YoY | 53 | 96 | 55.21% | 0 | Blocked |
| PBOC M2 YoY | 95 | 96 | 98.96% | 0 | Pass coverage, one explicit gap |

The NBS index begins at August 2021. Both NBS families therefore have the same
43 missing months from January 2018 through July 2021; this is an index-history
boundary, not a parser failure. The sole PBOC gap is January 2025.

The committed 288-row catalog preserves discovered URLs and leaves missing URLs
blank. A separate 201-row candidate table preserves every unique in-range
candidate before expansion to the expected monthly grid.

## Interpretation

The result rejects a tempting but weak workflow: web-searching 87 missing pages
and treating the first result as data. NBS historical pages are searchable, but
the official site search mixes website and social-media records and applies an
opaque ranking. It can be used only as a candidate generator. Each candidate
must still match an exact month-specific title, use an allowed official domain,
and pass body-level period and value extraction.

## Reproducibility Boundary

The local run archived 105 index pages with URL, byte count, and SHA-256 ledger.
Raw index HTML and generated run outputs remain ignored because they are live
retrieval artifacts. The committed catalog and candidate snapshot make the
observed coverage reviewable without claiming that the pages are historical
point-in-time versions.

No ETF return was read and no regime threshold was constructed.

## Next Gate

1. Add exact month-by-month NBS official-search discovery for the 86 missing
   PMI/CPI records, filtering to `stats.gov.cn` before accepting a candidate.
2. Resolve January 2025 M2 from a PBOC original page or retain it as missing.
3. Fetch each discovered article and require title period, release timestamp,
   and headline value agreement.
4. Require at least 95% ready article coverage in every source family.
5. Stop before transformations or regime construction if that gate fails.
