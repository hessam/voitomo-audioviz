#!/bin/bash
# Keeps the audioviz bot running. Runs from the folder it lives in, so the
# same script works for any git checkout (see scripts/deploy.sh).
APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")" && pwd)}"
PYTHON="${PYTHON:-/root/workspace/.venv/bin/python3}"

if [ -f "$APP_DIR/.env" ]; then
  set -a
  source "$APP_DIR/.env"
  set +a
fi
export REMOTE_RENDERER_URL="${REMOTE_RENDERER_URL:-http://127.0.0.1:4002}"

while true; do
  if ! pgrep -f "audioviz_bot_run\.py" > /dev/null; then
    echo "[$(date)] Audioviz bot not running. Starting..." >> /tmp/audioviz_supervisor.log
    cd "$APP_DIR"
    nohup "$PYTHON" "$APP_DIR/audioviz_bot_run.py" >> /tmp/audioviz_bot.log 2>&1 &
    sleep 3
  fi

  sleep 5
done
