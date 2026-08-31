"use strict";

/** Enhance the inline description and private attachment gallery. */
(() => {
  let activeUploads = 0;

  /** Enhance the ordinary description textarea with EasyMDE on demand. */
  function initializeDescriptionEditor(form) {
    if (form.dataset.editorReady === "true") {
      return form.tradefogEditor;
    }
    const source = form.querySelector(".tf-description-source");
    const Editor = window.EasyMDE;
    const sanitizer = window.DOMPurify;
    if (!source || typeof Editor !== "function" || !sanitizer) {
      return null;
    }
    const button = (name, action, text, title) => ({
      name,
      action,
      text,
      title,
      className: `tf-mde-button tf-mde-${name}`,
    });
    const editor = new Editor({
      element: source,
      autoDownloadFontAwesome: false,
      forceSync: true,
      inputStyle: "textarea",
      indentWithTabs: false,
      minHeight: "14rem",
      nativeSpellcheck: true,
      placeholder: form.dataset.editorPlaceholder,
      renderingConfig: {
        sanitizerFunction: (renderedHtml) =>
          sanitizer.sanitize(renderedHtml, {
            FORBID_ATTR: ["style"],
            FORBID_TAGS: ["img", "style"],
            USE_PROFILES: { html: true },
          }),
      },
      spellChecker: false,
      status: false,
      shortcuts: {
        drawImage: null,
        toggleFullScreen: null,
        toggleSideBySide: null,
      },
      toolbar: [
        button("bold", Editor.toggleBold, "B", form.dataset.editorBold),
        button("italic", Editor.toggleItalic, "I", form.dataset.editorItalic),
        button(
          "heading",
          Editor.toggleHeadingSmaller,
          "H",
          form.dataset.editorHeading,
        ),
        "|",
        button("quote", Editor.toggleBlockquote, "“", form.dataset.editorQuote),
        button(
          "unordered-list",
          Editor.toggleUnorderedList,
          "•",
          form.dataset.editorUnorderedList,
        ),
        button(
          "ordered-list",
          Editor.toggleOrderedList,
          "1.",
          form.dataset.editorOrderedList,
        ),
        "|",
        button("link", Editor.drawLink, "⌁", form.dataset.editorLink),
        button(
          "horizontal-rule",
          Editor.drawHorizontalRule,
          "—",
          form.dataset.editorHorizontalRule,
        ),
        "|",
        {
          ...button(
            "preview",
            Editor.togglePreview,
            "◫",
            form.dataset.editorPreview,
          ),
          noDisable: true,
        },
        button("undo", Editor.undo, "↶", form.dataset.editorUndo),
        button("redo", Editor.redo, "↷", form.dataset.editorRedo),
      ],
    });
    for (const toolbarButton of form.querySelectorAll(".editor-toolbar button")) {
      toolbarButton.setAttribute("aria-label", toolbarButton.title);
    }
    form.tradefogEditor = editor;
    form.dataset.editorReady = "true";
    return editor;
  }

  /** Toggle the description between its rendered and inline edit modes. */
  function initializeDescription() {
    const form = document.querySelector("[data-description-form]");
    if (!form) {
      return;
    }
    const rendered = document.querySelector("[data-description-view]");
    const edit = document.querySelector("[data-description-edit]");
    const cancel = form.querySelector("[data-description-cancel]");
    const save = form.querySelector("[data-description-save]");
    const status = form.querySelector("[data-description-save-status]");
    const source = form.querySelector(".tf-description-source");
    if (!rendered || !edit || !cancel || !save || !status || !source) {
      return;
    }
    let savedMarkdown = source.value;

    const showStatus = (message, isError = false) => {
      status.textContent = message;
      status.classList.toggle("text-danger", isError);
      status.classList.toggle("text-secondary", !isError);
    };

    const focusEditor = () => {
      const editor = initializeDescriptionEditor(form);
      requestAnimationFrame(() => {
        editor?.codemirror.refresh();
        editor?.codemirror.focus();
      });
      return editor;
    };

    if (!form.hidden) {
      initializeDescriptionEditor(form);
    }
    edit?.addEventListener("click", () => {
      form.hidden = false;
      rendered.hidden = true;
      edit.hidden = true;
      showStatus("");
      focusEditor();
    });
    cancel.addEventListener("click", () => {
      const editor = initializeDescriptionEditor(form);
      if (editor?.isPreviewActive()) {
        editor.togglePreview();
      }
      editor?.value(savedMarkdown);
      source.value = savedMarkdown;
      form.hidden = true;
      rendered.hidden = false;
      edit.hidden = false;
      showStatus("");
    });
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const editor = initializeDescriptionEditor(form);
      source.value = editor?.value() ?? source.value;
      save.disabled = true;
      save.setAttribute("aria-busy", "true");
      showStatus(form.dataset.descriptionSaving);
      try {
        const response = await fetch(form.action, {
          method: "POST",
          credentials: "same-origin",
          headers: { "X-Requested-With": "XMLHttpRequest" },
          body: new FormData(form),
        });
        if (
          response.status !== 200 ||
          response.headers.get("X-Tradefog-Description") !== "rendered"
        ) {
          throw new Error(`Unexpected save response: ${response.status}`);
        }
        const renderedHtml = await response.text();
        const isEmpty =
          response.headers.get("X-Tradefog-Description-Empty") === "true";
        savedMarkdown = source.value;
        showStatus(form.dataset.descriptionSaved);
        if (isEmpty) {
          rendered.replaceChildren();
          rendered.hidden = true;
          edit.hidden = true;
          cancel.hidden = true;
        } else {
          if (editor?.isPreviewActive()) {
            editor.togglePreview();
          }
          rendered.innerHTML = renderedHtml;
          form.hidden = true;
          rendered.hidden = false;
          edit.hidden = false;
          cancel.hidden = false;
        }
      } catch (_requestError) {
        showStatus(form.dataset.descriptionSaveError, true);
      } finally {
        save.disabled = false;
        save.removeAttribute("aria-busy");
      }
    });
  }

  /** Build an immediate local preview while one file is uploading. */
  function uploadPlaceholder(file, retryLabel, removeLabel) {
    const item = document.createElement("article");
    item.className = "tf-attachment-item tf-attachment-upload is-uploading";
    item.dataset.attachmentItem = "";

    const preview = document.createElement("div");
    preview.className = "tf-attachment-preview";
    let objectUrl = null;
    if (file.type.startsWith("image/")) {
      objectUrl = URL.createObjectURL(file);
      const image = document.createElement("img");
      image.src = objectUrl;
      image.alt = "";
      preview.append(image);
    } else {
      preview.classList.add("tf-attachment-document");
      const label = document.createElement("span");
      label.textContent = "PDF";
      preview.append(label);
    }

    const overlay = document.createElement("div");
    overlay.className = "tf-upload-overlay";
    const progress = document.createElement("div");
    progress.className = "progress progress-sm w-75";
    const bar = document.createElement("div");
    bar.className = "progress-bar";
    bar.setAttribute("role", "progressbar");
    bar.setAttribute("aria-valuemin", "0");
    bar.setAttribute("aria-valuemax", "100");
    bar.setAttribute("aria-valuenow", "0");
    progress.append(bar);
    overlay.append(progress);
    preview.append(overlay);

    const meta = document.createElement("div");
    meta.className = "tf-attachment-meta d-block";
    const name = document.createElement("div");
    name.className = "text-truncate";
    name.textContent = file.name;
    const error = document.createElement("div");
    error.className = "mt-2";
    const retry = document.createElement("button");
    retry.className = "btn btn-sm";
    retry.type = "button";
    retry.textContent = retryLabel;
    retry.hidden = true;
    const remove = document.createElement("button");
    remove.className = "btn btn-sm btn-outline-danger";
    remove.type = "button";
    remove.textContent = removeLabel;
    remove.hidden = true;
    const actions = document.createElement("div");
    actions.className = "tf-upload-actions mt-2";
    actions.append(retry, remove);
    meta.append(name, error, actions);
    item.append(preview, meta);
    return { item, bar, error, retry, remove, objectUrl };
  }

  /** Display a local or server-returned error on one upload item. */
  function showUploadError(task, html, isHtml = false) {
    task.item.classList.remove("is-uploading");
    task.item.classList.add("has-error");
    task.retry.hidden = false;
    task.remove.hidden = false;
    if (isHtml) {
      task.error.innerHTML = html;
    } else {
      task.error.textContent = html;
    }
  }

  /** Replace the temporary preview after the protected image is ready. */
  function revealAttachment(task, html) {
    const template = document.createElement("template");
    template.innerHTML = html.trim();
    const attachment = template.content.firstElementChild;
    if (!attachment) {
      showUploadError(task, task.form.dataset.networkError);
      return;
    }
    attachment.classList.add("is-revealing");
    task.item.before(attachment);
    const image = attachment.querySelector("img");
    const finish = () => {
      attachment.classList.remove("is-revealing");
      task.item.remove();
      if (task.objectUrl) {
        URL.revokeObjectURL(task.objectUrl);
      }
      if (window.refreshFsLightbox) {
        window.refreshFsLightbox();
      }
    };
    if (image && !image.complete) {
      image.addEventListener("load", finish, { once: true });
      image.addEventListener("error", finish, { once: true });
    } else {
      finish();
    }
  }

  /** Upload one file with real per-file progress reporting. */
  function upload(task) {
    task.retry.hidden = true;
    task.remove.hidden = true;
    task.error.replaceChildren();
    task.bar.style.width = "0";
    task.bar.setAttribute("aria-valuenow", "0");
    task.item.classList.add("is-uploading");
    task.item.classList.remove("has-error");
    const data = new FormData();
    data.append("file", task.file);
    const request = new XMLHttpRequest();
    request.open("POST", task.form.action);
    request.setRequestHeader(
      "X-CSRFToken",
      task.form.querySelector("[name=csrfmiddlewaretoken]").value,
    );
    activeUploads += 1;
    request.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) {
        return;
      }
      const percent = Math.round((event.loaded / event.total) * 100);
      task.bar.style.width = `${percent}%`;
      task.bar.setAttribute("aria-valuenow", String(percent));
    });
    request.addEventListener("loadend", () => {
      activeUploads = Math.max(0, activeUploads - 1);
    });
    request.addEventListener("load", () => {
      if (request.status === 201) {
        revealAttachment(task, request.responseText);
      } else {
        showUploadError(task, request.responseText, true);
      }
    });
    request.addEventListener("error", () => {
      showUploadError(task, task.form.dataset.networkError);
    });
    request.send(data);
  }

  /** Restore the empty prompt when no saved or local cards remain. */
  function restoreAttachmentEmptyState(grid, emptyTemplate) {
    if (
      !grid.querySelector("[data-attachment-item]") &&
      emptyTemplate instanceof HTMLTemplateElement
    ) {
      grid.append(emptyTemplate.content.cloneNode(true));
    }
  }

  /** Initialize independent asynchronous uploads for the attachment strip. */
  function initializeAttachments() {
    const form = document.querySelector("[data-attachment-upload]");
    const input = form?.querySelector("[data-attachment-input]");
    const grid = document.querySelector("[data-attachment-grid]");
    const emptyTemplate = document.querySelector(
      "[data-attachment-empty-template]",
    );
    if (!form || !input || !grid) {
      return;
    }
    input.addEventListener("change", () => {
      const maxSize = Number(form.dataset.maxSize || 0);
      for (const file of input.files) {
        grid.querySelector("[data-attachment-empty]")?.remove();
        const placeholder = uploadPlaceholder(
          file,
          form.dataset.retryLabel,
          form.dataset.removeLabel,
        );
        const task = { ...placeholder, file, form };
        grid.append(task.item);
        task.retry.addEventListener("click", () => upload(task));
        task.remove.addEventListener("click", () => {
          task.item.classList.add("is-removing");
          setTimeout(() => {
            task.item.remove();
            if (task.objectUrl) {
              URL.revokeObjectURL(task.objectUrl);
            }
            restoreAttachmentEmptyState(grid, emptyTemplate);
          }, 180);
        });
        if (maxSize > 0 && file.size > maxSize) {
          showUploadError(task, form.dataset.sizeError);
        } else {
          upload(task);
        }
      }
      input.value = "";
    });
  }

  /** Confirm and remove one attachment without reloading the trade. */
  function initializeAttachmentDeletion() {
    const modal = document.querySelector("#attachment-delete-modal");
    const form = modal?.querySelector("[data-attachment-delete-form]");
    const name = modal?.querySelector("[data-attachment-delete-name]");
    const error = modal?.querySelector("[data-attachment-delete-error]");
    const confirm = modal?.querySelector("[data-attachment-delete-confirm]");
    const grid = document.querySelector("[data-attachment-grid]");
    const emptyTemplate = document.querySelector(
      "[data-attachment-empty-template]",
    );
    if (!modal || !form || !name || !error || !confirm || !grid) {
      return;
    }

    let targetSelector = "";
    modal.addEventListener("show.bs.modal", (event) => {
      const trigger = event.relatedTarget;
      if (!(trigger instanceof HTMLElement)) {
        return;
      }
      form.action = trigger.dataset.deleteUrl || "";
      targetSelector = trigger.dataset.attachmentTarget || "";
      name.textContent = trigger.dataset.attachmentName || "";
      error.textContent = "";
      error.classList.add("d-none");
      confirm.disabled = false;
      confirm.removeAttribute("aria-busy");
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (!form.action || !targetSelector) {
        return;
      }
      confirm.disabled = true;
      confirm.setAttribute("aria-busy", "true");
      error.classList.add("d-none");
      try {
        const response = await fetch(form.action, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": form.querySelector(
              "[name=csrfmiddlewaretoken]",
            ).value,
            "X-Requested-With": "XMLHttpRequest",
          },
        });
        if (response.status !== 204) {
          throw new Error(`Unexpected delete response: ${response.status}`);
        }
        const item = document.querySelector(targetSelector);
        item?.classList.add("is-removing");
        modal.addEventListener(
          "hidden.bs.modal",
          () => {
            item?.remove();
            restoreAttachmentEmptyState(grid, emptyTemplate);
          },
          { once: true },
        );
        modal.querySelector("[data-bs-dismiss=modal]")?.click();
      } catch (_requestError) {
        error.textContent = form.dataset.deleteError;
        error.classList.remove("d-none");
        confirm.disabled = false;
        confirm.removeAttribute("aria-busy");
      }
    });
  }

  window.addEventListener("beforeunload", (event) => {
    if (activeUploads === 0) {
      return;
    }
    event.preventDefault();
    event.returnValue = "";
  });
  document.addEventListener("DOMContentLoaded", () => {
    initializeDescription();
    initializeAttachments();
    initializeAttachmentDeletion();
  });
})();
