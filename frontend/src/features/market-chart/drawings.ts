/** Versioned, bounded browser annotations, replaceable by an API store. */
export const drawingTools = [
  "horizontalStraightLine",
  "horizontalRayLine",
  "segment",
  "rayLine",
] as const;
export interface Drawing {
  name: (typeof drawingTools)[number];
  points: { timestamp: number; value: number }[];
}
export interface DrawingStore {
  load: (key: string) => Drawing[];
  save: (key: string, drawings: unknown) => boolean;
}

/** Strip library internals, unsupported tools and unbounded point arrays. */
export function sanitizeDrawings(value: unknown): Drawing[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 100).flatMap((item) => {
    if (
      !item ||
      !drawingTools.includes(item.name) ||
      !Array.isArray(item.points) ||
      item.points.length < 1 ||
      item.points.length > 2
    )
      return [];
    if (
      !item.points.every(
        (p: { timestamp?: number; value?: number }) =>
          p &&
          Number.isSafeInteger(p.timestamp) &&
          Number(p.timestamp) > 0 &&
          typeof p.value === "number" &&
          Number.isFinite(p.value),
      )
    )
      return [];
    return [
      {
        name: item.name,
        points: item.points.map((p: { timestamp: number; value: number }) => ({
          timestamp: p.timestamp,
          value: p.value,
        })),
      },
    ];
  });
}

export const browserDrawings: DrawingStore = {
  load(key) {
    try {
      const text = localStorage.getItem(key);
      if (!text || text.length > 64_000) return [];
      const value = JSON.parse(text);
      return value.version === 1 ? sanitizeDrawings(value.drawings) : [];
    } catch {
      return [];
    }
  },
  save(key, drawings) {
    try {
      localStorage.setItem(
        key,
        JSON.stringify({ version: 1, drawings: sanitizeDrawings(drawings) }),
      );
      return true;
    } catch {
      return false;
    }
  },
};
