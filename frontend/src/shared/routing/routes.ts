import "vue-router";

declare module "vue-router" {
  interface RouteMeta {
    authRequired?: boolean;
    guestOnly?: boolean;
  }
}

export const ROUTES = {
  admin: "/admin",
  auth: "/auth",
  confirmEmailChange: "/confirm-email-change",
  history: "/history",
  root: "/",
  settings: "/settings",
  verifyEmail: "/verify-email",
} as const;

export type AppRoutePath = (typeof ROUTES)[keyof typeof ROUTES];
