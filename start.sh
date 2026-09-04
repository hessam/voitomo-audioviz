#!/bin/bash
set -e

export NVM_DIR="/root/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"

export TELEGRAM_BOT_TOKEN=""
export TELEGRAM_ALLOWED_USERS="92241363"

cd /root/workspace

echo "🚀 Starting render server..."
cd /root/workspace/renderer
node -r ts-node/register server.ts >> /tmp/renderer.log 2>&1 &
RENDERER_PID=$!
echo "Renderer PID: $RENDERER_PID"

sleep 5

echo "🤖 Starting Telegram bot..."
cd /root/workspace
.venv/bin/python3 bot/main.py >> /tmp/bot.log 2>&1 &
BOT_PID=$!
echo "Bot PID: $BOT_PID"

echo "✅ Both services started"
wait $BOT_PID
