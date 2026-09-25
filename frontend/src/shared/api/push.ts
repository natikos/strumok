import type { components } from "./generated/openapi.ts";

import { appApiClient, buildApiError } from "./client";

type PushSubscriptionIn = components["schemas"]["PushSubscriptionIn"];

export async function getVapidPublicKey(): Promise<string> {
  const { error, data } = await appApiClient.GET("/push/vapid-public-key");

  if (!data?.public_key) {
    throw new Error(`Failed to get VAPID public key: ${error}`);
  }

  return data.public_key;
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
  const { data, response } = await appApiClient.POST("/push/test");

  // The endpoint has no request body/params, so FastAPI generates no error
  // response schema for it, which collapses openapi-fetch's `error` type to
  // `never` -- check `response.ok` instead of destructuring `error`.
  if (!response.ok || !data) {
    throw buildApiError(response.status, null);
  }

  return { removed: data.removed, sent: data.sent };
}
