"use strict";

/** Render date-safe daily candlesticks in the draft market context. */
(() => {
  /** @type {Map<Element, ApexCharts>} */
  const chartInstances = new Map();
  /** @type {WeakMap<Element, number>} */
  const observedWidths = new WeakMap();

  /** Keep the intended ratio while returning a concrete ApexCharts height. */
  function chartHeight(element) {
    const desktop = matchMedia("(min-width: 992px)").matches;
    const ratio = desktop ? 2 : 1;
    return Math.max(260, Math.round(element.clientWidth / ratio));
  }

  const resizeObserver = "ResizeObserver" in window
    ? new ResizeObserver((entries) => {
      for (const entry of entries) {
        const element = entry.target;
        const width = Math.round(entry.contentRect.width);
        const chart = chartInstances.get(element);
        if (!chart || observedWidths.get(element) === width) {
          continue;
        }
        observedWidths.set(element, width);
        void chart.updateOptions({
          chart: { height: chartHeight(element) },
        }, false, false, false);
      }
    })
    : null;

  /** Return one resolved Tabler theme color. */
  function themeColor(name) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
  }

  /** Escape labels before placing them in the chart tooltip. */
  function escapeHtml(value) {
    const text = document.createElement("span");
    text.textContent = String(value);
    return text.innerHTML;
  }

  /** Count the visible fractional places in a compact decimal step. */
  function fractionalPlaces(step) {
    const fraction = String(step).split(".")[1];
    return fraction ? fraction.length : 0;
  }

  /** Localize only the decimal mark without grouping or rounding. */
  function exactPrice(value, language) {
    const decimalMark = new Intl.NumberFormat(language)
      .formatToParts(1.1)
      .find((part) => part.type === "decimal")?.value ?? ".";
    return String(value).replace(".", decimalMark);
  }

  /** Build a restrained two-week candlestick chart. */
  function chartOptions(element, data) {
    const language = document.documentElement.lang;
    const places = fractionalPlaces(element.dataset.priceStep);
    const numberFormat = new Intl.NumberFormat(language, {
      maximumFractionDigits: places,
      useGrouping: false,
    });
    const dateFormat = new Intl.DateTimeFormat(language, {
      day: "2-digit",
      month: "short",
      timeZone: "UTC",
    });
    const darkTheme = document.documentElement.dataset.bsTheme === "dark";
    const reducedMotion = matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const lows = data.map((candle) => Number(candle.low));
    const highs = data.map((candle) => Number(candle.high));
    const visibleMinimum = Math.min(...lows);
    const visibleMaximum = Math.max(...highs);
    const visibleRange = visibleMaximum - visibleMinimum;
    const minimumPadding = Number(element.dataset.priceStep) * 2;
    const axisPadding = Math.max(visibleRange * 0.06, minimumPadding);

    return {
      chart: {
        type: "candlestick",
        height: chartHeight(element),
        fontFamily: "inherit",
        parentHeightOffset: 0,
        animations: { enabled: !reducedMotion },
        toolbar: { show: false },
        zoom: { enabled: false },
        background: "transparent",
      },
      theme: { mode: darkTheme ? "dark" : "light" },
      series: [{
        data: data.map((candle) => ({
          x: Date.parse(`${candle.date}T00:00:00Z`),
          exact: [
            candle.open,
            candle.high,
            candle.low,
            candle.close,
          ],
          y: [
            Number(candle.open),
            Number(candle.high),
            Number(candle.low),
            Number(candle.close),
          ],
        })),
      }],
      plotOptions: {
        candlestick: {
          colors: {
            upward: themeColor("--tblr-success"),
            downward: themeColor("--tblr-danger"),
          },
          wick: { useFillColor: true },
        },
      },
      dataLabels: { enabled: false },
      grid: {
        borderColor: themeColor("--tblr-border-color"),
        strokeDashArray: 4,
        padding: { left: 6, right: 8 },
      },
      xaxis: {
        type: "datetime",
        labels: {
          datetimeUTC: true,
          formatter: (_value, timestamp) => dateFormat.format(timestamp),
        },
        tooltip: { enabled: false },
      },
      yaxis: {
        min: Math.max(0, visibleMinimum - axisPadding),
        max: visibleMaximum + axisPadding,
        decimalsInFloat: places,
        forceNiceScale: false,
        tickAmount: 5,
        labels: { formatter: (value) => numberFormat.format(value) },
        title: { text: element.dataset.priceLabel },
      },
      tooltip: {
        theme: darkTheme ? "dark" : "light",
        custom: ({ seriesIndex, dataPointIndex, w }) => {
          const point = w.config.series[seriesIndex].data[dataPointIndex];
          const values = point.exact.map((value) => (
            exactPrice(value, language)
          ));
          const labels = [
            element.dataset.openLabel,
            element.dataset.highLabel,
            element.dataset.lowLabel,
            element.dataset.closeLabel,
          ];
          const rows = labels.map((label, index) => (
            `<div><span class="text-secondary">${escapeHtml(label)}:</span> ${escapeHtml(values[index])}</div>`
          )).join("");
          return `
            <div class="tf-chart-tooltip">
              <div class="fw-semibold mb-1">${escapeHtml(dateFormat.format(point.x))}</div>
              ${rows}
            </div>`;
        },
      },
    };
  }

  /** Initialize charts inside the document or an HTMX fragment. */
  function initializeCharts(root = document) {
    if (!window.ApexCharts) {
      return;
    }
    const charts = [];
    if (root instanceof Element && root.matches("[data-market-candle-chart]")) {
      charts.push(root);
    }
    charts.push(...root.querySelectorAll("[data-market-candle-chart]"));

    for (const element of charts) {
      if (chartInstances.has(element)) {
        continue;
      }
      const configElement = document.getElementById(element.dataset.configId);
      if (!configElement) {
        continue;
      }
      const data = JSON.parse(configElement.textContent);
      const chart = new ApexCharts(element, chartOptions(element, data));
      chartInstances.set(element, chart);
      observedWidths.set(element, Math.round(element.clientWidth));
      resizeObserver?.observe(element);
      void chart.render();
    }
  }

  /** Destroy charts before HTMX removes their owning fragment. */
  function destroyCharts(root) {
    for (const [element, chart] of chartInstances) {
      if (element === root || root.contains(element)) {
        resizeObserver?.unobserve(element);
        chart.destroy();
        chartInstances.delete(element);
      }
    }
  }

  document.addEventListener("DOMContentLoaded", () => initializeCharts());
  document.addEventListener("htmx:afterSettle", (event) => {
    initializeCharts(event.detail.elt);
  });
  document.addEventListener("htmx:beforeCleanupElement", (event) => {
    destroyCharts(event.detail.elt);
  });
  document.addEventListener("tradefog:theme-changed", () => {
    for (const element of [...chartInstances.keys()]) {
      destroyCharts(element);
      initializeCharts(element);
    }
  });
})();
