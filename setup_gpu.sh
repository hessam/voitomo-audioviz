#!/bin/bash
set -e
export DEBIAN_FRONTEND=noninteractive

echo "=== 1. APT Update & Core Packages ==="
apt-get update -y
apt-get install -y --no-install-recommends \
    curl git tmux ffmpeg python3-pip python3-venv \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libasound2 libcups2 libpango-1.0-0 \
    libcairo2 libxshmfence1

echo "=== 2. Node.js 20 Setup ==="
if ! which node >/dev/null 2>&1; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi
npm install -g ts-node typescript

echo "=== 3. Python AI Packages ==="
pip3 install --upgrade pip
pip3 install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
pip3 install "audio-separator[gpu]" faster-whisper fastapi uvicorn python-multipart requests

echo "=== 4. Warm-up Mel-Band RoFormer Model Checkpoint ==="
mkdir -p /root/audioviz/models
python3 -c "
from audio_separator.separator import Separator
sep = Separator(output_format='WAV', model_file_dir='/root/audioviz/models')
sep.load_model('vocals_mel_band_roformer.ckpt')
print('Mel-Band RoFormer downloaded & validated successfully.')
"

echo "=== 5. Setup Start Script ==="
cat << 'START_EOF' > /root/audioviz/start_services.sh
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
    tmux new-session -d -s remotion_renderer "cd /root/audioviz/renderer && ts-node server.ts 2>&1 | tee -a /root/audioviz/logs/renderer.log"
fi

echo "Start services routine finished."
START_EOF
chmod +x /root/audioviz/start_services.sh

echo "=== SETUP COMPLETE ==="
