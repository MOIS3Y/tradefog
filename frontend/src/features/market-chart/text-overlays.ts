/** Make built-in text geometry selectable without changing its appearance. */
import type { OverlayFigure } from "klinecharts";

let registered = false;

/** KLineCharts text templates ignore pointer events on all their figures. */
export function enableTextSelection(
  library: Pick<
    typeof import("klinecharts"),
    "getOverlayClass" | "registerOverlay"
  >,
): void {
  if (registered) return;
  for (const name of ["simpleAnnotation", "simpleTag"]) {
    const Constructor = library.getOverlayClass(name);
    if (!Constructor) return;
    const template = new Constructor();
    const figures = template.createPointFigures;
    library.registerOverlay({
      name,
      totalStep: 2,
      needDefaultPointFigure: true,
      styles: template.styles,
      createYAxisFigures: template.createYAxisFigures,
      createPointFigures: (params) => {
        const result = figures?.(params) ?? [];
        const items: OverlayFigure[] = Array.isArray(result)
          ? result
          : [result];
        return items.map((figure) => ({ ...figure, ignoreEvent: false }));
      },
    });
  }
  registered = true;
}
