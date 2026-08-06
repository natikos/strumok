#!/bin/sh
set -e

OWNER_REMOTE_PATTERN="natikos/strumok"
LOCAL_CONFIG=".vscode/credentials.local.sh"

ORIGIN_URL=$(git remote get-url origin 2>/dev/null || echo "")
case "$ORIGIN_URL" in
  *"$OWNER_REMOTE_PATTERN"*) ;;
  *)
    echo "Origin remote doesn't match $OWNER_REMOTE_PATTERN, skipping credential check."
    exit 0
    ;;
esac

if [ ! -f "$LOCAL_CONFIG" ]; then
  echo "No $LOCAL_CONFIG found, skipping credential check."
  echo "Create it (gitignored) with EXPECTED_GH_USER and EXPECTED_GIT_EMAIL to enable this check."
  exit 0
fi

. "$LOCAL_CONFIG"

ACTIVE_GH_USER=$(gh api user --jq .login 2>/dev/null || echo "")
LOCAL_GIT_EMAIL=$(git config --get user.email || echo "")

if [ -n "$EXPECTED_GH_USER" ] && [ "$ACTIVE_GH_USER" != "$EXPECTED_GH_USER" ]; then
  echo "gh active account is '$ACTIVE_GH_USER', switching to '$EXPECTED_GH_USER'..."
  gh auth switch --user "$EXPECTED_GH_USER"
fi

if [ -n "$EXPECTED_GIT_EMAIL" ] && [ "$LOCAL_GIT_EMAIL" != "$EXPECTED_GIT_EMAIL" ]; then
  echo "Local git user.email is '$LOCAL_GIT_EMAIL', setting to '$EXPECTED_GIT_EMAIL'..."
  git config user.email "$EXPECTED_GIT_EMAIL"
  [ -n "$EXPECTED_GH_USER" ] && git config user.name "$EXPECTED_GH_USER"
fi

echo "Credentials OK: gh=${EXPECTED_GH_USER:-unset} git=${EXPECTED_GIT_EMAIL:-unset}"
