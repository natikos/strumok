import type { VueWrapper } from "@vue/test-utils";

type AnyWrapper = Pick<VueWrapper, "attributes" | "find" | "findAllComponents">;

const SKELETON = { name: "Skeleton" };

function isBusy(wrapper: AnyWrapper): boolean {
  return wrapper.attributes("aria-busy") === "true" || wrapper.find('[aria-busy="true"]').exists();
}

/** The component is in its loading state: an aria-busy region holding skeletons. */
export function expectLoading(wrapper: AnyWrapper): void {
  if (!isBusy(wrapper)) throw new Error("expected an aria-busy=true region while loading");
  if (wrapper.findAllComponents(SKELETON).length === 0) {
    throw new Error("expected at least one Skeleton while loading");
  }
}

/** The loading state is gone: no aria-busy region and no skeletons. */
export function expectLoaded(wrapper: AnyWrapper): void {
  if (isBusy(wrapper)) throw new Error("expected no aria-busy=true region once loaded");
  if (wrapper.findAllComponents(SKELETON).length > 0) {
    throw new Error("expected no Skeleton once loaded");
  }
}

/** A promise the test resolves by hand, to hold a component in its loading state. */
export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}
