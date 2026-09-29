import { ref } from "vue";

import { type BillingWindowOut, getBillingWindow } from "@shared/api/billing";

const STORAGE_KEY = "strumok:billing-window";

const window_ = ref<BillingWindowOut | null>(readStored());
const isLoading = ref(false);

function readStored(): BillingWindowOut | null {
  try {
    const raw = globalThis.localStorage?.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as BillingWindowOut) : null;
  } catch {
    return null;
  }
}

function writeStored(value: BillingWindowOut): void {
  try {
    globalThis.localStorage?.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Best-effort cache only; a full storage quota or a private-browsing
    // block must not stop the window from being usable in-memory.
  }
}

/**
 * The Kyiv-computed submit window from GET /billing/window, so deadline
 * status doesn't depend on the resident's device clock or timezone (#141). The
 * last successful response is cached in localStorage so the countdown still
 * renders correctly if a later load happens offline.
 */
export function useBillingWindow() {
  async function load(): Promise<void> {
    isLoading.value = true;
    try {
      window_.value = await getBillingWindow();
      writeStored(window_.value);
    } catch {
      // Keep whatever we already have (fresh fetch or last cached value).
    } finally {
      isLoading.value = false;
    }
  }

  return { window: window_, isLoading, load };
}
