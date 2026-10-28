import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";

import PaySheet from "./PaySheet.vue";

const props = {
  amount: "250.50",
  iban: "UA213223130000026007233566001",
  recipient: "Strumok Co-op",
  comment: "Plot 1",
  visible: true,
};

function mountSheet() {
  return mount(PaySheet, {
    props,
    global: {
      plugins: appPlugins(),
      stubs: { Dialog: { template: "<div><slot /></div>" } },
    },
  });
}

describe("PaySheet", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows amount, IBAN, recipient and comment", () => {
    const text = mountSheet().text();

    for (const value of [props.amount, props.iban, props.recipient, props.comment]) {
      expect(text).toContain(value);
    }
  });

  it("copies a field to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const wrapper = mountSheet();

    await wrapper.findAll("button")[1]!.trigger("click");
    await flushPromises();

    expect(writeText).toHaveBeenCalledWith(props.iban);
  });

  it("tells the resident to select the text when copying fails", async () => {
    vi.stubGlobal("navigator", {});
    const wrapper = mountSheet();

    await wrapper.findAll("button")[0]!.trigger("click");
    await flushPromises();

    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
  });
});
