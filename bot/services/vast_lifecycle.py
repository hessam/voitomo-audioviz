import os
import time
import json
import asyncio
import logging
import subprocess
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger("vast_lifecycle")

VAST_API_KEY = os.environ.get("VAST_API_KEY", "")
VAST_WARM_INSTANCE_ID = int(os.environ.get("VAST_WARM_INSTANCE_ID", "52169289"))
IDLE_TIMEOUT_SECONDS = int(os.environ.get("GPU_IDLE_TIMEOUT_SECONDS", "900"))  # 15 minutes safety fallback
GPU_TUNNEL_PORT = 4002
GPU_TARGET_PORT = 4001

class VastLifecycleManager:
    _instance = None

    def __init__(self):
        self.last_active_time = time.time()
        self.is_operating = False
        self.current_instance_id: int = VAST_WARM_INSTANCE_ID
        self.cached_instance_id: Optional[str] = str(VAST_WARM_INSTANCE_ID)
        self._reaper_task: Optional[asyncio.Task] = None
        self._active_jobs = 0
        self._job_lock = asyncio.Lock()
        self._gpu_ready = False
        self._ephemeral_instance_ids = set()
        self._tunnel_target = None

    @classmethod
    def get_instance(cls) -> "VastLifecycleManager":
        if cls._instance is None:
            cls._instance = VastLifecycleManager()
        return cls._instance

    def start_reaper(self):
        """Starts the background idle watchdog loop."""
        if self._reaper_task is None or self._reaper_task.done():
            self._reaper_task = asyncio.create_task(self._idle_reaper_loop())
            logger.info("🛡️ Vast GPU on-demand idle reaper initialized (timeout: %ds)", IDLE_TIMEOUT_SECONDS)

    def record_activity(self):
        """Resets the idle timer on new user activity."""
        self.last_active_time = time.time()
        logger.info("⏱️ GPU activity recorded; idle timer reset to %ds.", IDLE_TIMEOUT_SECONDS)

    async def _api_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        import aiohttp

        url = f"https://console.vast.ai/api/{endpoint}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {VAST_API_KEY}"
        }
        async with aiohttp.ClientSession() as session:
            kwargs: Dict[str, Any] = {"headers": headers, "timeout": aiohttp.ClientTimeout(total=30)}
            if data is not None:
                kwargs["json"] = data
            async with session.request(method, url, **kwargs) as resp:
                text = await resp.text()
                try:
                    return json.loads(text)
                except Exception:
                    return {"raw": text, "status_code": resp.status}

    async def get_active_instance(self, instance_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        target_id = instance_id or self.current_instance_id or VAST_WARM_INSTANCE_ID
        res = await self._api_request("GET", "v1/instances/")
        instances = res.get("instances")
        if not isinstance(instances, list):
            raise RuntimeError("Could not retrieve the Vast instance list.")
        if not instances:
            return None
        for inst in instances:
            if str(inst.get("id")) == str(target_id):
                return inst
        return None

    async def ensure_remote_services(self, host: str, port: int) -> bool:
        """Invokes start_services.sh on the remote GPU instance via SSH."""
        logger.info(f"🚀 Ensuring remote GPU services are running on {host}:{port}...")
        cmd = [
            "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ConnectTimeout=10",
            "-p", str(port),
            f"root@{host}",
            "/root/audioviz/start_services.sh"
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        try:
            await asyncio.wait_for(proc.wait(), timeout=15)
            return proc.returncode == 0
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return False

    async def ensure_tunnel(self, host: str, port: int) -> bool:
        """Ensures the SSH tunnel port 4002 points to the active Vast instance."""
        import aiohttp

        target = (host, port)
        # Check if tunnel is alive and healthy
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{GPU_TUNNEL_PORT}/ai/health", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200 and self._tunnel_target == target:
                        return True
        except Exception:
            pass

        # Trigger remote services startup on the GPU
        await self.ensure_remote_services(host, port)

        logger.info(f"🔌 Rebuilding GPU SSH tunnel: {GPU_TUNNEL_PORT} -> {host}:{port}...")
        # Kill old tunnel
        subprocess.run(["pkill", "-9", "-f", f"ssh.*{GPU_TUNNEL_PORT}"], capture_output=True)
        await asyncio.sleep(1)

        # Spawn fresh tunnel
        cmd = [
            "nohup", "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=15",
            "-o", "ExitOnForwardFailure=yes",
            "-N", "-L", f"{GPU_TUNNEL_PORT}:127.0.0.1:{GPU_TARGET_PORT}",
            "-p", str(port),
            f"root@{host}"
        ]
        subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
        
        # Verify tunnel comes up
        for attempt in range(25):
            await asyncio.sleep(1)
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"http://127.0.0.1:{GPU_TUNNEL_PORT}/ai/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                        if resp.status == 200:
                            self._tunnel_target = target
                            logger.info("✅ GPU SSH tunnel verified healthy on port %d", GPU_TUNNEL_PORT)
                            return True
            except Exception:
                if attempt == 10:
                    await self.ensure_remote_services(host, port)
                continue
        logger.warning("⚠️ GPU SSH tunnel did not respond within 25s.")
        return False

    async def ensure_gpu_ready(self, status_callback=None) -> bool:
        async with self._job_lock:
            if self._active_jobs:
                return self._gpu_ready
            self._gpu_ready = await self._ensure_gpu_ready(status_callback)
            return self._gpu_ready

    async def _ensure_gpu_ready(self, status_callback=None) -> bool:
        """Wakes up the GPU instance if stopped, connects the tunnel, and waits for health."""
        self.record_activity()
        inst = await self.get_active_instance()
        if not inst:
            logger.warning("No Vast instance found. Manual provisioning required.")
            return False

        inst_id = inst.get("id")
        self.cached_instance_id = str(inst_id)
        status = inst.get("actual_status")
        ssh_host = inst.get("ssh_host") or inst.get("public_ipaddr")
        ssh_port = inst.get("ssh_port") or inst.get("ports", {}).get("22/tcp", [{}])[0].get("HostPort")

        if status == "running" and ssh_host and ssh_port:
            healthy = await self.ensure_tunnel(ssh_host, int(ssh_port))
            if healthy:
                return True

        # Need to wake up instance
        if status_callback:
            await status_callback("⚡ **Waking on-demand GPU instance...** Waiting for GPU boot (up to 5 min)...")

        logger.info(f"🚀 Waking Vast GPU instance {inst_id}...")
        wake_res = await self._api_request("PUT", f"v0/instances/{inst_id}/", {"state": "running"})
        logger.info("Wake request response: %s", wake_res)

        # Check for immediate resources_unavailable
        if wake_res.get("error") == "resources_unavailable" or (wake_res.get("success") is False and "resource" in str(wake_res).lower()):
            logger.warning("⚠️ Host reports resources unavailable! Triggering dedicated EU GPU failover...")
            if status_callback:
                await status_callback("⚠️ Primary host slot occupied. Finding fresh dedicated EU GPU...")
            return await self._failover_to_fresh_dedicated_gpu(inst_id, status_callback=status_callback)

        # Poll until running with open port (up to 300 seconds / 5 minutes)
        start_t = time.time()
        last_callback_t = start_t
        while time.time() - start_t < 300:
            await asyncio.sleep(3)
            elapsed = int(time.time() - start_t)
            if status_callback and (time.time() - last_callback_t) >= 15:
                await status_callback(f"⚡ **Waiting for GPU boot & CUDA initialization...** ({elapsed}s / 300s)")
                last_callback_t = time.time()

            inst = await self.get_active_instance()
            if not inst:
                break
            st = inst.get("actual_status")
            ssh_host = inst.get("ssh_host") or inst.get("public_ipaddr")
            ssh_port = inst.get("ssh_port") or inst.get("ports", {}).get("22/tcp", [{}])[0].get("HostPort")
            if st == "running" and ssh_host and ssh_port:
                logger.info(f"✨ Instance {inst_id} is running at {ssh_host}:{ssh_port}. Establishing tunnel...")
                self.record_activity()
                ready = await self.ensure_tunnel(ssh_host, int(ssh_port))
                if ready:
                    return True

            # Automatic failover if primary host is contested or stalls past 45s
            if elapsed > 45 and st != "running":
                logger.warning(f"⚠️ GPU instance {inst_id} stalled in state {st} (>45s). Triggering auto-recovery...")
                if status_callback:
                    await status_callback("⚠️ GPU wake delayed beyond 45s. Triggering automatic failover...")
                return await self._failover_to_fresh_dedicated_gpu(inst_id, status_callback=status_callback)

        logger.error(f"Failed to bring GPU instance {inst_id} online within 300s (5 minutes).")
        return False

    async def failover_to_fresh_dedicated_gpu(self, old_instance_id: Optional[int] = None, status_callback=None) -> bool:
        async with self._job_lock:
            if self._active_jobs:
                logger.warning("Cannot replace a GPU while workloads are active.")
                return False
            self._gpu_ready = await self._failover_to_fresh_dedicated_gpu(old_instance_id, status_callback)
            return self._gpu_ready

    async def _failover_to_fresh_dedicated_gpu(self, old_instance_id: Optional[int] = None, status_callback=None) -> bool:
        """Provision a replacement while retaining the warm instance for later jobs."""
        logger.info("🔄 Initiating automatic failover for dedicated EU GPU...")
        vast_bin = "/root/workspace/.venv/bin/vastai"
        if not os.path.exists(vast_bin):
            vast_bin = "vastai"

        # Search top verified dedicated RTX offer in EU
        query = "verified=true rentable=true num_gpus=1 gpu_frac=1.0 gpu_name in [RTX_3080,RTX_3090,RTX_4070,RTX_4080,RTX_4090,RTX_A4000,RTX_A4500,RTX_A5000] dph<=0.35 geolocation in [DE,CZ,PL,FR,NL,ES,AT,CH,IT,SE,NO,FI,DK,BE,GB]"
        cmd = [vast_bin, "search", "offers", "-d", "-n", query, "-o", "score-", "--raw"]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        try:
            offers = json.loads(stdout.decode())
        except Exception as e:
            logger.error("Failed to parse search offers: %s", e)
            offers = []

        if proc.returncode != 0 or not isinstance(offers, list) or not offers:
            logger.error("No dedicated EU offers found matching criteria.")
            return False

        best_offer = offers[0]
        offer_id = best_offer.get("id") or best_offer.get("ask_contract_id")
        logger.info(f"🎯 Selected replacement EU offer {offer_id} ({best_offer.get('gpu_name')}, {best_offer.get('geolocation')})")
        if status_callback:
            await status_callback(f"🚀 Provisioning replacement dedicated GPU ({best_offer.get('gpu_name')} in {best_offer.get('geolocation')})...")

        # Create replacement instance
        create_cmd = [
            vast_bin, "create", "instance", str(offer_id),
            "--image", "nvidia/cuda:12.4.1-devel-ubuntu22.04",
            "--disk", "35",
            "--ssh", "--direct",
            "--raw"
        ]
        cproc = await asyncio.create_subprocess_exec(*create_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        c_out, _ = await cproc.communicate()
        try:
            c_json = json.loads(c_out.decode())
            raw_id = c_json.get("new_contract") or c_json.get("id")
            if not isinstance(raw_id, (int, str)) or isinstance(raw_id, bool) or not str(raw_id).isdigit():
                raise ValueError("Invalid replacement ID")
            new_inst_id = int(raw_id)
            if cproc.returncode != 0 or c_json.get("success") is False or new_inst_id <= 0:
                raise ValueError("Replacement creation failed")
        except (ValueError, TypeError, AttributeError):
            logger.error("Replacement creation failed; retaining the warm GPU.")
            return False
        if new_inst_id == VAST_WARM_INSTANCE_ID or new_inst_id == old_instance_id:
            logger.error("Replacement creation returned the existing instance ID.")
            return False

        self._ephemeral_instance_ids.add(new_inst_id)

        try:
            ready = await self._initialize_replacement(new_inst_id, status_callback)
            if ready and old_instance_id:
                try:
                    if old_instance_id == VAST_WARM_INSTANCE_ID:
                        if not await self._stop_gpu(old_instance_id):
                            logger.error("Warm standby stop was not confirmed.")
                    elif old_instance_id in self._ephemeral_instance_ids:
                        await self._destroy_ephemeral_instance(old_instance_id)
                except Exception:
                    logger.exception("Failed to release previous owned GPU %s", old_instance_id)
            return ready
        finally:
            if self.current_instance_id != new_inst_id:
                try:
                    await self._destroy_ephemeral_instance(new_inst_id)
                except Exception:
                    logger.exception("Failed to clean up unready replacement %s", new_inst_id)

    async def _initialize_replacement(self, new_inst_id: int, status_callback=None) -> bool:

        # Poll for new instance to be ready
        for _ in range(60):
            await asyncio.sleep(5)
            inst = await self.get_active_instance(new_inst_id)
            if not inst:
                continue
            st = inst.get("actual_status")
            ssh_host = inst.get("ssh_host") or inst.get("public_ipaddr")
            ssh_port = inst.get("ssh_port") or inst.get("ports", {}).get("22/tcp", [{}])[0].get("HostPort")
            if st == "running" and ssh_host and ssh_port:
                logger.info(f"✨ New instance {inst.get('id')} running at {ssh_host}:{ssh_port}! Running initial setup...")
                if status_callback:
                    await status_callback("📦 Initializing renderer & AI models on fresh GPU...")
                setup_cmd = f"ssh -o StrictHostKeyChecking=no -p {ssh_port} root@{ssh_host} 'mkdir -p /root/audioviz /root/workspace && ln -s /root/audioviz/video_profiles /root/workspace/video_profiles 2>/dev/null || true' && tar -czf - -C /root/audioviz renderer video_profiles vast_ai_service.py | ssh -o StrictHostKeyChecking=no -p {ssh_port} root@{ssh_host} 'tar -xzf - -C /root/audioviz' && scp -o StrictHostKeyChecking=no -P {ssh_port} /root/setup_gpu.sh root@{ssh_host}:/root/setup_gpu.sh && ssh -o StrictHostKeyChecking=no -p {ssh_port} root@{ssh_host} 'chmod +x /root/setup_gpu.sh && /root/setup_gpu.sh'"
                sproc = await asyncio.create_subprocess_shell(setup_cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                await sproc.communicate()
                if sproc.returncode != 0:
                    logger.error("Replacement setup failed for instance %s", new_inst_id)
                    return False
                if await self.ensure_tunnel(ssh_host, int(ssh_port)):
                    self.current_instance_id = new_inst_id
                    self.cached_instance_id = str(new_inst_id)
                    return True
                return False

        return False

    @asynccontextmanager
    async def managed_gpu(self, status_callback=None):
        """Share a ready GPU lease; serialize admission against startup and shutdown."""
        admitted = False
        try:
            async with self._job_lock:
                self._active_jobs += 1
                admitted = True
                self.is_operating = True
                if not self._gpu_ready:
                    self._gpu_ready = await self._ensure_gpu_ready(status_callback)
                if not self._gpu_ready:
                    raise RuntimeError("Failed to ensure GPU readiness.")
            yield self.current_instance_id
        finally:
            if admitted:
                # No await before the decrement: a cancelled lock wait must not skip the release.
                self._active_jobs -= 1
                if self._active_jobs == 0:
                    self.is_operating = False
                    self._gpu_ready = False
                    logger.info("🏁 No active GPU workloads remaining. Releasing GPU...")
                    await self._shutdown_if_idle()

    async def _shutdown_if_idle(self) -> None:
        async with self._job_lock:
            if self._active_jobs:
                return
            try:
                if self.current_instance_id == VAST_WARM_INSTANCE_ID:
                    stopped = await self._finish_shutdown(self._stop_gpu(self.current_instance_id))
                else:
                    stopped = await self._finish_shutdown(self._destroy_ephemeral_instance(self.current_instance_id))
                if not stopped:
                    logger.error("GPU cleanup was not confirmed for %s", self.current_instance_id)
            except Exception:
                logger.exception("GPU cleanup failed for %s", self.current_instance_id)

    async def _finish_shutdown(self, operation) -> bool:
        """Retain the admission lock until shutdown ends, even after cancellation."""
        shutdown = asyncio.create_task(operation)
        cancellation_pending = False
        while True:
            try:
                result = await asyncio.shield(shutdown)
            except asyncio.CancelledError:
                if shutdown.cancelled():
                    raise
                cancellation_pending = True
                continue
            except Exception:
                if cancellation_pending:
                    logger.exception("GPU shutdown failed while cancellation was pending")
                    raise asyncio.CancelledError from None
                raise
            if cancellation_pending:
                raise asyncio.CancelledError
            return result

    async def destroy_current_instance(self) -> bool:
        async with self._job_lock:
            if self._active_jobs:
                return False
            self._gpu_ready = False
            return await self._finish_shutdown(self._destroy_ephemeral_instance(self.current_instance_id))

    async def _destroy_ephemeral_instance(self, instance_id: int) -> bool:
        """Destroy only a replacement created by this manager, never the warm asset."""
        if instance_id in self._ephemeral_instance_ids and instance_id != VAST_WARM_INSTANCE_ID:
            logger.info(f"🗑️ Destroying ephemeral GPU instance {instance_id}...")
            vast_bin = "/root/workspace/.venv/bin/vastai" if os.path.exists("/root/workspace/.venv/bin/vastai") else "vastai"
            if instance_id == self.current_instance_id:
                subprocess.run(["pkill", "-9", "-f", f"ssh.*{GPU_TUNNEL_PORT}"], capture_output=True)
                self._tunnel_target = None
            dcmd = f"echo y | {vast_bin} destroy instance {instance_id}"
            proc = await asyncio.create_subprocess_shell(dcmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
            await proc.communicate()
            if proc.returncode != 0 or await self.get_active_instance(instance_id) is not None:
                logger.error("Destruction not confirmed for instance %s", instance_id)
                return False
            self._ephemeral_instance_ids.discard(instance_id)
            if self.current_instance_id == instance_id:
                self.current_instance_id = VAST_WARM_INSTANCE_ID
                self.cached_instance_id = str(VAST_WARM_INSTANCE_ID)
            return True
        return False

    async def stop_gpu(self, instance_id: Optional[int] = None) -> bool:
        async with self._job_lock:
            if self._active_jobs:
                logger.warning("Cannot stop a GPU while workloads are active.")
                return False
            self._gpu_ready = False
            return await self._finish_shutdown(self._stop_gpu(instance_id))

    async def _stop_gpu(self, instance_id: Optional[int] = None) -> bool:
        """Stops the GPU instance to halt per-hour billing."""
        target_id = instance_id or self.current_instance_id or VAST_WARM_INSTANCE_ID
        inst = await self.get_active_instance(target_id)
        if not inst:
            return True
        actual_id = int(inst.get("id", target_id))
        status = inst.get("actual_status")
        if status == "exited" or inst.get("cur_state") == "stopped":
            logger.info("GPU instance %s is already stopped.", actual_id)
            return True

        logger.info(f"🛑 Stopping GPU instance {actual_id} to halt billing...")
        if actual_id == self.current_instance_id:
            self._tunnel_target = None
            subprocess.run(["pkill", "-9", "-f", f"ssh.*{GPU_TUNNEL_PORT}"], capture_output=True)
        res = await self._api_request("PUT", f"v0/instances/{actual_id}/", {"state": "stopped"})
        success = res.get("success", False)
        logger.info("Stop instance response: %s", res)
        return success

    async def _idle_reaper_loop(self):
        """Emergency safety watchdog: stops GPU if left running with 0 active jobs for > IDLE_TIMEOUT_SECONDS."""
        while True:
            try:
                await asyncio.sleep(30)
                if self.is_operating or self._active_jobs > 0:
                    self.last_active_time = time.time()
                    continue
                idle_duration = time.time() - self.last_active_time
                if idle_duration > IDLE_TIMEOUT_SECONDS:
                    inst = await self.get_active_instance()
                    if inst and inst.get("actual_status") == "running":
                        logger.info(f"⏰ GPU idle for {int(idle_duration)}s (safety threshold). Halting...")
                        await self.stop_gpu()
            except Exception as e:
                logger.error("Error in idle reaper watchdog: %s", e)
