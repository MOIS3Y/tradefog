import { beforeEach, describe, expect, it, vi } from "vitest";

import { reloadTokens } from "@/api/tokens";
import {
  createTrade,
  openTrade,
  previewPlan,
  savePlan,
  submitTrade,
  updateTrade,
  type PlanningContext,
  type Trade,
} from "@/features/trades/api";
import { assessChecklist } from "@/features/trades/checklist";
import {
  calculateAtrUsage,
  calculateLocalPosition,
  calculatePlannedProfit,
  normalizeToStep,
} from "@/features/trades/planning";
import { calculatePositionScale } from "@/features/trades/positionScale";
import { formatRoundedDecimal } from "@/utils/decimal";

const trade: Trade = {
  id: 21,
  profile_id: 3,
  strategy_id: 7,
  instrument_id: 11,
  trade_date: "2026-09-08",
  status: "draft",
  direction: "long",
  description_markdown: null,
  quality_rating: null,
  review_completed_at: null,
  realized_pnl: null,
  actual_exit_price: null,
  total_commission: null,
  funding_result: null,
  submitted_at: null,
  opened_at: null,
  closed_at: null,
  cancelled_at: null,
  created_at: "2026-09-08T12:00:00",
  checklist: {
    score: "0",
    direction: "NEUTRAL",
    completeness: "0",
    answered_count: 0,
    total_count: 4,
    gauge_position: 50,
    trend_relationship: "UNASSESSED",
    agrees_with_trade: null,
  },
  preparation: {
    planned_entry: null,
    planned_stop: null,
    market_sentiment: null,
    information_background: null,
    global_daily_direction: null,
    local_daily_movement: null,
    atr_value: null,
    atr_source: null,
    atr_contributing_date: null,
    atr_observation_time: null,
    atr_stale: false,
    observed_session_range: null,
  },
  reservations: [],
  plan: null,
  atr: null,
  snapshot: null,
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  window.localStorage.clear();
  reloadTokens();
  vi.unstubAllGlobals();
});

describe("trade lifecycle client", () => {
  it("distinguishes neutral context from a weak directional lean", () => {
    expect(
      assessChecklist(["NEUTRAL", "NEUTRAL", "NEUTRAL", "NEUTRAL"], "long")
        .verdict,
    ).toBe("balanced");
    expect(
      assessChecklist(["POSITIVE", "NEUTRAL", "NEUTRAL", "NEUTRAL"], "long")
        .verdict,
    ).toBe("lean");
    expect(
      assessChecklist(["POSITIVE", "NEUTRAL", "NEUTRAL", "NEUTRAL"], "short")
        .verdict,
    ).toBe("conflict");
  });

  it("calculates an executable plan locally without float loss", () => {
    const context: PlanningContext = {
      price_step: "0.01",
      quantity_step: "0.7",
      minimum_quantity: null,
      minimum_notional: null,
      reward_multiple: 3,
      planned_risk_percent: "1",
      target_risk_amount: "10",
      allocation_capital: "1000",
      already_reserved_risk: "0",
      remaining_risk_capacity: "1000",
      risk_stop_capital: null,
      wallet_balance: "10000",
      wallet_reserved: "0",
      wallet_available: "10000",
      deposit_floor_breach: false,
      product: "spot",
      direction: "long",
      base_asset_id: 1,
      settlement_asset_id: 2,
      inventory_wallet_asset_id: 4,
      inventory_available: "10",
    };
    const plan = calculateLocalPosition(context, "long", "100", "97", "20");

    expect(plan.planned_take_profit).toBe("109");
    expect(plan.quantity).toBe("2.8");
    expect(plan.planned_risk_amount).toBe("8.4");
    expect(plan.target_risk_amount).toBe("10");
    expect(plan.capital_remaining).toBe("9720");
    const shortContext = {
      ...context,
      quantity_step: "0.001",
      wallet_available: "20",
      inventory_available: "1",
    };
    const short = calculateLocalPosition(shortContext, "short", "100", "110");
    expect(short).toMatchObject({
      capital_remaining: "10",
      capital_sufficient: true,
      inventory_required: "1",
      settlement_required: "10",
    });
    expect(
      calculateLocalPosition(
        { ...shortContext, inventory_available: "0.9" },
        "short",
        "100",
        "110",
      ).capital_sufficient,
    ).toBe(false);
    expect(
      calculateLocalPosition(
        { ...shortContext, inventory_wallet_asset_id: null },
        "short",
        "100",
        "110",
      ).capital_sufficient,
    ).toBe(false);
    expect(
      calculateLocalPosition(
        { ...shortContext, product: "perpetual_future" },
        "short",
        "100",
        "110",
      ),
    ).toMatchObject({
      capital_remaining: "-80",
      capital_sufficient: false,
      inventory_required: "0",
    });
    expect(calculatePlannedProfit("8.4", 3)).toBe("25.2");
    expect(calculateAtrUsage("15", "40")).toBe("37.5");
    expect(normalizeToStep("100.005", "0.01")).toBe("100.01");
    expect(formatRoundedDecimal("123.456789012345678", 2)).toBe("123.46");
    expect(formatRoundedDecimal("0.004", 2)).toBe("0");
  });

  it("maps long, short, and out-of-range exits onto a readable scale", () => {
    const long = calculatePositionScale("long", "100", "95", "115", "110");
    const short = calculatePositionScale("short", "100", "105", "85", "90");
    const moderate = calculatePositionScale("long", "100", "95", "115", "120");
    const extreme = calculatePositionScale("long", "100", "95", "115", "200");

    expect(long).toMatchObject({ stop: 0, entry: 25, target: 100, exit: 75 });
    expect(short).toMatchObject({ stop: 0, entry: 25, target: 100, exit: 75 });
    expect(moderate).toMatchObject({
      stop: 0,
      entry: 20,
      target: 80,
      exit: 100,
      exitOverflow: null,
    });
    expect(extreme.exitOverflow).toBe("profit");
    expect(extreme.exit).toBe(100);
    expect(extreme.entry).toBeCloseTo(16.67, 2);
    expect(extreme.target).toBeCloseTo(66.67, 2);
  });

  it("keeps target-based planning and lifecycle actions explicit", async () => {
    const requests: Request[] = [];
    const plan = {
      planned_entry: "100",
      planned_stop: "95",
      planned_take_profit: "115",
      stop_distance: "5",
      take_profit_distance: "15",
      quantity: "20",
      reward_multiple: 3,
      planned_risk_percent: "1",
      target_risk_amount: "100",
      planned_risk_amount: "100",
      planned_notional: "2000",
      allocation_capital: "10000",
      already_reserved_risk: "0",
      remaining_risk_capacity: "9900",
      deposit_floor_breach: false,
      wallet_balance: "10000",
      wallet_reserved: "0",
      wallet_available: "10000",
      capital_remaining: "8000",
      capital_sufficient: true,
      atr_value: "40",
      take_profit_atr_percent: "37.5",
      fits_atr_limit: true,
      atr_limit_percent: "75",
    };
    const submittedTrade: Trade = {
      ...trade,
      status: "pending_entry",
      submitted_at: "2026-09-08T12:15:00Z",
      snapshot: {
        id: 31,
        instrument_symbol: "BTCUSDT",
        instrument_product: "spot",
        price_step: "0.01",
        qty_step: "0.001",
        min_qty: null,
        min_notional: null,
        strategy_capital_id: 17,
        settlement_asset_id: 5,
        planned_entry: "100",
        planned_stop: "95",
        planned_take_profit: "115",
        quantity: "20",
        reward_multiple: "3",
        planned_risk_percent: "1",
        planned_risk_amount: "100",
        planned_notional: "2000",
        allocation_capital: "10000",
        risk_stop_capital: null,
        already_reserved_risk: "0",
        remaining_risk_capacity: "9900",
        deposit_floor_breach: false,
        wallet_balance: "10000",
        wallet_reserved: "0",
        wallet_available: "10000",
        atr_value: "40",
        atr_source: "manual",
        atr_contributing_date: "2026-09-08",
        atr_observation_time: "2026-09-08T12:10:00Z",
        atr_stale: false,
        created_at: "2026-09-08T12:15:00Z",
        stop_distance: "5",
        take_profit_distance: "15",
      },
    };
    const responses = [
      jsonResponse(trade, 201),
      jsonResponse(plan),
      jsonResponse({
        ...trade,
        plan: {
          planned_entry: "100",
          planned_stop: "95",
        },
      }),
      jsonResponse(submittedTrade),
      jsonResponse({ ...submittedTrade, status: "open" }),
      jsonResponse({ ...submittedTrade, status: "open", quality_rating: 9 }),
    ];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        requests.push(input as Request);
        return responses.shift() as Response;
      }),
    );

    await createTrade({
      profile_id: 3,
      strategy_id: 7,
      instrument_id: 11,
      trade_date: "2026-09-08",
      direction: "long",
    });
    const input = {
      planned_entry: "100",
      planned_stop: "90",
    };
    await previewPlan(trade.id, input);
    await savePlan(trade.id, input);
    const submitted = await submitTrade(trade.id, "pending_entry");
    await openTrade(trade.id);
    const rated = await updateTrade(trade.id, { quality_rating: 9 });

    expect(requests.map((request) => request.method)).toEqual([
      "POST",
      "POST",
      "PUT",
      "POST",
      "POST",
      "PATCH",
    ]);
    expect(submitted.snapshot?.strategy_capital_id).toBe(17);
    expect(submitted.snapshot?.reward_multiple).toBe("3");
    expect(rated.quality_rating).toBe(9);
    expect(await requests[1]?.clone().json()).toEqual(input);
    expect(new URL(requests[4]?.url ?? "").pathname).toBe(
      `/api/v1/trades/${trade.id}/open`,
    );
    expect(await requests[5]?.clone().json()).toEqual({ quality_rating: 9 });
  });
});
