import type { components } from "./generated/openapi.ts";

import { appApiClient, buildApiError } from "./client";

type PushSubscriptionIn = components["schemas"]["PushSubscriptionIn"];

export async function getVapidPublicKey(): Promise<string> {
  const { data } = await appApiClient.GET("/push/vapid-public-key");

  return data?.public_key ?? "";
}

export async function subscribeToPush(subscription: PushSubscriptionIn): Promise<void> {
  const { error, response } = await appApiClient.POST("/push/subscribe", {
    body: subscription,
  });

  if (error) {
    throw buildApiError(response.status, error);
  }
}

export async function unsubscribeFromPush(endpoint: string): Promise<void> {
  const { error, response } = await appApiClient.DELETE("/push/subscribe", {
    body: { endpoint },
  });

  if (error) {
    throw buildApiError(response.status, error);
  }
}
