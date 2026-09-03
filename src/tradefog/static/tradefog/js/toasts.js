"use strict";

/**
 * Reusable dismissible toast notifications.
 *
 * Views dispatch a ``tradefog:toast`` event through the ``HX-Trigger``
 * response header; this module renders it in the global ``#toast-region``.
 * The toast markup carries the ``show`` class, so it is visible without
 * depending on the Bootstrap Toast JS API. Auto-hide and the dismiss button
 * are handled here.
 */
(() => {
  /** Status color per toast kind, aligned with the Tabler palette. */
  const statusColors = {
    success: "var(--tblr-success)",
    danger: "var(--tblr-danger)",
    info: "var(--tblr-info)",
    warning: "var(--tblr-warning)",
  };

  /** Capitalize the first letter of a kind to read its translated title. */
  const capitalize = (value) =>
    value[0].toUpperCase() + value.slice(1);

  /**
   * Format elapsed seconds into a compact localized counter.
   *
   * @param {HTMLTemplateElement} template - Toast template with unit tokens.
   * @param {number} seconds - Elapsed seconds since the toast appeared.
   * @returns {string} Localized elapsed time label.
   */
  const formatElapsed = (template, seconds) => {
    if (seconds < 1) {
      return template.dataset.timeJustNow;
    }
    if (seconds < 60) {
      return `${seconds}${template.dataset.timeSeconds}`;
    }
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) {
      return `${minutes}${template.dataset.timeMinutes}`;
    }
    return `${Math.floor(minutes / 60)}${template.dataset.timeHours}`;
  };

  /**
   * Show a toast notification cloned from the shared template.
   *
   * @param {string} message - Localized message text.
   * @param {"success" | "danger" | "info" | "warning"} [kind] - Status kind.
   * @returns {void}
   */
  window.showToast = (message, kind = "success") => {
    const container = document.getElementById("toast-region");
    const template = document.getElementById("toast-template");
    if (!container || !template || !(template instanceof HTMLTemplateElement)) {
      return;
    }

    const toast = template.content.firstElementChild.cloneNode(true);
    const body = toast.querySelector("[data-toast-body]");
    const title = toast.querySelector("[data-toast-title]");
    const dot = toast.querySelector("[data-toast-dot]");
    const time = toast.querySelector("[data-toast-time]");
    if (body) {
      body.textContent = message;
    }
    if (title) {
      title.textContent = template.dataset[`title${capitalize(kind)}`] || "";
    }
    if (dot) {
      dot.style.setProperty(
        "--tblr-status-color",
        statusColors[kind] || statusColors.info,
      );
    }
    container.appendChild(toast);

    const startedAt = Date.now();
    const updateTime = () => {
      if (time) {
        const elapsed = Math.floor((Date.now() - startedAt) / 1000);
        time.textContent = formatElapsed(template, elapsed);
      }
    };
    updateTime();
    const timer = window.setInterval(updateTime, 1000);

    const hide = () => {
      window.clearInterval(timer);
      toast.classList.remove("show");
      toast.style.display = "none";
      toast.remove();
    };
    toast.querySelector('[data-bs-dismiss="toast"]')?.addEventListener(
      "click",
      hide,
    );
    window.setTimeout(hide, 4000);
  };

  document.addEventListener("tradefog:toast", (event) => {
    window.showToast(event.detail.message, event.detail.kind);
  });
})();