# Analytics Specification

## Purpose

Tradefog analytics measures the quality and consistency of trading decisions
across a sequence of closed trades. It isolates execution quality from capital
fluctuations.

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

### 3. Cumulative Quality Trajectory (X/Y)

The X/Y trajectory visualizes performance over time:

- **X-axis**: Trade sequence index (or trade date).
- **Y-axis**: Cumulative Net R ($\sum \text{result\_r}$).
- **Break-even Reference Line**: For a strategy with a $1:3$ reward ratio,
  represents the expected trajectory for break-even performance.
- **Trajectory Reset**: Changing filters recalculates the curve from `(0, 0)`.

## Filter Cohorts

Analytics calculations support global multi-dimensional filtering:

- **Date Range**: All-time, 30 days, 90 days, Year-to-Date, or Custom Range
  (filtered by `trade_date`).
- **Profile**: Specific `TradingProfile`.
- **Strategy**: Specific `TradingStrategy`.
- **Product**: `SPOT`, `PERPETUAL_FUTURE`, `CASH_EQUITY`.
- **Instrument / Pair**: Specific canonical trading pair.
- **Settlement Asset**: Specific currency (for monetary views).

Financial and statistical calculations execute on the backend with exact
decimal precision.
