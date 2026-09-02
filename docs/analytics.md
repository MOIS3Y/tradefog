# Tradefog analytics

## Purpose

Analytics evaluates the quality and consistency of trading decisions over a
series of closed trades. It helps answer four practical questions:

1. Is the strategy producing a positive normalized result?
2. How difficult was the path to that result?
3. Where do the result and risk differ by profile, strategy, instrument,
   product, or direction?
4. Are the strategy rules followed consistently, and which recorded errors
   recur?

Analytics does not estimate a guaranteed probability of profit, rate the
trader with an invented composite score, or encourage a target trading
frequency. A checklist assessment describes alignment with the documented
strategy, not the probability of a successful trade.

## Shared analytical selection

The page has one global filter context. Unless a section explicitly states
otherwise, every summary, graph, and table uses the same selected trades.

The global filters are:

- period: all time, rolling 30 or 90 days, year to date, rolling year, or a
  custom inclusive date range;
- trading profile;
- trading strategy;
- product;
- profile instrument, displayed by its canonical trading pair.

`trade_date` is the source of truth for period filtering. Execution and audit
timestamps do not move a trade between analytical periods. Closed trades are
ordered by `trade_date`, creation time, and identifier so that calculations
are deterministic.

A `ProfileInstrument` belongs to one profile product and links to a reusable
venue instrument. Strategy-compatible selections have the same profile and
exactly the same settlement asset as the strategy. Filter choices narrow in
the sequence profile, strategy, product, and instrument. A lower-level
selection does not silently widen or replace an explicit higher-level
selection.

Changing the global filter recalculates the complete selection. In
particular, a filtered trajectory starts again at `(0, 0)`; it does not
continue from the lifetime coordinate. Corrections to journal facts also
recalculate the affected analytics.

Individual visualizations may have local presentation controls, such as a
rolling-window length, grouping dimension, or chart scale. Such controls do
not replace or widen the global selection.

## Common definitions

Only `CLOSED` trades participate in result-quality calculations. For each
closed trade:

```text
result_r = realized_pnl / planned_risk_amount
```

The trade is classified as:

- a win when `result_r > 0`;
- a loss when `result_r < 0`;
- break-even when `result_r = 0`.

All exact financial and R calculations are performed on the server with
decimal arithmetic. Chart coordinates may be converted to JavaScript numbers
only for presentation. ApexCharts renders data; it does not own business
formulas.

Ratios and averages are always displayed together with the number of trades.
Tradefog does not currently impose an arbitrary minimum sample size at which
a strategy becomes statistically valid.

Wallet deposits, withdrawals, and strategic capital do not enter normalized
strategy-quality calculations. They may appear in wallet or strategy context,
but they must not change R, X/Y trajectory, win rate, payoff, or drawdown in R.

## Result and outcome summary

The result summary gives a compact description of the selected series:

- closed trade count;
- wins, losses, and break-even trades;
- win rate;
- net and average result in R;
- gross profit and gross loss in R;
- current and maximum winning or losing streak.

The formulas are:

```text
net_result_r = sum(result_r)
average_result_r = net_result_r / closed_trade_count
gross_profit_r = sum(max(result_r, 0))
gross_loss_r = sum(abs(min(result_r, 0)))
win_rate = winning_trade_count / closed_trade_count * 100
```

Break-even trades remain in the closed-trade and win-rate denominator. They
end the current winning or losing streak because they belong to neither one.

## Strategy trajectory

### X/Y trajectory

The X/Y chart visualizes the path through full-stop and full-target
equivalents while preserving partial and manual outcomes:

```text
X += abs(min(result_r, 0))
Y += max(result_r, 0) / reward_multiple
```

Every submitted trade preserves its reward multiple. With the current fixed
`1:3` strategy, the break-even line is:

```text
Y = X / 3
```

There is no target line. The path and its ordered decision table are more
informative than the final coordinate alone: the same endpoint reached in a
short clean series differs from one reached through many mixed outcomes.

### Cumulative R

Cumulative R shows how the normalized result evolves in chronological order:

```text
cumulative_r[0] = 0
cumulative_r[i] = cumulative_r[i - 1] + result_r[i]
```

Unlike X/Y, this chart makes the magnitude and timing of partial results easy
to read on one axis. It is also the source series for drawdown calculations.

### Drawdown in R

Drawdown measures deterioration from the best previous cumulative-R result,
without mixing in deposits or capital size:

```text
peak_r[i] = max(0, cumulative_r[1], ..., cumulative_r[i])
drawdown_r[i] = peak_r[i] - cumulative_r[i]
```

`drawdown_r` is a non-negative magnitude. Useful values are:

- current drawdown at the final selected trade;
- maximum drawdown in the selected series;
- current drawdown duration in trades;
- maximum drawdown duration in trades;
- whether the previous peak has been recovered.

Duration counts closed trades after a peak until cumulative R reaches or
exceeds that peak. An unrecovered interval ends at the end of the selection.

### Rolling average R

Rolling average R exposes recent improvement or deterioration without a
calendar-frequency assumption. A point for a window of `N` trades is:

```text
rolling_average_r[i] = sum(result_r[i - N + 1:i + 1]) / N
```

The initial incomplete window is not displayed. Practical initial windows
are 10, 20, and 50 trades, selected locally on the chart.

## Profitability and payoff

Win rate alone cannot describe a strategy with asymmetric outcomes. It is
interpreted together with average win, average loss, payoff, and profit
factor.

```text
average_win_r = gross_profit_r / winning_trade_count
average_loss_r = gross_loss_r / losing_trade_count
payoff_ratio = average_win_r / average_loss_r
profit_factor = gross_profit_r / gross_loss_r
breakeven_win_rate = average_loss_r
    / (average_win_r + average_loss_r) * 100
```

Average loss is displayed as a positive magnitude. Payoff and break-even win
rate are undefined when the selection has no wins or no losses. Profit factor
is undefined when gross loss is zero; the interface displays no finite value
instead of claiming infinite performance.

Median R, best R, and worst R complement the averages. Median R reduces the
influence of a few extreme outcomes, while best and worst R reveal outliers
that should be inspected in the journal.

## Outcome distribution

Distribution reveals whether the strategy produces its intended result shape
or relies on unusual exits. Domain-oriented buckets are more actionable than
an arbitrary histogram:

- worse than `-1R`;
- exactly `-1R`;
- between `-1R` and `0R`;
- exactly `0R`;
- between `0R` and `+3R`;
- exactly `+3R`;
- better than `+3R`.

The buckets distinguish excess losses, full stops, reduced losses, manual or
partial profits, full targets, and outcomes beyond the planned target. They
do not imply that every deviation is an error; journal context remains the
source for that conclusion.

## Comparative breakdowns

The selected series can be grouped by:

- trading profile;
- trading strategy;
- canonical venue instrument;
- product;
- `LONG` or `SHORT` direction.

Each group shows at least trade count, net R, average R, win rate, payoff,
profit factor, and maximum drawdown in R. Group calculations restart from
zero and retain deterministic chronological ordering within the group.

Normalized R can be compared across profiles, strategies, and currencies.
Monetary values cannot be combined across different currencies without a
defined conversion policy. Profile, strategy, and sample size remain visible
so that a small group is not mistaken for strong evidence.

## Monetary result

Net realized P&L answers a different question from strategy quality: how much
money was actually recorded. It is displayed by strategy and settlement
asset. Values in unlike currencies are not summed into a synthetic total.

Recorded realized P&L is already net and may include fees, slippage, funding,
stops, targets, and manual exits. Optional commission and funding fields are
useful for explaining costs, but must not be subtracted a second time.
Coverage is shown whenever only some trades have those optional details.

Strategy virtual equity is labelled as strategic capital plus its realized
P&L. It is not a wallet balance or a cash-flow-adjusted investment return.

## Decision quality and journal review

These capabilities require the corresponding checklist and post-trade data:

- result by checklist assessment range;
- agreement or disagreement between selected direction and checklist result;
- result by strategy-compliance state;
- repeated execution and analysis errors;
- conclusions and review completion;
- comparison of considered, submitted, cancelled, and completed setups.

Outcome comparisons in this section still use closed trades. The setup funnel
is the explicit exception: it includes non-closed states to describe which
documented decisions progressed to execution and completion.

These views support journal review and hypothesis formation. Correlation
between a checklist value and an outcome is not presented as proof of
causation or as a probability of profit.

## Presentation structure

The analytics page uses one global filter area followed by progressively more
detailed sections:

1. result and outcome summary;
2. X/Y and cumulative-R trajectory;
3. drawdown and payoff metrics;
4. outcome distribution and comparative breakdowns;
5. monetary result;
6. decision-quality and journal-review analysis.

Empty selections show an explicit no-data state. Undefined ratios show an
em dash with an explanation where needed; they are never coerced to zero.
Tables accompany charts when exact values or individual trades are important.

## Analytics roadmap

This roadmap is local to the analytics feature. Its order follows practical
value and calculation dependencies rather than the project's implementation
stages.

### Shared foundation and core trajectory

- [x] Owner-scoped selection of closed trades with deterministic ordering.
- [x] Global period, profile, product, and instrument filters in the current
  model.
- [x] Recalculation of filtered results and trajectory from the origin.
- [x] Closed, win, loss, break-even, and win-rate summary.
- [x] Net, average, gross-profit, and gross-loss R metrics.
- [x] Current and maximum winning or losing streaks.
- [x] X/Y trajectory, break-even line, and ordered decision table.
- [x] Localized HTMX filtering and ApexCharts presentation.

### Result path and risk

- [ ] Add the cumulative-R series and chart.
- [ ] Derive current and maximum drawdown from cumulative R.
- [ ] Add the drawdown-in-R chart.
- [ ] Add current and maximum drawdown duration and recovery state.

### Payoff and result shape

- [ ] Add average win and average loss in R.
- [ ] Add payoff ratio and profit factor with undefined-value states.
- [ ] Add break-even win rate derived from observed payoff.
- [ ] Add median, best, and worst result in R.
- [ ] Add the domain-oriented outcome distribution.

### Comparison and recent behavior

- [ ] Add breakdowns by profile, strategy, instrument, product, and direction.
- [ ] Recalculate maximum drawdown and payoff inside each group.
- [ ] Add rolling average R with 10, 20, and 50-trade windows.

### Monetary context

- [ ] Add realized P&L grouped by strategy and currency.
- [ ] Show commission and funding coverage without double subtraction.
- [ ] Add strategy virtual equity and wallet activity as separate context.

### Decision quality and review

- [ ] Add result analysis by checklist assessment range.
- [ ] Compare direction agreement and disagreement with checklist output.
- [ ] Add strategy-compliance and recurring-error breakdowns.
- [ ] Add review-completion and conclusion coverage.
- [ ] Compare considered, submitted, cancelled, and completed setups.

### Validation and maintainability

- [ ] Add focused tests for every new metric and undefined edge case.
- [ ] Add cross-section tests proving that all widgets share one selection.
- [ ] Add query-count checks when comparative sections are implemented.
- [ ] Document any deliberate change to formulas before migrating history.
