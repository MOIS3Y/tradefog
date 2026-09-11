/** Exact display calculations do not affect journal values or market I/O. */
import { describe, expect, it } from "vitest";
import { groupLevels, groupingSteps } from "@/features/market-chart/grouping";
import { formatDecimal } from "@/utils/decimal";

describe("exact position values", () => {
  it.each([
    ["505.5809878", "505.5809878"],
    ["0.001234500", "0.0012345"],
    ["0.000000123456789", "0.000000123456789"],
    ["-505.580987800", "-505.5809878"],
    ["1000.0000", "1000"],
    ["0", "0"],
    ["999999.9", "999999.9"],
    ["1e-18", "0.000000000000000001"],
    [
      "12345678901234567890.123456789012345678900",
      "12345678901234567890.1234567890123456789",
    ],
  ])("formats %s as %s without approximation", (value, expected) => {
    expect(formatDecimal(value)).toBe(expected);
  });
});

describe("snapshot aggregation", () => {
  const level = (price: string, size = "0.1") => ({ price, size, total: "0" });
  it("rounds asks up and bids down with exact summed volumes", () => {
    expect(
      groupLevels([level("100.01"), level("100.09", "0.2")], "0.1", "asks"),
    ).toEqual([{ price: "100.1", size: "0.3", total: "0.3" }]);
    expect(
      groupLevels([level("100.09"), level("100.01")], "0.1", "bids"),
    ).toEqual([{ price: "100", size: "0.2", total: "0.2" }]);
  });
  it("aggregates all received levels before limiting display rows", () => {
    const levels = Array.from({ length: 50 }, (_, i) => level(String(100 + i)));
    expect(groupLevels(levels, "100", "asks")).toEqual([
      { price: "100", size: "0.1", total: "0.1" },
      { price: "200", size: "4.9", total: "5" },
    ]);
    expect(groupLevels(levels, "0", "asks")).toHaveLength(20);
    expect(levels[0]!.total).toBe("0");
  });
  it("supports tiny prices and empty snapshots without floating point", () => {
    expect(groupingSteps([level("0.00000001")])).toEqual([
      "0.00000001",
      "0.0000001",
      "0.000001",
      "0.00001",
    ]);
    expect(groupLevels([], "0.1", "bids")).toEqual([]);
  });
});
