import { onBeforeUnmount, readonly, ref } from "vue";

/**
 * Reactive `matchMedia`.
 *
 * Layout belongs in SCSS via `layout.respond-to`; this is for the cases CSS
 * can't reach — chart.js tick formatting, for one, where the label text itself
 * has to change rather than its styling.
 */
export function useMediaQuery(query: string) {
  const matches = ref(false);

  if (typeof window !== "undefined" && typeof window.matchMedia === "function") {
    const media = window.matchMedia(query);
    matches.value = media.matches;

    const update = (event: MediaQueryListEvent) => {
      matches.value = event.matches;
    };

    media.addEventListener("change", update);
    onBeforeUnmount(() => media.removeEventListener("change", update));
  }

  return readonly(matches);
}

/** The `lg` breakpoint from `_layout.scss` — the desktop layout's floor. */
export function useIsDesktop() {
  return useMediaQuery("(min-width: 60rem)");
}
