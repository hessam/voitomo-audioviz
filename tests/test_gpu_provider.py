"""Offline tests for GPU provider selection and the Modal backend.

The Modal health/auth tests run against a loopback HTTP server; nothing contacts
Modal, Vast.ai, or SSH.
"""

import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import AsyncMock, patch

from bot.services import modal_gpu
from bot.services.gpu_provider import active_provider, gpu_base_url, gpu_request_headers, get_gpu_manager
from bot.services.modal_gpu import ModalGpuManager
from bot.services.vast_lifecycle import VastLifecycleManager

TOKEN_ID = "test-token-id"
TOKEN_SECRET = "test-token-secret"
GPU_ENV_KEYS = (
    "GPU_PROVIDER", "MODAL_GPU_URL", "MODAL_PROXY_TOKEN_ID", "MODAL_PROXY_TOKEN_SECRET",
    "REMOTE_RENDERER_URL", "AUDIOVIZ_AI_URL", "MODAL_CONTROL_URL", "MODAL_DAILY_CAP_USD",
    "MODAL_BILLING_RECONCILE", "MODAL_GPU_RATE_PER_SECOND", "MODAL_GPU_TYPE", "MODAL_SCALEDOWN_SECONDS",
)


class ProxyAuthHandler(BaseHTTPRequestHandler):
    """Answers /ai/health like the Modal proxy: 200 only with the right tokens."""

    def do_GET(self):
        authorized = (
            self.path == "/ai/health"
            and self.headers.get("Modal-Key") == TOKEN_ID
            and self.headers.get("Modal-Secret") == TOKEN_SECRET
        )
        self.send_response(200 if authorized else 401)
        self.end_headers()

    def log_message(self, *args):
        return None


class GpuEnvTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        patcher = patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in GPU_ENV_KEYS:
            os.environ.pop(key, None)
        ledger_dir = tempfile.TemporaryDirectory()
        self.addCleanup(ledger_dir.cleanup)
        os.environ["GPU_LEDGER_PATH"] = os.path.join(ledger_dir.name, "leases.jsonl")

    def use_env(self, **values):
        os.environ.update(values)


class TestProviderSelection(GpuEnvTestCase):
    def test_modal_is_the_default_provider(self):
        self.assertEqual(active_provider(), "modal")
        self.assertIsInstance(get_gpu_manager(), ModalGpuManager)

    def test_vast_is_selected_by_manual_switch(self):
        self.use_env(GPU_PROVIDER="vast")
        self.assertEqual(active_provider(), "vast")
        self.assertIsInstance(get_gpu_manager(), VastLifecycleManager)

    def test_unknown_provider_fails_loudly(self):
        self.use_env(GPU_PROVIDER="runpod")
        with self.assertRaisesRegex(RuntimeError, "GPU_PROVIDER"):
            active_provider()

    def test_modal_base_url_comes_from_the_deployed_endpoint(self):
        self.use_env(MODAL_GPU_URL="https://example--audioviz-gpu.modal.run/")
        self.assertEqual(gpu_base_url(), "https://example--audioviz-gpu.modal.run")

    def test_missing_modal_url_is_an_explicit_error(self):
        with self.assertRaisesRegex(RuntimeError, "MODAL_GPU_URL"):
            gpu_base_url()

    def test_vast_base_url_keeps_the_existing_tunnel_default(self):
        self.use_env(GPU_PROVIDER="vast")
        self.assertEqual(gpu_base_url(), "http://127.0.0.1:4002")

    def test_vast_base_url_prefers_remote_renderer_url(self):
        self.use_env(GPU_PROVIDER="vast", REMOTE_RENDERER_URL="http://127.0.0.1:4555/")
        self.assertEqual(gpu_base_url(), "http://127.0.0.1:4555")

    def test_vast_sends_no_proxy_headers(self):
        self.use_env(GPU_PROVIDER="vast")
        self.assertEqual(gpu_request_headers(), {})


class TestModalHeaders(GpuEnvTestCase):
    def test_modal_headers_use_proxy_token_pair(self):
        self.use_env(MODAL_PROXY_TOKEN_ID=TOKEN_ID, MODAL_PROXY_TOKEN_SECRET=TOKEN_SECRET)
        self.assertEqual(gpu_request_headers(), {"Modal-Key": TOKEN_ID, "Modal-Secret": TOKEN_SECRET})

    def test_missing_proxy_token_fails_before_any_request(self):
        self.use_env(MODAL_PROXY_TOKEN_ID=TOKEN_ID)
        with self.assertRaisesRegex(RuntimeError, "MODAL_PROXY_TOKEN_SECRET"):
            gpu_request_headers()


class TestModalLifecycle(GpuEnvTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ProxyAuthHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def configure(self, token_id=TOKEN_ID, token_secret=TOKEN_SECRET):
        self.use_env(
            MODAL_GPU_URL=self.url,
            MODAL_PROXY_TOKEN_ID=token_id,
            MODAL_PROXY_TOKEN_SECRET=token_secret,
        )

    async def test_ready_endpoint_is_admitted_with_proxy_headers(self):
        self.configure()
        async with ModalGpuManager().managed_gpu() as base_url:
            self.assertEqual(base_url, self.url)

    async def test_wrong_proxy_token_is_reported_not_retried(self):
        self.configure(token_secret="wrong")
        with self.assertRaisesRegex(RuntimeError, "rejected the proxy token"):
            await ModalGpuManager().ensure_gpu_ready()

    async def test_cold_start_waits_until_healthy(self):
        self.configure()
        statuses = []

        async def record(message):
            statuses.append(message)

        with (
            patch.object(ModalGpuManager, "_is_healthy", AsyncMock(side_effect=[False, False, True])),
            patch("bot.services.modal_gpu.asyncio.sleep", new_callable=AsyncMock) as sleep,
        ):
            self.assertTrue(await ModalGpuManager().ensure_gpu_ready(record))
        self.assertEqual(sleep.await_count, 2)
        self.assertEqual(len(statuses), 1)

    async def test_cold_start_timeout_fails_the_job(self):
        self.configure()
        with (
            patch.object(modal_gpu, "COLD_START_TIMEOUT_SECONDS", 0),
            patch.object(ModalGpuManager, "_is_healthy", AsyncMock(return_value=False)),
            self.assertLogs("modal_gpu", level="ERROR"),
        ):
            with self.assertRaisesRegex(RuntimeError, "Failed to ensure GPU readiness"):
                async with ModalGpuManager().managed_gpu():
                    self.fail("An unready GPU was admitted")

    async def test_stop_without_control_endpoint_never_touches_the_gpu(self):
        self.configure()
        with patch.object(ModalGpuManager, "_is_healthy", AsyncMock()) as health:
            self.assertTrue(await ModalGpuManager().stop_gpu())
        health.assert_not_awaited()

    async def test_status_without_control_endpoint_does_not_wake_the_gpu(self):
        self.configure()
        with patch.object(ModalGpuManager, "_is_healthy", AsyncMock()) as health:
            text = await ModalGpuManager().status_text()
        health.assert_not_awaited()
        self.assertIn("MODAL_CONTROL_URL", text)


if __name__ == "__main__":
    unittest.main()
