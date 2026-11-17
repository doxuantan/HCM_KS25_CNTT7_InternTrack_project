let confirmationResolver = null;
let initializePromise = null;

export async function initializeSharedUi() {
  if (initializePromise) {
    return initializePromise;
  }

  initializePromise = (async () => {
    if (!document.querySelector("[data-toast-region]")) {
      const [toastResponse, modalResponse] = await Promise.all([
        fetch("components/toast.html"),
        fetch("components/modal.html"),
      ]);
      if (!toastResponse.ok || !modalResponse.ok) {
        throw new Error("Không thể tải component thông báo và xác nhận.");
      }

      const [toastMarkup, modalMarkup] = await Promise.all([
        toastResponse.text(),
        modalResponse.text(),
      ]);
      document.body.insertAdjacentHTML("beforeend", `${toastMarkup}${modalMarkup}`);
    }

    const dialog = document.querySelector("[data-confirm-dialog]");
    const accept = dialog?.querySelector("[data-confirm-accept]");
    if (!(dialog instanceof HTMLDialogElement) || !(accept instanceof HTMLButtonElement)) {
      throw new Error("Thiếu cấu trúc modal xác nhận dùng chung.");
    }

    accept.addEventListener("click", () => finishConfirmation(true));
    dialog.querySelectorAll("[data-confirm-cancel]").forEach((button) => {
      button.addEventListener("click", () => finishConfirmation(false));
    });
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finishConfirmation(false);
    });
    dialog.addEventListener("click", (event) => {
      if (event.target === dialog) {
        finishConfirmation(false);
      }
    });
  })();

  try {
    await initializePromise;
  } catch (error) {
    initializePromise = null;
    throw error;
  }
}

function finishConfirmation(confirmed) {
  const dialog = document.querySelector("[data-confirm-dialog]");
  const resolver = confirmationResolver;
  confirmationResolver = null;
  if (dialog instanceof HTMLDialogElement && dialog.open) {
    dialog.close();
  }
  resolver?.(confirmed);
}

export function showToast(message, { kind = "success", duration = 4200 } = {}) {
  const region = document.querySelector("[data-toast-region]");
  if (!(region instanceof HTMLElement)) {
    throw new Error("Toast component chưa được khởi tạo.");
  }

  const toast = document.createElement("div");
  toast.className = "toast";
  toast.dataset.kind = kind;
  toast.setAttribute("role", kind === "error" ? "alert" : "status");

  const content = document.createElement("p");
  content.className = "toast-message";
  content.textContent = message;

  const close = document.createElement("button");
  close.className = "toast-close";
  close.type = "button";
  close.setAttribute("aria-label", "Đóng thông báo");
  close.textContent = "×";

  let timeout = 0;
  const dismiss = () => {
    window.clearTimeout(timeout);
    toast.remove();
  };
  close.addEventListener("click", dismiss);
  toast.append(content, close);
  region.append(toast);
  if (duration > 0) {
    timeout = window.setTimeout(dismiss, duration);
  }
}

export function confirmAction({
  title = "Xác nhận thao tác",
  message,
  confirmLabel = "Xác nhận",
  destructive = false,
} = {}) {
  const dialog = document.querySelector("[data-confirm-dialog]");
  const titleElement = dialog?.querySelector("[data-confirm-title]");
  const messageElement = dialog?.querySelector("[data-confirm-message]");
  const accept = dialog?.querySelector("[data-confirm-accept]");
  const cancel = dialog?.querySelector("[data-confirm-cancel]");
  if (
    !(dialog instanceof HTMLDialogElement) ||
    !(titleElement instanceof HTMLElement) ||
    !(messageElement instanceof HTMLElement) ||
    !(accept instanceof HTMLButtonElement) ||
    !(cancel instanceof HTMLButtonElement)
  ) {
    throw new Error("Modal xác nhận chưa được khởi tạo.");
  }
  if (confirmationResolver) {
    throw new Error("Một hộp thoại xác nhận khác đang được mở.");
  }

  titleElement.textContent = title;
  messageElement.textContent = message || "";
  accept.textContent = confirmLabel;
  accept.classList.toggle("button-danger", destructive);
  accept.classList.toggle("button-primary", !destructive);

  return new Promise((resolve) => {
    confirmationResolver = resolve;
    dialog.showModal();
    cancel.focus();
  });
}
