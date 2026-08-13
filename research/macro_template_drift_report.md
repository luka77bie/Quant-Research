# Macro Source Template Drift Audit v0.1

## Decision

Proceed to the full monthly official-release catalog. Do not construct regime
states or join ETF outcomes yet.

## Design

The return-blind audit uses three official anchor pages per source family. NBS
PMI and CPI cover 2018, 2021, and 2025. PBOC M2 covers 2018, 2021, and 2024
because a 2025 year-end original M2 page was not stably discoverable during the
official-source search; no retrospective substitute was used.

Each source family has one deterministic parser:

- NBS PMI: first displayed NBS timestamp plus the manufacturing PMI headline.
- NBS CPI: first displayed NBS timestamp plus signed headline CPI YoY.
- PBOC M2: displayed article timestamp plus headline M2 YoY.

## Result

| Source family | Ready anchors | Anchor years | Timestamp match | Value match |
| --- | ---: | --- | ---: | ---: |
| NBS manufacturing PMI | 3/3 | 2018, 2021, 2025 | 3/3 | 3/3 |
| NBS CPI YoY | 3/3 | 2018, 2021, 2025 | 3/3 | 3/3 |
| PBOC M2 YoY | 3/3 | 2018, 2021, 2024 | 3/3 | 3/3 |

All nine pages are separately archived with retrieval metadata and locked
SHA-256 values. The parser result is compared with independently registered
release times and values; exact agreement is required.

## Findings

- NBS pages migrated to 2023 URL paths while retaining older displayed release
  timestamps. URL dates are therefore not valid release-time evidence.
- NBS PMI moved from a 09:00 release in the 2018 and 2021 anchors to 09:30 in
  the 2025 anchor. The parser reads the page rather than assuming a fixed time.
- CPI parsing handles positive, negative, and textual `同比持平` headlines.
- PBOC punctuation varies between Chinese and ASCII forms, but the core M2
  headline structure remains deterministic across the tested anchors.

## Limitations

Nine anchors establish extraction feasibility, not full 2018-2025 coverage.
Current official pages are not contemporaneous historical snapshots. PBOC M2
discoverability after site migration remains a collection risk, especially for
2025 year-end releases. Page checksums prove the retrieved version only.

## Next Gate

1. Build the complete monthly source catalog for 2018-2025.
2. Archive each page and require deterministic parser agreement.
3. Record missing pages, date-only evidence, and revision notes explicitly.
4. Freeze transformations and release-lag conventions without ETF outcomes.
5. Stop before regime construction if source-family coverage is below 95%.
