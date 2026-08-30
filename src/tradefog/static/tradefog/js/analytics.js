"use strict";

/** Render interactive analytics charts from server-supplied JSON data. */
(() => {
  /** @type {Map<Element, ApexCharts>} */
  const chartInstances = new Map();

  /** Return a Tabler CSS custom property resolved for the active theme. */
  function themeColor(name) {
    return getComputedStyle(document.documentElement)
      .getPropertyValue(name)
      .trim();
  }

  /** Escape server-supplied labels before placing them in a custom tooltip. */
  function escapeHtml(value) {
    const element = document.createElement("span");
    element.textContent = String(value);
    return element.innerHTML;
  }

  /** Format chart-only approximations using the language in the URL page. */
  function numberFormatter(maximumFractionDigits = 2) {
    return new Intl.NumberFormat(document.documentElement.lang, {
      maximumFractionDigits,
    });
  }

  /** Build the concrete X/Y trajectory chart options. */
  function trajectoryOptions(data) {
    const formatNumber = numberFormatter();
    const reducedMotion = matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const darkTheme = document.documentElement.dataset.bsTheme === "dark";

    return {
      chart: {
        type: "line",
        height: 400,
        fontFamily: "inherit",
        parentHeightOffset: 0,
        animations: { enabled: !reducedMotion },
        toolbar: { show: false },
        zoom: { enabled: false },
        background: "transparent",
      },
      theme: { mode: darkTheme ? "dark" : "light" },
      series: [
        { name: data.labels.trajectory, data: data.trajectory },
        { name: data.labels.breakEven, data: data.breakEven },
      ],
      colors: [themeColor("--tblr-primary"), themeColor("--tblr-secondary")],
      stroke: {
        width: [3, 2],
        curve: "straight",
        lineCap: "round",
        dashArray: [0, 7],
      },
      markers: {
        size: [4, 0],
        strokeWidth: 2,
        hover: { sizeOffset: 3 },
        discrete: [{
          seriesIndex: 0,
          dataPointIndex: data.trajectory.length - 1,
          fillColor: themeColor("--tblr-primary"),
          strokeColor: themeColor("--tblr-bg-surface"),
          size: 7,
        }],
      },
      dataLabels: { enabled: false },
      grid: {
        borderColor: themeColor("--tblr-border-color"),
        strokeDashArray: 4,
        padding: { left: 8, right: 12 },
      },
      legend: {
        position: "bottom",
        horizontalAlign: "left",
        markers: { size: 5 },
        itemMargin: { horizontal: 10, vertical: 8 },
      },
      xaxis: {
        type: "numeric",
        min: 0,
        tickAmount: 5,
        labels: { formatter: (value) => formatNumber.format(value) },
        title: { text: "X" },
        tooltip: { enabled: false },
      },
      yaxis: {
        min: 0,
        tickAmount: 5,
        forceNiceScale: true,
        labels: { formatter: (value) => formatNumber.format(value) },
        title: { text: "Y" },
      },
      tooltip: {
        shared: false,
        intersect: true,
        theme: darkTheme ? "dark" : "light",
        custom: ({ seriesIndex, dataPointIndex, w }) => {
          const point = w.config.series[seriesIndex].data[dataPointIndex];
          if (!point.trade) {
            const label = seriesIndex === 1
              ? data.labels.breakEven
              : data.labels.start;
            return `<div class="tf-chart-tooltip">${escapeHtml(label)}</div>`;
          }
          return `
            <div class="tf-chart-tooltip">
              <div class="fw-semibold">${escapeHtml(point.trade.pair)} · ${escapeHtml(point.trade.direction)}</div>
              <div class="text-secondary">${escapeHtml(point.trade.date)} · ${escapeHtml(point.trade.profile)}</div>
              <div>${escapeHtml(data.labels.result)}: ${formatNumber.format(point.trade.resultR)}R</div>
              <div>X ${formatNumber.format(point.x)} · Y ${formatNumber.format(point.y)}</div>
            </div>`;
        },
      },
      responsive: [{
        breakpoint: 576,
        options: {
          chart: { height: 320 },
          legend: { position: "bottom" },
        },
      }],
    };
  }

  /** Reveal explicit date controls only for the custom range. */
  function initializeFilter(form) {
    if (form.dataset.analyticsFiltersReady === "true") {
      return;
    }
    const period = form.querySelector("[name=period]");
    const profile = form.querySelector("[name=profile]");
    const tradingPair = form.querySelector("[name=trading_pair]");
    const customDateFields = form.querySelectorAll("[data-custom-date-field]");
    if (!period) {
      return;
    }
    const synchronizeDates = () => {
      for (const field of customDateFields) {
        field.classList.toggle("d-none", period.value !== "CUSTOM");
      }
    };
    period.addEventListener("change", synchronizeDates);
    profile?.addEventListener("change", () => {
      if (tradingPair) {
        tradingPair.value = "";
        tradingPair.disabled = true;
      }
    });
    synchronizeDates();
    form.dataset.analyticsFiltersReady = "true";
  }

  /** Create charts found in a newly loaded document fragment. */
  function initializeCharts(root = document) {
    const filters = [];
    if (root instanceof Element && root.matches("[data-analytics-filters]")) {
      filters.push(root);
    }
    filters.push(...root.querySelectorAll("[data-analytics-filters]"));
    for (const form of filters) {
      initializeFilter(form);
    }

    if (!window.ApexCharts) {
      return;
    }
    const charts = [];
    if (root instanceof Element && root.matches("[data-analytics-chart]")) {
      charts.push(root);
    }
    charts.push(...root.querySelectorAll("[data-analytics-chart]"));

    for (const element of charts) {
      if (chartInstances.has(element)) {
        continue;
      }
      const configElement = document.getElementById(element.dataset.configId);
      if (!configElement || element.dataset.analyticsChart !== "xy-trajectory") {
        continue;
      }
      const data = JSON.parse(configElement.textContent);
      const chart = new ApexCharts(element, trajectoryOptions(data));
      chartInstances.set(element, chart);
      void chart.render();
    }
  }

  /** Destroy chart instances before HTMX removes their elements. */
  function destroyCharts(root) {
    for (const [element, chart] of chartInstances) {
      if (element === root || root.contains(element)) {
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
