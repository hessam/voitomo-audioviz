"""Offline lifecycle regressions: never invoke Vast, SSH, or pkill."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, patch

from bot.services.vast_lifecycle import VastLifecycleManager, VAST_WARM_INSTANCE_ID


class FakeProcess:
    def __init__(self, result, returncode=0):
        self.returncode = returncode
        self.output = json.dumps(result).encode()

    async def communicate(self):
        return self.output, b""


class TestGpuLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.manager = VastLifecycleManager()
        self.instances = {
            VAST_WARM_INSTANCE_ID: {
                "id": VAST_WARM_INSTANCE_ID,
                "actual_status": "running",
                "ssh_host": "test.invalid",
                "ssh_port": 1234,
            }
        }
        self.manager._api_request = AsyncMock(side_effect=self.api_request)
        self.manager.ensure_tunnel = AsyncMock(return_value=True)
        self.process_patch = patch("bot.services.vast_lifecycle.subprocess.run")
        self.process_patch.start()
        self.addCleanup(self.process_patch.stop)

    async def api_request(self, method, endpoint, data=None):
        if method == "GET":
            return {"instances": [dict(item) for item in self.instances.values()]}
        instance_id = int(endpoint.split("/")[-2])
        self.instances[instance_id]["actual_status"] = (
            "running" if data["state"] == "running" else "exited"
        )
        return {"success": True}

    def failover_processes(self, create_result):
        async def execute(*args, **kwargs):
            if "search" in args:
                return FakeProcess([{"id": 123, "gpu_name": "test"}])
            if "create" in args:
                return FakeProcess(create_result)
            raise AssertionError(f"Unexpected process: {args}")

        return execute

    async def test_missing_target_does_not_select_another_instance(self):
        self.instances = {99: {"id": 99, "actual_status": "running"}}
        self.assertIsNone(await self.manager.get_active_instance())

    async def test_exact_lookup_accepts_string_instance_id(self):
        self.instances[VAST_WARM_INSTANCE_ID]["id"] = str(VAST_WARM_INSTANCE_ID)
        self.assertIsNotNone(await self.manager.get_active_instance())

    async def test_instance_api_error_is_not_treated_as_empty_account(self):
        self.manager._api_request = AsyncMock(return_value={"error": "unavailable"})
        with self.assertRaisesRegex(RuntimeError, "instance list"):
            await self.manager.get_active_instance()

    async def test_stop_missing_target_does_not_stop_another_instance(self):
        self.instances = {99: {"id": 99, "actual_status": "running"}}
        await self.manager.stop_gpu()
        self.assertFalse(any(call.args[0] == "PUT" for call in self.manager._api_request.call_args_list))

    async def test_failed_creation_preserves_warm_instance(self):
        with (
            patch("bot.services.vast_lifecycle.asyncio.create_subprocess_exec", side_effect=self.failover_processes({"success": False})),
            patch("bot.services.vast_lifecycle.asyncio.create_subprocess_shell", new_callable=AsyncMock) as shell,
            patch("bot.services.vast_lifecycle.asyncio.sleep", new_callable=AsyncMock),
        ):
            shell.return_value = FakeProcess({})
            self.assertFalse(await self.manager.failover_to_fresh_dedicated_gpu(VAST_WARM_INSTANCE_ID))
            shell.assert_not_awaited()
        self.assertEqual(self.manager.current_instance_id, VAST_WARM_INSTANCE_ID)

    async def test_malformed_replacement_ids_are_rejected(self):
        for invalid_id in (True, 12.5, -1, "bad-id"):
            with self.subTest(instance_id=invalid_id), patch(
                "bot.services.vast_lifecycle.asyncio.create_subprocess_exec",
                side_effect=self.failover_processes({"new_contract": invalid_id}),
            ), patch("bot.services.vast_lifecycle.asyncio.create_subprocess_shell", new_callable=AsyncMock) as shell:
                self.assertFalse(await self.manager.failover_to_fresh_dedicated_gpu(VAST_WARM_INSTANCE_ID))
                shell.assert_not_awaited()

    async def test_failed_setup_cleans_only_unready_replacement(self):
        replacement_id = VAST_WARM_INSTANCE_ID + 1
        self.instances[replacement_id] = {**self.instances[VAST_WARM_INSTANCE_ID], "id": replacement_id}
        commands = []

        async def shell(command, **kwargs):
            commands.append(command)
            if "destroy instance" in command:
                self.instances.pop(replacement_id)
                return FakeProcess({"success": True})
            return FakeProcess({}, returncode=1)

        with (
            patch("bot.services.vast_lifecycle.asyncio.create_subprocess_exec", side_effect=self.failover_processes({"new_contract": replacement_id})),
            patch("bot.services.vast_lifecycle.asyncio.create_subprocess_shell", side_effect=shell),
            patch("bot.services.vast_lifecycle.asyncio.sleep", new_callable=AsyncMock),
        ):
            self.assertFalse(await self.manager.failover_to_fresh_dedicated_gpu(VAST_WARM_INSTANCE_ID))
        self.assertIn(VAST_WARM_INSTANCE_ID, self.instances)
        self.assertNotIn(replacement_id, self.instances)
        self.assertEqual(self.manager.current_instance_id, VAST_WARM_INSTANCE_ID)
        self.manager.ensure_tunnel.assert_not_awaited()
        self.assertFalse(any(f"destroy instance {VAST_WARM_INSTANCE_ID}" in command for command in commands))

    async def test_missing_replacement_does_not_initialize_warm_as_replacement(self):
        replacement_id = VAST_WARM_INSTANCE_ID + 1
        with (
            patch("bot.services.vast_lifecycle.asyncio.create_subprocess_exec", side_effect=self.failover_processes({"new_contract": replacement_id})),
            patch("bot.services.vast_lifecycle.asyncio.create_subprocess_shell", new_callable=AsyncMock) as shell,
            patch("bot.services.vast_lifecycle.asyncio.sleep", new_callable=AsyncMock),
        ):
            shell.return_value = FakeProcess({"success": True})
            self.assertFalse(await self.manager.failover_to_fresh_dedicated_gpu(VAST_WARM_INSTANCE_ID))
            self.assertEqual(shell.await_count, 1)
            self.assertIn(f"destroy instance {replacement_id}", shell.call_args.args[0])
        self.manager.ensure_tunnel.assert_not_awaited()
        self.assertEqual(self.manager.current_instance_id, VAST_WARM_INSTANCE_ID)

    async def test_failover_keeps_warm_instance_for_next_job(self):
        replacement_id = VAST_WARM_INSTANCE_ID + 1
        self.instances[replacement_id] = {
            **self.instances[VAST_WARM_INSTANCE_ID], "id": replacement_id
        }
        commands = []

        async def shell(command, **kwargs):
            commands.append(command)
            if "destroy instance" in command:
                instance_id = int(command.split("destroy instance ")[1].split()[0])
                self.instances.pop(instance_id, None)
            return FakeProcess({"success": True})

        with (
            patch("bot.services.vast_lifecycle.asyncio.create_subprocess_exec", side_effect=self.failover_processes({"success": True, "new_contract": replacement_id})),
            patch("bot.services.vast_lifecycle.asyncio.create_subprocess_shell", side_effect=shell),
            patch("bot.services.vast_lifecycle.asyncio.sleep", new_callable=AsyncMock),
        ):
            self.assertTrue(await self.manager.failover_to_fresh_dedicated_gpu(VAST_WARM_INSTANCE_ID))
            self.assertEqual(self.instances[VAST_WARM_INSTANCE_ID]["actual_status"], "exited")
            async with self.manager.managed_gpu():
                self.assertEqual(self.manager.current_instance_id, replacement_id)
            self.assertIn(VAST_WARM_INSTANCE_ID, self.instances)
            self.assertNotIn(replacement_id, self.instances)
            async with self.manager.managed_gpu():
                self.assertEqual(self.manager.current_instance_id, VAST_WARM_INSTANCE_ID)
        self.assertFalse(any(f"destroy instance {VAST_WARM_INSTANCE_ID}" in command for command in commands))

    async def test_nested_analysis_lease_does_not_stop_after_stems(self):
        async with self.manager.managed_gpu():
            async with self.manager.managed_gpu():
                pass
            self.assertEqual(self.manager._active_jobs, 1)
            self.assertEqual(self.instances[VAST_WARM_INSTANCE_ID]["actual_status"], "running")
        self.assertEqual(self.manager._active_jobs, 0)
        self.assertEqual(self.instances[VAST_WARM_INSTANCE_ID]["actual_status"], "exited")

    async def test_cancel_while_releasing_lease_still_releases_accounting(self):
        entered = asyncio.Event()
        release_work = asyncio.Event()

        async def job():
            async with self.manager.managed_gpu():
                entered.set()
                await release_work.wait()

        task = asyncio.create_task(job())
        await entered.wait()
        # Hold the admission lock so the lease release must wait on it.
        await self.manager._job_lock.acquire()
        release_work.set()
        for _ in range(3):
            await asyncio.sleep(0)
        task.cancel()
        self.manager._job_lock.release()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.manager._active_jobs, 0)
        self.assertFalse(self.manager.is_operating)

    async def test_manual_stop_cannot_interrupt_active_work(self):
        async with self.manager.managed_gpu():
            self.assertFalse(await self.manager.stop_gpu())
            self.assertEqual(self.instances[VAST_WARM_INSTANCE_ID]["actual_status"], "running")

    async def test_cannot_destroy_an_unowned_instance(self):
        self.manager.current_instance_id = 99
        with patch("bot.services.vast_lifecycle.asyncio.create_subprocess_shell", new_callable=AsyncMock) as shell:
            self.assertFalse(await self.manager.destroy_current_instance())
            shell.assert_not_awaited()

    async def test_failed_startup_releases_accounting(self):
        self.instances = {}
        with self.assertRaisesRegex(RuntimeError, "readiness"):
            async with self.manager.managed_gpu():
                self.fail("An unready GPU was admitted")
        self.assertEqual(self.manager._active_jobs, 0)
        self.assertFalse(self.manager.is_operating)

    async def test_new_job_waits_for_previous_shutdown(self):
        stopping = asyncio.Event()
        finish_stop = asyncio.Event()
        admitted = asyncio.Event()
        original_api = self.api_request

        async def api(method, endpoint, data=None):
            if method == "PUT" and data["state"] == "stopped":
                stopping.set()
                await finish_stop.wait()
            return await original_api(method, endpoint, data)

        self.manager._api_request.side_effect = api

        async def job(mark_admitted=False):
            async with self.manager.managed_gpu():
                if mark_admitted:
                    admitted.set()

        original_sleep = asyncio.sleep

        async def fast_sleep(*args):
            await original_sleep(0)

        with patch("bot.services.vast_lifecycle.asyncio.sleep", side_effect=fast_sleep):
            first = asyncio.create_task(job())
            await asyncio.wait_for(stopping.wait(), 1)
            second = asyncio.create_task(job(True))
            try:
                for _ in range(5):
                    await original_sleep(0)
                self.assertFalse(admitted.is_set(), "New work entered during shutdown")
            finally:
                finish_stop.set()
                await asyncio.wait_for(asyncio.gather(first, second), 1)
        self.assertTrue(admitted.is_set())

    async def test_workload_failure_is_not_masked_by_cleanup(self):
        async def api(method, endpoint, data=None):
            if method == "PUT":
                raise OSError("cleanup unavailable")
            return await self.api_request(method, endpoint, data)

        self.manager._api_request.side_effect = api
        with self.assertLogs("vast_lifecycle", level="ERROR"), self.assertRaisesRegex(ValueError, "workload failed"):
            async with self.manager.managed_gpu():
                raise ValueError("workload failed")
        self.assertEqual(self.manager._active_jobs, 0)

    async def test_cancelled_shutdown_still_blocks_new_admission(self):
        stopping = asyncio.Event()
        finish_stop = asyncio.Event()
        admitted = asyncio.Event()
        original_api = self.api_request

        async def api(method, endpoint, data=None):
            if method == "PUT" and data["state"] == "stopped":
                stopping.set()
                await finish_stop.wait()
            return await original_api(method, endpoint, data)

        self.manager._api_request.side_effect = api

        async def first_job():
            async with self.manager.managed_gpu():
                pass

        async def next_job():
            async with self.manager.managed_gpu():
                admitted.set()

        original_sleep = asyncio.sleep

        async def fast_sleep(*args):
            await original_sleep(0)

        with patch("bot.services.vast_lifecycle.asyncio.sleep", side_effect=fast_sleep):
            first = asyncio.create_task(first_job())
            await asyncio.wait_for(stopping.wait(), 1)
            first.cancel()
            for _ in range(3):
                await original_sleep(0)
            second = asyncio.create_task(next_job())
            try:
                for _ in range(5):
                    await original_sleep(0)
                self.assertFalse(admitted.is_set(), "Cancellation released admission before shutdown ended")
            finally:
                finish_stop.set()
                with self.assertRaises(asyncio.CancelledError):
                    await first
                await asyncio.wait_for(second, 1)


if __name__ == "__main__":
    unittest.main()
