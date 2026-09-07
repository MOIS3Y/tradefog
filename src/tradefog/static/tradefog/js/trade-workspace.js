/**
 * @fileoverview Trade Workspace reactive frontend module.
 * Provides live position sizing via big.js, searchable instrument selector
 * via Tom Select, on-demand candlestick charting via ApexCharts, dynamic ATR
 * metrics, and real-time market checklist assessment.
 */

/* global Big, TomSelect, ApexCharts */

(function () {
  "use strict";

  const SVG_ICONS = {
    activity:
      '<svg xmlns="http://www.w3.org/2000/svg" class="icon alert-icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M3 12h4l3 8l4 -16l3 8h4" /></svg>',
    alertTriangle:
      '<svg xmlns="http://www.w3.org/2000/svg" class="icon alert-icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 9v4" /><path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0z" /><path d="M12 16h.01" /></svg>',
    circleCheck:
      '<svg xmlns="http://www.w3.org/2000/svg" class="icon alert-icon" width="24" height="24" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round"><path stroke="none" d="M0 0h24v24H0z" fill="none"/><path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0" /><path d="M9 12l2 2l4 -4" /></svg>',
  };

  const I18N = {
    en: {
      assessedCount: (n, total) => `${n} of ${total} assessed`,
      selectObservations: "Select checklist observations to evaluate alignment.",
      d1AlignedTitle: "D1 observations aligned",
      d1AlignedDesc: "Global and local D1 observations are aligned.",
      d1DivergentTitle: "D1 observations divergent",
      d1DivergentDesc: "Global and local D1 observations are divergent.",
      d1MixedTitle: "D1 observations mixed",
      d1MixedDesc: "Global and local D1 observations are mixed.",
      agreesTitle: "Direction agrees with the checklist",
      agreesDesc: "This is advisory and does not block the trade.",
      disagreesTitle: "Direction disagrees with the checklist",
      disagreesDesc: "This is advisory and does not block the trade.",
      manualAtrContext: "Manual volatility context",
      closedCandlesThrough: "Closed candles through",
      exceeds75: "Exceeds 75% ATR",
      exceeds100: "Exceeds 100% ATR",
      capacityAvailable: "Available",
      capacityExceeded: "Exceeded",
    },
    ru: {
      assessedCount: (n, total) => `Оценено: ${n} из ${total}`,
      selectObservations:
        "Выберите наблюдения чек-листа для оценки согласованности.",
      d1AlignedTitle: "Наблюдения D1 согласованы",
      d1AlignedDesc: "Глобальное и локальное наблюдения D1 согласованы.",
      d1DivergentTitle: "Наблюдения D1 расходятся",
      d1DivergentDesc: "Глобальное и локальное наблюдения D1 расходятся.",
      d1MixedTitle: "Наблюдения D1 смешанные",
      d1MixedDesc: "Глобальное и локальное наблюдения D1 разнонаправлены.",
      agreesTitle: "Направление согласуется с чек-листом",
      agreesDesc: "Это рекомендательная оценка, она не блокирует сделку.",
      disagreesTitle: "Направление расходится с чек-листом",
      disagreesDesc: "Это рекомендательная оценка, она не блокирует сделку.",
      manualAtrContext: "Ручной контекст волатильности",
      closedCandlesThrough: "Закрытые свечи по",
      exceeds75: "Превышает 75% ATR",
      exceeds100: "Превышает 100% ATR",
      capacityAvailable: "Достаточно",
      capacityExceeded: "Превышен",
    },
  };

  /**
   * Format decimal string to compact representation stripping redundant trailing zeros.
   * @param {string|number|null|undefined} val
   * @returns {string}
   */
  function formatCompactNumber(val) {
    if (val === null || val === undefined || val === "") return "";
    try {
      const b = new Big(val);
      return b.toString();
    } catch (_) {
      return String(val).replace(/(\.\d*?[1-9])0+$|\.0+$/, "$1");
    }
  }

  /**
   * Pure position sizing and risk calculations using big.js.
   */
  class PositionCalculator {
    /**
     * Round down a Big value to the nearest positive step increment.
     * @param {Big} value - Number to round.
     * @param {Big} step - Positive step increment (e.g. 0.001).
     * @returns {Big} Step-aligned value rounded towards zero.
     */
    static roundDownToStep(value, step) {
      if (step.lte(0)) {
        return value;
      }
      const steps = value.div(step).round(0, 0); // 0 = roundDown in big.js
      return steps.times(step);
    }

    /**
     * Check if a Big value is aligned with an exact step tick.
     * @param {Big} value - Number to check.
     * @param {Big} step - Step tick.
     * @returns {boolean} True if aligned.
     */
    static isStepAligned(value, step) {
      if (step.lte(0)) {
        return true;
      }
      return value.mod(step).eq(0);
    }

    /**
     * Calculate position plan metrics.
     * @param {Object} params
     * @param {string} params.direction - "long" or "short".
     * @param {string} params.entryStr - Entry price string.
     * @param {string} params.stopStr - Stop price string.
     * @param {string} params.targetRiskStr - Fixed 1R monetary risk string.
     * @param {string} params.rewardMultipleStr - Reward multiple (e.g. "3").
     * @param {string} params.priceStepStr - Instrument price tick string.
     * @param {string} params.qtyStepStr - Instrument quantity step string.
     * @param {string|null} [params.minQtyStr] - Minimum order quantity.
     * @param {string|null} [params.minNotionalStr] - Minimum order value.
     * @param {string|null} [params.walletAvailableStr] - Available wallet funds.
     * @returns {{
     *   success: boolean,
     *   error: string|null,
     *   plan: {
     *     distance: string,
     *     stopLoss: string,
     *     takeProfit: string,
     *     quantity: string,
     *     notional: string,
     *     plannedRiskAmount: string,
     *     plannedProfitAmount: string,
     *     targetRiskAmount: string,
     *     rewardMultiple: string,
     *     exceedsWallet: boolean,
     *     capacityAfterPlan: string|null
     *   }|null
     * }}
     */
    static calculate(params) {
      const {
        direction,
        entryStr,
        stopStr,
        targetRiskStr,
        rewardMultipleStr,
        priceStepStr,
        qtyStepStr,
        minQtyStr,
        minNotionalStr,
        walletAvailableStr,
      } = params;

      if (!entryStr || !stopStr || !targetRiskStr) {
        return { success: false, error: null, plan: null };
      }

      let entry, stop, targetRisk, rewardMultiple, priceStep, qtyStep;

      try {
        entry = new Big(entryStr.trim());
        stop = new Big(stopStr.trim());
        targetRisk = new Big(targetRiskStr.trim());
        rewardMultiple = new Big(rewardMultipleStr || "3");
        priceStep = new Big(priceStepStr || "0.01");
        qtyStep = new Big(qtyStepStr || "0.001");
      } catch (err) {
        return { success: false, error: "Invalid numeric input format.", plan: null };
      }

      if (entry.lte(0)) {
        return { success: false, error: "Entry price must be positive.", plan: null };
      }
      if (stop.lte(0)) {
        return { success: false, error: "Stop loss must be positive.", plan: null };
      }
      if (targetRisk.lte(0)) {
        return {
          success: false,
          error: "Selected strategy currently has no positive risk capital.",
          plan: null,
        };
      }
      if (rewardMultiple.lte(0)) {
        return { success: false, error: "Reward multiple must be positive.", plan: null };
      }

      const normDir = (direction || "long").toLowerCase();
      let distance, takeProfit;

      if (normDir === "long") {
        distance = entry.minus(stop);
        if (distance.lte(0)) {
          return {
            success: false,
            error: "A LONG stop must be placed below the entry price.",
            plan: null,
          };
        }
        takeProfit = entry.plus(distance.times(rewardMultiple));
      } else if (normDir === "short") {
        distance = stop.minus(entry);
        if (distance.lte(0)) {
          return {
            success: false,
            error: "A SHORT stop must be placed above the entry price.",
            plan: null,
          };
        }
        takeProfit = entry.minus(distance.times(rewardMultiple));
        if (takeProfit.lte(0)) {
          return {
            success: false,
            error: "Calculated SHORT take profit must remain positive.",
            plan: null,
          };
        }
      } else {
        return { success: false, error: "Select a valid trade direction.", plan: null };
      }

      const rawQuantity = targetRisk.div(distance);
      const quantity = PositionCalculator.roundDownToStep(rawQuantity, qtyStep);

      if (quantity.lte(0)) {
        return {
          success: false,
          error: "Risk and stop distance produce a quantity below one step.",
          plan: null,
        };
      }

      if (minQtyStr) {
        try {
          const minQty = new Big(minQtyStr);
          if (quantity.lt(minQty)) {
            return {
              success: false,
              error: `Calculated quantity (${quantity.toString()}) is below instrument minimum (${minQty.toString()}).`,
              plan: null,
            };
          }
        } catch (_) {}
      }

      const notional = entry.times(quantity);

      if (minNotionalStr) {
        try {
          const minNotional = new Big(minNotionalStr);
          if (notional.lt(minNotional)) {
            return {
              success: false,
              error: `Order value (${notional.toString()}) is below instrument minimum (${minNotional.toString()}).`,
              plan: null,
            };
          }
        } catch (_) {}
      }

      const plannedRiskAmount = quantity.times(distance);
      const plannedProfitAmount = plannedRiskAmount.times(rewardMultiple);

      let exceedsWallet = false;
      let capacityAfterPlan = null;

      if (walletAvailableStr) {
        try {
          const walletAvail = new Big(walletAvailableStr);
          capacityAfterPlan = walletAvail.minus(notional);
          if (notional.gt(walletAvail)) {
            exceedsWallet = true;
          }
        } catch (_) {}
      }

      return {
        success: true,
        error: null,
        plan: {
          entry: entry.toString(),
          distance: distance.toFixed(4).replace(/\.?0+$/, ""),
          stopLoss: stop.toString(),
          takeProfit: takeProfit.toFixed(4).replace(/\.?0+$/, ""),
          quantity: quantity.toString(),
          notional: notional.toFixed(2),
          plannedRiskAmount: plannedRiskAmount.toFixed(2),
          plannedProfitAmount: plannedProfitAmount.toFixed(2),
          targetRiskAmount: targetRisk.toFixed(2),
          rewardMultiple: rewardMultiple.toString(),
          exceedsWallet,
          capacityAfterPlan: capacityAfterPlan ? capacityAfterPlan.toFixed(2) : null,
        },
      };
    }
  }

  /**
   * Manages checklist scoring, direction gauge, and qualitative advisory.
   */
  class ChecklistManager {
    /**
     * Compute checklist assessment from radio states.
     * @param {Object} state - Form state containing checklist answers and trade direction.
     * @returns {{
     *   answeredCount: number,
     *   totalCount: number,
     *   gaugePosition: number,
     *   trendRelationship: string,
     *   agreesWithTrade: boolean|null
     * }}
     */
    static assess(state) {
      const keys = [
        "market_sentiment",
        "information_background",
        "global_daily_direction",
        "local_daily_movement",
      ];
      let answeredCount = 0;
      let score = 0; // -4 (pure short) to +4 (pure long)

      keys.forEach((key) => {
        const val = state[key];
        if (val) {
          answeredCount++;
          if (val === "POSITIVE" || val === "LONG") {
            score += 1;
          } else if (val === "NEGATIVE" || val === "SHORT") {
            score -= 1;
          }
        }
      });

      // Map score [-4, 4] to gauge percentage [0, 100]
      const gaugePosition = Math.round(((score + 4) / 8) * 100);

      // Trend relationship between Global D1 and Local D1
      const gDir = state.global_daily_direction;
      const lDir = state.local_daily_movement;
      let trendRelationship = "NONE";

      if (gDir && lDir) {
        if (gDir === lDir && gDir !== "FLAT") {
          trendRelationship = "ALIGNED";
        } else if (
          (gDir === "LONG" && lDir === "SHORT") ||
          (gDir === "SHORT" && lDir === "LONG")
        ) {
          trendRelationship = "DIVERGENT";
        } else {
          trendRelationship = "MIXED";
        }
      }

      // Agreement with planned trade direction
      const tradeDir = (state.direction || "long").toLowerCase();
      let agreesWithTrade = null;

      if (answeredCount >= 2) {
        if (tradeDir === "long" && score > 0) {
          agreesWithTrade = true;
        } else if (tradeDir === "short" && score < 0) {
          agreesWithTrade = true;
        } else if (
          (tradeDir === "long" && score < 0) ||
          (tradeDir === "short" && score > 0)
        ) {
          agreesWithTrade = false;
        }
      }

      return {
        answeredCount,
        totalCount: 4,
        gaugePosition,
        trendRelationship,
        agreesWithTrade,
      };
    }

    /**
     * Render assessment results to the DOM.
     * @param {Object} assessment
     */
    static render(assessment) {
      const countEl = document.getElementById("checklist-assessment-count");
      const markerEl = document.getElementById("checklist-gauge-marker");
      const feedbackEl = document.getElementById("checklist-feedback-container");
      const lang = document.documentElement.lang?.startsWith("ru") ? "ru" : "en";
      const t = I18N[lang] || I18N.en;

      if (countEl) {
        countEl.textContent = t.assessedCount(
          assessment.answeredCount,
          assessment.totalCount
        );
      }
      if (markerEl) {
        markerEl.style.setProperty(
          "--tf-gauge-position",
          `${assessment.gaugePosition}%`
        );
      }
      if (!feedbackEl) return;

      if (assessment.answeredCount === 0) {
        feedbackEl.innerHTML = `
          <div class="text-secondary small text-center my-auto tf-fade-in">
            <span class="status-dot status-dot-animated bg-azure me-1" aria-hidden="true"></span>
            ${t.selectObservations}
          </div>
        `;
        return;
      }

      let alertsHtml = '<div class="tf-fade-in d-flex flex-column gap-2">';

      if (assessment.trendRelationship === "ALIGNED") {
        alertsHtml += `
          <div class="alert alert-info d-flex align-items-center mb-0 py-2" role="status">
            <div class="me-3 d-flex align-items-center">${SVG_ICONS.activity}</div>
            <div>
              <div class="fw-semibold">${t.d1AlignedTitle}</div>
              <div class="text-secondary small">${t.d1AlignedDesc}</div>
            </div>
          </div>`;
      } else if (assessment.trendRelationship === "DIVERGENT") {
        alertsHtml += `
          <div class="alert alert-warning d-flex align-items-center mb-0 py-2" role="status">
            <div class="me-3 d-flex align-items-center">${SVG_ICONS.alertTriangle}</div>
            <div>
              <div class="fw-semibold">${t.d1DivergentTitle}</div>
              <div class="text-secondary small">${t.d1DivergentDesc}</div>
            </div>
          </div>`;
      } else if (assessment.trendRelationship === "MIXED") {
        alertsHtml += `
          <div class="alert alert-secondary d-flex align-items-center mb-0 py-2" role="status">
            <div class="me-3 d-flex align-items-center">${SVG_ICONS.activity}</div>
            <div>
              <div class="fw-semibold">${t.d1MixedTitle}</div>
              <div class="text-secondary small">${t.d1MixedDesc}</div>
            </div>
          </div>`;
      }

      if (assessment.agreesWithTrade === true) {
        alertsHtml += `
          <div class="alert alert-success d-flex align-items-center mb-0 py-2" role="status">
            <div class="me-3 d-flex align-items-center">${SVG_ICONS.circleCheck}</div>
            <div>
              <div class="fw-semibold">${t.agreesTitle}</div>
              <div class="text-secondary small">${t.agreesDesc}</div>
            </div>
          </div>`;
      } else if (assessment.agreesWithTrade === false) {
        alertsHtml += `
          <div class="alert alert-warning d-flex align-items-center mb-0 py-2" role="status">
            <div class="me-3 d-flex align-items-center">${SVG_ICONS.alertTriangle}</div>
            <div>
              <div class="fw-semibold">${t.disagreesTitle}</div>
              <div class="text-secondary small">${t.disagreesDesc}</div>
            </div>
          </div>`;
      }

      alertsHtml += "</div>";
      feedbackEl.innerHTML = alertsHtml;
    }
  }

  /**
   * Manages on-demand candlestick charting, ATR metrics, and mode toggling.
   */
  class ATRManager {
    /**
     * @param {Object} options
     * @param {string} options.marketDataUrl - URL endpoint for market data.
     * @param {Function} options.onATRChange - Callback when active ATR changes.
     * @param {boolean} [options.isReadOnly] - Whether workspace is in read-only mode.
     * @param {string} [options.initialMode] - Initial ATR mode ("auto"|"manual").
     * @param {string|null} [options.initialAtrValue] - Initial ATR numeric value.
     * @param {Array} [options.initialCandles] - Initial candles array.
     * @param {string|null} [options.initialDate] - Initial contributing date.
     * @param {string|null} [options.initialProvider] - Initial provider name.
     */
    constructor(options = {}) {
      this.marketDataUrl = options.marketDataUrl || "/trades/workspace/market-data/";
      this.onATRChange = options.onATRChange || null;
      this.isReadOnly = !!options.isReadOnly;
      this.chart = null;
      this.currentAtrValue = options.initialAtrValue || null;
      this.currentMode = options.initialMode || "auto"; // "auto" or "manual"
      this.cachedCandles = options.initialCandles || [];
      this.initChart();
      this.bindEvents();

      if (this.cachedCandles && this.cachedCandles.length > 0) {
        this.renderCandles(this.cachedCandles);
      }
      if (this.currentAtrValue) {
        this.updateATRDisplays(
          this.currentAtrValue,
          (options.initialProvider || this.currentMode).toUpperCase(),
          options.initialDate
        );
      }
      if (options.initialObservedSessionRange) {
        this.updateSessionMetric(
          options.initialObservedSessionRange,
          options.initialSessionRangePercent || "0"
        );
      }
      if (this.currentAtrValue && this.onATRChange) {
        this.onATRChange(this.currentAtrValue);
      }
    }

    /**
     * Initialize ApexCharts candlestick instance.
     */
    initChart() {
      const container = document.getElementById("market-candle-chart");
      if (!container || typeof ApexCharts === "undefined") return;

      const chartOptions = {
        series: [{ data: [] }],
        chart: {
          type: "candlestick",
          height: 280,
          toolbar: { show: false },
          animations: { enabled: false },
          background: "transparent",
        },
        theme: {
          mode: document.documentElement.getAttribute("data-bs-theme") === "dark" ? "dark" : "light",
        },
        xaxis: {
          type: "category",
          labels: {
            formatter: (val) => (val ? val.substring(5) : ""),
            style: { fontSize: "11px" },
          },
        },
        yaxis: {
          tooltip: { enabled: true },
          labels: {
            formatter: (val) => (typeof val === "number" ? val.toFixed(2) : val),
          },
        },
        plotOptions: {
          candlestick: {
            colors: {
              upward: "#2fb344",
              downward: "#d63939",
            },
          },
        },
        grid: {
          borderColor: "rgba(100, 116, 139, 0.15)",
        },
      };

      this.chart = new ApexCharts(container, chartOptions);
      this.chart.render();
    }

    /**
     * Bind DOM controls for ATR and mode switching.
     */
    bindEvents() {
      if (this.isReadOnly) return;

      const autoRadio = document.getElementById("atr-source-auto");
      const manualRadio = document.getElementById("atr-source-manual");
      const fetchBtn = document.getElementById("btn-fetch-market-data");
      const manualAtrInput = document.getElementById("manual-atr-value");
      const sessionRangeInput = document.getElementById("manual-session-range");

      if (autoRadio) {
        autoRadio.addEventListener("change", () => this.setMode("auto"));
      }
      if (manualRadio) {
        manualRadio.addEventListener("change", () => this.setMode("manual"));
      }
      if (fetchBtn) {
        fetchBtn.addEventListener("click", () => this.fetchMarketData());
      }
      if (manualAtrInput) {
        manualAtrInput.addEventListener("input", () => {
          if (this.currentMode === "manual") {
            this.handleManualInputChange();
          }
        });
      }
      if (sessionRangeInput) {
        sessionRangeInput.addEventListener("input", (e) => {
          const valStr = e.target.value.trim();
          if (this.currentAtrValue && valStr) {
            try {
              const val = new Big(valStr);
              const pct = val.div(this.currentAtrValue).times(100);
              this.updateSessionMetric(val.toFixed(2), pct.toString());
              return;
            } catch (_) {}
          }
          this.updateSessionMetric(valStr || "—", "0");
        });
      }
    }

    /**
     * Switch between Auto and Manual ATR modes.
     * @param {"auto"|"manual"} mode
     */
    setMode(mode) {
      this.currentMode = mode;
      const autoSection = document.getElementById("atr-auto-section");
      const manualSection = document.getElementById("atr-manual-section");
      const autoRadio = document.getElementById("atr-source-auto");
      const manualRadio = document.getElementById("atr-source-manual");
      const contributingLabel = document.getElementById(
        "atr-contributing-label"
      );
      const sourceBadge = document.getElementById("atr-source-badge");
      const lang = document.documentElement.lang?.startsWith("ru")
        ? "ru"
        : "en";
      const t = I18N[lang] || I18N.en;

      if (mode === "manual") {
        const hiddenCandlesInput = document.getElementById("candles-data-input");
        if (hiddenCandlesInput) hiddenCandlesInput.value = "";
        const autoAtrInput = document.getElementById("auto-atr-value-input");
        if (autoAtrInput) autoAtrInput.value = "";
        const atrDateInput = document.getElementById("atr-contributing-date-input");
        if (atrDateInput) atrDateInput.value = "";
        const obsRangeInput = document.getElementById("observed-session-range-input");
        if (obsRangeInput) obsRangeInput.value = "";
        const sessPctInput = document.getElementById("session-range-percent-input");
        if (sessPctInput) sessPctInput.value = "";

        if (manualRadio) manualRadio.checked = true;
        if (autoSection) autoSection.classList.add("d-none");
        if (manualSection) manualSection.classList.remove("d-none");
        if (contributingLabel)
          contributingLabel.textContent = t.manualAtrContext;
        if (sourceBadge) {
          sourceBadge.textContent = lang === "ru" ? "Вручную" : "Manual";
          sourceBadge.className = "badge bg-secondary-lt";
        }
        this.handleManualInputChange();
      } else {
        if (autoRadio) autoRadio.checked = true;
        if (manualSection) manualSection.classList.add("d-none");
        if (autoSection) autoSection.classList.remove("d-none");
        if (sourceBadge) {
          sourceBadge.textContent = lang === "ru" ? "Авто" : "Auto";
          sourceBadge.className = "badge bg-secondary-lt";
        }
        if (!this.isReadOnly) {
          this.fetchMarketData();
        }
      }
    }

    /**
     * Handle manual ATR value change.
     */
    handleManualInputChange() {
      const manualAtrInput = document.getElementById("manual-atr-value");
      const sessionRangeInput = document.getElementById("manual-session-range");
      const val = manualAtrInput ? manualAtrInput.value.trim() : "";
      if (val) {
        try {
          new Big(val);
          this.currentAtrValue = val;
          this.updateATRDisplays(val, "Manual");
          if (sessionRangeInput && sessionRangeInput.value.trim()) {
            try {
              const sessVal = new Big(sessionRangeInput.value.trim());
              const pct = sessVal.div(val).times(100);
              this.updateSessionMetric(sessVal.toFixed(2), pct.toString());
            } catch (_) {}
          } else {
            this.updateSessionMetric("—", "0");
          }
          if (this.onATRChange) this.onATRChange(val);
          return;
        } catch (_) {}
      }
      this.currentAtrValue = null;
      this.updateATRDisplays(null, "Manual");
      this.updateSessionMetric("—", "0");
      if (this.onATRChange) this.onATRChange(null);
    }

    /**
     * Fetch market data and candles via JSON endpoint.
     */
    async fetchMarketData() {
      const instSelect = document.getElementById("trade-instrument");
      const dateInput = document.getElementById("trade-date");
      const alertContainer = document.getElementById("market-data-alert");

      const instrumentId = instSelect ? instSelect.value : null;
      const tradeDate = dateInput ? dateInput.value : "";

      if (!instrumentId) return;

      if (alertContainer) alertContainer.innerHTML = "";

      const fetchBtn = document.getElementById("btn-fetch-market-data");
      if (fetchBtn) fetchBtn.classList.add("btn-loading");

      try {
        const url = `${this.marketDataUrl}?instrument=${encodeURIComponent(instrumentId)}&trade_date=${encodeURIComponent(tradeDate)}`;
        const response = await fetch(url);
        const data = await response.json();

        if (data.status === "ok") {
          this.currentAtrValue = data.atr_value;
          this.cachedCandles = data.candles || [];
          this.renderCandles(this.cachedCandles);

          const hiddenCandlesInput = document.getElementById("candles-data-input");
          if (hiddenCandlesInput && this.cachedCandles.length > 0) {
            hiddenCandlesInput.value = JSON.stringify(this.cachedCandles);
          }
          const autoAtrInput = document.getElementById("auto-atr-value-input");
          if (autoAtrInput) autoAtrInput.value = data.atr_value || "";
          const atrDateInput = document.getElementById("atr-contributing-date-input");
          if (atrDateInput) atrDateInput.value = data.contributing_date || "";
          const obsRangeInput = document.getElementById("observed-session-range-input");
          if (obsRangeInput) obsRangeInput.value = data.observed_session_range || "";
          const sessPctInput = document.getElementById("session-range-percent-input");
          if (sessPctInput) sessPctInput.value = data.session_range_percent || "";

          this.updateATRDisplays(
            data.atr_value,
            data.provider.toUpperCase(),
            data.contributing_date
          );
          if (data.observed_session_range) {
            const rangeInput = document.getElementById("manual-session-range");
            if (rangeInput) rangeInput.value = data.observed_session_range;
            this.updateSessionMetric(
              data.observed_session_range,
              data.session_range_percent || "0"
            );
          } else {
            this.updateSessionMetric("—", "0");
          }
          if (this.onATRChange) this.onATRChange(data.atr_value);
        } else if (data.status === "manual") {
          this.setMode("manual");
        } else {
          if (alertContainer) {
            alertContainer.innerHTML = `
              <div class="alert alert-warning mb-3 py-2 d-flex align-items-center">
                <span class="me-2">${SVG_ICONS.alertTriangle}</span>
                <div>${data.message || "Failed to fetch market candles."} <button type="button" class="btn btn-sm btn-link p-0 ms-2" id="switch-to-manual-btn">Enter manually</button></div>
              </div>
            `;
            const switchBtn = document.getElementById("switch-to-manual-btn");
            if (switchBtn) {
              switchBtn.addEventListener("click", () => this.setMode("manual"));
            }
          }
        }
      } catch (err) {
        if (alertContainer) {
          alertContainer.innerHTML = `
            <div class="alert alert-danger mb-3 py-2">
              Network error fetching market data.
            </div>
          `;
        }
      } finally {
        if (fetchBtn) fetchBtn.classList.remove("btn-loading");
      }
    }

    /**
     * Render candlestick series to ApexCharts.
     * @param {Array<Object>} candles
     */
    renderCandles(candles) {
      if (!this.chart || !candles.length) return;
      const seriesData = candles.map((c) => ({
        x: c.date,
        y: [c.open, c.high, c.low, c.close],
      }));
      this.chart.updateSeries([{ data: seriesData }]);
    }

    /**
     * Update ATR display cards and reference 75% ATR values.
     * @param {string|null} atrValue
     * @param {string} sourceName
     * @param {string|null} contributingDate
     */
    updateATRDisplays(atrValue, sourceName, contributingDate) {
      const atrEl = document.getElementById("metric-atr-value");
      const ref75El = document.getElementById("metric-atr-75");
      const sourceBadge = document.getElementById("atr-source-badge");
      const contributingLabel = document.getElementById(
        "atr-contributing-label"
      );
      const lang = document.documentElement.lang?.startsWith("ru")
        ? "ru"
        : "en";
      const t = I18N[lang] || I18N.en;

      if (sourceBadge && sourceName) {
        sourceBadge.textContent = sourceName;
        if (sourceName.toLowerCase() === "manual" || sourceName === "Вручную") {
          sourceBadge.className = "badge bg-secondary-lt";
        } else {
          sourceBadge.className = "badge bg-primary-lt";
        }
      }

      if (contributingLabel) {
        if (this.currentMode === "manual") {
          contributingLabel.textContent = t.manualAtrContext;
        } else if (contributingDate) {
          contributingLabel.textContent = `${t.closedCandlesThrough} ${contributingDate}`;
        }
      }

      if (!atrValue) {
        if (atrEl) atrEl.textContent = "—";
        if (ref75El) ref75El.textContent = "—";
        return;
      }

      try {
        const bigAtr = new Big(atrValue);
        const big75 = bigAtr.times("0.75");
        if (atrEl) atrEl.textContent = bigAtr.toFixed(2);
        if (ref75El) ref75El.textContent = big75.toFixed(2);
      } catch (_) {}
    }

    /**
     * Update session range metric in UI.
     * @param {string} valueStr
     * @param {string} percentStr
     */
    updateSessionMetric(valueStr, percentStr) {
      const rangeEl = document.getElementById("metric-session-range");
      const pctEl = document.getElementById("metric-session-percent");
      const tapeEl = document.getElementById("atr-session-tape");
      const fillEl = document.getElementById("atr-session-fill");

      let pctNumber = 0;
      if (
        percentStr !== undefined &&
        percentStr !== null &&
        percentStr !== ""
      ) {
        pctNumber = Math.round(Number(percentStr));
      }
      if (isNaN(pctNumber)) pctNumber = 0;

      if (rangeEl) rangeEl.textContent = valueStr || "—";
      if (pctEl) pctEl.textContent = `${pctNumber}%`;

      if (tapeEl) {
        tapeEl.style.setProperty(
          "--tf-range-percent",
          `${Math.min(100, Math.max(0, pctNumber))}%`
        );
      }
      if (fillEl) {
        fillEl.classList.remove(
          "tf-range-tape-fill-warning",
          "tf-range-tape-fill-danger"
        );
        if (pctNumber > 100) {
          fillEl.classList.add("tf-range-tape-fill-danger");
        } else if (pctNumber > 75) {
          fillEl.classList.add("tf-range-tape-fill-warning");
        }
      }
    }
  }

  /**
   * Main workspace controller orchestrating forms, calculations, and components.
   */
  class WorkspaceController {
    constructor() {
      this.config = this.loadConfig();
      this.instrumentsMap = new Map();
      this.strategiesMap = new Map();
      this.currentInstrument = null;
      this.currentStrategy = null;
      this.currentProductKind = null;
      this.tomSelectInstance = null;
      this.atrManager = null;
    }

    /**
     * Load initial configuration JSON embedded in the page.
     * @returns {Object}
     */
    loadConfig() {
      const configScript = document.getElementById("trade-workspace-config");
      if (configScript && configScript.textContent) {
        try {
          return JSON.parse(configScript.textContent);
        } catch (e) {
          console.error("Failed to parse trade-workspace-config", e);
        }
      }
      return {};
    }

    /**
     * Initialize the workspace module.
     */
    init() {
      this.populateMaps();
      this.restoreConfigValues();
      this.initProductKindSelector();
      this.initInstrumentSelector();
      this.updateInputSteps();
      this.initATRManager();
      this.bindFormEvents();
      this.syncShortAvailability();
      this.recalculateAll();
      this.updateChecklist();

      if (this.config.is_read_only) {
        this.applyReadOnlyMode();
      } else if (
        this.config.selected_instrument_id &&
        this.config.atr_source !== "manual" &&
        (!this.config.candles_data || this.config.candles_data.length === 0)
      ) {
        this.atrManager.fetchMarketData();
      }
    }

    /**
     * Update step attributes on planned entry and planned stop inputs based on current instrument.
     */
    updateInputSteps() {
      const step =
        (this.currentInstrument && this.currentInstrument.price_step) || "any";
      const entryInput = document.getElementById("planned-entry");
      const stopInput = document.getElementById("planned-stop");
      if (entryInput) entryInput.setAttribute("step", step);
      if (stopInput) stopInput.setAttribute("step", step);
    }

    /**
     * Restore form inputs from configuration if not already populated by the server.
     */
    restoreConfigValues() {
      if (this.config.trade_date) {
        const dateInput = document.getElementById("trade-date");
        if (dateInput && !dateInput.value) {
          dateInput.value = this.config.trade_date;
        }
      }
      if (this.config.planned_entry) {
        const entryInput = document.getElementById("planned-entry");
        if (entryInput && !entryInput.value) {
          entryInput.value = this.config.planned_entry;
        }
      }
      if (this.config.planned_stop) {
        const stopInput = document.getElementById("planned-stop");
        if (stopInput && !stopInput.value) {
          stopInput.value = this.config.planned_stop;
        }
      }
      if (this.config.manual_atr_value) {
        const atrInput = document.getElementById("manual-atr-value");
        if (atrInput && !atrInput.value) {
          atrInput.value = this.config.manual_atr_value;
        }
      }
      if (this.config.manual_session_range) {
        const sessionInput = document.getElementById("manual-session-range");
        if (sessionInput && !sessionInput.value) {
          sessionInput.value = this.config.manual_session_range;
        }
      }
      if (this.config.checklist) {
        const checklistKeys = [
          "market_sentiment",
          "information_background",
          "global_daily_direction",
          "local_daily_movement",
        ];
        checklistKeys.forEach((key) => {
          const val = this.config.checklist[key];
          if (val) {
            const radio = document.querySelector(`input[name="${key}"][value="${val}"]`);
            if (radio) radio.checked = true;
          }
        });
      }
    }

    /**
     * Populate strategies and instruments local memory maps.
     */
    populateMaps() {
      if (this.config.strategies) {
        this.config.strategies.forEach((s) => this.strategiesMap.set(String(s.id), s));
      }
      if (this.config.instruments) {
        this.config.instruments.forEach((inst) =>
          this.instrumentsMap.set(String(inst.id), inst)
        );
      }

      if (this.config.selected_strategy_id) {
        this.currentStrategy = this.strategiesMap.get(
          String(this.config.selected_strategy_id)
        );
      }
      if (this.config.selected_instrument_id) {
        this.currentInstrument = this.instrumentsMap.get(
          String(this.config.selected_instrument_id)
        );
      }
    }

    /**
     * Initialize product kind segmented pills and listeners.
     */
    initProductKindSelector() {
      if (this.currentInstrument) {
        this.currentProductKind = this.currentInstrument.product;
      } else if (this.config.product_kind) {
        this.currentProductKind = this.config.product_kind;
      } else if (this.instrumentsMap.size > 0) {
        this.currentProductKind =
          Array.from(this.instrumentsMap.values())[0].product;
      }

      this.syncProductKindPills();

      const container = document.getElementById("product-kind-options");
      if (container) {
        container.addEventListener("change", (e) => {
          const target = e.target;
          if (target && target.name === "product_kind") {
            this.setProductKind(target.value);
          }
        });
      }
    }

    /**
     * Sync checked state on product kind radio buttons.
     */
    syncProductKindPills() {
      if (!this.currentProductKind) return;
      const radio = document.querySelector(
        `input[name="product_kind"][value="${this.currentProductKind}"]`
      );
      if (radio) {
        radio.checked = true;
      }
    }

    /**
     * Switch active product kind and filter pair dropdown options.
     * @param {string} productKind
     */
    setProductKind(productKind) {
      if (this.currentProductKind === productKind && this.currentInstrument) {
        return;
      }
      this.currentProductKind = productKind;
      this.syncProductKindPills();
      this.filterInstrumentOptions();
    }

    /**
     * Filter instrument options in Tom Select based on currentProductKind.
     */
    filterInstrumentOptions() {
      const filtered = Array.from(this.instrumentsMap.values()).filter(
        (inst) =>
          !this.currentProductKind || inst.product === this.currentProductKind
      );

      if (this.tomSelectInstance) {
        this.tomSelectInstance.clear();
        this.tomSelectInstance.clearOptions();
        filtered.forEach((inst) => {
          this.tomSelectInstance.addOption({
            value: String(inst.id),
            text: inst.canonical_symbol,
            exec_symbol: inst.exec_symbol,
            product: inst.product,
          });
        });
        this.tomSelectInstance.refreshOptions(false);

        let targetId = null;
        if (
          this.currentInstrument &&
          this.currentInstrument.product === this.currentProductKind
        ) {
          targetId = String(this.currentInstrument.id);
        } else if (filtered.length > 0) {
          targetId = String(filtered[0].id);
        }

        if (targetId) {
          this.tomSelectInstance.setValue(targetId, true);
          this.currentInstrument = this.instrumentsMap.get(targetId) || null;
          this.updateInputSteps();
          this.syncShortAvailability();
          this.updateContextBarSymbols();
          this.recalculateAll();
          if (
            this.currentInstrument &&
            this.atrManager &&
            this.atrManager.currentMode !== "manual"
          ) {
            this.atrManager.fetchMarketData();
          }
        } else {
          this.currentInstrument = null;
          this.updateInputSteps();
          this.syncShortAvailability();
          this.recalculateAll();
        }
      }
    }

    /**
     * Initialize Tom Select searchable dropdown on the instrument selector.
     */
    initInstrumentSelector() {
      const selectEl = document.getElementById("trade-instrument");
      if (!selectEl || typeof TomSelect === "undefined") return;

      const filtered = Array.from(this.instrumentsMap.values()).filter(
        (inst) =>
          !this.currentProductKind || inst.product === this.currentProductKind
      );

      const initialSelectedId = this.currentInstrument
        ? String(this.currentInstrument.id)
        : (filtered.length > 0 ? String(filtered[0].id) : null);

      this.tomSelectInstance = new TomSelect(selectEl, {
        create: false,
        maxItems: 1,
        placeholder: "Search trading pair (e.g. BTC/USDT)...",
        searchField: ["text", "exec_symbol"],
        valueField: "value",
        labelField: "text",
        options: filtered.map((inst) => ({
          value: String(inst.id),
          text: inst.canonical_symbol,
          exec_symbol: inst.exec_symbol,
          product: inst.product,
        })),
        items: initialSelectedId ? [initialSelectedId] : [],
        onChange: (value) => {
          this.currentInstrument =
            this.instrumentsMap.get(String(value)) || null;
          if (
            this.currentInstrument &&
            this.currentInstrument.product !== this.currentProductKind
          ) {
            this.currentProductKind = this.currentInstrument.product;
            this.syncProductKindPills();
          }
          this.updateInputSteps();
          this.syncShortAvailability();
          this.updateContextBarSymbols();
          this.recalculateAll();
          if (
            this.currentInstrument &&
            this.atrManager &&
            this.atrManager.currentMode !== "manual"
          ) {
            this.atrManager.fetchMarketData();
          }
        },
      });
    }

    /**
     * Initialize ATR manager component.
     */
    initATRManager() {
      this.atrManager = new ATRManager({
        marketDataUrl: "/trades/workspace/market-data/",
        onATRChange: () => this.updateATRExceedsCheck(),
        isReadOnly: !!this.config.is_read_only,
        initialMode: this.config.atr_source || "auto",
        initialAtrValue: this.config.atr_value || null,
        initialCandles: this.config.candles_data || [],
        initialDate: this.config.atr_contributing_date || null,
        initialObservedSessionRange:
          this.config.observed_session_range || null,
        initialSessionRangePercent:
          this.config.session_range_percent || null,
        initialProvider: this.config.context_bar
          ? this.config.context_bar.market_data_provider
          : null,
      });

      if (this.config.atr_source === "manual") {
        this.atrManager.setMode("manual");
      }
    }

    /**
     * Lock and disable form controls when viewing a frozen (non-draft) trade.
     */
    applyReadOnlyMode() {
      if (this.tomSelectInstance) {
        this.tomSelectInstance.disable();
      }

      const formControls = document.querySelectorAll(
        "#trade-form input:not([type='hidden']), #trade-form select, #trade-form button, .tf-checklist-options input, input[name='product_kind'], #atr-source-auto, #atr-source-manual, #btn-fetch-market-data, #manual-atr-value, #manual-session-range"
      );
      formControls.forEach((el) => {
        el.disabled = true;
        if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
          el.setAttribute("readonly", "readonly");
        }
      });

      const directionAndProductLabels = document.querySelectorAll(
        ".btn-group[aria-label] label, .tf-checklist-options label, .tf-product-options label"
      );
      directionAndProductLabels.forEach((lbl) => {
        lbl.classList.add("disabled");
        lbl.style.pointerEvents = "none";
      });
    }

    /**
     * Bind inputs and changes across the trade decision form.
     */
    bindFormEvents() {
      const entryInput = document.getElementById("planned-entry");
      const stopInput = document.getElementById("planned-stop");
      const profileSelect = document.getElementById("trade-profile");
      const strategySelect = document.getElementById("trade-strategy");
      const dateInput = document.getElementById("trade-date");
      const directionInputs = document.querySelectorAll("input[name='direction']");
      const checklistInputs = document.querySelectorAll(
        ".tf-checklist-options input"
      );

      if (entryInput) {
        entryInput.addEventListener("input", () => this.recalculateAll());
      }
      if (stopInput) {
        stopInput.addEventListener("input", () => this.recalculateAll());
      }
      if (dateInput) {
        dateInput.addEventListener("change", () => {
          if (this.atrManager && this.atrManager.currentMode !== "manual") {
            this.atrManager.fetchMarketData();
          }
        });
      }

      directionInputs.forEach((radio) => {
        radio.addEventListener("change", () => {
          this.recalculateAll();
          this.updateChecklist();
        });
      });

      checklistInputs.forEach((radio) => {
        radio.addEventListener("change", () => this.updateChecklist());
      });

      if (profileSelect) {
        profileSelect.addEventListener("change", (e) =>
          this.handleProfileChange(e.target.value)
        );
      }
      if (strategySelect) {
        strategySelect.addEventListener("change", (e) =>
          this.handleStrategyChange(e.target.value)
        );
      }
    }

    /**
     * Handle profile selection change by fetching updated strategies and instruments.
     * @param {string} profileId
     */
    async handleProfileChange(profileId) {
      if (!profileId) return;
      try {
        const res = await fetch(
          `/trades/workspace/options/?profile=${encodeURIComponent(profileId)}`
        );
        const data = await res.json();
        this.updateWorkspaceOptions(data);
      } catch (err) {
        console.error("Failed to load options for profile", err);
      }
    }

    /**
     * Handle strategy selection change by fetching updated instruments.
     * @param {string} strategyId
     */
    async handleStrategyChange(strategyId) {
      const profileSelect = document.getElementById("trade-profile");
      const profileId = profileSelect ? profileSelect.value : this.config.selected_profile_id;
      if (!strategyId || !profileId) return;

      try {
        const res = await fetch(
          `/trades/workspace/options/?profile=${encodeURIComponent(profileId)}&strategy=${encodeURIComponent(strategyId)}`
        );
        const data = await res.json();
        this.updateWorkspaceOptions(data);
      } catch (err) {
        console.error("Failed to load options for strategy", err);
      }
    }

    /**
     * Update workspace state, product pills, and Tom Select options from JSON options payload.
     * @param {Object} data
     */
    updateWorkspaceOptions(data) {
      this.strategiesMap.clear();
      this.instrumentsMap.clear();

      data.strategies.forEach((s) => this.strategiesMap.set(String(s.id), s));
      data.instruments.forEach((inst) =>
        this.instrumentsMap.set(String(inst.id), inst)
      );

      this.currentStrategy =
        this.strategiesMap.get(String(data.selected_strategy_id)) || null;
      this.currentInstrument =
        this.instrumentsMap.get(String(data.selected_instrument_id)) || null;

      // Update strategy select element
      const strategySelect = document.getElementById("trade-strategy");
      if (strategySelect) {
        strategySelect.innerHTML = data.strategies
          .map(
            (s) =>
              `<option value="${s.id}" ${String(s.id) === String(data.selected_strategy_id) ? "selected" : ""}>${s.name} (${formatCompactNumber(s.risk_percent)}%, 1:${formatCompactNumber(s.reward_multiple)} R)</option>`
          )
          .join("");
      }

      // Update product pills container
      const productOptionsContainer = document.getElementById(
        "product-kind-options"
      );
      if (productOptionsContainer) {
        const availableProducts = [];
        const seen = new Set();
        data.instruments.forEach((inst) => {
          if (!seen.has(inst.product)) {
            seen.add(inst.product);
            availableProducts.push({
              value: inst.product,
              label: inst.product_label,
            });
          }
        });

        if (
          this.currentInstrument &&
          seen.has(this.currentInstrument.product)
        ) {
          this.currentProductKind = this.currentInstrument.product;
        } else if (availableProducts.length > 0) {
          this.currentProductKind = availableProducts[0].value;
        }

        productOptionsContainer.innerHTML = availableProducts
          .map(
            (p) =>
              `<input class="btn-check" id="product-kind-${p.value}" name="product_kind" type="radio" value="${p.value}" ${p.value === this.currentProductKind ? "checked" : ""}><label class="btn btn-outline-primary" for="product-kind-${p.value}">${p.label}</label>`
          )
          .join("");
      }

      this.filterInstrumentOptions();

      // Update Context Bar
      if (data.context_bar) {
        this.updateContextBar(data.context_bar);
      }

      this.updateInputSteps();
      this.syncShortAvailability();
      this.recalculateAll();
      if (this.currentInstrument && this.atrManager.currentMode !== "manual") {
        this.atrManager.fetchMarketData();
      }
    }

    /**
     * Synchronize context bar metric displays.
     * @param {Object} ctx
     */
    updateContextBar(ctx) {
      const fixed1rEl = document.getElementById("ctx-fixed-1r");
      const walletAvailEl = document.getElementById("ctx-wallet-available");
      const profileEl = document.getElementById("ctx-profile-name");
      const venueEl = document.getElementById("ctx-venue-name");
      const ratioEl = document.getElementById("ctx-reward-multiple");

      if (profileEl && ctx.profile_name) profileEl.textContent = ctx.profile_name;
      if (venueEl && ctx.venue_name) venueEl.textContent = ctx.venue_name;
      if (fixed1rEl) {
        fixed1rEl.textContent = ctx.fixed_1r
          ? `${ctx.fixed_1r} ${ctx.settlement_symbol || ""}`
          : "—";
      }
      if (walletAvailEl) {
        walletAvailEl.textContent = ctx.wallet_available
          ? `${ctx.wallet_available} ${ctx.settlement_symbol || ""}`
          : "—";
      }
      if (ratioEl && ctx.reward_multiple) {
        ratioEl.textContent = `1:${formatCompactNumber(ctx.reward_multiple)} R`;
      }
      this.config.context_bar = ctx;
    }

    /**
     * Update settlement symbol suffix in form input groups.
     */
    updateContextBarSymbols() {
      const symbol =
        (this.currentInstrument && this.currentInstrument.settlement_symbol) ||
        (this.config.context_bar && this.config.context_bar.settlement_symbol) ||
        "USD";

      document.querySelectorAll(".tf-settlement-symbol").forEach((el) => {
        el.textContent = symbol;
      });
    }

    /**
     * Enable/disable SHORT button depending on whether product is spot/cash equity.
     */
    syncShortAvailability() {
      const shortRadio = document.getElementById("direction-short");
      const shortLabel = document.querySelector("label[for='direction-short']");
      const longRadio = document.getElementById("direction-long");
      const tooltipWrap = document.getElementById("short-tooltip-wrapper");
      if (!shortRadio || !shortLabel) return;

      const product =
        (this.currentInstrument && this.currentInstrument.product) ||
        this.currentProductKind ||
        "";
      const isShortDisabled = product === "spot" || product === "cash_equity";

      shortRadio.disabled = isShortDisabled;
      if (isShortDisabled) {
        shortLabel.classList.add("disabled");
        if (shortRadio.checked && longRadio) {
          longRadio.checked = true;
          this.recalculateAll();
        }
        if (tooltipWrap) {
          const hint =
            tooltipWrap.dataset.shortDisabledTitle ||
            tooltipWrap.getAttribute("title") ||
            "";
          if (hint) {
            tooltipWrap.setAttribute("title", hint);
            tooltipWrap.setAttribute("data-bs-toggle", "tooltip");
            tooltipWrap.setAttribute("tabindex", "0");
            if (window.bootstrap && window.bootstrap.Tooltip) {
              const inst =
                window.bootstrap.Tooltip.getOrCreateInstance(tooltipWrap);
              inst.enable();
            }
          }
        }
      } else {
        shortLabel.classList.remove("disabled");
        if (tooltipWrap) {
          tooltipWrap.removeAttribute("title");
          tooltipWrap.removeAttribute("data-bs-original-title");
          tooltipWrap.removeAttribute("data-bs-toggle");
          tooltipWrap.removeAttribute("tabindex");
          if (window.bootstrap && window.bootstrap.Tooltip) {
            const inst = window.bootstrap.Tooltip.getInstance(tooltipWrap);
            if (inst) {
              inst.hide();
              inst.disable();
              inst.dispose();
            }
          }
        }
      }
    }

    /**
     * Get active form state values.
     * @returns {Object}
     */
    getFormState() {
      const entryInput = document.getElementById("planned-entry");
      const stopInput = document.getElementById("planned-stop");
      const checkedDir = document.querySelector("input[name='direction']:checked");

      const getChecklistVal = (name) => {
        const checked = document.querySelector(`input[name='${name}']:checked`);
        return checked ? checked.value : "";
      };

      return {
        direction: checkedDir ? checkedDir.value : "long",
        planned_entry: entryInput ? entryInput.value.trim() : "",
        planned_stop: stopInput ? stopInput.value.trim() : "",
        market_sentiment: getChecklistVal("market_sentiment"),
        information_background: getChecklistVal("information_background"),
        global_daily_direction: getChecklistVal("global_daily_direction"),
        local_daily_movement: getChecklistVal("local_daily_movement"),
      };
    }

    /**
     * Recalculate position plan metrics and update the DOM.
     */
    recalculateAll() {
      const state = this.getFormState();
      const planEmptyEl = document.getElementById("plan-empty-state");
      const planMetricsEl = document.getElementById("plan-metrics-state");
      const planAlertEl = document.getElementById("plan-alert-container");

      if (!this.currentStrategy || !this.currentInstrument) {
        if (planEmptyEl) planEmptyEl.classList.remove("d-none");
        if (planMetricsEl) planMetricsEl.classList.add("d-none");
        return;
      }

      const fixed1r =
        (this.config.context_bar && this.config.context_bar.fixed_1r) ||
        null;
      const walletAvail =
        (this.config.context_bar && this.config.context_bar.wallet_available) ||
        null;

      const calcResult = PositionCalculator.calculate({
        direction: state.direction,
        entryStr: state.planned_entry,
        stopStr: state.planned_stop,
        targetRiskStr: fixed1r,
        rewardMultipleStr: this.currentStrategy.reward_multiple,
        priceStepStr: this.currentInstrument.price_step,
        qtyStepStr: this.currentInstrument.qty_step,
        minQtyStr: this.currentInstrument.min_qty,
        minNotionalStr: this.currentInstrument.min_notional,
        walletAvailableStr: walletAvail,
      });

      if (!calcResult.success || !calcResult.plan) {
        if (planAlertEl) {
          planAlertEl.innerHTML = calcResult.error
            ? `<div class="alert alert-warning mb-3 py-2">${calcResult.error}</div>`
            : "";
        }
        if (planEmptyEl) planEmptyEl.classList.remove("d-none");
        if (planMetricsEl) planMetricsEl.classList.add("d-none");
        this.updateATRExceedsCheck();
        return;
      }

      if (planAlertEl) planAlertEl.innerHTML = "";
      if (planEmptyEl) planEmptyEl.classList.add("d-none");
      if (planMetricsEl) planMetricsEl.classList.remove("d-none");

      const plan = calcResult.plan;
      const setVal = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };

      setVal("plan-risk-amount", plan.plannedRiskAmount);
      setVal("plan-profit-amount", plan.plannedProfitAmount);
      setVal("plan-stop-loss", plan.stopLoss);
      setVal("plan-take-profit", plan.takeProfit);
      setVal("plan-quantity", plan.quantity);
      setVal("plan-notional", plan.notional);
      setVal("plan-distance", plan.distance);
      setVal("plan-capacity-after", plan.capacityAfterPlan || "—");

      const targetRatioEl = document.getElementById("plan-target-ratio");
      if (targetRatioEl) {
        targetRatioEl.textContent = `1:${formatCompactNumber(this.currentStrategy.reward_multiple || "3")} R`;
      }

      const lang = document.documentElement.lang?.startsWith("ru") ? "ru" : "en";
      const t = I18N[lang] || I18N.en;

      const capacityEl = document.getElementById("plan-capacity-after");
      const capacityStatusEl = document.getElementById("plan-capacity-status");
      if (capacityEl) {
        if (plan.exceedsWallet) {
          capacityEl.classList.add("text-danger", "fw-semibold");
        } else {
          capacityEl.classList.remove("text-danger", "fw-semibold");
        }
      }

      if (capacityStatusEl) {
        if (plan.exceedsWallet) {
          capacityStatusEl.className = "badge bg-danger-lt";
          capacityStatusEl.textContent = t.capacityExceeded;
        } else {
          capacityStatusEl.className = "badge bg-success-lt";
          capacityStatusEl.textContent = t.capacityAvailable;
        }
      }

      const walletExceedAlert = document.getElementById("plan-wallet-exceed-alert");
      if (walletExceedAlert) {
        if (plan.exceedsWallet) {
          walletExceedAlert.classList.remove("d-none");
        } else {
          walletExceedAlert.classList.add("d-none");
        }
      }

      this.updatePriceLadder({
        direction: state.direction,
        entry: plan.entry,
        stopLoss: plan.stopLoss,
        takeProfit: plan.takeProfit,
        rewardMultiple: this.currentStrategy.reward_multiple,
      });

      this.updateATRExceedsCheck();
    }

    /**
     * Update the visual price ladder / risk-reward range bar in Position Plan.
     * @param {Object} params
     * @param {string} params.direction - "long" or "short".
     * @param {string} params.entry
     * @param {string} params.stopLoss
     * @param {string} params.takeProfit
     * @param {string|number} params.rewardMultiple
     */
    updatePriceLadder(params) {
      const ladderEl = document.getElementById("plan-price-ladder");
      const dirBadge = document.getElementById("plan-direction-badge");
      const leftLabel = document.getElementById("plan-ladder-left-label");
      const leftPrice = document.getElementById("plan-ladder-left-price");
      const pinPrice = document.getElementById("plan-entry-pin-price");
      const rightLabel = document.getElementById("plan-ladder-right-label");
      const rightPrice = document.getElementById("plan-ladder-right-price");
      const segmentRisk = document.getElementById("plan-segment-risk");
      const segmentReward = document.getElementById("plan-segment-reward");
      const anchorEntry = document.getElementById("plan-anchor-entry");
      const riskRatioLabel = document.getElementById("plan-risk-ratio-label");
      const rewardRatioLabel = document.getElementById("plan-reward-ratio-label");

      if (!ladderEl) return;

      if (pinPrice) {
        pinPrice.textContent = params.entry || "—";
      }

      const isShort = params.direction.toLowerCase() === "short";
      const multiple = Math.max(
        0.1,
        Number(params.rewardMultiple) || 3
      );
      const riskPct = Math.round((1 / (1 + multiple)) * 100);
      const rewardPct = 100 - riskPct;

      const lang = document.documentElement.lang?.startsWith("ru") ? "ru" : "en";
      const stopText = lang === "ru" ? "Стоп-лосс" : "Stop loss";
      const tpText = lang === "ru" ? "Тейк-профит" : "Take profit";

      if (isShort) {
        ladderEl.classList.add("is-short");
        if (dirBadge) {
          dirBadge.className = "badge bg-danger-lt";
          dirBadge.textContent = "SHORT";
        }
        if (leftLabel) {
          leftLabel.className = "text-success small fw-semibold";
          leftLabel.textContent = tpText;
        }
        if (leftPrice) leftPrice.textContent = params.takeProfit;
        if (rightLabel) {
          rightLabel.className = "text-danger small fw-semibold";
          rightLabel.textContent = stopText;
        }
        if (rightPrice) rightPrice.textContent = params.stopLoss;

        if (segmentReward) {
          segmentReward.style.width = `${rewardPct}%`;
          segmentReward.style.order = "1";
        }
        if (segmentRisk) {
          segmentRisk.style.width = `${riskPct}%`;
          segmentRisk.style.order = "2";
        }
        if (anchorEntry) {
          anchorEntry.style.left = `${rewardPct}%`;
        }
      } else {
        ladderEl.classList.remove("is-short");
        if (dirBadge) {
          dirBadge.className = "badge bg-success-lt";
          dirBadge.textContent = "LONG";
        }
        if (leftLabel) {
          leftLabel.className = "text-danger small fw-semibold";
          leftLabel.textContent = stopText;
        }
        if (leftPrice) leftPrice.textContent = params.stopLoss;
        if (rightLabel) {
          rightLabel.className = "text-success small fw-semibold";
          rightLabel.textContent = tpText;
        }
        if (rightPrice) rightPrice.textContent = params.takeProfit;

        if (segmentRisk) {
          segmentRisk.style.width = `${riskPct}%`;
          segmentRisk.style.order = "1";
        }
        if (segmentReward) {
          segmentReward.style.width = `${rewardPct}%`;
          segmentReward.style.order = "2";
        }
        if (anchorEntry) {
          anchorEntry.style.left = `${riskPct}%`;
        }
      }

      if (riskRatioLabel) riskRatioLabel.textContent = "1R";
      if (rewardRatioLabel) {
        rewardRatioLabel.textContent = `${formatCompactNumber(multiple)}R`;
      }
    }

    /**
     * Check if planned move exceeds 75% of ATR and render advisory badge and tape.
     */
    updateATRExceedsCheck() {
      const state = this.getFormState();
      const badgeEl = document.getElementById("atr-exceeds-badge");
      const moveMetricEl = document.getElementById("metric-planned-move");
      const movePctEl = document.getElementById("metric-planned-move-pct");
      const plannedTapeEl = document.getElementById("atr-planned-tape");
      const plannedFillEl = document.getElementById("atr-planned-fill");

      const lang = document.documentElement.lang?.startsWith("ru")
        ? "ru"
        : "en";
      const t = I18N[lang] || I18N.en;

      if (!state.planned_entry || !state.planned_stop || !this.currentStrategy) {
        if (badgeEl) badgeEl.classList.add("d-none");
        if (moveMetricEl) moveMetricEl.textContent = "—";
        if (movePctEl) movePctEl.textContent = "0%";
        if (plannedTapeEl) plannedTapeEl.style.setProperty("--tf-range-percent", "0%");
        if (plannedFillEl) {
          plannedFillEl.classList.remove(
            "tf-range-tape-fill-warning",
            "tf-range-tape-fill-danger"
          );
        }
        return;
      }

      const atrVal = this.atrManager ? this.atrManager.currentAtrValue : null;
      if (!atrVal) {
        if (badgeEl) badgeEl.classList.add("d-none");
        if (moveMetricEl) moveMetricEl.textContent = "—";
        if (movePctEl) movePctEl.textContent = "0%";
        if (plannedTapeEl) plannedTapeEl.style.setProperty("--tf-range-percent", "0%");
        if (plannedFillEl) {
          plannedFillEl.classList.remove(
            "tf-range-tape-fill-warning",
            "tf-range-tape-fill-danger"
          );
        }
        return;
      }

      try {
        const entry = new Big(state.planned_entry);
        const stop = new Big(state.planned_stop);
        const distance = entry.minus(stop).abs();
        const rewardMult = new Big(this.currentStrategy.reward_multiple || "3");
        const plannedMove = distance.times(rewardMult);
        const atrBig = new Big(atrVal);

        if (atrBig.gt(0)) {
          const movePct = plannedMove.div(atrBig).times(100);
          const pctRound = Math.round(Number(movePct.toString()));
          const boundedPct = Math.min(100, Math.max(0, pctRound));

          if (moveMetricEl) moveMetricEl.textContent = plannedMove.toFixed(2);
          if (movePctEl) movePctEl.textContent = `${pctRound}%`;

          if (plannedTapeEl) {
            plannedTapeEl.style.setProperty("--tf-range-percent", `${boundedPct}%`);
          }

          if (plannedFillEl) {
            plannedFillEl.classList.remove(
              "tf-range-tape-fill-warning",
              "tf-range-tape-fill-danger"
            );
            if (pctRound > 100) {
              plannedFillEl.classList.add("tf-range-tape-fill-danger");
            } else if (pctRound > 75) {
              plannedFillEl.classList.add("tf-range-tape-fill-warning");
            }
          }

          if (badgeEl) {
            if (pctRound > 100) {
              badgeEl.textContent = t.exceeds100;
              badgeEl.className = "badge bg-danger-lt";
              badgeEl.classList.remove("d-none");
            } else if (pctRound > 75) {
              badgeEl.textContent = t.exceeds75;
              badgeEl.className = "badge bg-warning-lt";
              badgeEl.classList.remove("d-none");
            } else {
              badgeEl.classList.add("d-none");
            }
          }
        }
      } catch (_) {}
    }

    /**
     * Update checklist assessment scoring and rendered feedback.
     */
    updateChecklist() {
      const state = this.getFormState();
      const assessment = ChecklistManager.assess(state);
      ChecklistManager.render(assessment);
    }
  }

  // Self-initialize on DOM ready
  document.addEventListener("DOMContentLoaded", () => {
    const controller = new WorkspaceController();
    controller.init();
  });
})();
