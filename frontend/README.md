# Frontend

Minimal Vue 3 SPA for Strumok.

## Setup

Run from the `frontend/` folder:

```bash
bun install
```

## Run

Run from the `frontend/` folder:

```bash
bun run dev
```

Default app URL: `http://localhost:5173`

## Build / Preview

```bash
bun run build
bun run preview
```

## API Contract Sync (OpenAPI)

Generate frontend types from backend OpenAPI schema.
Run backend first (default: `http://localhost:8000`), then run:

```bash
bun run api:types
```

Override backend OpenAPI URL when needed:

```bash
OPENAPI_URL=http://localhost:9000/openapi.json bun run api:types
```
