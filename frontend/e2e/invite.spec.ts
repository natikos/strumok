import { expect, test } from "./fixtures";
import { createHousehold, inviteResident, unassignHousehold } from "./support/seed";

test("an invited resident sets a password from the emailed link and lands on the dashboard", async ({
  page,
  seedUser,
  apiAs,
  readOutbox,
  setNow,
}) => {
  // Noon Kyiv (UTC+3), day 2 of July.
  await setNow("2026-07-02T12:00:00+03:00");
  const adminUser = await seedUser({ isAdmin: true, firstName: "Head", lastName: "Admin" });
  const admin = await apiAs(adminUser);

  // A household needs an owner at creation, so the admin holds it briefly.
  const household = await createHousehold(admin, { name: "Plot 7", ownerId: adminUser.id });
  await unassignHousehold(admin, household.id);
  const resident = await inviteResident(admin, {
    email: "resident@example.com",
    firstName: "Olena",
    lastName: "Koval",
    householdId: household.id,
  });

  const [message] = await readOutbox(resident.email);
  expect(message, "the invite email should reach the outbox").toBeDefined();
  const href = /href="([^"]*\/set-password\?token=[^"]+)"/.exec(message?.html_content ?? "")?.[1];
  expect(href, "the invite email should carry a set-password link").toBeDefined();
  const link = new URL(href!.replaceAll("&amp;", "&"));

  await page.goto(`${link.pathname}${link.search}`);
  // Resolved by accessible name (the placeholder); see the label test below.
  await page.getByRole("textbox", { name: "Password", exact: true }).fill("a-new-password-1");
  await page.getByRole("textbox", { name: "Confirm password" }).fill("a-new-password-1");
  await page.getByRole("button", { name: "Set password and continue" }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("navigation", { name: "Main" })).toBeVisible();
  // The Secure session cookie was accepted over http://localhost.
  const me = await page.request.get("/auth/me");
  expect(me.status()).toBe(200);
  const body = (await me.json()) as { email: string; households: { id: number }[] };
  expect(body.email).toBe(resident.email);
  expect(body.households.map((h) => h.id)).toEqual([household.id]);
});

// DEFECT #288: FormFieldControl puts the `id` on PrimeVue Password's wrapper <div>, so
// <label for> points at a div and the input has no label, only a placeholder.
// Remove `test.fail` once the label resolves to the input.
test.fail("the set-password fields can be found by their visible labels", async ({ page }) => {
  await page.goto("/set-password?token=not-a-real-token");
  await expect(page.getByLabel("Password", { exact: true })).toBeVisible({ timeout: 3000 });
  await expect(page.getByLabel("Confirm password")).toBeVisible({ timeout: 3000 });
});
