#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "→ Building frontend"
(cd "$repo_root/frontend" && bun install && bun run build)

echo "→ Deploying backend to FastAPI Cloud"
(cd "$repo_root/backend" && fastapi deploy)
