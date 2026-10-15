"""Cost model for the Modal GPU: you pay for container-seconds.

cost = rate x (cold start + useful work + idle tail + shutdown delay)

Everything here is pure arithmetic over ledger records so it can be tested offline.
Spend is estimated from container lifetimes (the container ledger) and compared with
the provider's bill; the higher number wins.
"""
import json
import os
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from bot.services.container_ledger import is_live, last_active_at

# Dollars per hour. Source: third-party summary of modal.com/pricing (July 2026):
# https://www.spheron.network/blog/modal-gpu-pricing-2026-per-second-billing/
# Verify against https://modal.com/pricing and override with MODAL_GPU_RATE_PER_SECOND.
# CPU and memory are billed separately by Modal; the bill reconciliation covers them.
GPU_DOLLARS_PER_HOUR = {
    "T4": 0.59,
    "L4": 0.80,
    "A10": 1.10,
    "A10G": 1.10,
    "L40S": 1.95,
    "A100-40GB": 2.10,
    "A100": 2.50,
    "A100-80GB": 2.50,
    "H100": 3.95,
    "H200": 4.54,
    "B200": 6.25,
}
DEFAULT_DAILY_CAP_USD = 2.00
CANCEL_AT_FRACTION = 0.95
# Used until the ledger has measured a real cold start.
DEFAULT_COLD_START_SECONDS = 60.0
DEFAULT_SCALEDOWN_SECONDS = 60.0


class BudgetExceeded(RuntimeError):
    pass


def rate_per_second(gpu_type: Optional[str] = None) -> float:
    """GPU dollars per second. An unknown GPU type is priced as the most expensive one."""
    override = os.environ.get("MODAL_GPU_RATE_PER_SECOND", "").strip()
    if override:
        return float(override)
    spec = (gpu_type or os.environ.get("MODAL_GPU_TYPE", "L4")).strip().upper()
    name, _, count = spec.partition(":")
    per_hour = GPU_DOLLARS_PER_HOUR.get(name, max(GPU_DOLLARS_PER_HOUR.values()))
    return per_hour * (int(count) if count.isdigit() else 1) / 3600.0


def scaledown_seconds() -> float:
    return float(os.environ.get("MODAL_SCALEDOWN_SECONDS", DEFAULT_SCALEDOWN_SECONDS))


def daily_cap_usd() -> float:
    return float(os.environ.get("MODAL_DAILY_CAP_USD", DEFAULT_DAILY_CAP_USD))


def utc_day_start(now: float) -> float:
    moment = datetime.fromtimestamp(now, tz=timezone.utc)
    return moment.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()


def container_billable_seconds(record: Dict[str, Any], now: float, window_start: float,
                               scaledown: float) -> float:
    """Seconds billed for one container inside the window, idle tail counted up front.

    A live container is charged its remaining idle time immediately: if busy, the full
    window (it starts when the work ends); if idle, what is left of it.
    """
    started = record.get("started_at") or now
    if record.get("exited_at") is not None:
        end = record["exited_at"]
    elif is_live(record, now):
        end = now
    else:
        end = record.get("heartbeat_at") or started
    seconds = max(0.0, end - max(started, window_start))
    if record.get("exited_at") is None and is_live(record, now):
        if record.get("busy"):
            seconds += scaledown
        else:
            active_at = last_active_at(record) or now
            seconds += max(0.0, scaledown - (now - active_at))
    return seconds


def spend_from_containers(records: Iterable[Dict[str, Any]], now: float, rate: float,
                          scaledown: float) -> float:
    window_start = utc_day_start(now)
    return rate * sum(container_billable_seconds(r, now, window_start, scaledown) for r in records)


def projected_new_container_cost(rate: float, cold_start: float, scaledown: float) -> float:
    return rate * (cold_start + scaledown)


def check_admission(spent: float, projected: float, cap: float) -> None:
    """Refuse a job before it starts when it cannot fit under the daily cap."""
    if spent + projected >= cap:
        raise BudgetExceeded(
            f"Daily GPU cap ${cap:.2f} reached: spent ${spent:.3f} + this job ${projected:.3f}."
        )


def over_cancel_threshold(spent: float, cap: float) -> bool:
    return spent >= cap * CANCEL_AT_FRACTION


class LeaseLedger:
    """Client-side JSONL record of each GPU lease, kept as a measurement and fallback."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.environ.get(
            "GPU_LEDGER_PATH", os.path.expanduser("~/.audioviz/gpu_lease_ledger.jsonl")
        )

    def append(self, record: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")

    def read(self, since: float = 0.0) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        rows = []
        with open(self.path, encoding="utf-8") as stream:
            for line in stream:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if row.get("ended_at", 0) >= since:
                    rows.append(row)
        return rows


def spend_from_leases(leases: Iterable[Dict[str, Any]], rate: float) -> float:
    """Fallback estimate when the container ledger is unreachable (tail included)."""
    return rate * sum(
        lease.get("cold_start_s", 0.0) + lease.get("work_s", 0.0) + lease.get("tail_s", 0.0)
        for lease in leases
    )


def summarize(containers: List[Dict[str, Any]], leases: List[Dict[str, Any]],
              rate: float) -> Dict[str, Any]:
    """Measured terms of the cost formula, plus the break-even idle window."""
    cold = [c["ready_at"] - c["started_at"] for c in containers if c.get("ready_at") and c.get("started_at")]
    tails = []
    lifetimes = 0.0
    for c in containers:
        end = c.get("exited_at") or c.get("heartbeat_at")
        if end and c.get("started_at"):
            lifetimes += max(0.0, end - c["started_at"])
            active_at = last_active_at(c)
            if active_at:
                tails.append(max(0.0, end - active_at))
    work = sum(lease.get("work_s", 0.0) for lease in leases)
    median_cold = statistics.median(cold) if cold else None
    return {
        "containers": len(containers),
        "median_cold_start_s": median_cold,
        "median_idle_tail_s": statistics.median(tails) if tails else None,
        "container_seconds": lifetimes,
        "work_seconds": work,
        "estimated_cost_usd": rate * lifetimes,
        # Keeping a container warm longer than a cold start takes costs more than restarting.
        "suggested_scaledown_s": max(15.0, round(median_cold)) if median_cold else None,
    }
