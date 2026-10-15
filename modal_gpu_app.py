"""Modal GPU endpoint: the same AI service and renderer that run on the Vast box.

One container serves both on one URL, matching the Vast topology:
  /ai/*          -> vast_ai_service.py (Whisper, Mel-Band RoFormer, alignment)
  renderer routes -> renderer/server.ts (Remotion, port 4001)

Deploy (CI/CD owns deploys; this is for a manual, owner-run deploy):
  pip install modal && python3 -m modal setup
  modal deploy modal_gpu_app.py

Then set MODAL_GPU_URL and MODAL_CONTROL_URL to the printed URLs and create a proxy
auth token in the Modal dashboard for MODAL_PROXY_TOKEN_ID / MODAL_PROXY_TOKEN_SECRET.

Cost notes (you pay for container-seconds: cold start + work + idle tail + shutdown delay):
- One GPU container only (max_containers=1), so parallel requests queue instead of each
  paying a cold start and an idle tail.
- `control` is a CPU function for status and release. It reads the ledger and never calls
  the GPU function, so asking for status or releasing never starts hardware.
- The container heartbeats to a ledger (modal.Dict) and exits when the bot asks for a
  release while it is idle. The exit signal and the Dict ledger are unverified on a live
  deploy: do one small real run and compare the ledger with the Modal dashboard.
- Use `modal deploy`, not `modal serve`, for the bot. A dev app dies when your laptop
  connection drops and bills GPU while it lives. "Live app" on the dashboard means
  deployed, not running: check the container list.
"""
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

import modal

APP_NAME = "audioviz-gpu"
GPU_TYPE = os.environ.get("MODAL_GPU_TYPE", "L4")
# Keeping a container warm longer than a cold start takes costs more than restarting it.
# 60s is a starting point, not a measurement: read the real cold start from
# `python3 -m bot.services.modal_gpu` and set this near it.
SCALEDOWN_SECONDS = int(os.environ.get("MODAL_SCALEDOWN_SECONDS", "60"))
REMOTE_ROOT = "/root/audioviz"
RENDERER_PORT = 4001
AI_PORT = 5001
LEDGER_NAME = "audioviz-gpu-ledger"
WATCH_INTERVAL_SECONDS = 5


def _download_models() -> None:
    """Fetch model weights at image build so cold starts do not download them."""
    from faster_whisper import WhisperModel
    from audio_separator.separator import Separator

    WhisperModel("large-v3", device="cpu", compute_type="int8")
    separator = Separator(output_format="WAV", model_file_dir=f"{REMOTE_ROOT}/models")
    separator.load_model("vocals_mel_band_roformer.ckpt")


image = (
    # Same CUDA base as the Vast instance (see vast_lifecycle.py).
    modal.Image.from_registry("nvidia/cuda:12.4.1-devel-ubuntu22.04", add_python="3.11")
    .apt_install(
        "curl", "ca-certificates", "gnupg", "ffmpeg",
        "libnss3", "libnspr4", "libatk1.0-0", "libatk-bridge2.0-0", "libxcomposite1",
        "libxdamage1", "libxfixes3", "libxrandr2", "libgbm1", "libxkbcommon0",
        "libasound2", "libcups2", "libpango-1.0-0", "libcairo2", "libxshmfence1",
    )
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        "npm install -g ts-node typescript",
    )
    .pip_install(
        "fastapi", "uvicorn", "python-multipart", "requests", "aiohttp",
        "torch", "torchaudio", "faster-whisper", "audio-separator[gpu]",
    )
    .add_local_file("vast_ai_service.py", f"{REMOTE_ROOT}/vast_ai_service.py", copy=True)
    .add_local_file("bot/__init__.py", f"{REMOTE_ROOT}/bot/__init__.py", copy=True)
    .add_local_file("bot/services/__init__.py", f"{REMOTE_ROOT}/bot/services/__init__.py", copy=True)
    .add_local_file("bot/services/alignment.py", f"{REMOTE_ROOT}/bot/services/alignment.py", copy=True)
    .add_local_file("bot/services/container_ledger.py", f"{REMOTE_ROOT}/bot/services/container_ledger.py", copy=True)
    .add_local_dir("video_profiles", f"{REMOTE_ROOT}/video_profiles", copy=True)
    .add_local_dir("renderer", f"{REMOTE_ROOT}/renderer", copy=True, ignore=["node_modules"])
    .run_commands(
        f"cd {REMOTE_ROOT}/renderer && npm ci",
        "mkdir -p /root/workspace && ln -sfn /root/audioviz/video_profiles /root/workspace/video_profiles",
    )
    .run_function(_download_models)
    .env({"RENDERER_BIND_HOST": "0.0.0.0"})
)

app = modal.App(APP_NAME)


@app.function(
    image=image,
    gpu=GPU_TYPE,
    timeout=4 * 60 * 60,
    scaledown_window=SCALEDOWN_SECONDS,
    # Stems live on this container's disk and are downloaded after separation,
    # so one container must serve the whole job.
    max_containers=1,
)
@modal.web_server(RENDERER_PORT, startup_timeout=900, requires_proxy_auth=True)
def gpu_services() -> None:
    # web_server functions start their servers in the background and return.
    subprocess.Popen(
        ["python3", "-m", "uvicorn", "vast_ai_service:app", "--host", "127.0.0.1", "--port", str(AI_PORT)],
        cwd=REMOTE_ROOT,
    )
    subprocess.Popen(["ts-node", "server.ts"], cwd=f"{REMOTE_ROOT}/renderer")
    sys.path.insert(0, REMOTE_ROOT)
    store = modal.Dict.from_name(LEDGER_NAME, create_if_missing=True)
    container_id = os.environ.get("MODAL_TASK_ID") or uuid.uuid4().hex
    threading.Thread(target=_watch_lifecycle, args=(store, container_id), daemon=True).start()


def _fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


def _probe() -> dict:
    """Ready once models and renderer answer; busy while any job or request is in flight."""
    try:
        _fetch_json(f"http://127.0.0.1:{AI_PORT}/ai/health")
        health = _fetch_json(f"http://127.0.0.1:{RENDERER_PORT}/health")
    except Exception:
        # Not up yet, or unreadable: never report idle on a guess.
        return {"ready": False, "busy": True, "last_activity_at": None}
    return {
        "ready": True,
        "busy": health["activeJobs"] > 0 or health["inFlight"] > 0,
        "last_activity_at": health["lastActivityAt"] / 1000.0,
    }


def _watch_lifecycle(store, container_id: str) -> None:
    """Heartbeat to the ledger and exit when the control endpoint asks for a release."""
    from bot.services.container_ledger import start_container, watcher_step

    start_container(store, container_id, time.time())
    while True:
        time.sleep(WATCH_INTERVAL_SECONDS)
        try:
            if watcher_step(store, container_id, _probe(), time.time()):
                # Same signal the platform sends when it scales a container down.
                os.kill(os.getpid(), signal.SIGTERM)
                return
        except Exception as error:
            print(f"ledger heartbeat failed: {error}", flush=True)


control_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("fastapi")
    .add_local_file("bot/__init__.py", f"{REMOTE_ROOT}/bot/__init__.py", copy=True)
    .add_local_file("bot/services/__init__.py", f"{REMOTE_ROOT}/bot/services/__init__.py", copy=True)
    .add_local_file("bot/services/container_ledger.py", f"{REMOTE_ROOT}/bot/services/container_ledger.py", copy=True)
)


@app.function(image=control_image, scaledown_window=30)
@modal.asgi_app(requires_proxy_auth=True)
def control():
    """CPU-only: status and release. Never touches the GPU function, so it never starts hardware."""
    sys.path.insert(0, REMOTE_ROOT)
    from fastapi import FastAPI
    from pydantic import BaseModel
    from bot.services import container_ledger

    store = modal.Dict.from_name(LEDGER_NAME, create_if_missing=True)
    api = FastAPI()

    class ReleaseRequest(BaseModel):
        min_idle_seconds: float = 0
        force: bool = False

    @api.get("/ledger")
    def ledger():
        return {"now": time.time(), "containers": container_ledger.container_records(store)}

    @api.post("/release")
    def release(body: ReleaseRequest):
        return container_ledger.request_release(store, time.time(), body.min_idle_seconds, body.force)

    return api
