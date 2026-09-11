/** Boundary parity with backend sizing: zero is never executable quantity. */
import { describe, expect, it } from "vitest";
import type { PlanningContext } from "@/features/trades/api";
import {
  calculateLocalPosition,
  calculateAtrUsage,
  normalizeToStep,
  previewPosition,
} from "@/features/trades/planning";

const context: PlanningContext = {
  price_step: "0.01",
  quantity_step: "1",
  minimum_quantity: null,
  minimum_notional: null,
  reward_multiple: 3,
  planned_risk_percent: "1",
  target_risk_amount: "1",
  allocation_capital: "100",
  already_reserved_risk: "0",
  remaining_risk_capacity: "1",
  risk_stop_capital: null,
  wallet_balance: "1000",
  wallet_reserved: "0",
  wallet_available: "1000",
  deposit_floor_breach: false,
  product: "cash_equity",
  direction: "long",
  base_asset_id: 1,
  settlement_asset_id: 2,
  inventory_asset_id: 1,
  inventory_available: "10",
};

describe("executable quantity boundaries", () => {
  it("keeps price geometry and minimum risk when capital cannot fund one unit", () => {
    expect(previewPosition(context, "long", "250", "120")).toMatchObject({
      target: "640",
      distance: "130",
      minimumQuantity: "1",
      minimumRisk: "130",
      minimumCost: "250",
    });
    expect(() => calculateLocalPosition(context, "long", "250", "120")).toThrow(
      "quantityBelowMinimum",
    );
    expect(previewPosition(context, "long", "", "120")).toBeNull();
    expect(previewPosition(context, "long", "100", "110")).toBeNull();
  });
  it("aligns combined instrument minimums before calculating required risk", () => {
    expect(
      previewPosition(
        {
          ...context,
          quantity_step: "0.7",
          minimum_quantity: "1",
          minimum_notional: "250",
        },
        "long",
        "100",
        "90",
      ),
    ).toMatchObject({ minimumQuantity: "2.8", minimumRisk: "28" });
  });
  it.each(["0", "1", "9.999999999999999999"])(
    "rejects risk %s below one whole unit",
    (risk) => {
      expect(() =>
        calculateLocalPosition(
          { ...context, target_risk_amount: risk },
          "long",
          "100",
          "90",
        ),
      ).toThrow("quantityBelowMinimum");
    },
  );
  it("accepts exactly one step and never rounds risk upward", () => {
    for (const risk of [
      "10",
      "10.000000000000000001",
      "19.999999999999999999",
    ]) {
      expect(
        calculateLocalPosition(
          { ...context, target_risk_amount: risk },
          "long",
          "100",
          "90",
        ),
      ).toMatchObject({
        quantity: "1",
        planned_risk_amount: "10",
        planned_notional: "100",
      });
    }
  });
  it("accepts fractional and very small valid units", () => {
    expect(
      calculateLocalPosition(
        { ...context, quantity_step: "0.1" },
        "long",
        "100",
        "90",
      ).quantity,
    ).toBe("0.1");
    expect(
      calculateLocalPosition(
        {
          ...context,
          quantity_step: "0.00000001",
          target_risk_amount: "0.0000001",
        },
        "long",
        "100",
        "90",
      ).quantity,
    ).toBe("0.00000001");
  });
  it("enforces quantity and notional minima, accepting exact equality", () => {
    const valid = {
      ...context,
      target_risk_amount: "10",
      minimum_quantity: "1",
      minimum_notional: "100",
    };
    expect(calculateLocalPosition(valid, "long", "100", "90").quantity).toBe(
      "1",
    );
    expect(() =>
      calculateLocalPosition(
        { ...valid, minimum_quantity: "1.1" },
        "long",
        "100",
        "90",
      ),
    ).toThrow("quantityBelowMinimum");
    expect(() =>
      calculateLocalPosition(
        { ...valid, minimum_notional: "100.01" },
        "long",
        "100",
        "90",
      ),
    ).toThrow("notionalBelowMinimum");
  });
  it("rejects zero prices, collapsed stops and zero short targets", () => {
    expect(() => calculateLocalPosition(context, "long", "100", "0")).toThrow(
      "invalidPlan",
    );
    expect(() =>
      calculateLocalPosition(context, "long", "100", "99.999"),
    ).toThrow("invalidLongStop");
    expect(() => calculateLocalPosition(context, "short", "30", "40")).toThrow(
      "nonPositiveTarget",
    );
    expect(() =>
      calculateLocalPosition(context, "short", "100", "110"),
    ).toThrow("quantityBelowMinimum");
    expect(calculateAtrUsage("10", "0")).toBeNull();
    expect(normalizeToStep("100", "0")).toBe("100");
  });
});
