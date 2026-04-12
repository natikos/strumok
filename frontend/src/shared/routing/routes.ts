import "vue-router";

declare module "vue-router" {
  interface RouteMeta {
    authRequired?: boolean;
    guestOnly?: boolean;
  }
}

export const ROUTES = {
  auth: "/auth",
  dashboard: "/",
  verifyEmail: "/verify-email",
} as const;

export type AppRoutePath = (typeof ROUTES)[keyof typeof ROUTES];
