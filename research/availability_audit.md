# ETF Availability Audit v0.1

## Rule

`available_from` is the official secondary-market listing date, not the fund
contract effective date. It controls when an ETF may enter the dynamic research
universe. Price observations before that date are invalid; absent observations
before that date are expected and must not be filled.

## Sources

- Seventeen Shanghai-listed ETFs were verified on 2026-08-06 through the
  Shanghai Stock Exchange official fund list, which exposes `LISTING_DATE`.
- `159915` was verified through the Shenzhen Stock Exchange official ETF fund
  list, which exposes `上市日期`.
- Exact dates, venues, source labels, and URLs are committed in
  `configs/etf_availability_sources.csv`.

The source snapshot is configuration evidence, not a claim that the providers'
historical price archives start on exactly the same dates. The common-sample
audit separately compares observed trading dates with a reference exchange
calendar derived from the designated reference ETF.

## Research consequence

With a 2018 research start, `588000` becomes eligible on 2020-11-16 and
`515790` on 2020-12-18. Requiring either ETF to have 2018 history would create a
false data failure; backfilling it before listing would create look-ahead and
availability bias.
