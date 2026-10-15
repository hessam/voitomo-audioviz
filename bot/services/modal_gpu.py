"""Modal GPU backend.

The bot calls the deployed GPU endpoint (modal_gpu_app.py) for work and a small CPU
control endpoint for everything that must not start hardware: status, budget checks
and release. Modal starts the GPU container on the first GPU request and scales it
to zero when idle; the bot also releases it explicitly after a quiet period.
"""
import os
import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from bot.services import gpu_cost
from bot.services.gpu_cost import BudgetExceeded

logger = logging.getLogger("modal_gpu")

COLD_START_TIMEOUT_SECONDS = int(os.environ.get("MODAL_COLD_START_TIMEOUT_SECONDS", "600"))
# Quiet time after the last lease before the bot asks the control endpoint to release.
# Starting value, not a measurement: tune it against `python3 -m bot.services.modal_gpu`.
RELEASE_QUIET_SECONDS = float(os.environ.get("MODAL_RELEASE_QUIET_SECONDS", "20"))
BUDGET_CHECK_SECONDS = 30
BILLING_CACHE_SECONDS = 600
HEALTH_POLL_SECONDS = 5


def modal_base_url() -> str:
    url = os.environ.get("MODAL_GPU_URL", "").strip().rstrip("/")
    if not url:
        raise RuntimeError("MODAL_GPU_URL is not set. Deploy modal_gpu_app.py and set the printed URL.")
    return url


def control_base_url() -> Optional[str]:
    return os.environ.get("MODAL_CONTROL_URL", "").strip().rstrip("/") or None


def modal_request_headers() -> Dict[str, str]:
    token_id = os.environ.get("MODAL_PROXY_TOKEN_ID", "").strip()
    token_secret = os.environ.get("MODAL_PROXY_TOKEN_SECRET", "").strip()
    if not token_id or not token_secret:
        raise RuntimeError("MODAL_PROXY_TOKEN_ID and MODAL_PROXY_TOKEN_SECRET must be set for the Modal GPU.")
    return {"Modal-Key": token_id, "Modal-Secret": token_secret}


class ModalGpuManager:
    _instance = None

    def __init__(self):
        self._active = 0
        self._running: Dict[str, float] = {}
        self._release_task: Optional[asyncio.Task] = None
        self._billing_cache = (0.0, None)

    @classmethod
    def get_instance(cls) -> "ModalGpuManager":
        if cls._instance is None:
            cls._instance = ModalGpuManager()
        return cls._instance

    def start_reaper(self) -> None:
        # Idle shutdown is the container watcher's job plus Modal's scaledown window.
        logger.info("Modal GPU selected; idle shutdown is handled by the container and Modal.")

    def record_activity(self) -> None:
        return None

    # --- CPU control endpoint (never starts the GPU) -------------------------------

    async def _control(self, method: str, path: str, payload: Optional[dict] = None) -> Optional[dict]:
        base = control_base_url()
        if not base:
            return None
        import aiohttp

        try:
            async with aiohttp.ClientSession(headers=modal_request_headers()) as session:
                async with session.request(
                    method, f"{base}{path}", json=payload, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status in (401, 403):
                        raise RuntimeError(
                            f"Modal rejected the proxy token (HTTP {resp.status}). "
                            "Check MODAL_PROXY_TOKEN_ID and MODAL_PROXY_TOKEN_SECRET."
                        )
                    if resp.status != 200:
                        return None
                    return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError):
            return None

    async def _ledger(self) -> Optional[dict]:
        return await self._control("GET", "/ledger")

    async def _release(self, min_idle: float, force: bool = False) -> Optional[dict]:
        return await self._control("POST", "/release", {"min_idle_seconds": min_idle, "force": force})

    # --- cost model ---------------------------------------------------------------

    async def _billed_today(self) -> Optional[float]:
        """The provider's own bill, when reconciliation is enabled (needs the modal package)."""
        if os.environ.get("MODAL_BILLING_RECONCILE", "") != "1":
            return None
        cached_at, cached = self._billing_cache
        if time.time() - cached_at < BILLING_CACHE_SECONDS:
            return cached

        def fetch() -> Optional[float]:
            from datetime import datetime, timezone
            import modal

            start = datetime.fromtimestamp(gpu_cost.utc_day_start(time.time()), tz=timezone.utc)
            items = modal.billing.workspace_billing_report(start=start, resolution="d")
            app = os.environ.get("MODAL_APP_NAME", "audioviz-gpu")
            ours = [i for i in items if app in str(i.get("description", ""))]
            # Unsure which rows are ours: count the whole workspace (the higher number).
            return float(sum(i["cost"] for i in (ours or items)))

        try:
            billed = await asyncio.to_thread(fetch)
        except Exception as e:
            logger.warning("Modal bill reconciliation unavailable: %s", e)
            billed = None
        self._billing_cache = (time.time(), billed)
        return billed

    async def _spend_today(self, ledger: Optional[dict] = None) -> float:
        rate = gpu_cost.rate_per_second()
        scaledown = gpu_cost.scaledown_seconds()
        ledger = ledger if ledger is not None else await self._ledger()
        if ledger is not None:
            estimate = gpu_cost.spend_from_containers(
                ledger["containers"].values(), ledger["now"], rate, scaledown
            )
        else:
            now = time.time()
            leases = gpu_cost.LeaseLedger().read(since=gpu_cost.utc_day_start(now))
            estimate = gpu_cost.spend_from_leases(leases, rate)
            estimate += sum(rate * (now - start + scaledown) for start in self._running.values())
        billed = await self._billed_today()
        return max(estimate, billed or 0.0)

    def _cold_start_estimate(self, ledger: Optional[dict]) -> float:
        if ledger:
            summary = gpu_cost.summarize(list(ledger["containers"].values()), [], 0.0)
            if summary["median_cold_start_s"]:
                return summary["median_cold_start_s"]
        return gpu_cost.DEFAULT_COLD_START_SECONDS

    async def _admit(self) -> None:
        """Refuse the job before it starts if it cannot fit under the daily cap."""
        ledger = await self._ledger()
        spent = await self._spend_today(ledger)
        projected = 0.0
        if not self._active:
            warm = ledger is not None and bool(_live(ledger))
            if not warm:
                projected = gpu_cost.projected_new_container_cost(
                    gpu_cost.rate_per_second(),
                    self._cold_start_estimate(ledger),
                    gpu_cost.scaledown_seconds(),
                )
        gpu_cost.check_admission(spent, projected, gpu_cost.daily_cap_usd())

    async def _watch_budget(self, host: asyncio.Task, breach: Dict[str, Any]) -> None:
        while True:
            await asyncio.sleep(BUDGET_CHECK_SECONDS)
            try:
                spent = await self._spend_today()
                if gpu_cost.over_cancel_threshold(spent, gpu_cost.daily_cap_usd()):
                    breach.update(hit=True, spent=spent)
                    # Cancelling our wait does not stop the container, so stop it too.
                    await self._release(0, force=True)
                    host.cancel()
                    return
            except Exception:
                logger.exception("Budget check failed; will retry.")

    # --- readiness and leases -----------------------------------------------------

    async def _is_healthy(self, url: str, headers: Dict[str, str]) -> bool:
        import aiohttp

        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(f"{url}/ai/health", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status in (401, 403):
                        raise RuntimeError(
                            f"Modal rejected the proxy token (HTTP {resp.status}). "
                            "Check MODAL_PROXY_TOKEN_ID and MODAL_PROXY_TOKEN_SECRET."
                        )
                    return resp.status == 200
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
            return False

    async def _wait_ready(self, status_callback=None) -> bool:
        url = modal_base_url()
        headers = modal_request_headers()
        deadline = time.monotonic() + COLD_START_TIMEOUT_SECONDS
        notified = False
        while True:
            if await self._is_healthy(url, headers):
                return True
            if time.monotonic() >= deadline:
                logger.error("Modal GPU did not become healthy within %ds.", COLD_START_TIMEOUT_SECONDS)
                return False
            if status_callback and not notified:
                await status_callback(
                    "⚡ **Starting Modal GPU...** The first job after idle can take a few minutes."
                )
                notified = True
            await asyncio.sleep(HEALTH_POLL_SECONDS)

    async def ensure_gpu_ready(self, status_callback=None) -> bool:
        """Wake the GPU (budget-checked). Used by the /gpu wake button."""
        await self._admit()
        return await self._wait_ready(status_callback)

    @asynccontextmanager
    async def managed_gpu(self, status_callback=None):
        self._cancel_pending_release()
        await self._admit()
        outermost = self._active == 0
        self._active += 1
        lease_id = uuid.uuid4().hex
        started = time.time()
        if outermost:
            self._running[lease_id] = started
        host = asyncio.current_task()
        breach: Dict[str, Any] = {"hit": False}
        watchdog = (
            asyncio.create_task(self._watch_budget(host, breach)) if outermost and host else None
        )
        work_started = started
        try:
            if not await self._wait_ready(status_callback):
                raise RuntimeError("Failed to ensure GPU readiness.")
            work_started = time.time()
            yield modal_base_url()
        except asyncio.CancelledError:
            if breach["hit"]:
                host.uncancel()
                raise BudgetExceeded(
                    f"Stopped at 95% of the daily GPU cap (${breach['spent']:.3f} of "
                    f"${gpu_cost.daily_cap_usd():.2f})."
                ) from None
            raise
        finally:
            if watchdog:
                watchdog.cancel()
            self._active -= 1
            if outermost:
                self._running.pop(lease_id, None)
                ended = time.time()
                try:
                    gpu_cost.LeaseLedger().append({
                        "started_at": started,
                        "ended_at": ended,
                        "cold_start_s": max(0.0, work_started - started),
                        "work_s": max(0.0, ended - work_started),
                        "tail_s": gpu_cost.scaledown_seconds(),
                    })
                except OSError:
                    logger.exception("Could not write the GPU lease ledger.")
                self._schedule_release()

    # --- release ------------------------------------------------------------------

    def _cancel_pending_release(self) -> None:
        if self._release_task and not self._release_task.done():
            self._release_task.cancel()
        self._release_task = None

    def _schedule_release(self) -> None:
        if not control_base_url():
            return
        self._release_task = asyncio.create_task(self._release_after_quiet())

    async def _release_after_quiet(self) -> None:
        await asyncio.sleep(RELEASE_QUIET_SECONDS)
        if self._active == 0:
            result = await self._release(RELEASE_QUIET_SECONDS)
            logger.info("Quiet-period GPU release: %s", result)

    async def stop_gpu(self, instance_id=None) -> bool:
        """Release now. True when nothing is left running; False when a job still holds it."""
        if self._active:
            return False
        self._cancel_pending_release()
        result = await self._release(0)
        if result is None:
            logger.info("No control endpoint; Modal will scale the GPU down on its own.")
            return True
        return not result["busy"]

    # --- status (CPU only) --------------------------------------------------------

    async def status_text(self) -> str:
        if not control_base_url():
            return (
                "ℹ️ **Modal GPU status needs `MODAL_CONTROL_URL`.** Checking the GPU "
                "endpoint directly would start it and bill you."
            )
        try:
            ledger = await self._ledger()
        except RuntimeError as e:
            return f"❌ **Modal GPU is not usable:** {e}"
        if ledger is None:
            return "⚠️ **Modal control endpoint is unreachable.** The GPU state is unknown."
        live = _live(ledger)
        spent = await self._spend_today(ledger)
        cold = self._cold_start_estimate(ledger)
        if not live:
            state = "OFF (starts on the next job)"
        else:
            record = live[0]
            if record.get("busy"):
                state = "RUNNING (busy)"
            else:
                active_at = record.get("last_activity_at") or record.get("ready_at") or ledger["now"]
                state = f"RUNNING (idle {int(ledger['now'] - active_at)}s)"
        return (
            f"☁️ **Modal GPU Status:** `{state}`\n"
            f"• **Today:** ${spent:.3f} of ${gpu_cost.daily_cap_usd():.2f} cap (estimate)\n"
            f"• **Cold start:** about {int(cold)}s after idle\n"
            f"• **Idle window:** {int(gpu_cost.scaledown_seconds())}s; released after "
            f"{int(RELEASE_QUIET_SECONDS)}s of quiet"
        )


def _live(ledger: dict) -> list:
    from bot.services.container_ledger import is_live

    return [rec for rec in ledger["containers"].values() if is_live(rec, ledger["now"])]


async def _report() -> Dict[str, Any]:
    manager = ModalGpuManager()
    ledger = await manager._ledger()
    if ledger is None:
        raise SystemExit("Control endpoint unreachable; set MODAL_CONTROL_URL and the proxy tokens.")
    now = ledger["now"]
    leases = gpu_cost.LeaseLedger().read(since=gpu_cost.utc_day_start(now))
    containers = [
        rec for rec in ledger["containers"].values()
        if (rec.get("exited_at") or rec.get("heartbeat_at") or 0) >= gpu_cost.utc_day_start(now)
    ]
    summary = gpu_cost.summarize(containers, leases, gpu_cost.rate_per_second())
    summary["spend_today_usd"] = await manager._spend_today(ledger)
    summary["daily_cap_usd"] = gpu_cost.daily_cap_usd()
    return summary


if __name__ == "__main__":
    print(json.dumps(asyncio.run(_report()), indent=2))
