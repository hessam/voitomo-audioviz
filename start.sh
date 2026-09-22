#!/bin/bash
set -e

export NVM_DIR="/root/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

# Load environment variables from .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
export RENDERER_URL="${RENDERER_URL:-http://127.0.0.1:4001}"
export VAULT_STORAGE_PATH="${VAULT_STORAGE_PATH:-/opt/hermes-vault/viz}"

cd /root/audioviz

echo "🚀 Starting Audioviz 3D WebGL render server on port 4001..."
cd /root/audioviz/renderer
nohup node -r ts-node/register server.ts >> /tmp/audioviz_renderer.log 2>&1 &
RENDERER_PID=$!
echo "Renderer PID: $RENDERER_PID"

sleep 5

echo "🤖 Starting Audioviz Telegram bot (@audiovizbot)..."
cd /root/audioviz
nohup /root/workspace/.venv/bin/python3 audioviz_bot_run.py >> /tmp/audioviz_bot.log 2>&1 &
BOT_PID=$!
echo "Bot PID: $BOT_PID"

echo "✅ Both Audioviz services running"
wait $BOT_PID
