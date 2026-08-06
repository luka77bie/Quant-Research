# Frozen MOM60 Baseline Report v0.1

## Run Identity

- Qualified sample: Tencent, 18 ETFs, 35,372 long-form rows.
- Research range: 2018-01-01 to 2026-07-31.
- Invested simulation range: 2018-05-02 to 2026-07-31.
- Code commit: `7bcb77751be0a13ab8d322b4e7253611a3b5d2db`.
- Both sample and baseline manifests recorded a clean worktree.
- Signal: 60-session momentum, monthly Top-3, equal target weight.

## Headline Result

| Metric | 10 bps |
| --- | ---: |
| Total return | 108.47% |
| Annualized return | 9.68% |
| Annualized volatility | 25.94% |
| Sharpe, zero rate | 0.486 |
| Maximum drawdown | -42.02% |
| Rebalances | 99 |
| Total one-way turnover | 49.16 |

The maximum drawdown runs from the 2021-01-07 equity peak to the 2022-12-20
trough. No selected asset was marked non-tradable on its execution date.

## Cost Sensitivity

| Cost assumption | Annualized return | Sharpe | Maximum drawdown |
| --- | ---: | ---: | ---: |
| 10 bps | 9.68% | 0.486 | -42.02% |
| 20 bps | 9.00% | 0.462 | -42.80% |
| 30 bps | 8.33% | 0.438 | -43.57% |

## Calendar-Year Path

| Year | Net return |
| --- | ---: |
| 2018, from May | 1.33% |
| 2019 | 27.48% |
| 2020 | 103.99% |
| 2021 | -3.96% |
| 2022 | -32.39% |
| 2023 | 4.34% |
| 2024 | 19.15% |
| 2025 | 5.92% |
| 2026, through July | -7.46% |

## Interpretation

This is a qualified benchmark, not evidence of stable alpha. Aggregate return
depends heavily on 2020, while the 2021-2022 path shows a long, deep failure
regime. Higher costs degrade the result but do not erase it over this sample.

The next falsification task is to reproduce the predecessor project's
market-attention proxy on this exact panel and test whether its reported
2022-2023 defensive behavior survives the new pipeline. Narrative or regime
models should not be implemented before that comparison is reproducible.

## Remaining Limits

- Close-to-close next-panel-date execution remains an approximation.
- The manually chosen live universe is not a historical point-in-time universe.
- Tencent is a convenience source without a licensed data-quality guarantee.
- The zero-rate Sharpe is not an excess-return Sharpe.
- 2018 and 2026 are partial simulation years.
