(() => {
  let requestInFlight = false;

  const replaceDocument = (html) => {
    document.open();
    document.write(html);
    document.close();
  };

  const showBusy = (message) => {
    requestInFlight = true;
    document.querySelectorAll("button, input").forEach((control) => {
      control.disabled = true;
    });
    const overlay = document.createElement("div");
    overlay.className = "client-loading-overlay";
    overlay.setAttribute("role", "status");
    overlay.setAttribute("aria-live", "polite");
    overlay.innerHTML = `<span class="workflow-loader" aria-hidden="true"><span></span></span><strong>${message}</strong>`;
    document.body.appendChild(overlay);
  };

  const post = async (path, payload = {}) => {
    if (requestInFlight) return;
    showBusy(path === "/workflow/confirm" ? "מסנכרנים בבטחה…" : "בודקים את הקובץ…");
    try {
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      replaceDocument(await response.text());
    } catch (_error) {
      requestInFlight = false;
      document.querySelector(".client-loading-overlay")?.remove();
      document.querySelectorAll("button, input").forEach((control) => {
        control.disabled = false;
      });
      const panel = document.querySelector(".onboarding-panel");
      if (panel) {
        const error = document.createElement("p");
        error.className = "workflow-error";
        error.setAttribute("role", "alert");
        error.textContent = "לא הצלחנו ליצור קשר עם היישום המקומי. נסו שוב.";
        panel.prepend(error);
      }
    }
  };

  document.querySelector("[data-file-input]")?.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file || requestInFlight) return;
    try {
      const content = await file.text();
      await post("/workflow/preview", { filename: file.name, content });
    } catch (_error) {
      await post("/workflow/preview", { filename: file.name, content: null });
    }
  });

  document.querySelector("[data-confirm-import]")?.addEventListener("click", () => {
    void post("/workflow/confirm");
  });
  document.querySelectorAll("[data-reset-workflow]").forEach((button) => {
    button.addEventListener("click", () => void post("/workflow/reset"));
  });
  document.querySelector("[data-continue-dashboard]")?.addEventListener("click", () => {
    void post("/workflow/dashboard");
  });

  const progressInput = document.querySelector("[data-progress-input]");
  progressInput?.addEventListener("input", () => {
    const output = document.querySelector("[data-progress-output]");
    if (output) output.textContent = `${progressInput.value}%`;
  });
  document.querySelector("[data-assignment-form]")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (requestInFlight) return;
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form).entries());
    values.is_completed = form.elements.is_completed.checked ? "true" : "false";
    const assignmentId = form.dataset.assignmentId;
    await post(`/assignments/${assignmentId}/save`, values);
  });
  document.querySelectorAll("[data-subtask-form]").forEach((form) => form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (requestInFlight) return;
    await post(`/assignments/${form.dataset.assignmentId}/subtasks/save`, Object.fromEntries(new FormData(form).entries()));
  }));
  document.querySelectorAll("[data-subtask-action]").forEach((button) => button.addEventListener("click", () => {
    const assignmentId = document.querySelector("[data-assignment-form]")?.dataset.assignmentId;
    void post(`/assignments/${assignmentId}/subtasks/action`, { action: button.dataset.subtaskAction, subtask_id: button.dataset.id, version: button.dataset.version });
  }));
  const deleteDialog = document.querySelector("[data-delete-dialog]");
  let pendingDelete = null;
  document.querySelectorAll("[data-subtask-delete]").forEach((button) => button.addEventListener("click", () => {
    pendingDelete = button;
    deleteDialog?.showModal();
  }));
  document.querySelector("[data-delete-cancel]")?.addEventListener("click", () => deleteDialog?.close());
  document.querySelector("[data-delete-confirm]")?.addEventListener("click", () => {
    if (!pendingDelete) return;
    const assignmentId = document.querySelector("[data-assignment-form]")?.dataset.assignmentId;
    void post(`/assignments/${assignmentId}/subtasks/action`, { action: "delete", confirmed: "true", subtask_id: pendingDelete.dataset.id, version: pendingDelete.dataset.version });
  });

  const menuButton = document.querySelector("[data-menu-toggle]");
  const sidebar = document.querySelector(".sidebar");
  const dialog = document.querySelector("[data-dialog]");
  menuButton?.addEventListener("click", () => {
    const isOpen = sidebar?.classList.toggle("is-open") ?? false;
    menuButton.setAttribute("aria-expanded", String(isOpen));
  });
  document.querySelectorAll("[data-dialog-open]").forEach((opener) => {
    opener.addEventListener("click", () => dialog?.showModal());
  });
  dialog?.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
})();
