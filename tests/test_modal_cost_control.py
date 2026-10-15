"""Budget, release and status behavior of the Modal manager.

A loopback server stands in for the CPU control endpoint and runs the real ledger
logic; the GPU health check is mocked. Nothing contacts Modal.
"""

import asyncio
import json
import os
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import AsyncMock, patch

from bot.services import container_ledger as ledger
from bot.services import gpu_cost, modal_gpu
from bot.services.gpu_cost import BudgetExceeded
from bot.services.modal_gpu import ModalGpuManager


class FakeStore(dict):
    def put(self, key, value):
        self[key] = value

    def pop(self, key, default=None):
        return super().pop(key, default)


class ControlHandler(BaseHTTPRequestHandler):
    def _reply(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/ledger":
            self.send_response(404)
            self.end_headers()
            return
        self._reply({"now": time.time(), "containers": ledger.container_records(self.server.store)})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self._reply(ledger.request_release(
            self.server.store, time.time(), body["min_idle_seconds"], body["force"]
        ))

    def log_message(self, *args):
        return None


class ModalCostTestCase(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ControlHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        patcher = patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in list(os.environ):
            if key.startswith("MODAL_") or key.startswith("GPU_"):
                del os.environ[key]
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        os.environ.update(
            GPU_LEDGER_PATH=os.path.join(directory.name, "leases.jsonl"),
            MODAL_GPU_URL="http://gpu.invalid",
            MODAL_CONTROL_URL=f"http://127.0.0.1:{self.server.server_port}",
            MODAL_PROXY_TOKEN_ID="id",
            MODAL_PROXY_TOKEN_SECRET="secret",
            MODAL_DAILY_CAP_USD="2.0",
            MODAL_GPU_RATE_PER_SECOND="0.001",
        )
        self.store = FakeStore()
        self.server.store = self.store
        self.manager = ModalGpuManager()
        self.addCleanup(self.manager._cancel_pending_release)
        health = patch.object(ModalGpuManager, "_is_healthy", AsyncMock(return_value=True))
        self.health = health.start()
        self.addCleanup(health.stop)

    def add_container(self, busy=False, idle_for=100.0):
        now = time.time()
        ledger.start_container(self.store, "c1", now - 500)
        ledger.watcher_step(
            self.store, "c1", {"ready": True, "busy": busy, "last_activity_at": now - idle_for}, now - 1
        )

    def add_spent_container(self, dollars):
        """An exited container that cost `dollars` today at the test rate."""
        day_start = gpu_cost.utc_day_start(time.time())
        seconds = dollars / 0.001
        self.store["c:old"] = {
            "started_at": day_start, "exited_at": day_start + seconds,
            "heartbeat_at": day_start + seconds, "ready_at": None,
        }


class TestBudget(ModalCostTestCase):
    async def test_job_over_the_daily_cap_is_refused_before_any_gpu_work(self):
        self.add_spent_container(1.99)
        with patch.object(ModalGpuManager, "_wait_ready", AsyncMock(return_value=True)) as ready:
            with self.assertRaises(BudgetExceeded):
                async with self.manager.managed_gpu():
                    self.fail("An over-budget job was admitted")
        ready.assert_not_awaited()
        self.assertEqual(self.manager._active, 0)

    async def test_job_under_the_cap_runs_and_is_recorded(self):
        self.add_spent_container(0.10)
        async with self.manager.managed_gpu() as url:
            self.assertEqual(url, "http://gpu.invalid")
        leases = gpu_cost.LeaseLedger().read()
        self.assertEqual(len(leases), 1)
        self.assertEqual(leases[0]["tail_s"], gpu_cost.scaledown_seconds())

    async def test_a_cold_start_and_its_idle_tail_are_projected_into_admission(self):
        self.add_spent_container(1.9)
        with self.assertRaises(BudgetExceeded):
            await self.manager._admit()  # 1.9 + (60s cold + 60s tail) * 0.001 = 2.02 >= 2.0

    async def test_a_warm_container_adds_no_cold_start_projection(self):
        os.environ["MODAL_DAILY_CAP_USD"] = "0.6"
        self.add_container(busy=False, idle_for=5)  # ~500s alive + 55s tail left = ~0.555
        await self.manager._admit()  # a cold start would add 0.12 and cross 0.6

    async def test_running_job_is_cancelled_at_95_percent_and_the_container_is_forced_down(self):
        self.add_container(busy=True)
        calls = []

        async def spend(ledger_arg=None):
            calls.append(1)
            return 0.0 if len(calls) == 1 else 1.95

        with (
            patch.object(modal_gpu, "BUDGET_CHECK_SECONDS", 0.01),
            patch.object(ModalGpuManager, "_spend_today", side_effect=spend),
            patch.object(ModalGpuManager, "_wait_ready", AsyncMock(return_value=True)),
        ):
            with self.assertRaisesRegex(BudgetExceeded, "95%"):
                async with self.manager.managed_gpu():
                    await asyncio.sleep(2)
        request = self.store[ledger.release_key("c1")]
        self.assertTrue(request["force"])
        self.assertEqual(self.manager._active, 0)

    async def test_provider_bill_wins_when_higher_than_the_estimate(self):
        self.add_spent_container(0.10)
        with patch.object(ModalGpuManager, "_billed_today", AsyncMock(return_value=5.0)):
            self.assertEqual(await self.manager._spend_today(), 5.0)

    async def test_estimate_wins_when_higher_than_the_provider_bill(self):
        self.add_spent_container(0.50)
        with patch.object(ModalGpuManager, "_billed_today", AsyncMock(return_value=0.01)):
            self.assertAlmostEqual(await self.manager._spend_today(), 0.50)

    async def test_unreachable_control_falls_back_to_the_lease_ledger(self):
        os.environ["MODAL_CONTROL_URL"] = "http://127.0.0.1:1"
        gpu_cost.LeaseLedger().append(
            {"ended_at": time.time(), "cold_start_s": 100, "work_s": 800, "tail_s": 100}
        )  # 1000s * 0.001 = 1.00
        self.assertAlmostEqual(await self.manager._spend_today(), 1.0)
        gpu_cost.LeaseLedger().append(
            {"ended_at": time.time(), "cold_start_s": 100, "work_s": 800, "tail_s": 100}
        )
        with self.assertRaises(BudgetExceeded):
            await self.manager._admit()


class TestRelease(ModalCostTestCase):
    async def test_idle_container_is_released_after_the_quiet_period(self):
        self.add_container(busy=False, idle_for=100)
        with patch.object(modal_gpu, "RELEASE_QUIET_SECONDS", 0.05):
            async with self.manager.managed_gpu():
                pass
            await asyncio.sleep(0.4)
        self.assertIn(ledger.release_key("c1"), self.store)

    async def test_new_work_cancels_the_pending_release(self):
        self.add_container(busy=False, idle_for=100)
        with patch.object(modal_gpu, "RELEASE_QUIET_SECONDS", 0.3):
            async with self.manager.managed_gpu():
                pass
            async with self.manager.managed_gpu():
                await asyncio.sleep(0.5)
                self.assertNotIn(ledger.release_key("c1"), self.store)

    async def test_release_call_never_contacts_the_gpu_endpoint(self):
        self.add_container(busy=False, idle_for=100)
        self.assertTrue(await self.manager.stop_gpu())
        self.health.assert_not_awaited()

    async def test_stop_is_not_confirmed_while_a_job_runs_on_the_container(self):
        self.add_container(busy=True)
        self.assertFalse(await self.manager.stop_gpu())
        self.assertNotIn(ledger.release_key("c1"), self.store)

    async def test_stop_is_refused_while_the_bot_holds_a_lease(self):
        self.add_container(busy=False, idle_for=100)
        async with self.manager.managed_gpu():
            self.assertFalse(await self.manager.stop_gpu())

    async def test_stop_with_no_container_is_a_no_op(self):
        self.assertTrue(await self.manager.stop_gpu())


class TestStatus(ModalCostTestCase):
    async def test_status_comes_from_the_ledger_and_never_wakes_the_gpu(self):
        self.add_container(busy=True)
        text = await self.manager.status_text()
        self.health.assert_not_awaited()
        self.assertIn("RUNNING (busy)", text)
        self.assertIn("cap", text)

    async def test_status_shows_off_when_no_container_is_live(self):
        text = await self.manager.status_text()
        self.assertIn("OFF", text)
        self.health.assert_not_awaited()

    async def test_status_reports_an_unreachable_control_endpoint(self):
        os.environ["MODAL_CONTROL_URL"] = "http://127.0.0.1:1"
        self.assertIn("unreachable", await self.manager.status_text())


if __name__ == "__main__":
    unittest.main()
