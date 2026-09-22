import os
import time
import json
import asyncio
import logging
import subprocess
from typing import Optional, Dict, Any

import aiohttp

logger = logging.getLogger("vast_lifecycle")

VAST_API_KEY = os.environ.get("VAST_API_KEY", "")
IDLE_TIMEOUT_SECONDS = int(os.environ.get("GPU_IDLE_TIMEOUT_SECONDS", "900"))  # 5 minutes default
GPU_TUNNEL_PORT = 4002
GPU_TARGET_PORT = 4001

class VastLifecycleManager:
    _instance = None

    def __init__(self):
        self.last_active_time = time.time()
        self.is_operating = False
        self.cached_instance_id: Optional[str] = None
        self._reaper_task: Optional[asyncio.Task] = None

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

    async def get_active_instance(self) -> Optional[Dict[str, Any]]:
        res = await self._api_request("GET", "v1/instances/")
        instances = res.get("instances", [])
        if not instances:
            return None
        return instances[0]

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
        # Check if tunnel is alive and healthy
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"http://127.0.0.1:{GPU_TUNNEL_PORT}/ai/health", timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
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
                            logger.info("✅ GPU SSH tunnel verified healthy on port %d", GPU_TUNNEL_PORT)
                            return True
            except Exception:
                if attempt == 10:
                    await self.ensure_remote_services(host, port)
                continue
        logger.warning("⚠️ GPU SSH tunnel did not respond within 25s.")
        return False

    async def ensure_gpu_ready(self, status_callback=None) -> bool:
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

        logger.error(f"Failed to bring GPU instance {inst_id} online within 300s (5 minutes).")
        return False

    async def stop_gpu(self) -> bool:
        """Stops the GPU instance to halt per-hour billing."""
        inst = await self.get_active_instance()
        if not inst:
            return True
        inst_id = inst.get("id")
        status = inst.get("actual_status")
        if status == "exited" or inst.get("cur_state") == "stopped":
            logger.info("GPU instance is already stopped.")
            return True

        logger.info(f"🛑 Stopping GPU instance {inst_id} to halt billing...")
        subprocess.run(["pkill", "-9", "-f", f"ssh.*{GPU_TUNNEL_PORT}"], capture_output=True)
        res = await self._api_request("PUT", f"v0/instances/{inst_id}/", {"state": "stopped"})
        success = res.get("success", False)
        logger.info("Stop instance response: %s", res)
        return success

    async def _idle_reaper_loop(self):
        """Periodically checks if the GPU has been idle for > IDLE_TIMEOUT_SECONDS."""
        while True:
            try:
                await asyncio.sleep(30)
                if self.is_operating:
                    self.last_active_time = time.time()
                    continue
                idle_duration = time.time() - self.last_active_time
                if idle_duration > IDLE_TIMEOUT_SECONDS:
                    inst = await self.get_active_instance()
                    if inst and inst.get("actual_status") == "running":
                        logger.info(f"⏰ GPU idle for {int(idle_duration)}s (exceeded {IDLE_TIMEOUT_SECONDS}s). Auto-stopping...")
                        await self.stop_gpu()
            except Exception as e:
                logger.error("Error in idle reaper loop: %s", e)
