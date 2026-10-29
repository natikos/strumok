import type { APIRequestContext, Page } from "@playwright/test";

import { expect, test } from "./fixtures";
import {
  assignOwner,
  createHousehold,
  createRate,
  type HouseholdInput,
  unassignHousehold,
} from "./support/seed";

// Day 2 of July at noon Kyiv (UTC+3, away from the DST changes): the open
// window is for June, the prior month.
const NOW = "2026-07-02T12:00:00+03:00";

async function submitJuneReading(page: Page): Promise<void> {
  await page.goto("/");
  await page.getByLabel("Day", { exact: true }).fill("1234");
  await page.getByLabel("Night", { exact: true }).fill("567");
  await page.getByRole("button", { name: /^Submit (first )?reading$/ }).click();
  await expect(page.getByText("Reading submitted")).toBeVisible();
}

async function seedRate(admin: APIRequestContext): Promise<void> {
  await createRate(admin, { effectiveFrom: "2026-06" });
}

const BASELINE: Pick<HouseholdInput, "startingDay" | "startingNight"> = {
  startingDay: "1000",
  startingNight: "500",
};

test("a resident's submitted reading is shown as submitted and survives a reload", async ({
  page,
  seedUser,
  apiAs,
  loginAs,
  setNow,
}) => {
  await setNow(NOW);
  const adminUser = await seedUser({ isAdmin: true });
  const resident = await seedUser({ firstName: "Olena", lastName: "Koval" });
  const admin = await apiAs(adminUser);
  await seedRate(admin);
  await createHousehold(admin, { name: "Plot 7", ownerId: resident.id, ...BASELINE });

  await loginAs(resident);
  await submitJuneReading(page);
  await expect(page.getByLabel("Day", { exact: true })).toHaveCount(0);

  await page.reload();

  await expect(page.getByText("Reading submitted")).toBeVisible();
  await expect(page.getByLabel("Day", { exact: true })).toHaveCount(0);

  const readings = await page.request.get("/meter-readings");
  const list = (await readings.json()) as { period: string; day_meter_value: string }[];
  expect(list.find((r) => r.period === "2026-06")?.day_meter_value).toBe("1234.00");
});

// The owner took over this month (the head created the plot, freed it, and
// handed it to the resident during days 1-5) and must still see the handover
// reading that stands in for the open period.
test("a reading for the open period survives a reload when the owner was assigned this month", async ({
  page,
  seedUser,
  apiAs,
  loginAs,
  setNow,
}) => {
  await setNow(NOW);
  const adminUser = await seedUser({ isAdmin: true });
  const resident = await seedUser({ firstName: "Olena", lastName: "Koval" });
  const admin = await apiAs(adminUser);
  await seedRate(admin);
  const household = await createHousehold(admin, {
    name: "Plot 7",
    ownerId: adminUser.id,
    ...BASELINE,
  });
  await unassignHousehold(admin, household.id);
  await assignOwner(admin, household.id, {
    handover: { day: "1234", night: "567" },
    userId: resident.id,
  });

  await loginAs(resident);
  await page.goto("/");
  await page.reload();

  await expect(page.getByText("Reading submitted")).toBeVisible({ timeout: 5000 });
});
