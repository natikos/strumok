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

// TEMPORARY: manual end-to-end verification after a deploy. Safe to remove
// once push has been confirmed working in production (issue #94).
export async function sendTestPush(): Promise<{ removed: number; sent: number }> {
  const { data, error, response } = await appApiClient.POST("/push/test");

  if (error) {
    throw buildApiError(response.status, error);
  }

  return { removed: data?.removed ?? 0, sent: data?.sent ?? 0 };
}
