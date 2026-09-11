import { beforeEach, describe, expect, it, vi } from "vitest";

import { reloadTokens } from "@/api/tokens";
import {
  createInstrument,
  refreshInstrument,
} from "@/features/profiles/marketApi";
import { formatDecimal, isPositiveDecimal } from "@/utils/decimal";

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

describe("venue catalog flow", () => {
  it("formats exact decimals without insignificant zeroes", () => {
    expect(formatDecimal("0.010000000000000000")).toBe("0.01");
    expect(formatDecimal("0.000001000000000000")).toBe("0.000001");
    expect(formatDecimal("10.000000000000000000")).toBe("10");
    expect(formatDecimal("0E-18")).toBe("0");
    expect(formatDecimal("-0E-18")).toBe("0");
    expect(formatDecimal("12345678901234567890.0100")).toBe(
      "12345678901234567890.01",
    );
    expect(isPositiveDecimal(79701)).toBe(true);
  });

  it("imports selected metadata without wallet writes", async () => {
    const requests: Request[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (request: Request) => {
        requests.push(request);
        return jsonResponse({ id: 7, exec_symbol: "BTCUSDT" }, 201);
      }),
    );
    await createInstrument(8, {
      mode: "bybit",
      exec_symbol: "BTCUSDT",
      product: "spot",
    });
    await refreshInstrument(8, 7);
    expect(requests.map((r) => new URL(r.url).pathname)).toEqual([
      "/api/v1/profiles/8/instruments",
      "/api/v1/profiles/8/instruments/7/refresh",
    ]);
    expect(await requests[0]!.clone().json()).toEqual({
      mode: "bybit",
      exec_symbol: "BTCUSDT",
      product: "spot",
    });
  });
});
