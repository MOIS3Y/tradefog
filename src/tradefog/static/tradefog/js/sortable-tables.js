"use strict";

/** Enhance server-rendered tables with client-side List.js sorting. */
(() => {
  /**
   * Return sortable table containers at or below an updated DOM node.
   *
   * @param {Element | Document} root - Full document or an HTMX swap target.
   * @returns {Element[]} Containers that have not necessarily been enhanced.
   */
  function sortableContainers(root) {
    const containers = Array.from(
      root.querySelectorAll("[data-sortable-table]"),
    );
    if (root instanceof Element && root.matches("[data-sortable-table]")) {
      containers.unshift(root);
    }
    return containers;
  }

  /**
   * Reflect List.js sort state through the table's accessible header state.
   *
   * @param {Element} container - One sortable table container.
   * @param {HTMLButtonElement} activeButton - Activated sort control.
   * @returns {void}
   */
  function updateAccessibleSortState(container, activeButton) {
    for (const button of container.querySelectorAll(".table-sort")) {
      const header = button.closest("th");
      if (!header) {
        continue;
      }
      let direction = "none";
      if (button === activeButton) {
        direction = button.classList.contains("desc")
          ? "descending"
          : "ascending";
      }
      header.setAttribute("aria-sort", direction);
    }
  }

  /**
   * Initialize one table without changing its server-defined initial order.
   *
   * Every sortable cell carries a canonical `data-sort-value`, allowing the
   * visible value to stay localized and formatted for financial reading.
   *
   * @param {Element} container - One sortable table container.
   * @returns {void}
   */
  function initializeSortableTable(container) {
    if (container.dataset.sortableTableInitialized === "true") {
      return;
    }

    const buttons = Array.from(container.querySelectorAll(".table-sort"));
    if (!buttons.length || typeof window.List !== "function") {
      return;
    }

    const valueNames = buttons.map((button) => ({
      attr: "data-sort-value",
      name: button.dataset.sort,
    }));
    new window.List(container, {
      listClass: "table-tbody",
      sortClass: "table-sort",
      valueNames,
    });
    container.dataset.sortableTableInitialized = "true";

    for (const button of buttons) {
      button.closest("th")?.setAttribute("aria-sort", "none");
      button.addEventListener("click", () => {
        queueMicrotask(() => updateAccessibleSortState(container, button));
      });
    }
  }

  /** Initialize Tabler tooltips contained in newly rendered markup. */
  function initializeTooltips(root) {
    const tooltipFactory = window.tabler?.Tooltip;
    if (!tooltipFactory) {
      return;
    }
    for (const trigger of root.querySelectorAll('[data-bs-toggle="tooltip"]')) {
      tooltipFactory.getOrCreateInstance(trigger);
    }
  }

  /** Enhance sortable tables and their related compact disclosures. */
  function initializeTableControls(root = document) {
    for (const container of sortableContainers(root)) {
      initializeSortableTable(container);
    }
    initializeTooltips(root);
  }

  initializeTableControls();
  document.addEventListener("htmx:afterSettle", (event) => {
    if (event.target instanceof Element) {
      initializeTableControls(event.target);
    }
  });
})();
