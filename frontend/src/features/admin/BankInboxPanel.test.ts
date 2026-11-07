import { flushPromises, mount } from "@vue/test-utils";
import Button from "primevue/button";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins } from "@/shared/testing/mount";
import type { Component } from "vue";

const api = vi.hoisted(() => ({ checkBankInbox: vi.fn(), listInboxFetches: vi.fn() }));
const { toastAdd } = vi.hoisted(() => ({ toastAdd: vi.fn() }));

vi.mock("primevue/usetoast", () => ({ useToast: () => ({ add: toastAdd }) }));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let BankInboxPanel: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => api);
  BankInboxPanel = (await import("./BankInboxPanel.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

const rejected = {
  id: 2,
  status: "rejected",
  reason: "senderNotAllowed",
  fetched_at: "2026-10-10T09:00:00Z",
};

function mountPanel() {
  return mount(BankInboxPanel, { global: { plugins: appPlugins(), stubs: { ErrorState: true } } });
}

describe("BankInboxPanel", () => {
  beforeEach(() => {
    api.checkBankInbox.mockReset();
    api.listInboxFetches.mockReset().mockResolvedValue([rejected]);
    toastAdd.mockReset();
  });

  it("lists recent fetches with the reason a message was rejected", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain("Rejected");
    expect(wrapper.text()).toContain("Sender isn't on the allowed list");
  });

  it("shows an empty state when nothing was fetched", async () => {
    api.listInboxFetches.mockResolvedValue([]);
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain("No emails looked at yet");
  });

  it("checks the inbox on demand, warns about rejections and reloads the list", async () => {
    api.checkBankInbox.mockResolvedValue({ received: 1, imported: 0, rejected: 1, credits_new: 0 });
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.findComponent(Button).trigger("click");
    await flushPromises();

    expect(api.checkBankInbox).toHaveBeenCalledOnce();
    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: "warn" }));
    expect(api.listInboxFetches).toHaveBeenCalledTimes(2);
    expect(wrapper.emitted("imported")).toBeUndefined();
  });

  it("tells the queue to reload when a check imported rows", async () => {
    api.checkBankInbox.mockResolvedValue({ received: 1, imported: 1, rejected: 0, credits_new: 3 });
    const wrapper = mountPanel();
    await flushPromises();

    await wrapper.findComponent(Button).trigger("click");
    await flushPromises();

    expect(wrapper.emitted("imported")).toHaveLength(1);
  });
});
