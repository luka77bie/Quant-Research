# Provider Probe Report: 2026-08-06

## Scope

This is an operational probe, not a data-quality endorsement. Requests used
adjusted daily history for January 2024 and wrote to isolated temporary caches.

Environment:

- AKShare 1.18.82
- yfinance 0.2.66
- pandas 2.3.3
- Python 3.12

## Results

| Probe | Result | Evidence |
| --- | --- | --- |
| AKShare, `510300`, one month | Passed | 22 normalized rows; checksum and cache audit passed |
| Yahoo, `510300.SS`, one month | Failed | `YFRateLimitError: Too Many Requests` |
| AKShare, 18-symbol universe, one month | Failed globally | Eastmoney closed the connection for all 18 symbols after the earlier successful probe |

The single-symbol AKShare pass followed by a complete batch failure indicates
an endpoint-level availability or throttling event, not 18 independent ticker
mapping errors. Yahoo cannot currently be treated as a dependable immediate
fallback from this environment.

## Engineering response

- Provider exceptions are preserved in append-only manifests.
- Yahoo uses `raise_errors=True`, so rate-limit failures are not collapsed into
  a generic empty-frame error.
- Successful provider-symbol caches survive reruns.
- Three consecutive incomplete symbols trip a batch circuit breaker by
  default. A follow-up live probe confirmed three requests were attempted and
  the remaining 15 symbols were marked `skipped` for later resumption.
- Provider caches remain isolated. This probe does not justify splicing
  AKShare and Yahoo histories.

## Research implication

Do not launch a full-history run until the endpoint recovers. When it does,
download in resumable batches with conservative spacing, then run `nrea audit`
before constructing the common sample. If these provider-level failures consume
two consecutive project weeks without an auditable sample, the research
contract's data-plumbing stop condition applies.
