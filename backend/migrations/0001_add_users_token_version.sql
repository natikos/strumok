-- Issue #146: bumped on logout (and any future password reset/change,
-- deactivation, or email change) to invalidate every outstanding
-- access/refresh token for a user immediately.
ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version integer NOT NULL DEFAULT 0;
