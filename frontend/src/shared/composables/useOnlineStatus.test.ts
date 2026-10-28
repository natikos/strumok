import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it } from "vitest";
import { defineComponent, h } from "vue";

import { useOnlineStatus } from "./useOnlineStatus";

function setNavigatorOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { configurable: true, value });
}

describe("useOnlineStatus", () => {
  afterEach(() => setNavigatorOnline(true));

  it("follows offline then online events", () => {
    setNavigatorOnline(false);
    let status!: ReturnType<typeof useOnlineStatus>;
    const wrapper = mount(
      defineComponent({
        setup() {
          status = useOnlineStatus();
          return () => h("div");
        },
      })
    );

    expect(status.isOnline.value).toBe(false);
    window.dispatchEvent(new Event("online"));
    expect(status.isOnline.value).toBe(true);
    window.dispatchEvent(new Event("offline"));
    expect(status.isOnline.value).toBe(false);
    wrapper.unmount();
  });
});
