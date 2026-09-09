/** Plain-language explanations for the analytics workspace. */
export const analyticsHelp = {
  netR: {
    ru: "Сумма результатов закрытых сделок в единицах риска (R). Для каждой сделки чистый P&L делится на риск позиции при её отправке. Например, две победы по +3R и четыре потери по −1R дают +2R. Это не процент доходности.",
    en: "The sum of closed-trade results in risk units (R). Each net P&L is divided by the position risk frozen at submission. Two +3R wins and four −1R losses give +2R. This is not a percentage return.",
  },
  expectancy: {
    ru: "Средний результат одной сделки в выбранной истории. Например, +6R за 10 сделок — это +0,6R на сделку. Показывает прошлый результат, а не обещает такой же доход в будущем.",
    en: "The average result per trade in this selection. For example, +6R over 10 trades means +0.6R per trade. It describes past results, not a promise of future returns.",
  },
  winRate: {
    ru: "Доля сделок с положительным чистым результатом среди всех закрытых, включая сделки в ноль. Например, 3 прибыльные из 10 дают 30%. Низкая доля побед может сочетаться с прибылью, если победы покрывают потери.",
    en: "Profitable trades as a share of all closed trades, including break-even trades. Three wins out of ten give 30%. A low win rate can still be profitable when wins outweigh losses.",
  },
  drawdown: {
    ru: "Самое большое падение накопленного результата от достигнутого пика до последующего минимума в выбранном периоде. Например, рост до +5R и падение до +2R дают просадку 3R. Начальная точка — 0R.",
    en: "The largest fall from a cumulative-result peak to a later low within this selection. A rise to +5R followed by a fall to +2R gives a 3R drawdown. The starting point is 0R.",
  },
  profitFactor: {
    ru: "Суммарная прибыль в R, делённая на суммарные потери в R. Например, +9R прибыли и 3R потерь дают 3: на единицу потерь пришлось три единицы прибыли. Выше 1 — прибыль, ниже 1 — убыток. Прочерк означает, что потерь нет и делить не на что.",
    en: "Total gains in R divided by total losses in R. Gains of 9R and losses of 3R give 3. Above 1 means a profit; below 1 means a loss. A dash means there are no losses to divide by.",
  },
  averageR: {
    ru: "Итоговый R, делённый на число закрытых сделок. Например, +4R за 8 сделок дают +0,5R. В текущем расчёте совпадает с матожиданием: это два способа выразить средний результат.",
    en: "Net R divided by the number of closed trades. +4R over eight trades gives +0.5R. In this calculation it equals expectancy: both describe the average result.",
  },
  averageRating: {
    ru: "Средняя выставленная вами оценка качества сделки по шкале от 1 до 10. Например, оценки 6 и 8 дают 7. Сделки без оценки не учитываются; если оценок нет, показан прочерк. Прибыльность не определяет оценку автоматически.",
    en: "The average quality score you assigned, from 1 to 10. Scores of 6 and 8 average to 7. Unrated trades are excluded; a dash means no ratings. Profitability does not automatically determine the score.",
  },
  wins: {
    ru: "Число закрытых сделок с чистым P&L больше нуля. Даже частичный выход с +0,2R считается одной прибыльной сделкой.",
    en: "Closed trades with net P&L above zero. Even a partial exit at +0.2R counts as one win.",
  },
  losses: {
    ru: "Число закрытых сделок с чистым P&L меньше нуля. И −0,2R, и −1R считаются одной убыточной сделкой, но по-разному влияют на итоговый R.",
    en: "Closed trades with net P&L below zero. Both −0.2R and −1R count as one loss, but affect net R differently.",
  },
  breakEven: {
    ru: "Число сделок с чистым P&L ровно ноль. Выход по цене входа с расходами может оказаться убыточным. Сделка в ноль прерывает серию побед или потерь.",
    en: "Trades with net P&L exactly zero. An exit at the entry price can still be a loss after costs. A break-even trade interrupts a win or loss streak.",
  },
  currentStreak: {
    ru: "Последовательность одинаковых исходов в конце выбранной истории, по времени закрытия. Например, победа, потеря, потеря — текущая серия из двух потерь. Сделка в ноль сбрасывает серию.",
    en: "The run of matching outcomes at the end of the selection, ordered by closing time. Win, loss, loss gives a current streak of two losses. Break-even resets the streak.",
  },
  bestWinStreak: {
    ru: "Самое большое число прибыльных сделок подряд в выбранной истории. Например, победа, победа, потеря, победа — максимальная серия из двух побед.",
    en: "The longest run of profitable trades in the selection. Win, win, loss, win has a longest winning streak of two.",
  },
  worstLossStreak: {
    ru: "Самое большое число убыточных сделок подряд в выбранной истории. Например, три потери до следующей победы дают серию из трёх потерь.",
    en: "The longest run of losing trades in the selection. Three losses before the next win give a losing streak of three.",
  },
  review: {
    ru: "Доля закрытых сделок, для которых вы нажали «Завершить разбор». Например, 6 разобранных из 10 — 60%. Все закрытые сделки участвуют в аналитике, даже если разбор ещё не завершён.",
    en: "The share of closed trades marked as reviewed. Six reviewed out of ten means 60%. All closed trades contribute to analytics, even before review is complete.",
  },
  trajectory: {
    ru: "Как менялся накопленный R после каждой закрытой сделки. По горизонтали — порядок закрытия, по вертикали — общий результат. Например, +3R, −1R, +3R дают точки 3, 2 и 5R. При смене фильтров путь начинается заново с нуля.",
    en: "Cumulative R after each closed trade. The horizontal axis is closing order; the vertical axis is the total result. +3R, −1R, +3R give points at 3, 2 and 5R. Changing filters restarts the path at zero.",
  },
  discipline: {
    ru: "Потери двигают точку вправо, прибыль — вверх. При 1:3 потеря −1R добавляет один полный стоп, прибыль +3R — один полный тейк; +1,5R добавляет половину тейка. На пунктирной линии результат нулевой, выше — прибыль, ниже — убыток. График строится для одной аллокации; короткая удачная серия ещё не доказывает устойчивость стратегии.",
    en: "Losses move the point right; profits move it up. At 1:3, −1R adds one full stop, +3R one full target, and +1.5R half a target. The dashed line means break-even; above it is profit, below it is loss. This chart uses one allocation. A short successful run does not establish a strategy's reliability.",
  },
  grossProfit: {
    ru: "Сумма положительных чистых P&L этой аллокации за выбранный период. Например, +10, +20 и −5 USDT дают 30 USDT в «Принесла». Расходы уже входят в записанный чистый результат и повторно не вычитаются.",
    en: "The sum of positive net P&L for this allocation in the selected period. +10, +20 and −5 USDT give 30 USDT in gross profit. Costs are already included in recorded net results and are not subtracted again.",
  },
  grossLoss: {
    ru: "Сумма потерь по убыточным сделкам этой аллокации. Например, −5 и −8 USDT означают, что стратегия забрала 13 USDT. Вывод средств из кошелька сюда не входит.",
    en: "Total losses from losing trades in this allocation. −5 and −8 USDT mean 13 USDT lost. Wallet withdrawals do not count as trading losses.",
  },
  return: {
    ru: "Чистый P&L за выбранный период относительно фиксированного капитала аллокации. Например, +20 USDT при аллокации 100 USDT дают +20%. Это доходность выбранного периода, не годовая; пополнения и выводы не являются P&L.",
    en: "Net P&L for the selected period divided by the fixed allocation capital. +20 USDT on a 100 USDT allocation gives +20%. This is the selected period's return, not an annualized return. Deposits and withdrawals are not P&L.",
  },
  trades: {
    ru: "Число закрытых сделок в выбранном периоде, по дате закрытия. Черновики, ожидающие, открытые и отменённые сделки не учитываются. Например, открытая в августе и закрытая в сентябре сделка входит в сентябрь.",
    en: "The number of trades closed in the selected period, based on closing date. Draft, pending, open and cancelled trades are excluded. A trade opened in August and closed in September belongs to September.",
  },
  netMoney: {
    ru: "Сколько аллокация принесла за вычетом потерь по закрытым сделкам. Например, принесла 30 и забрала 10 USDT — итог +20 USDT. Разные аллокации и валюты не складываются. Линия ниже показывает накопление этого результата по сделкам.",
    en: "What this allocation earned after trading losses. Gains of 30 and losses of 10 USDT give +20 USDT. Different allocations and currencies are not added together. The line below shows this result accumulating trade by trade.",
  },
} as const;

export type AnalyticsHelpKey = keyof typeof analyticsHelp;
