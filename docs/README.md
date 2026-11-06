# Documentation index

Find the task, follow the link.

## I want to…

| Task | Go to |
| ---- | ----- |
| Set up and run the app locally | [development.md](development.md) |
| Run, create or reset migrations on my local database | [development.md → Migrations](development.md#migrations) |
| Understand the migration rules (backward-compatible, `# contract:`) | [deployment.md → Migrations](deployment.md#migrations) |
| See every way code reaches production (tag, manual run, rollback) | [deployment.md → Ways to deploy](deployment.md#ways-to-deploy) |
| Cut a release | [deployment.md](deployment.md#ways-to-deploy), or run `/deploy` in Claude Code |
| Set env vars / GitHub secrets | [deployment.md → Environment Variables](deployment.md#environment-variables) |
| Recover from a failed release, restore a backup | [operations.md](operations.md#failed-release) |
| Create the first admin, check health, handle personal-data requests | [operations.md](operations.md) |
| Run backend, frontend or e2e tests | [testing.md](testing.md) |
| Commit message format, git hooks | [contributing.md](contributing.md) |
| See project health metrics | [metrics.md](metrics.md) |
| Understand the domain (billing, ledger, ownership, bank import) | [domain.md](domain.md) |

## Other files

- [README.md](../README.md): what Strumok is for.
- [backend/README.md](../backend/README.md): Python version and venv troubleshooting.
- [frontend/README.md](../frontend/README.md): frontend commands.
- [CLAUDE.md](../CLAUDE.md): instructions and code conventions (errors, module
  layout, styling, migrations) for Claude Code; worth reading for humans too.
- `.claude/`: agents, skills and slash commands (`/deploy`, `/shipit`) for
  Claude Code. Not needed to work on the project by hand.

Keep this table current when you add or move a doc.
