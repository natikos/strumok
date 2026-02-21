interface ToastPayload {
  fallbackMessageKey: string;
  life?: number;
  messageKey: string;
  severity: "error" | "info" | "success" | "warn";
}

type ToastPresenter = (payload: ToastPayload) => void;

let toastPresenter: ToastPresenter | null = null;

function getStatusMessageKey(status: number): string {
  switch (status) {
    case 401:
      return "errors.unauthorized";
    case 429:
      return "errors.tooManyRequests";
    case 500:
      return "errors.serverError";
    default:
      return "errors.requestFailed";
  }
}

export function registerToastPresenter(presenter: ToastPresenter): () => void {
  toastPresenter = presenter;

  return () => {
    if (toastPresenter === presenter) {
      toastPresenter = null;
    }
  };
}

export function showApiErrorToast(status: number, body: Record<"detail", string>): void {
  if (!toastPresenter) {
    return;
  }

  const fallbackMessageKey = getStatusMessageKey(status);
  const DEFAULT_TOAST_LIFE_MS = 5000;

  toastPresenter({
    fallbackMessageKey,
    life: DEFAULT_TOAST_LIFE_MS,
    messageKey: body.detail ? `errors.${body.detail}` : fallbackMessageKey,
    severity: "error",
  });
}
