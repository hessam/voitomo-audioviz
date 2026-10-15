"""Chooses the active GPU backend.

GPU_PROVIDER=modal (default) uses the Modal endpoint from modal_gpu_app.py.
GPU_PROVIDER=vast uses the Vast.ai instance. Switch by changing the variable
and restarting the bot; both backends expose the same calls to the bot.
"""
import os
from typing import Dict

GPU_PROVIDERS = ("modal", "vast")
DEFAULT_VAST_URL = "http://127.0.0.1:4002"


def active_provider() -> str:
    provider = os.environ.get("GPU_PROVIDER", "modal").strip().lower()
    if provider not in GPU_PROVIDERS:
        raise RuntimeError(f"GPU_PROVIDER must be one of {GPU_PROVIDERS}, got {provider!r}.")
    return provider


def get_gpu_manager():
    if active_provider() == "vast":
        from bot.services.vast_lifecycle import VastLifecycleManager
        return VastLifecycleManager.get_instance()
    from bot.services.modal_gpu import ModalGpuManager
    return ModalGpuManager.get_instance()


def gpu_base_url() -> str:
    """Base URL that serves both /ai/* and the renderer endpoints."""
    if active_provider() == "modal":
        from bot.services.modal_gpu import modal_base_url
        return modal_base_url()
    url = os.environ.get("REMOTE_RENDERER_URL") or os.environ.get("AUDIOVIZ_AI_URL") or DEFAULT_VAST_URL
    return url.rstrip("/")


def gpu_request_headers() -> Dict[str, str]:
    if active_provider() == "modal":
        from bot.services.modal_gpu import modal_request_headers
        return modal_request_headers()
    return {}
