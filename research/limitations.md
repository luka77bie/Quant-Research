# Limitations and Failure Cases v0.1

- Tencent, AKShare, and Yahoo Finance are convenience interfaces, not guaranteed
  data archives. Provider success does not prove historical completeness.
- ETF launch dates, delistings, ticker changes, and the manually selected
  universe can create survivorship and availability bias.
- A seven-day boundary tolerance avoids false alarms around weekends and
  holidays but cannot identify every missing trading observation.
- Yahoo-adjusted prices and AKShare forward-adjusted prices may not be exactly
  comparable. Cross-provider differences must be measured before combining
  histories.
- The frozen close-to-close execution convention includes overnight movement
  on the next panel date even though a real strategy cannot trade at the prior
  close. An open-aware delayed-execution sensitivity test is required before
  interpreting return levels as implementable.
- The current baseline engine assumes all selected ETFs share a common trading
  calendar. Verified suspensions are explicitly marked at the prior close;
  every other missing return for a held ETF remains a hard failure.
- Chinese historical policy and news timestamps may be incomplete or revised.
  Retrieval time cannot substitute for original point-in-time availability.
- A currently downloadable, versioned official PDF still may have been replaced
  after publication. Without a historical snapshot and matching checksum it is
  provisional, not strictly point-in-time verified.
- Current PBOC page paths for some 2024-2025 reports reflect a later site
  migration, so URL structure is not evidence of original publication-time
  availability. The 2019 Q3 page displays exactly 09:00:00, a default-looking
  time that should be covered by delay sensitivity rather than treated as
  precise to the second.
- Wayback requests timed out and exact Common Crawl index queries returned
  gateway errors in the current environment. Snapshot availability is therefore
  unresolved; these failures are not evidence that snapshots do not exist.
- PDF text extraction passing structural quality thresholds does not establish
  semantic fidelity for every table, reading order, heading, or policy phrase.
  Section-level validation is required before constructing features.
- Daily market data cannot establish intraday execution. Narrative timing uses
  the first audited 09:30 reference-session open on or after each effective
  timestamp; holidays can create long and uneven calendar delays. This is a
  conservative information-availability convention, not an executable fill.
- A small number of macro regimes makes conditional results especially easy to
  overfit. Crisis case studies are interpretation, not independent validation.
- Tencent does not expose transaction value in the qualified endpoint. The
  predecessor attention control therefore uses `close * volume` as an activity
  proxy; it is not an exact reproduction of the AKShare amount field.
- The attention control uses only market observables. Calling it a narrative or
  AI signal would be a construct-validity error even when its returns improve.

No output from this repository should be described as live-trading-ready until
corporate actions, spreads, taxes, market impact, operational monitoring, and
provider licensing have been separately validated.
