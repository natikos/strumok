import { computed, ref } from "vue";

import { isIosNotInstalled } from "@/features/push-notifications/web-push";

// Chrome-family browsers fire `beforeinstallprompt` once, early, and expect the
// app to keep the event until the resident asks to install.
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISSED_KEY = "strumok:install-prompt-dismissed";

const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null);
const isDismissed = ref(readDismissed());

function readDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) !== null;
  } catch {
    return false;
  }
}

/** Starts listening for the install events; call once at boot so none is missed. */
export function captureInstallPrompt(): void {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferredPrompt.value = event as BeforeInstallPromptEvent;
  });
  window.addEventListener("appinstalled", () => {
    deferredPrompt.value = null;
  });
}

export function useInstallPrompt() {
  const showIosSteps = computed(() => !isDismissed.value && isIosNotInstalled());
  const canInstall = computed(() => !isDismissed.value && deferredPrompt.value !== null);
  const isVisible = computed(() => canInstall.value || showIosSteps.value);

  // Remembered per device: it is a nudge, not something to nag about.
  function dismiss(): void {
    isDismissed.value = true;
    try {
      localStorage.setItem(DISMISSED_KEY, "1");
    } catch {
      // Without storage it only stays hidden until the next load.
    }
  }

  async function install(): Promise<void> {
    const event = deferredPrompt.value;
    if (!event) {
      return;
    }

    deferredPrompt.value = null;
    await event.prompt();
    const { outcome } = await event.userChoice;
    if (outcome === "dismissed") {
      dismiss();
    }
  }

  return { canInstall, showIosSteps, isVisible, install, dismiss };
}
