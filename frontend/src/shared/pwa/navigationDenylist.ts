// Navigations the service worker must leave to the network: backend paths and
// files. Every other navigation is a client route served by the precached shell.
export const navigationDenylist: RegExp[] = [
  /^\/favicon\//,
  /^\/admin\/export\//,
  /^\/(?:health|docs|redoc|openapi\.json)(?:\/|$)/,
  /\.(?:png|jpe?g|gif|svg|ico|webp|woff2?|ttf|otf|eot|webmanifest|json)$/,
];
