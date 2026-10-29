import { type APIRequestContext, expect } from "@playwright/test";

// Seed helpers go through the real admin API with an admin-authenticated
// context (see `apiAs` in ../fixtures.ts). Nothing here touches the database.

export interface RateInput {
  /** `YYYY-MM`: the first period this rate bills. */
  effectiveFrom: string;
  day?: string;
  night?: string;
}

export async function createRate(admin: APIRequestContext, input: RateInput): Promise<void> {
  const response = await admin.post("/electricity-rates", {
    data: {
      day_rate_uah: input.day ?? "4.32",
      night_rate_uah: input.night ?? "2.16",
      effective_from: input.effectiveFrom,
    },
  });
  expect(response.status(), await response.text()).toBe(201);
}

export interface HouseholdInput {
  name: string;
  /** Households need an owner at creation; reassign or unassign afterwards. */
  ownerId: number;
  startingDay?: string;
  startingNight?: string;
}

export async function createHousehold(
  admin: APIRequestContext,
  input: HouseholdInput
): Promise<{ id: number; name: string }> {
  const response = await admin.post("/admin/households", {
    data: {
      name: input.name,
      user_id: input.ownerId,
      ...(input.startingDay === undefined
        ? {}
        : {
            starting_day_meter_value: input.startingDay,
            starting_night_meter_value: input.startingNight ?? "0",
          }),
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  return (await response.json()) as { id: number; name: string };
}

/** Frees a household so an invite can be assigned to it. */
export async function unassignHousehold(
  admin: APIRequestContext,
  householdId: number
): Promise<void> {
  const response = await admin.patch(`/admin/households/${householdId}/owner`, {
    data: { user_id: null, confirm_reassignment: true },
  });
  expect(response.status(), await response.text()).toBe(200);
}

export async function assignOwner(
  admin: APIRequestContext,
  householdId: number,
  userId: number
): Promise<void> {
  const response = await admin.patch(`/admin/households/${householdId}/owner`, {
    data: { user_id: userId, confirm_reassignment: true },
  });
  expect(response.status(), await response.text()).toBe(200);
}

export interface InviteInput {
  email: string;
  firstName: string;
  lastName: string;
  householdId: number;
}

export async function inviteResident(
  admin: APIRequestContext,
  input: InviteInput
): Promise<{ id: number; email: string }> {
  const response = await admin.post("/admin/users", {
    data: {
      email: input.email,
      first_name: input.firstName,
      last_name: input.lastName,
      language: "en",
      household_id: input.householdId,
    },
  });
  expect(response.status(), await response.text()).toBe(201);
  const body = (await response.json()) as { user: { id: number; email: string } };
  return body.user;
}
