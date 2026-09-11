/** Built-in drawing catalog and bounded browser-local persistence. */
export const drawingGroups = {
  lines: [
    "horizontalStraightLine",
    "horizontalRayLine",
    "horizontalSegment",
    "verticalStraightLine",
    "verticalRayLine",
    "verticalSegment",
    "straightLine",
    "rayLine",
    "segment",
  ],
  channels: ["priceChannelLine", "parallelStraightLine"],
  fibonacci: ["fibonacciLine"],
  labels: ["simpleAnnotation", "simpleTag", "priceLine"],
} as const;
export const drawingTools = Object.values(drawingGroups).flat();
export type DrawingTool = (typeof drawingTools)[number];
export type DrawingGroup = keyof typeof drawingGroups;
export const defaultDrawingColor = "#6aafff";
export const drawingColors = [
  "#6aafff",
  "#35d990",
  "#e8b85f",
  "#f16e76",
  "#e7edf2",
  "#84919e",
];
const maximumBytes = 128 * 1024;
export interface Drawing {
  name: DrawingTool;
  points: { timestamp: number; value: number }[];
  color: string;
  text?: string;
}
export interface DrawingSelection {
  color: string;
  text?: string;
}
export interface DrawingStore {
  load: (key: string) => Drawing[];
  save: (key: string, drawings: unknown) => boolean;
}

/** Text-bearing built-ins need user content rather than a price label. */
export function isTextDrawing(name: string): boolean {
  return name === "simpleAnnotation" || name === "simpleTag";
}

/** Completed built-ins have one, two or three price/time anchors. */
export function drawingPointCount(name: DrawingTool): number {
  if (name === "priceChannelLine" || name === "parallelStraightLine") return 3;
  if (
    [
      "horizontalStraightLine",
      "verticalStraightLine",
      "priceLine",
      "simpleAnnotation",
      "simpleTag",
    ].includes(name)
  )
    return 1;
  return 2;
}

/** Strip runtime objects; reject malformed anchors, styles and text. */
export function sanitizeDrawings(value: unknown): Drawing[] {
  if (!Array.isArray(value)) return [];
  return value.slice(0, 100).flatMap((item) => {
    if (
      !item ||
      !drawingTools.includes(item.name) ||
      !Array.isArray(item.points) ||
      item.points.length !== drawingPointCount(item.name)
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
    const color = item.color ?? defaultDrawingColor;
    if (typeof color !== "string" || !/^#[0-9a-f]{6}$/i.test(color)) return [];
    const text = isTextDrawing(item.name) ? item.text : undefined;
    if (
      isTextDrawing(item.name) &&
      (typeof text !== "string" ||
        !text.trim() ||
        text.length > 200 ||
        /[\r\n]/.test(text))
    )
      return [];
    return [
      {
        name: item.name,
        points: item.points.map((p: { timestamp: number; value: number }) => ({
          timestamp: p.timestamp,
          value: p.value,
        })),
        color: color.toLowerCase(),
        ...(text === undefined ? {} : { text: text.trim() }),
      },
    ];
  });
}

export const browserDrawings: DrawingStore = {
  load(key) {
    try {
      const text = localStorage.getItem(key);
      if (!text || new TextEncoder().encode(text).length > maximumBytes)
        return [];
      const value = JSON.parse(text);
      return value.version === 1 || value.version === 2
        ? sanitizeDrawings(value.drawings)
        : [];
    } catch {
      return [];
    }
  },
  save(key, drawings) {
    try {
      const text = JSON.stringify({
        version: 2,
        drawings: sanitizeDrawings(drawings),
      });
      if (new TextEncoder().encode(text).length > maximumBytes) return false;
      localStorage.setItem(key, text);
      return true;
    } catch {
      return false;
    }
  },
};
