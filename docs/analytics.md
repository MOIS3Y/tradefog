# Analytics Specification

## Purpose

Tradefog analytics determines whether fixed risk rules produce a sustainable
sequence of decisions. It separates dimensionless trading quality from money,
wallet movements, and capital size.

Metrics are calculated on demand by the backend from immutable snapshots and
closed trades. The MVP does not persist summary or rollup tables; filters
always produce a fresh exact-decimal aggregation. The client presents the
returned result and does not independently recompute authoritative analytics.

## Core Metrics

All quality calculations use only `CLOSED` trades.

### 1. Dimensionless R-Multiple (`result_r`)

For each closed trade:

```text
result_r = net_realized_pnl / planned_risk_amount
```

- **Win**: `result_r > 0`
- **Loss**: `result_r < 0`
- **Break-even**: `result_r == 0`

Because `result_r` is dimensionless, metrics can be aggregated across
different currencies without mixing monetary units.

### 2. Summary Statistics

- **Trade Count ($N$)**: Total closed trades in the cohort.
- **Win Rate**: $\text{Wins} / N \times 100\%$
- **Net R**: $\sum \text{result\_r}$
- **Average R ($\bar{R}$)**: $\text{Net R} / N$
- **Profit Factor (R)**: $\sum \text{Gross Gains (R)} / |\sum \text{Gross Losses (R)}|$
- **Expectancy (R)**: $(\text{Win Rate} \times \text{Avg Win R}) - (\text{Loss Rate} \times |\text{Avg Loss R}|)$
- **Max Drawdown (R)**: Peak-to-trough decline in cumulative Net R.
- **Streaks**: Maximum consecutive winning and losing trades.
- **Average Quality Rating**: Mean of available optional integer ratings from
  `1` through `10`; unrated trades do not become zero-rated observations.
- **Review Coverage**: Count of closed trades with a completed post-trade
  review. Unreviewed closed trades remain in financial and quality metrics.

### 3. Strategy Discipline Trajectory (L/W)

The primary plane belongs to one profile, strategy, and concrete capital
allocation. Every closed trade adds one chronological point:

- **L-axis (X)**: cumulative full-stop equivalents,
  `sum(abs(negative result_r))`.
- **W-axis (Y)**: cumulative full-target equivalents,
  `sum(positive result_r / snapshotted_reward_multiple)`.
- **Break-even Reference Line**: `Y = X / reward_multiple`. For `1:3`, one
  target equivalent offsets three stop equivalents.
- **Trajectory Reset**: Changing filters recalculates the curve from `(0, 0)`.

Fractional exits remain honest: `+1.5R` advances Y by `0.5` for a `1:3`
strategy, while `-0.4R` advances X by `0.4`. Points above the reference line
are profitable; points below it signal that the selected strategy cohort is
losing. Fewer trades can produce a more efficient result, but sample size and
Average R remain visible because a short sequence is less statistically
reliable.

The L/W plane is not produced for mixed strategies or allocations because
different reward rules and capital cohorts do not share one meaningful
reference line.

### 4. Monetary Performance

Money is aggregated only inside one concrete `StrategyCapital` and its frozen
settlement asset:

```text
gross_profit_money = sum(positive net_realized_pnl)
gross_loss_money = sum(abs(negative net_realized_pnl))
net_pnl_money = gross_profit_money - gross_loss_money
allocation_return_percent = net_pnl_money / allocation_capital * 100
```

Deposits and withdrawals are wallet movements and never strategy P&L.
`net_realized_pnl` is authoritative and already includes execution costs;
commission and funding fields are explanatory breakdowns and must not be
applied to it a second time. Monetary trajectory points include the individual
and cumulative net P&L in the settlement asset.

Cross-allocation and cross-currency pages may aggregate normalized R. They must
return monetary results as separate allocation groups and never add unlike
assets without an explicit future conversion model.

## Filter Cohorts

Analytics calculations support global multi-dimensional filtering:

- **Date Range**: All-time, 30 days, 90 days, Year-to-Date, or Custom Range.
  Realized performance is filtered and ordered by `closed_at`; `trade_date`
  remains descriptive entry/planning context.
- **Profile**: Specific `TradingProfile`.
- **Strategy**: Specific `TradingStrategy`.
- **Product**: `SPOT`, `PERPETUAL_FUTURE`, `CASH_EQUITY`.
- **Instrument / Pair**: Specific canonical trading pair.
- **Settlement Asset**: Specific currency (for monetary views).
- **Strategy Capital**: Exact immutable allocation cohort required by L/W and
  monetary views.

Financial and statistical calculations execute on the backend with exact
decimal precision.
