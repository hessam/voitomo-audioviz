#!/usr/bin/env bash
# Deploy one commit from origin/main into a git checkout, restart the bot,
# and roll back to the previous commit if the health check fails.
#
# Usage: DEPLOY_DIR=... RESTART_CMD=... HEALTH_CMD=... deploy.sh <sha>
# Ignored files (.env, .deployed_sha) are never touched by checkout.
set -euo pipefail

SHA="${1:?usage: deploy.sh <sha>}"
DEPLOY_DIR="${DEPLOY_DIR:?set DEPLOY_DIR}"
RESTART_CMD="${RESTART_CMD:?set RESTART_CMD}"
HEALTH_CMD="${HEALTH_CMD:?set HEALTH_CMD}"
HEALTH_WAIT="${HEALTH_WAIT:-10}"
STATE_FILE="$DEPLOY_DIR/.deployed_sha"

cd "$DEPLOY_DIR"

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "drift: tracked files differ from HEAD; refusing to deploy" >&2
  git status --short --untracked-files=no >&2
  exit 1
fi

git fetch --quiet origin
if ! git merge-base --is-ancestor "$SHA" origin/main; then
  echo "$SHA is not on origin/main; refusing to deploy" >&2
  exit 1
fi

PREVIOUS="$(git rev-parse HEAD)"

activate() {
  git checkout --quiet --detach "$1" || return 1
  eval "$RESTART_CMD" || true
  sleep "$HEALTH_WAIT"
  eval "$HEALTH_CMD"
}

if activate "$SHA"; then
  echo "$SHA" > "$STATE_FILE"
  echo "deployed $SHA (previous $PREVIOUS)"
  exit 0
fi

echo "health check failed for $SHA; rolling back to $PREVIOUS" >&2
if activate "$PREVIOUS"; then
  echo "rolled back to $PREVIOUS" >&2
else
  echo "rollback to $PREVIOUS also failed; manual intervention needed" >&2
fi
exit 1
