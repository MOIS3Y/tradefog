/** Candle display precision is independent of catalog order steps. */
import { expect, it } from "vitest";
import { candlePrecision } from "@/features/market-chart/precision";
import type { Candle } from "@/features/market-chart/types";

const candle: Candle = {
  timestamp: 1000,
  open: "78350.1000",
  high: "78351.1250",
  low: "78349",
  close: "78350.20",
  volume: "0.001200",
};

it("uses all OHLC values and ignores insignificant trailing zeros", () => {
  expect(
    candlePrecision([candle], { pricePrecision: 0, volumePrecision: 0 }),
  ).toEqual({ pricePrecision: 3, volumePrecision: 4 });
});

it("grows for finer prices without shrinking on later integer candles", () => {
  const initial = { pricePrecision: 3, volumePrecision: 4 };
  const finer = candlePrecision([{ ...candle, low: "0.00000001" }], initial);
  expect(finer).toEqual({ pricePrecision: 8, volumePrecision: 4 });
  expect(
    candlePrecision(
      [{ timestamp: 2000, open: "1", high: "2", low: "1", close: "2" }],
      finer,
    ),
  ).toEqual(finer);
  expect(candlePrecision([], finer)).toEqual(finer);
});

it("handles exponent notation without converting through floating point", () => {
  expect(
    candlePrecision([{ ...candle, low: "1.25e-8" }], {
      pricePrecision: 0,
      volumePrecision: 0,
    }),
  ).toEqual({ pricePrecision: 10, volumePrecision: 4 });
});
