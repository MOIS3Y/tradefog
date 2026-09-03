"use strict";

/**
 * Close a Bootstrap modal after a successful or rejected HTMX mutation.
 *
 * Views dispatch a ``tradefog:close-modal`` event through the ``HX-Trigger``
 * response header with a modal id. Prefers the Bootstrap instance and falls
 * back to the declarative dismiss button, which matches how the logout modal
 * is closed.
 */
(() => {
  /**
   * @param {string} id - Modal element id.
   * @returns {void}
   */
  window.closeAssetModal = (id) => {
    const modal = document.getElementById(id);
    if (!modal) {
      return;
    }
    const instance = window.bootstrap?.Modal?.getInstance(modal);
    if (instance) {
      instance.hide();
      return;
    }
    modal.querySelector('[data-bs-dismiss="modal"]')?.click();
  };

  document.addEventListener("tradefog:close-modal", (event) => {
    window.closeAssetModal(event.detail.id);
  });
})();