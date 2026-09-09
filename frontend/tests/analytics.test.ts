import { beforeEach, describe, expect, it, vi } from "vitest";

import { reloadTokens } from "@/api/tokens";
import { getAnalytics, type Analytics } from "@/features/analytics/api";
import {
  buildDisciplineSeries,
  buildMonetarySeries,
  buildOverviewSeries,
} from "@/features/analytics/chartData";

const analytics: Analytics = {
  closed_trade_count: 2,
  reviewed_trade_count: 1,
  excluded_trade_count: 0,
  win_count: 1,
  loss_count: 1,
  break_even_count: 0,
  win_rate_percent: "50.000000000000000000",
  net_result_r: "2.000000000000000000",
  average_result_r: "1.000000000000000000",
  average_win_r: "3.000000000000000000",
  average_loss_r: "1.000000000000000000",
  gross_profit_r: "3.000000000000000000",
  gross_loss_r: "1.000000000000000000",
  profit_factor_r: "3.000000000000000000",
  expectancy_r: "1.000000000000000000",
  maximum_drawdown_r: "1.000000000000000000",
  current_streak: { outcome: "LOSS", count: 1 },
  maximum_winning_streak: 1,
  maximum_losing_streak: 1,
  average_quality_rating: "8.000000000000000000",
  trajectory: [
    {
      sequence: 1,
      trade_id: 41,
      trade_date: "2026-09-01",
      closed_at: "2026-09-01T12:00:00Z",
      profile_name: "Main",
      product: "spot",
      pair_symbol: "BTC/USD",
      direction: "long",
      result_r: "3.000000000000000000",
      outcome: "WIN",
      cumulative_result_r: "3.000000000000000000",
      discipline_x: "0.000000000000000000",
      discipline_y: "1.000000000000000000",
    },
    {
      sequence: 2,
      trade_id: 42,
      trade_date: "2026-09-02",
      closed_at: "2026-09-02T12:00:00Z",
      profile_name: "Main",
      product: "spot",
      pair_symbol: "ETH/USD",
      direction: "short",
      result_r: "-1.000000000000000000",
      outcome: "LOSS",
      cumulative_result_r: "2.000000000000000000",
      discipline_x: "1.000000000000000000",
      discipline_y: "1.000000000000000000",
    },
  ],
  break_even_reference: [
    { sequence: 0, cumulative_result_r: "0" },
    { sequence: 2, cumulative_result_r: "0" },
  ],
  discipline_available: true,
  discipline_reward_multiple: 3,
  discipline_break_even_reference: [
    { x: "0", y: "0" },
    { x: "3", y: "1" },
  ],
  monetary: [
    {
      strategy_capital_id: 7,
      settlement_asset_id: 2,
      settlement_asset_symbol: "USD",
      allocation_capital: "1000.000000000000000000",
      trade_count: 2,
      gross_profit: "30.000000000000000000",
      gross_loss: "10.000000000000000000",
      net_pnl: "20.000000000000000000",
      allocation_return_percent: "2.000000000000000000",
      trajectory: [
        {
          sequence: 1,
          trade_id: 41,
          closed_at: "2026-09-01T12:00:00Z",
          realized_pnl: "30.000000000000000000",
          cumulative_pnl: "30.000000000000000000",
        },
        {
          sequence: 2,
          trade_id: 42,
          closed_at: "2026-09-02T12:00:00Z",
          realized_pnl: "-10.000000000000000000",
          cumulative_pnl: "20.000000000000000000",
        },
      ],
    },
  ],
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  window.localStorage.clear();
  reloadTokens();
  vi.unstubAllGlobals();
});

describe("analytics presentation", () => {
  it("preserves exact values while preparing all three trajectories", () => {
    const overview = buildOverviewSeries(analytics);
    const discipline = buildDisciplineSeries(analytics);
    const money = buildMonetarySeries(analytics.monetary[0]!);

    expect(overview.trajectory[0]).toMatchObject({
      value: [0, 0],
      tradeId: null,
    });
    expect(overview.trajectory[1]).toMatchObject({
      value: [1, 3],
      exactY: "3.000000000000000000",
      tradeId: 41,
    });
    expect(discipline.trajectory[0]).toMatchObject({
      value: [0, 0],
      tradeId: null,
    });
    expect(discipline.trajectory.at(-1)).toMatchObject({
      value: [1, 1],
      tradeId: 42,
    });
    expect(discipline.reference.at(-1)?.value).toEqual([3, 1]);
    expect(money.at(-1)).toMatchObject({
      value: [2, 20],
      exactY: "20.000000000000000000",
      tradeId: 42,
    });
  });

  it("sends only the selected server filters and custom dates", async () => {
    const requests: Request[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        requests.push(request);
        return jsonResponse(analytics);
      }),
    );

    await getAnalytics({
      period: "custom",
      dateFrom: "2026-09-01",
      dateTo: "2026-09-30",
      profileId: 3,
      strategyId: null,
      product: "spot",
      instrumentId: null,
      pairId: 5,
      settlementAssetId: null,
      strategyCapitalId: 7,
    });

    const url = new URL(requests[0]!.url);
    expect(url.searchParams.get("period")).toBe("custom");
    expect(url.searchParams.get("date_from")).toBe("2026-09-01");
    expect(url.searchParams.get("date_to")).toBe("2026-09-30");
    expect(url.searchParams.get("profile_id")).toBe("3");
    expect(url.searchParams.get("strategy_id")).toBeNull();
    expect(url.searchParams.get("product")).toBe("spot");
    expect(url.searchParams.get("pair_id")).toBe("5");
    expect(url.searchParams.get("strategy_capital_id")).toBe("7");
  });
});
