# PBOC Quarterly Archive and Text Report v0.2

## Decision

The archive and text-extraction stages pass. The strict point-in-time modeling
stage remains blocked.

The repository now contains a reviewed catalog for all 32 PBOC monetary policy
execution reports from 2018 Q1 through 2025 Q4. Each current official PDF is
checksum-locked, cached independently, and assigned a conservative availability
time 24 hours after the official page's displayed publication timestamp.

This supports reproducible exploratory publication-time reconstruction. It does
not prove that the same bytes were available historically and cannot support a
strict point-in-time backtest or headline performance claim.

## Archive Evidence

- Source: the official PBOC monetary policy execution report master index and
  its 32 linked report pages.
- Catalog: `configs/pboc_mpr_catalog.csv`.
- Coverage: 32 of 32 expected quarter ends, 2018-03-31 through 2025-12-31.
- Integrity: 32 unique locked PDF SHA-256 values; no duplicate source-quarter.
- Availability: exact displayed publication timestamp plus 24 hours.
- Archive result: 32 ready, zero missing, 100% coverage.
- Point-in-time result: zero verified and 32 provisional.

The 2019 Q4 page linked an HTTP attachment. The HTTPS response was byte-for-byte
identical, including SHA-256
`e5df0ac4843a17a2e686514a764b8c0be7e33c9664b085ca69e847f7c7a6f825`,
so the catalog uses HTTPS. Previously reviewed 2020 Q4, 2022 Q4, and 2024 Q4
hashes also matched the expanded catalog retrieval.

## Snapshot Feasibility

Historical-byte verification could not be completed. Wayback CDX requests timed
out, while exact Common Crawl index queries returned gateway errors in the
current environment. These service failures leave feasibility unresolved and
must not be interpreted as evidence that snapshots are absent.

Current PBOC paths also show site-migration effects, particularly among recent
reports. The 2019 Q3 page displays exactly `09:00:00`, which may be a CMS default.
Both observations reinforce the use of conservative signal delays and explicit
revision-risk language.

## Extraction Result

Commit `430da6ab2b883086e77a25bfe42b3fc0578731e3` produced the clean formal
run using Python 3.12.13 and pypdf 6.15.0.

| Check | Result |
| --- | ---: |
| Reports ready | 32 / 32 |
| Pages extracted | 1,901 |
| Non-whitespace characters | 1,323,999 |
| Empty pages | 0 |
| Replacement characters | 0 |
| Minimum document CJK ratio | 67.34% |
| Maximum document CJK ratio | 73.06% |

Text is normalized deterministically, separated by page, cached against the
source PDF checksum and extraction schema, and screened for short documents,
empty pages, replacement characters, low CJK share, and duplicate text hashes.
All outputs are marked `exploratory_only`.

## Permitted Next Stage

1. Build one deterministic parser for the forward-looking policy section and
   require successful isolation in at least 30 of 32 reports.
2. Freeze a transparent non-LLM baseline: document length, policy-term counts,
   change from the previous quarter, and cosine similarity to the prior report.
3. Define joins using `available_at` and test 24-hour, 48-hour, and next-month
   delays before inspecting portfolio outcomes.
4. Evaluate feature stability and economic interpretation before adding any LLM
   representation or optimizing a strategy.

## Stop Conditions

- Stop section-based research if one deterministic parser cannot isolate the
  target policy section in at least 30 reports.
- Do not add an LLM feature before the parser, transparent baseline, and delay
  protocol are frozen and tested.
- Stop a feature family if conclusions depend on one wording convention, one
  crisis period, or a small number of reports.
- Do not report strict point-in-time performance unless matching historical
  document evidence is obtained.
- If snapshot verification remains unavailable, the final claim must remain a
  publication-time reconstruction with revision-risk and delay sensitivities.
