import { expect, test } from "./fixtures";
import { createHousehold, createRate } from "./support/seed";

const NOW = "2026-07-02T12:00:00+03:00";

test("dashboard shows the co-op rate and does not overflow at 360px", async ({
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
  await createRate(admin, { effectiveFrom: "2026-06", day: "4.32", night: "2.16" });
  await createHousehold(admin, { name: "Plot 7", ownerId: resident.id });

  await loginAs(resident);
  await page.goto("/");

  // At 360px the strip collapses to a day/night pill that opens a popover.
  const pill = page.getByRole("button", { name: /Co-op rate/ });
  await expect(pill).toBeVisible();
  await expect(pill).toHaveText(/^4[.,]32\/2[.,]16$/);
  await pill.click();
  const strip = page.locator(".tariff-strip__details");
  await expect(strip).toBeVisible();
  await expect(strip).toContainText(/4[.,]32/);
  await expect(strip).toContainText(/2[.,]16/);
  await expect(strip).toContainText("from 01.06");

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("dashboard shows no rate strip when no rate is configured", async ({
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
  await createHousehold(admin, { name: "Plot 7", ownerId: resident.id });

  await loginAs(resident);
  await page.goto("/");

  await expect(page.getByLabel("Day", { exact: true })).toBeVisible();
  await expect(page.getByText("Co-op rate")).toHaveCount(0);
});
