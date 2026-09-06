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

  /** Return one resolved Tabler theme color or a reliable fallback. */
  function themeColor(name, fallback = "") {
    const fromDoc = getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
    if (fromDoc) return fromDoc;
    const fromBody = document.body
      ? getComputedStyle(document.body).getPropertyValue(name).trim()
      : "";
    return fromBody || fallback;
  }

  /** Escape labels before placing them in the chart tooltip. */
  function escapeHtml(value) {
    const text = document.createElement("span");
    text.textContent = String(value);
    return text.innerHTML;
  }

  /** Safely parse price step from dataset attribute. */
  function parsePriceStep(step) {
    if (!step) return 0.01;
    const normalized = String(step).replace(",", ".");
    const num = Number(normalized);
    return Number.isFinite(num) && num > 0 ? num : 0.01;
  }

  /** Count the visible fractional places in a compact decimal step. */
  function fractionalPlaces(step) {
    if (!step) return 2;
    const normalized = String(step).replace(",", ".");
    const fraction = normalized.split(".")[1];
    return fraction ? Math.min(fraction.length, 8) : 0;
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
    const step = parsePriceStep(element.dataset.priceStep);
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
    const lows = data.map((candle) => Number(candle.low)).filter(Number.isFinite);
    const highs = data.map((candle) => Number(candle.high)).filter(Number.isFinite);
    const visibleMinimum = lows.length ? Math.min(...lows) : 0;
    const visibleMaximum = highs.length ? Math.max(...highs) : 100;
    const visibleRange = Math.max(0, visibleMaximum - visibleMinimum);
    const minimumPadding = step * 2;
    const axisPadding = Math.max(visibleRange * 0.06, minimumPadding);

    const yMin = Number.isFinite(visibleMinimum) && Number.isFinite(axisPadding)
      ? Math.max(0, visibleMinimum - axisPadding)
      : undefined;
    const yMax = Number.isFinite(visibleMaximum) && Number.isFinite(axisPadding)
      ? visibleMaximum + axisPadding
      : undefined;

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
            upward: themeColor("--tblr-success", "#2fb344"),
            downward: themeColor("--tblr-danger", "#d63939"),
          },
          wick: { useFillColor: true },
        },
      },
      dataLabels: { enabled: false },
      grid: {
        borderColor: themeColor("--tblr-border-color", "rgba(101, 109, 119, 0.16)"),
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
        min: yMin,
        max: yMax,
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

  /** Dynamically recalculate ATR target and session comparisons when inputs change. */
  function updateAtrComparison() {
    const comparisonContainer = document.getElementById("atr-target-comparison");
    const manualAtrInput = document.getElementById("manual-atr-value");
    const manualSessionInput = document.getElementById("manual-session-range");

    let atrValue = NaN;
    let rewardMultiple = 3;

    if (manualAtrInput && manualAtrInput.value.trim()) {
      atrValue = Number(String(manualAtrInput.value).replace(",", "."));
    } else if (comparisonContainer) {
      const atrRaw = comparisonContainer.dataset.atrValue;
      atrValue = Number(String(atrRaw).replace(",", "."));
    }

    if (comparisonContainer) {
      const rewardMultipleRaw = comparisonContainer.dataset.rewardMultiple || "3";
      const parsedReward = Number(String(rewardMultipleRaw).replace(",", "."));
      if (Number.isFinite(parsedReward) && parsedReward > 0) {
        rewardMultiple = parsedReward;
      }
    }

    // Update ATR display and 75% reference if in manual mode
    const atrDisplay = document.getElementById("atr-display-value");
    const atrRef75 = document.getElementById("atr-reference-75");
    if (atrDisplay) {
      if (Number.isFinite(atrValue) && atrValue > 0) {
        atrDisplay.textContent = atrValue.toFixed(2);
      } else {
        atrDisplay.textContent = "—";
      }
    }
    if (atrRef75) {
      if (Number.isFinite(atrValue) && atrValue > 0) {
        atrRef75.textContent = (atrValue * 0.75).toFixed(2);
      } else {
        atrRef75.textContent = "—";
      }
    }

    // Update Session Range comparison (manual input or auto from dataset)
    const sessionContainer = document.getElementById("atr-session-comparison");
    const sessionPctEl = document.getElementById("atr-session-pct");
    const sessionTapeEl = document.getElementById("atr-session-tape");
    const sessionFillEl = document.getElementById("atr-session-fill");
    const sessionMoveEl = document.getElementById("atr-session-move");

    if (sessionPctEl && sessionTapeEl && sessionFillEl) {
      let sessionRange = NaN;
      let sessionPct = NaN;

      const manualRadio = document.getElementById("atr-source-manual");
      const isManual = Boolean(manualRadio && manualRadio.checked);

      if (isManual && manualSessionInput && manualSessionInput.value.trim()) {
        sessionRange = Number(String(manualSessionInput.value).replace(",", "."));
        if (Number.isFinite(sessionRange) && sessionRange >= 0 && Number.isFinite(atrValue) && atrValue > 0) {
          sessionPct = (sessionRange / atrValue) * 100;
        }
      } else if (!isManual && sessionContainer) {
        const rawRange = sessionContainer.dataset.sessionRange;
        const rawPct = sessionContainer.dataset.sessionRangePercent;
        if (rawRange) {
          sessionRange = Number(String(rawRange).replace(",", "."));
        }
        if (rawPct) {
          sessionPct = Number(String(rawPct).replace(",", "."));
        } else if (Number.isFinite(sessionRange) && Number.isFinite(atrValue) && atrValue > 0) {
          sessionPct = (sessionRange / atrValue) * 100;
        }
      }

      if (Number.isFinite(sessionPct) && sessionPct >= 0) {
        const roundedSessionPct = Math.round(sessionPct);
        sessionPctEl.textContent = `${roundedSessionPct}%`;
        sessionTapeEl.style.setProperty("--tf-range-percent", `${sessionPct}%`);
        if (sessionMoveEl && Number.isFinite(sessionRange)) {
          sessionMoveEl.textContent = sessionRange.toFixed(2);
        }
        sessionFillEl.classList.remove("tf-range-tape-fill-warning", "tf-range-tape-fill-danger");
        if (sessionPct > 100) {
          sessionFillEl.classList.add("tf-range-tape-fill-danger");
        } else if (sessionPct > 75) {
          sessionFillEl.classList.add("tf-range-tape-fill-warning");
        }
      } else {
        sessionPctEl.textContent = "0%";
        sessionTapeEl.style.setProperty("--tf-range-percent", "0%");
        if (sessionMoveEl) sessionMoveEl.textContent = "—";
        sessionFillEl.classList.remove("tf-range-tape-fill-warning", "tf-range-tape-fill-danger");
      }
    }

    // Update Target / Planned Move comparison
    const entryInput = document.getElementById("planned-entry");
    const stopInput = document.getElementById("planned-stop");
    const pctEl = document.getElementById("atr-planned-pct");
    const tapeEl = document.getElementById("atr-planned-tape");
    const fillEl = document.getElementById("atr-planned-fill");
    const moveEl = document.getElementById("atr-planned-move");
    const badgeEl = document.getElementById("atr-planned-badge");

    if (!pctEl || !tapeEl || !fillEl) return;

    if (!Number.isFinite(atrValue) || atrValue <= 0 || !entryInput || !stopInput) {
      pctEl.textContent = "0%";
      tapeEl.style.setProperty("--tf-range-percent", "0%");
      if (moveEl) moveEl.textContent = "—";
      fillEl.classList.remove("tf-range-tape-fill-warning", "tf-range-tape-fill-danger");
      if (badgeEl) badgeEl.className = "badge d-none";
      return;
    }

    const entry = Number(String(entryInput.value).replace(",", "."));
    const stop = Number(String(stopInput.value).replace(",", "."));

    if (Number.isFinite(entry) && Number.isFinite(stop) && entry > 0 && stop > 0 && entry !== stop) {
      const distance = Math.abs(entry - stop);
      const plannedMove = distance * rewardMultiple;
      const movePct = (plannedMove / atrValue) * 100;
      const roundedPct = Math.round(movePct);

      pctEl.textContent = `${roundedPct}%`;
      tapeEl.style.setProperty("--tf-range-percent", `${movePct}%`);

      if (moveEl) {
        moveEl.textContent = plannedMove.toFixed(2);
      }

      fillEl.classList.remove("tf-range-tape-fill-warning", "tf-range-tape-fill-danger");
      if (movePct > 100) {
        fillEl.classList.add("tf-range-tape-fill-danger");
        if (badgeEl) {
          badgeEl.className = "badge bg-danger-lt";
          badgeEl.textContent = document.documentElement.lang === "ru" ? "Превышает 100% ATR" : "Exceeds 100% ATR";
        }
      } else if (movePct > 75) {
        fillEl.classList.add("tf-range-tape-fill-warning");
        if (badgeEl) {
          badgeEl.className = "badge bg-warning-lt";
          badgeEl.textContent = document.documentElement.lang === "ru" ? "Превышает 75% ATR" : "Exceeds 75% ATR";
        }
      } else {
        if (badgeEl) {
          badgeEl.className = "badge d-none";
        }
      }
    } else {
      pctEl.textContent = "0%";
      tapeEl.style.setProperty("--tf-range-percent", "0%");
      if (moveEl) moveEl.textContent = "—";
      fillEl.classList.remove("tf-range-tape-fill-warning", "tf-range-tape-fill-danger");
      if (badgeEl) badgeEl.className = "badge d-none";
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    initializeCharts();
    updateAtrComparison();
  });
  document.addEventListener("input", (event) => {
    if (event.target && (
      event.target.id === "planned-entry" ||
      event.target.id === "planned-stop" ||
      event.target.id === "manual-atr-value" ||
      event.target.id === "manual-session-range"
    )) {
      updateAtrComparison();
    }
  });
  document.addEventListener("change", (event) => {
    if (event.target && (
      event.target.id === "planned-entry" ||
      event.target.id === "planned-stop" ||
      event.target.id === "manual-atr-value" ||
      event.target.id === "manual-session-range" ||
      event.target.id === "trade-strategy"
    )) {
      updateAtrComparison();
    }
  });
  document.addEventListener("htmx:afterSettle", (event) => {
    initializeCharts(event.detail.elt);
    updateAtrComparison();
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
