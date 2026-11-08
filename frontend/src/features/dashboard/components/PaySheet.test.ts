import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import { bankPaymentLink } from "@shared/utils/bankLink";

import PaySheet from "./PaySheet.vue";

const props = {
  amount: "250.50",
  iban: "UA213223130000026007233566001",
  recipient: "Strumok Co-op",
  comment: "Plot 1",
  visible: true,
};

function mountSheet(extra: { edrpou?: string | null } = {}) {
  return mount(PaySheet, {
    props: { ...props, ...extra },
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

  it("shows and copies the EDRPOU when set", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const wrapper = mountSheet({ edrpou: "12345678" });

    expect(wrapper.text()).toContain("12345678");
    const index = wrapper.findAll("dt").findIndex((dt) => dt.text() === "EDRPOU");
    await wrapper.findAll(".pay-sheet__row button")[index]!.trigger("click");
    await flushPromises();

    expect(writeText).toHaveBeenCalledWith("12345678");
  });

  it("omits the EDRPOU row when it is not set", () => {
    expect(mountSheet({ edrpou: null }).findAll("dt").map((dt) => dt.text())).not.toContain(
      "EDRPOU"
    );
  });

  it("copies a field to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const wrapper = mountSheet();

    await wrapper.findAll(".pay-sheet__row button")[1]!.trigger("click");
    await flushPromises();

    expect(writeText).toHaveBeenCalledWith(props.iban);
  });

  it("tells the resident to select the text when copying fails", async () => {
    vi.stubGlobal("navigator", {});
    const wrapper = mountSheet();

    await wrapper.findAll(".pay-sheet__row button")[0]!.trigger("click");
    await flushPromises();

    expect(wrapper.find('[role="alert"]').exists()).toBe(true);
  });
});

describe("PaySheet bank link", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("links to the prefilled bank payment", () => {
    const href = mountSheet().find("a.pay-sheet__bank").attributes("href");

    expect(href).toBe(
      bankPaymentLink({
        recipient: props.recipient,
        iban: props.iban,
        amount: props.amount,
        purpose: props.comment,
      })
    );
  });

  it("copies the bank link", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    const wrapper = mountSheet();

    await wrapper.find(".pay-sheet__link").trigger("click");
    await flushPromises();

    expect(writeText).toHaveBeenCalledWith(expect.stringContaining("https://bank.gov.ua/qr/"));
  });
});
