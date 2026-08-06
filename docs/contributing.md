# Contributing

## Git Hooks

Pre-commit hooks (lint + format on staged files) run via [lefthook](https://github.com/evilmartians/lefthook). One-time setup per clone:

```bash
brew install lefthook   # or see lefthook docs for other package managers
lefthook install
```

## Commit Messages

All commit messages must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification.

- Use prefixes: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `style`, etc.
- Format: `<type>(<scope>): <description>`
- Examples:
  - `feat(auth): add JWT authentication`
  - `fix(routes): correct user route validation`
- Keep messages concise and descriptive.
- Do not use generic messages like "update" or "changes".
