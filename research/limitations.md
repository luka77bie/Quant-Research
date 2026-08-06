# Limitations and Failure Cases v0.1

- AKShare and Yahoo Finance are convenience interfaces, not guaranteed data
  archives. Provider success does not prove historical completeness.
- ETF launch dates, delistings, ticker changes, and the manually selected
  universe can create survivorship and availability bias.
- A seven-day boundary tolerance avoids false alarms around weekends and
  holidays but cannot identify every missing trading observation.
- Yahoo-adjusted prices and AKShare forward-adjusted prices may not be exactly
  comparable. Cross-provider differences must be measured before combining
  histories.
- Chinese historical policy and news timestamps may be incomplete or revised.
  Retrieval time cannot substitute for original point-in-time availability.
- A small number of macro regimes makes conditional results especially easy to
  overfit. Crisis case studies are interpretation, not independent validation.

No output from this repository should be described as live-trading-ready until
corporate actions, spreads, taxes, market impact, operational monitoring, and
provider licensing have been separately validated.
