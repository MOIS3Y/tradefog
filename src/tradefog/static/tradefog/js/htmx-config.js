"use strict";

/**
 * Configure application-wide HTMX behavior.
 *
 * HTMX 2.x defaults to discarding 4xx/5xx response bodies. Validation
 * errors and blocked mutations return those statuses with a fragment the
 * UI needs to show, so error responses are swapped while remaining marked
 * as errors. Loaded with ``defer`` after ``htmx.min.js`` so the global is
 * available at execution time.
 */
(() => {
  if (!window.htmx) {
    return;
  }
  window.htmx.config.responseHandling = [
    { code: "204", swap: false },
    { code: "[23]..", swap: true },
    { code: "[45]..", swap: true, error: true },
  ];
})();