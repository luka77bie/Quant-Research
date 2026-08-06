# Data Gate Status: 2026-08-06

## Completed

- Official secondary-market listing dates are verified for all 18 ETFs.
- The full AKShare-Eastmoney adjusted history for `510300` downloaded from
  2018-01-01 through 2026-07-31 with 2,081 rows.
- Dynamic listing eligibility and strict reference-calendar alignment are
  implemented and tested offline.

## Blocked

Immediately after the successful `510300` request, the same endpoint closed
connections for `510500`, `512100`, and `159915`, despite ten-second spacing
and retries. The circuit breaker then skipped the remaining 14 requests. The
current local data gate is therefore one ready cache and seventeen missing
caches.

A later isolated retry requested only `510500` through the selective-resume
path. Both attempts ended with the same remote connection closure. No further
symbols were requested after that confirmation.

No formal MOM60 result is permitted from this state. The successful symbol is
preserved and later runs resume without requesting it again. Yahoo remains
rate-limited, and the unadjusted Sina endpoint is not an equivalent replacement
for the frozen adjusted-close baseline.
