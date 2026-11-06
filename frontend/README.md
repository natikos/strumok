# Frontend

Vue 3 + TypeScript PWA (Vite, PrimeVue, vue-i18n). Run commands from `frontend/` with [Bun](https://bun.sh).
Full local setup: [docs/development.md](../docs/development.md).

## Commands

| Task | Command |
| ---- | ------- |
| Install | `bun install` |
| Dev server (`http://localhost:5173`) | `bun run dev` |
| Lint | `bun run lint` |
| Unit tests | `bun run test` (`test:watch` while developing) |
| End-to-end tests | `bun run e2e` (see [docs/testing.md](../docs/testing.md#end-to-end-e2e)) |
| Production build (type-check + Vite, outputs to `../backend/dist/`) | `bun run build` |
| Preview the build | `bun run preview` |

## API types (OpenAPI)

Types in `src/shared/api/generated/openapi.ts` are generated from the backend and
must not be edited by hand. With the backend running on `http://localhost:8000`:

```bash
bun run api:types
```

Point at another backend with `OPENAPI_URL=http://localhost:9000/openapi.json bun run api:types`.
