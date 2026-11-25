import { flushPromises, mount } from "@vue/test-utils";
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { appPlugins, tUa } from "@/shared/testing/mount";
import type { Component } from "vue";

const api = vi.hoisted(() => ({
  getStatementOutcome: vi.fn(),
  listAdminHouseholds: vi.fn(),
  listStatementFiles: vi.fn(),
}));

// The suite runs with isolate: false, so mock the API late (see AuditLogPanel.test).
let BankOutcomePanel: Component;

beforeAll(async () => {
  vi.resetModules();
  vi.doMock("@shared/api/admin", () => api);
  BankOutcomePanel = (await import("./BankOutcomePanel.vue")).default;
});

afterAll(() => {
  vi.doUnmock("@shared/api/admin");
  vi.resetModules();
});

function makeFile(overrides: Record<string, unknown> = {}) {
  return {
    id: 7,
    original_filename: "oct.csv",
    uploaded_at: "2026-10-12T09:00:00Z",
    credits_new: 3,
    credits_duplicate: 2,
    covered_through: "2026-10-11",
    ...overrides,
  };
}

function makeHousehold(id: number, name: string) {
  return { id, name, user_id: null, is_active: true, owner: null };
}

function makeCredit(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    operation_date: "2026-10-10",
    amount_uah: "1234.57",
    payer_name: "Іваненко І.",
    purpose: "STR-11 жовтень",
    suggested_household_id: null,
    suggestion_source: null,
    suggestions: [],
    link_candidates: [],
    ...overrides,
  };
}

function makeOutcome(overrides: Record<string, unknown> = {}) {
  return {
    file: makeFile(),
    auto_confirmed: [],
    needs_attention: [],
    unmatched: [],
    handled_count: 0,
    ...overrides,
  };
}

function mountPanel() {
  return mount(BankOutcomePanel, {
    global: { plugins: appPlugins(), stubs: { ErrorState: true, Select: true } },
  });
}

describe("BankOutcomePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.listStatementFiles.mockReset().mockResolvedValue([makeFile()]);
    api.listAdminHouseholds
      .mockReset()
      .mockResolvedValue([makeHousehold(11, "Ділянка 11"), makeHousehold(12, "Ділянка 12")]);
    api.getStatementOutcome.mockReset().mockResolvedValue(makeOutcome());
  });

  it("shows the empty message and no file picker when nothing was imported", async () => {
    api.listStatementFiles.mockResolvedValue([]);
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain(tUa("admin.bank.outcome.empty"));
    expect(wrapper.find("select-stub").exists()).toBe(false);
    expect(api.getStatementOutcome).not.toHaveBeenCalled();
  });

  it("loads the newest file's outcome and lists each group with counts, rows and household names", async () => {
    api.listStatementFiles.mockResolvedValue([
      makeFile({ id: 9, uploaded_at: "2026-11-12T09:00:00Z" }),
      makeFile({ id: 7 }),
      makeFile({ id: 3, uploaded_at: "2026-09-12T09:00:00Z" }),
    ]);
    api.getStatementOutcome.mockResolvedValue(
      makeOutcome({
        auto_confirmed: [
          {
            ...makeCredit({ id: 1, payer_name: "Автоплатник", purpose: "STR-11 авто" }),
            payments: [{ household_id: 11, amount_uah: "1234.57" }],
          },
        ],
        needs_attention: [
          makeCredit({
            id: 2,
            operation_date: "2026-10-09",
            amount_uah: "300.10",
            payer_name: "Увага П.",
            purpose: "STR-11 STR-12",
            suggestions: [
              { household_id: 11, source: "reference" },
              { household_id: 12, source: "reference" },
            ],
          }),
        ],
        unmatched: [
          makeCredit({
            id: 3,
            payer_name: "Невідомий",
            purpose: "за світло",
            suggestions: [{ household_id: 99, source: "name" }],
          }),
          makeCredit({ id: 4, payer_name: "Другий", purpose: "без ознак" }),
        ],
      })
    );
    const wrapper = mountPanel();
    await flushPromises();

    expect(api.getStatementOutcome).toHaveBeenCalledExactlyOnceWith(9);
    const text = wrapper.text();
    expect(text).toContain(`${tUa("admin.bank.outcome.auto")} (1)`);
    expect(text).toContain(`${tUa("admin.bank.outcome.attention")} (1)`);
    expect(text).toContain(`${tUa("admin.bank.outcome.unmatched")} (2)`);
    expect(text).toContain("2026-10-10");
    expect(text).toContain("2026-10-09");
    expect(text).toMatch(/1\D?234,57/);
    expect(text).toMatch(/300,10/);
    expect(text).toContain("Автоплатник");
    expect(text).toContain("STR-11 авто");
    expect(text).toContain(tUa("admin.bank.outcome.paidFor", { name: "Ділянка 11" }));
    expect(text).toContain(
      tUa("admin.bank.outcome.suggestedFor", { name: "Ділянка 11, Ділянка 12" })
    );
    // A household missing from the list falls back to its id rather than vanishing.
    expect(text).toContain(tUa("admin.bank.outcome.suggestedFor", { name: "99" }));
    // A credit with no suggestion shows no match line.
    expect(
      text.match(new RegExp(tUa("admin.bank.outcome.suggestedFor", { name: "" }).trim(), "g"))
    ).toHaveLength(2);
  });

  it("states how many credits were handled earlier and how many were duplicates", async () => {
    api.listStatementFiles.mockResolvedValue([makeFile({ credits_duplicate: 5 })]);
    api.getStatementOutcome.mockResolvedValue(
      makeOutcome({ file: makeFile({ credits_duplicate: 5 }), handled_count: 4 })
    );
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain(tUa("admin.bank.outcome.handled", { count: 4 }));
    expect(wrapper.text()).toContain(tUa("admin.bank.outcome.duplicates", { count: 5 }));
  });

  it.each([
    ["needs attention", { needs_attention: [makeCredit({ id: 2 })] }, true],
    ["is unmatched", { unmatched: [makeCredit({ id: 3 })] }, true],
    [
      "was only auto-confirmed",
      { auto_confirmed: [{ ...makeCredit({ id: 1 }), payments: [] }] },
      false,
    ],
  ])("act hint is shown only when a row %s", async (_name, overrides, expected) => {
    api.getStatementOutcome.mockResolvedValue(makeOutcome(overrides));
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text().includes(tUa("admin.bank.outcome.actHint"))).toBe(expected);
  });

  it("tells the admin there were no new credits when the file had none and nothing was handled earlier", async () => {
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).toContain(tUa("admin.bank.outcome.noCredits"));
  });

  it("does not claim 'no credits' when earlier-handled credits exist", async () => {
    api.getStatementOutcome.mockResolvedValue(makeOutcome({ handled_count: 2 }));
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.text()).not.toContain(tUa("admin.bank.outcome.noCredits"));
  });

  it("shows the error state when loading the files fails", async () => {
    api.listStatementFiles.mockRejectedValue(new Error("boom"));
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.findComponent({ name: "ErrorState" }).exists()).toBe(true);
    expect(wrapper.text()).not.toContain(tUa("admin.bank.outcome.empty"));
  });

  it("shows the error state when loading the outcome fails", async () => {
    api.getStatementOutcome.mockRejectedValue(new Error("boom"));
    const wrapper = mountPanel();
    await flushPromises();

    expect(wrapper.findComponent({ name: "ErrorState" }).exists()).toBe(true);
  });
});
