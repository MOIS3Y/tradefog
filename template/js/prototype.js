/**
 * Tradefog Static Prototype Shared Behavior
 */
(() => {
  "use strict";

  /** @typedef {"auto" | "dark" | "light"} ThemeChoice */

  /** @type {ThemeChoice[]} */
  const themeOrder = ["auto", "dark", "light"];

  /** System preference used when the selected theme is automatic. */
  const systemTheme = matchMedia("(prefers-color-scheme: dark)");

  /**
   * Read and validate the saved theme preference.
   * @returns {ThemeChoice}
   */
  function storedTheme() {
    let savedTheme = "auto";
    try {
      savedTheme = localStorage.getItem("tradefog-theme") || "auto";
    } catch {
      // Local storage unavailable fallback
    }
    const migrated = savedTheme === "system" ? "auto" : savedTheme;
    return themeOrder.includes(migrated) ? migrated : "auto";
  }

  /**
   * Resolve theme choice to concrete color scheme.
   * @param {ThemeChoice} choice
   * @returns {"dark" | "light"}
   */
  function resolvedTheme(choice) {
    if (choice !== "auto") {
      return choice;
    }
    return systemTheme.matches ? "dark" : "light";
  }

  /**
   * Apply theme preference to document root.
   * @param {ThemeChoice} choice
   */
  function applyTheme(choice) {
    const concrete = resolvedTheme(choice);
    document.documentElement.setAttribute("data-bs-theme", concrete);
    document.documentElement.dataset.bsTheme = concrete;
    document.documentElement.dataset.themeChoice = choice;

    document.dispatchEvent(
      new CustomEvent("tradefog:theme-changed", {
        detail: { theme: concrete, choice },
      }),
    );
  }

  const initialTheme = storedTheme();
  applyTheme(initialTheme);

  /**
   * Synchronize button icons and labels with active theme.
   * @param {HTMLButtonElement} button
   * @param {ThemeChoice} choice
   */
  function updateThemeButton(button, choice) {
    const labels = {
      auto: "Theme: Auto (System)",
      dark: "Theme: Dark",
      light: "Theme: Light",
    };
    const label = labels[choice] || "Toggle theme";
    button.setAttribute("aria-label", label);
    button.setAttribute("title", label);

    const hiddenLabel = button.querySelector("[data-theme-label]");
    if (hiddenLabel) {
      hiddenLabel.textContent = label;
    }

    const icons = button.querySelectorAll(
      ".tf-theme-icon-auto, .tf-theme-icon-dark, .tf-theme-icon-light",
    );
    icons.forEach((icon) => {
      icon.classList.toggle(
        "d-none",
        !icon.classList.contains(`tf-theme-icon-${choice}`),
      );
    });
  }

  /**
   * Smoothly rotate the newly active icon.
   * @param {HTMLButtonElement} button
   * @param {ThemeChoice} choice
   */
  function animateThemeIcon(button, choice) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const icon = button.querySelector(`.tf-theme-icon-${choice}`);
    if (icon) {
      icon.animate(
        [
          { transform: "rotate(0turn) scale(0.8)", opacity: 0.5 },
          { transform: "rotate(1turn) scale(1)", opacity: 1 },
        ],
        {
          duration: 350,
          easing: "cubic-bezier(0.25, 1, 0.5, 1)",
        },
      );
    }
  }

  /**
   * Initialize theme toggle buttons across the page.
   */
  function initializeThemeToggle() {
    const themeButtons = document.querySelectorAll("[data-theme-toggle]");
    if (!themeButtons.length) return;

    themeButtons.forEach((btn) => {
      if (btn instanceof HTMLButtonElement) {
        updateThemeButton(btn, storedTheme());

        btn.addEventListener("click", (e) => {
          e.preventDefault();
          const current = document.documentElement.dataset.themeChoice || "auto";
          const currentIndex = themeOrder.indexOf(current);
          const next = themeOrder[(currentIndex + 1) % themeOrder.length];

          applyTheme(next);
          themeButtons.forEach((b) => updateThemeButton(b, next));
          animateThemeIcon(btn, next);

          try {
            localStorage.setItem("tradefog-theme", next);
          } catch {
            // Ignore storage errors
          }
        });
      }
    });

    systemTheme.addEventListener("change", () => {
      if (document.documentElement.dataset.themeChoice === "auto") {
        applyTheme("auto");
      }
    });
  }

  /**
   * Initialize Scroll-to-top button.
   */
  function initializeScrollTop() {
    const button = document.querySelector(".tf-scroll-top, [data-scroll-top]");
    if (!(button instanceof HTMLButtonElement)) return;

    let updatePending = false;
    const updateVisibility = () => {
      button.classList.toggle("is-visible", window.scrollY > 400);
      updatePending = false;
    };

    window.addEventListener(
      "scroll",
      () => {
        if (!updatePending) {
          updatePending = true;
          requestAnimationFrame(updateVisibility);
        }
      },
      { passive: true },
    );

    button.addEventListener("click", () => {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }

  /**
   * ApexCharts Trajectory initialization.
   */
  let trajectoryChart = null;

  function initializeCharts() {
    const trajectoryEl = document.querySelector('[data-analytics-chart="xy-trajectory"]');
    if (trajectoryEl && window.ApexCharts) {
      const isDark = document.documentElement.getAttribute("data-bs-theme") === "dark";
      const options = {
        chart: {
          type: "line",
          height: 380,
          toolbar: { show: false },
          background: "transparent",
          fontFamily: "inherit",
          animations: {
            enabled: true,
            easing: "easeinout",
            speed: 600,
          },
        },
        theme: {
          mode: isDark ? "dark" : "light",
        },
        colors: ["#206bc4", "#6c757d"],
        series: [
          {
            name: "Trajectory (R)",
            data: [
              { x: 0, y: 0 },
              { x: 1, y: -1 },
              { x: 2, y: 1 },
              { x: 3, y: 2.5 },
              { x: 4, y: 1.5 },
              { x: 5, y: 3.5 },
              { x: 6, y: 5.2 },
              { x: 7, y: 4.2 },
              { x: 8, y: 6.8 },
              { x: 9, y: 8.5 },
            ],
          },
          {
            name: "Break-even",
            data: [
              { x: 0, y: 0 },
              { x: 9, y: 0 },
            ],
          },
        ],
        stroke: {
          curve: ["straight", "straight"],
          width: [3, 1],
          dashArray: [0, 5],
        },
        markers: {
          size: [5, 0],
          hover: { size: 7 },
        },
        grid: {
          borderColor: "rgba(108, 117, 125, 0.2)",
          strokeDashArray: 4,
        },
        xaxis: {
          title: { text: "Cumulative Closed Decisions (Risk units taken)" },
          labels: { formatter: (val) => val + "R" },
        },
        yaxis: {
          title: { text: "Cumulative Realized Gain (R-Target units)" },
          labels: { formatter: (val) => (val > 0 ? "+" : "") + val + "R" },
        },
        tooltip: {
          theme: isDark ? "dark" : "light",
          y: {
            formatter: (val) => (val > 0 ? "+" : "") + val + "R",
          },
        },
      };

      trajectoryChart = new ApexCharts(trajectoryEl, options);
      trajectoryChart.render();

      document.addEventListener("tradefog:theme-changed", (e) => {
        if (trajectoryChart) {
          trajectoryChart.updateOptions({
            theme: { mode: e.detail.theme },
            tooltip: { theme: e.detail.theme },
          });
        }
      });
    }
  }

  // DOM Content Loaded Handler
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      initializeThemeToggle();
      initializeScrollTop();
      initializeCharts();
    });
  } else {
    initializeThemeToggle();
    initializeScrollTop();
    initializeCharts();
  }
})();
