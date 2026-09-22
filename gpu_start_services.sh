#!/bin/bash
mkdir -p /root/audioviz/logs

if ! curl -s --max-time 2 http://127.0.0.1:5001/ai/health > /dev/null; then
    echo "Starting vast_ai in tmux..."
    tmux kill-session -t vast_ai 2>/dev/null || true
    pkill -9 -f "vast_ai_service.py" 2>/dev/null || true
    tmux new-session -d -s vast_ai "cd /root/audioviz && python3 vast_ai_service.py 2>&1 | tee -a /root/audioviz/logs/vast_ai_service.log"
fi

if ! curl -s --max-time 2 http://127.0.0.1:4001/health > /dev/null; then
    echo "Starting remotion_renderer in tmux..."
    tmux kill-session -t remotion_renderer 2>/dev/null || true
    pkill -9 -f "server.ts" 2>/dev/null || true
    tmux new-session -d -s remotion_renderer "cd /root/audioviz/renderer && /usr/bin/ts-node server.ts 2>&1 | tee -a /root/audioviz/logs/renderer.log"
fi

echo "Start services routine finished."
