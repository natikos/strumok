import { flushPromises } from "@vue/test-utils";
import Button from "primevue/button";
import InputMask from "primevue/inputmask";
import InputNumber from "primevue/inputnumber";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mountWithPlugins } from "@/shared/testing/mount";
import type * as ElectricityRatesApi from "@shared/api/electricity-rates";
import type { ElectricityRateOut } from "@shared/api/electricity-rates";

import ElectricityRatesSettings from "./ElectricityRatesSettings.vue";

const { listElectricityRates, createElectricityRate } = vi.hoisted(() => ({
  createElectricityRate: vi.fn(),
  listElectricityRates: vi.fn(),
}));

vi.mock("@shared/api/electricity-rates", async () => {
  const actual = await vi.importActual<typeof ElectricityRatesApi>("@shared/api/electricity-rates");
  return {
    ...actual,
    createElectricityRate,
    listElectricityRates,
  };
});

vi.mock("primevue/usetoast", () => ({
  useToast: () => ({ add: vi.fn() }),
}));

function makeRate(overrides: Partial<ElectricityRateOut> = {}): ElectricityRateOut {
  return {
    day_rate_uah: "4.5000",
    effective_from: "2026-01",
    id: 1,
    night_rate_uah: "2.5000",
    ...overrides,
  };
}

async function mountSettings() {
  const wrapper = mountWithPlugins(ElectricityRatesSettings, {
    global: { components: { Button, InputMask, InputNumber } },
  });
  await flushPromises();
  return wrapper;
}

describe("ElectricityRatesSettings", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 6, 15)); // "today" is July 15, 2026
    listElectricityRates.mockReset();
    createElectricityRate.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("warns about both the current and next submission periods when no rate covers them", async () => {
    listElectricityRates.mockResolvedValue([]);

    const wrapper = await mountSettings();

    const warnings = wrapper.findAll(".electricity-rates__warning").map((el) => el.text());
    expect(warnings).toHaveLength(2);
    expect(warnings).toContain("No rate covers 2026-06 yet");
    expect(warnings).toContain("No rate covers 2026-07 yet");
  });

  it("stops warning about both periods once a rate effective before them is present", async () => {
    // A rate effective from well before either submission period covers both
    // (effective_from <= period), so both warnings should disappear.
    listElectricityRates.mockResolvedValue([makeRate({ effective_from: "2026-01", id: 1 })]);

    const wrapper = await mountSettings();

    expect(wrapper.findAll(".electricity-rates__warning")).toHaveLength(0);
  });

  it("still warns about the uncovered current period when only the next one is covered", async () => {
    // Rate is effective from next month's submission period (2026-07), so it
    // covers that period but not the still-uncovered current one (2026-06):
    // a coverage rate isn't retroactive.
    listElectricityRates.mockResolvedValue([makeRate({ effective_from: "2026-07", id: 1 })]);

    const wrapper = await mountSettings();

    const warnings = wrapper.findAll(".electricity-rates__warning").map((el) => el.text());
    expect(warnings).toHaveLength(1);
    expect(warnings[0]).toBe("No rate covers 2026-06 yet");
  });
});
