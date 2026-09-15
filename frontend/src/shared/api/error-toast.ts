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
    case 422:
      return "errors.validationError";
    case 429:
      return "errors.tooManyRequests";
    case 500:
      return "errors.serverError";
    default:
      return "errors.requestFailed";
  }
}

// Detail codes callers render inline instead of via a toast — surfacing both
// would be redundant. noHouseholdMembership: AppLayout blocks the whole app
// behind a dedicated "no household yet" screen for it.
const SILENCED_DETAILS = new Set(["noHouseholdMembership"]);

function toErrorMessageKey(body: unknown, fallbackMessageKey: string): string {
  if (!body || typeof body !== "object" || !("detail" in body)) {
    return fallbackMessageKey;
  }

  if (typeof body.detail !== "string") {
    return fallbackMessageKey;
  }

  return `errors.${body.detail}`;
}

export function registerToastPresenter(presenter: ToastPresenter): () => void {
  toastPresenter = presenter;

  return () => {
    if (toastPresenter === presenter) {
      toastPresenter = null;
    }
  };
}

function isSilencedDetail(body: unknown): boolean {
  return (
    !!body &&
    typeof body === "object" &&
    "detail" in body &&
    typeof body.detail === "string" &&
    SILENCED_DETAILS.has(body.detail)
  );
}

export function showApiErrorToast(status: number, body: unknown): void {
  if (!toastPresenter || isSilencedDetail(body)) {
    return;
  }

  const fallbackMessageKey = getStatusMessageKey(status);
  const DEFAULT_TOAST_LIFE_MS = 5000;

  toastPresenter({
    fallbackMessageKey,
    life: DEFAULT_TOAST_LIFE_MS,
    messageKey: toErrorMessageKey(body, fallbackMessageKey),
    severity: "error",
  });
}
