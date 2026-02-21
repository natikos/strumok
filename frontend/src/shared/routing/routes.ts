export const ROUTES = {
  auth: "/auth",
  dashboard: "/",
} as const;

export type AppRoutePath = (typeof ROUTES)[keyof typeof ROUTES];
