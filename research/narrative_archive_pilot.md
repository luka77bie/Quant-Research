# Point-in-Time Narrative Archive Pilot v0.1

> Historical pilot record. The completed 32-report outcome and current decision
> are documented in `research/pboc_archive_and_text_report.md`.

## Decision

The archive plumbing passes and the modeling gate remains blocked. The official
source is operationally usable, but three currently retrieved PDFs do not form
a point-in-time 2018-2025 quarterly archive.

## Pilot Scope

- Source: People's Bank of China monetary policy execution reports.
- Records: 2020 Q4, 2022 Q4, and 2024 Q4.
- Archive implementation commits: `ee262de` and integrity fix `44f53dd`.
- Manifest worktree state: clean.
- Required fields: exact `published_at`, retrieval-generated `retrieved_at`, and
  a 24-hour delayed `available_at`.
- Required evidence: timestamped official index, HTTPS source-domain match,
  PDF signature, locked document SHA-256, and per-document metadata.

The reviewed source pages are the official PBOC indexes for
[2020 Q4](https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/4021036/8d39aa9d730046c896289d17c09346d2/index.html),
[2022 Q4](https://www.pbc.gov.cn/zhengcehuobisi/125207/125227/125957/4584071/d7e45aa7d98c4664a9a6c2393d16787d/index.html),
and [2024 Q4](https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/2025092212554550369/index.html).

## Retrieval Result

| Record | Bytes | Archive | Point-in-time |
| --- | ---: | --- | --- |
| 2020 Q4 | 1,723,498 | Ready | Provisional |
| 2022 Q4 | 1,404,546 | Ready | Provisional |
| 2024 Q4 | 1,270,128 | Ready | Provisional |

All three downloads succeeded on their first trial and a second run used the
validated caches without a network request. Their exact checksums are locked in
the catalog then named `configs/narrative_pilot_catalog.csv` (now replaced by
`configs/pboc_mpr_catalog.csv`). A changed official file, corrupt cache,
wrong domain, HTML queue page, or duplicate source-quarter now blocks the run.

## Gate Result

| Check | Result |
| --- | --- |
| Cached documents ready | 3 / 3 |
| Expected quarters, 2018-2025 | 32 |
| Covered quarters | 3 |
| Coverage | 9.375% |
| Historical snapshots with matching hash | 0 |
| Modeling gate | Blocked |

The current official URLs and timestamped index pages support a reproducible
present-day archive and a conservative historical availability assumption.
They do not prove that the downloaded bytes were unchanged since publication.
For that reason all three records remain `provisional`; current retrieval time
cannot substitute for a contemporaneous snapshot.

## Next Gate And Stop Conditions

1. Expand the reviewed catalog to every quarter from 2018 Q1 through 2025 Q4.
2. Locate historical snapshots or another independent dated checksum source.
3. Keep report extraction and language-model features blocked until coverage is
   complete and point-in-time status is resolved explicitly.
4. Stop this source if more than five quarterly documents lack exact official
   publication times or return mutable HTML without a versioned PDF.
5. If historical snapshots are unavailable for most records, downgrade the
   project claim to a documented publication-time sensitivity study; do not
   call the archive strictly point-in-time verified.

The next phase is catalog completion and snapshot feasibility, not sentiment
scoring or portfolio optimization.
