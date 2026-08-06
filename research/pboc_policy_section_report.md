# PBOC Policy Section Parser Report v0.1

## Decision

The deterministic policy-section gate passes for all 32 reports. This permits a
transparent, non-LLM text-feature baseline under the exploratory publication-time
protocol. It does not unblock a strict point-in-time backtest.

## Frozen Rule

The parser accepts only these canonical headings after removing whitespace:

- `二、下一阶段主要政策思路`
- `二、下一阶段货币政策主要思路`

Dotted table-of-contents entries do not equal either canonical heading. When an
extracted PDF contains more than one exact heading, the parser selects the final
occurrence and retains text through the end of the report. The output cache is
bound to the extracted-text SHA-256 and parser schema version.

## Audit Result

| Check | Result |
| --- | ---: |
| Reports ready | 32 / 32 |
| Required reports | 30 / 32 |
| Total non-whitespace characters | 88,768 |
| Minimum section length | 2,080 |
| Maximum section length | 3,829 |
| Minimum CJK ratio | 90.28% |
| Maximum CJK ratio | 91.89% |
| Duplicate section hashes | 0 |

Twenty-two reports use the original heading and ten reports from 2023 Q3 onward
use the expanded `货币政策` heading. Three PDFs expose two exact heading
occurrences; selecting the final occurrence consistently isolates the body.

## Remaining Boundary

Passing this gate demonstrates consistent structural isolation, not perfect
reading order or semantic validity. The next stage may compute pre-specified,
interpretable text diagnostics without returns. It must not tune a dictionary,
feature weights, or thresholds against portfolio performance, and all rows must
retain the catalog's conservative `available_at` timestamp and provisional
point-in-time status.
