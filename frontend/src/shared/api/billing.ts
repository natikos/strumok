import type { components } from "./generated/openapi.ts";

import { appApiClient } from "./client";

export type BillingWindowOut = components["schemas"]["BillingWindowOut"];

export async function getBillingWindow(): Promise<BillingWindowOut> {
  const { data } = await appApiClient.GET("/billing/window");

  if (!data) {
    throw new Error("Billing window response was empty");
  }

  return data;
}
