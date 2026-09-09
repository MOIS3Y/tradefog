/** Presentation-only adapters from exact API decimals to chart coordinates. */

import type { Analytics } from "@/features/analytics/api";

type Trajectory = Analytics["trajectory"][number];
type Monetary = Analytics["monetary"][number];

export interface ChartPoint {
  value: [number, number];
  exactX: string;
  exactY: string;
  tradeId: number | null;
  trade?: Trajectory;
}

/** Convert a decimal only at the non-authoritative chart boundary. */
function coordinate(value: string | number): number {
  const result = Number(value);
  return Number.isFinite(result) ? result : 0;
}

/** Build the chronological cumulative-R path and its zero reference. */
export function buildOverviewSeries(data: Analytics): {
  trajectory: ChartPoint[];
  reference: ChartPoint[];
} {
  return {
    trajectory: [
      {
        value: [0, 0],
        exactX: "0",
        exactY: "0",
        tradeId: null,
      },
      ...data.trajectory.map((point) => ({
        value: [point.sequence, coordinate(point.cumulative_result_r)] as [
          number,
          number,
        ],
        exactX: String(point.sequence),
        exactY: point.cumulative_result_r,
        tradeId: point.trade_id,
        trade: point,
      })),
    ],
    reference: data.break_even_reference.map((point) => ({
      value: [point.sequence, coordinate(point.cumulative_result_r)],
      exactX: String(point.sequence),
      exactY: point.cumulative_result_r,
      tradeId: null,
    })),
  };
}

/** Build an exact-allocation L/W path, including the analytical origin. */
export function buildDisciplineSeries(data: Analytics): {
  trajectory: ChartPoint[];
  reference: ChartPoint[];
} {
  const trajectory: ChartPoint[] = [
    {
      value: [0, 0],
      exactX: "0",
      exactY: "0",
      tradeId: null,
    },
  ];
  for (const point of data.trajectory) {
    if (point.discipline_x === null || point.discipline_y === null) continue;
    trajectory.push({
      value: [coordinate(point.discipline_x), coordinate(point.discipline_y)],
      exactX: point.discipline_x,
      exactY: point.discipline_y,
      tradeId: point.trade_id,
      trade: point,
    });
  }
  return {
    trajectory,
    reference: data.discipline_break_even_reference.map((point) => ({
      value: [coordinate(point.x), coordinate(point.y)],
      exactX: point.x,
      exactY: point.y,
      tradeId: null,
    })),
  };
}

/** Build the cumulative money path for one immutable allocation. */
export function buildMonetarySeries(allocation: Monetary): ChartPoint[] {
  return [
    {
      value: [0, 0],
      exactX: "0",
      exactY: "0",
      tradeId: null,
    },
    ...allocation.trajectory.map((point) => ({
      value: [point.sequence, coordinate(point.cumulative_pnl)] as [
        number,
        number,
      ],
      exactX: String(point.sequence),
      exactY: point.cumulative_pnl,
      tradeId: point.trade_id,
    })),
  ];
}
