"""Container ledger and cost model: pure arithmetic, no network."""

import os
import tempfile
import unittest
from unittest.mock import patch

from bot.services import container_ledger as ledger
from bot.services import gpu_cost

NOW = 1_800_000_000.0  # a fixed instant; the UTC day containing it starts before NOW


class FakeStore(dict):
    def put(self, key, value):
        self[key] = value

    def pop(self, key, default=None):
        return super().pop(key, default)


def booted(store, cid="a", ready_after=27, at=NOW - 1000):
    ledger.start_container(store, cid, at)
    ledger.watcher_step(store, cid, {"ready": True, "busy": False, "last_activity_at": None}, at + ready_after)
    # A fresh heartbeat, so the container counts as live at NOW.
    ledger.watcher_step(store, cid, {"ready": True, "busy": False, "last_activity_at": None}, NOW - 1)
    return cid


class TestRelease(unittest.TestCase):
    def test_idle_ready_container_is_released(self):
        store = FakeStore()
        cid = booted(store)
        ledger.watcher_step(store, cid, {"ready": True, "busy": False, "last_activity_at": NOW - 100}, NOW - 5)
        result = ledger.request_release(store, NOW, min_idle_seconds=20)
        self.assertEqual(result["released"], [cid])

    def test_busy_container_is_never_released(self):
        store = FakeStore()
        cid = booted(store)
        ledger.watcher_step(store, cid, {"ready": True, "busy": True, "last_activity_at": NOW - 100}, NOW - 1)
        result = ledger.request_release(store, NOW, min_idle_seconds=0)
        self.assertEqual(result["released"], [])
        self.assertEqual(result["busy"], [cid])

    def test_recently_active_container_is_left_warm(self):
        store = FakeStore()
        cid = booted(store)
        ledger.watcher_step(store, cid, {"ready": True, "busy": False, "last_activity_at": NOW - 3}, NOW - 1)
        self.assertEqual(ledger.request_release(store, NOW, min_idle_seconds=20)["released"], [])

    def test_booting_container_is_not_released(self):
        store = FakeStore()
        ledger.start_container(store, "a", NOW - 10)
        self.assertEqual(ledger.request_release(store, NOW, min_idle_seconds=0)["released"], [])

    def test_stale_heartbeat_means_not_live_and_nothing_to_release(self):
        store = FakeStore()
        booted(store)
        later = NOW + ledger.HEARTBEAT_STALE_SECONDS + 1
        self.assertEqual(ledger.request_release(store, later, 0), {"released": [], "busy": [], "live": 0})

    def test_container_exits_only_after_a_release_and_when_idle(self):
        store = FakeStore()
        cid = booted(store)
        idle = {"ready": True, "busy": False, "last_activity_at": NOW - 100}
        self.assertFalse(ledger.watcher_step(store, cid, idle, NOW))
        ledger.request_release(store, NOW, 20)
        self.assertTrue(ledger.watcher_step(store, cid, idle, NOW + 1))
        self.assertEqual(store[ledger.container_key(cid)]["exited_at"], NOW + 1)

    def test_work_after_the_request_cancels_it(self):
        store = FakeStore()
        cid = booted(store)
        ledger.request_release(store, NOW, 0)
        arrived = {"ready": True, "busy": False, "last_activity_at": NOW + 2}
        self.assertFalse(ledger.watcher_step(store, cid, arrived, NOW + 3))
        self.assertNotIn(ledger.release_key(cid), store)

    def test_busy_container_ignores_a_normal_request_but_obeys_force(self):
        store = FakeStore()
        cid = booted(store)
        busy = {"ready": True, "busy": True, "last_activity_at": NOW - 1}
        ledger.watcher_step(store, cid, busy, NOW - 1)
        ledger.request_release(store, NOW, 0)
        self.assertEqual(store.get(ledger.release_key(cid)), None)
        ledger.request_release(store, NOW, 0, force=True)
        self.assertTrue(ledger.watcher_step(store, cid, busy, NOW + 1))

    def test_old_records_are_pruned(self):
        store = FakeStore()
        for index in range(ledger.MAX_RECORDS + 5):
            ledger.start_container(store, f"c{index}", NOW + index)
        records = ledger.container_records(store)
        self.assertEqual(len(records), ledger.MAX_RECORDS)
        self.assertNotIn("c0", records)


class TestCostModel(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in ("MODAL_GPU_RATE_PER_SECOND", "MODAL_GPU_TYPE", "MODAL_SCALEDOWN_SECONDS", "MODAL_DAILY_CAP_USD", "MODAL_CPU", "MODAL_MEMORY_MB"):
            os.environ.pop(key, None)

    # Default container: 4 cores and 8 GiB on top of the GPU.
    OVERHEAD = 4 * 0.0000131 + 8 * 0.00000222

    def test_rate_is_gpu_plus_cpu_plus_memory(self):
        self.assertAlmostEqual(gpu_cost.rate_per_second("L4"), 0.80 / 3600 + self.OVERHEAD)

    def test_cpu_and_memory_follow_the_deployed_size(self):
        os.environ.update(MODAL_CPU="1", MODAL_MEMORY_MB="1024")
        self.assertAlmostEqual(gpu_cost.rate_per_second("L4"), 0.80 / 3600 + 0.0000131 + 0.00000222)

    def test_unknown_gpu_is_priced_as_the_most_expensive(self):
        expected = max(gpu_cost.GPU_DOLLARS_PER_HOUR.values()) / 3600 + self.OVERHEAD
        self.assertAlmostEqual(gpu_cost.rate_per_second("QuantumX"), expected)

    def test_gpu_count_multiplies_only_the_gpu_part(self):
        self.assertAlmostEqual(gpu_cost.rate_per_second("H100:2"), 2 * 3.95 / 3600 + self.OVERHEAD)

    def test_rate_override_wins(self):
        os.environ["MODAL_GPU_RATE_PER_SECOND"] = "0.5"
        self.assertEqual(gpu_cost.rate_per_second("L4"), 0.5)

    def test_exited_container_is_billed_for_its_whole_life(self):
        record = {"started_at": NOW - 200, "exited_at": NOW - 100, "heartbeat_at": NOW - 100}
        self.assertEqual(gpu_cost.container_billable_seconds(record, NOW, NOW - 10_000, 60), 100)

    def test_live_busy_container_is_charged_a_full_idle_tail_up_front(self):
        record = {"started_at": NOW - 100, "heartbeat_at": NOW, "busy": True, "ready_at": NOW - 70,
                  "last_activity_at": NOW}
        self.assertEqual(gpu_cost.container_billable_seconds(record, NOW, NOW - 10_000, 60), 100 + 60)

    def test_live_idle_container_is_charged_only_the_tail_that_is_left(self):
        record = {"started_at": NOW - 100, "heartbeat_at": NOW, "busy": False, "ready_at": NOW - 70,
                  "last_activity_at": NOW - 25}
        self.assertEqual(gpu_cost.container_billable_seconds(record, NOW, NOW - 10_000, 60), 100 + 35)

    def test_only_todays_seconds_count(self):
        day_start = gpu_cost.utc_day_start(NOW)
        record = {"started_at": day_start - 500, "exited_at": day_start + 100, "heartbeat_at": day_start + 100}
        self.assertEqual(gpu_cost.container_billable_seconds(record, NOW, day_start, 60), 100)

    def test_job_is_refused_before_it_starts_when_it_cannot_fit(self):
        with self.assertRaises(gpu_cost.BudgetExceeded):
            gpu_cost.check_admission(spent=1.95, projected=0.05, cap=2.00)
        gpu_cost.check_admission(spent=1.0, projected=0.05, cap=2.00)

    def test_running_job_is_cancelled_at_95_percent(self):
        self.assertFalse(gpu_cost.over_cancel_threshold(1.89, 2.00))
        self.assertTrue(gpu_cost.over_cancel_threshold(1.90, 2.00))

    def test_summary_reports_measured_terms_and_break_even_window(self):
        containers = [
            {"started_at": 1000, "ready_at": 1027, "last_activity_at": 1100, "exited_at": 1134, "heartbeat_at": 1134},
            {"started_at": 1500, "ready_at": 1530, "last_activity_at": 1600, "exited_at": 1640, "heartbeat_at": 1640},
        ]
        summary = gpu_cost.summarize(containers, [{"work_s": 70.0}], rate=0.001)
        self.assertEqual(summary["median_cold_start_s"], 28.5)
        self.assertEqual(summary["median_idle_tail_s"], 37)
        self.assertEqual(summary["container_seconds"], 134 + 140)
        self.assertEqual(summary["suggested_scaledown_s"], 28)
        self.assertAlmostEqual(summary["estimated_cost_usd"], 0.274)

    def test_lease_ledger_round_trip_for_the_fallback_estimate(self):
        with tempfile.TemporaryDirectory() as directory:
            leases = gpu_cost.LeaseLedger(os.path.join(directory, "x", "leases.jsonl"))
            leases.append({"ended_at": NOW, "cold_start_s": 10, "work_s": 30, "tail_s": 60})
            self.assertEqual(gpu_cost.spend_from_leases(leases.read(), rate=0.01), 1.0)


if __name__ == "__main__":
    unittest.main()
