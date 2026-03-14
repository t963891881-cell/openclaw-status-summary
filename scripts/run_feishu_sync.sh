#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SKILL_DIR/.feishu_sync.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

exec "$SCRIPT_DIR/sync_feishu_bitable.py" \
  --app-id "$APP_ID" \
  --app-secret "$APP_SECRET" \
  --app-token "$APP_TOKEN"
