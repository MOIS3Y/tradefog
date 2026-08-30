"use strict";

/**
 * Manage browser-only behavior shared by every Tradefog page.
 *
 * The initial theme is applied before the document is rendered to avoid a
 * flash of the wrong color scheme. Controls that require DOM elements are
 * initialized after the document is ready.
 */
(() => {
  /** @typedef {"auto" | "dark" | "light"} ThemeChoice */

  /** @type {ThemeChoice[]} */
  const themeOrder = ["auto", "dark", "light"];

  /** System preference used when the selected theme is automatic. */
  const systemTheme = matchMedia("(prefers-color-scheme: dark)");

  /**
   * Read and validate the saved theme preference.
   *
   * The former `system` value is migrated to `auto`. Storage failures fall
   * back to the automatic theme without preventing the page from loading.
   *
   * @returns {ThemeChoice} A supported theme preference.
   */
  function storedTheme() {
    let savedTheme = "auto";
    try {
      savedTheme = localStorage.getItem("tradefog-theme") || "auto";
    } catch {
      // Local storage can be unavailable in privacy-restricted contexts.
    }

    const migratedTheme = savedTheme === "system" ? "auto" : savedTheme;
    return themeOrder.includes(migratedTheme) ? migratedTheme : "auto";
  }

  /**
   * Resolve a theme preference to the concrete Tabler color scheme.
   *
   * @param {ThemeChoice} choice - Theme preference selected by the user.
   * @returns {"dark" | "light"} Concrete color scheme to render.
   */
  function resolvedTheme(choice) {
    if (choice !== "auto") {
      return choice;
    }
    return systemTheme.matches ? "dark" : "light";
  }

  /**
   * Apply a theme preference to the document root.
   *
   * Both the resolved scheme and original choice are retained because the UI
   * needs to distinguish automatic mode from an explicitly selected scheme.
   *
   * @param {ThemeChoice} choice - Theme preference to apply.
   * @returns {void}
   */
  function applyTheme(choice) {
    document.documentElement.dataset.bsTheme = resolvedTheme(choice);
    document.documentElement.dataset.themeChoice = choice;
  }

  const initialTheme = storedTheme();
  applyTheme(initialTheme);

  /**
   * Synchronize the theme button's accessible label with its current state.
   *
   * @param {HTMLButtonElement} button - Theme toggle button.
   * @param {ThemeChoice} choice - Currently selected theme preference.
   * @returns {void}
   */
  function updateThemeButton(button, choice) {
    const labelKey = `label${choice[0].toUpperCase()}${choice.slice(1)}`;
    const label = button.dataset[labelKey];
    const hiddenLabel = button.querySelector("[data-theme-label]");

    button.ariaLabel = label;
    button.title = label;
    if (hiddenLabel) {
      hiddenLabel.textContent = label;
    }
  }

  /**
   * Rotate the newly selected theme icon once after activation.
   *
   * Motion is skipped when the operating system requests reduced animation.
   *
   * @param {HTMLButtonElement} button - Theme toggle button.
   * @param {ThemeChoice} choice - Newly selected theme preference.
   * @returns {void}
   */
  function animateThemeIcon(button, choice) {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }

    const icon = button.querySelector(`.tf-theme-icon-${choice}`);
    icon?.animate(
      [
        { transform: "rotate(0turn)" },
        { transform: "rotate(1turn)" },
      ],
      {
        duration: 350,
        easing: "ease-out",
      },
    );
  }

  /**
   * Attach theme-control events after its markup becomes available.
   *
   * @returns {void}
   */
  function initializeThemeToggle() {
    /** @type {HTMLButtonElement | null} */
    const themeButton = document.querySelector("[data-theme-toggle]");
    if (!themeButton) {
      return;
    }

    updateThemeButton(themeButton, initialTheme);
    themeButton.addEventListener("click", () => {
      const current = document.documentElement.dataset.themeChoice || "auto";
      const currentIndex = themeOrder.indexOf(current);
      const next = themeOrder[(currentIndex + 1) % themeOrder.length];

      applyTheme(next);
      updateThemeButton(themeButton, next);
      animateThemeIcon(themeButton, next);
      try {
        localStorage.setItem("tradefog-theme", next);
      } catch {
        // The selected theme still applies for the current page.
      }
    });

    systemTheme.addEventListener("change", () => {
      if (document.documentElement.dataset.themeChoice === "auto") {
        applyTheme("auto");
      }
    });
  }

  /** Initialize every interactive control that depends on rendered markup. */
  function initializeControls() {
    initializeThemeToggle();
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      initializeControls,
      { once: true },
    );
  } else {
    initializeControls();
  }
})();
