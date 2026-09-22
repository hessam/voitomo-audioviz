#!/bin/bash
if [ -f /root/audioviz/.env ]; then
  set -a
  source /root/audioviz/.env
  set +a
fi
export REMOTE_RENDERER_URL="${REMOTE_RENDERER_URL:-http://127.0.0.1:4002}"

while true; do
  if ! pgrep -f "audioviz_bot_run\.py" > /dev/null; then
    echo "[$(date)] Audioviz bot not running. Starting..." >> /tmp/audioviz_supervisor.log
    cd /root/audioviz
    nohup /root/workspace/.venv/bin/python3 /root/audioviz/audioviz_bot_run.py >> /tmp/audioviz_bot.log 2>&1 &
    sleep 3
  fi

  sleep 5
done
