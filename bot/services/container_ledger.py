"""Container lifecycle ledger shared by the GPU container and the CPU control endpoint.

The store is any object with get(key, default), put(key, value), pop(key, default)
and keys() (a modal.Dict in production). One record per container:
started_at, ready_at, heartbeat_at, last_activity_at, busy, exited_at (epoch seconds).

A release is requested by the CPU control endpoint and carried out by the container
itself, so releasing never starts hardware and never touches a busy container.
"""
from typing import Any, Dict, List, Optional, Tuple

HEARTBEAT_STALE_SECONDS = 30
MAX_RECORDS = 200
CONTAINER_PREFIX = "c:"
RELEASE_PREFIX = "release:"


def container_key(container_id: str) -> str:
    return f"{CONTAINER_PREFIX}{container_id}"


def release_key(container_id: str) -> str:
    return f"{RELEASE_PREFIX}{container_id}"


def start_container(store, container_id: str, now: float) -> None:
    store.put(container_key(container_id), {
        "started_at": now,
        "ready_at": None,
        "heartbeat_at": now,
        "last_activity_at": None,
        "busy": False,
        "exited_at": None,
    })
    _prune(store)


def _prune(store) -> None:
    records = container_records(store)
    excess = len(records) - MAX_RECORDS
    if excess <= 0:
        return
    oldest_first = sorted(records.items(), key=lambda item: item[1].get("started_at") or 0)
    for container_id, _ in oldest_first[:excess]:
        store.pop(container_key(container_id), None)
        store.pop(release_key(container_id), None)


def container_records(store) -> Dict[str, Dict[str, Any]]:
    records = {}
    for key in list(store.keys()):
        if isinstance(key, str) and key.startswith(CONTAINER_PREFIX):
            record = store.get(key, None)
            if record:
                records[key[len(CONTAINER_PREFIX):]] = record
    return records


def is_live(record: Dict[str, Any], now: float) -> bool:
    if record.get("exited_at") is not None:
        return False
    return now - (record.get("heartbeat_at") or 0) <= HEARTBEAT_STALE_SECONDS


def live_containers(store, now: float) -> List[Tuple[str, Dict[str, Any]]]:
    return [(cid, rec) for cid, rec in container_records(store).items() if is_live(rec, now)]


def last_active_at(record: Dict[str, Any]) -> Optional[float]:
    """Last real activity; a container with none yet counts from when it became ready."""
    return record.get("last_activity_at") or record.get("ready_at")


def request_release(store, now: float, min_idle_seconds: float, force: bool = False) -> Dict[str, Any]:
    """Ask idle, ready containers to exit. Busy or still-booting containers are left alone.

    force=True is for the hard budget cap only: it also stops a container that is mid-job,
    because cancelling the client's wait does not stop work already running on it.
    """
    released: List[str] = []
    skipped_busy: List[str] = []
    live = live_containers(store, now)
    for container_id, record in live:
        if not force:
            active_at = last_active_at(record)
            if record.get("ready_at") is None or active_at is None:
                continue
            if record.get("busy") or now - active_at < min_idle_seconds:
                skipped_busy.append(container_id)
                continue
        store.put(release_key(container_id), {"at": now, "force": force})
        released.append(container_id)
    return {"released": released, "busy": skipped_busy, "live": len(live)}


def watcher_step(store, container_id: str, probe: Dict[str, Any], now: float) -> bool:
    """One heartbeat. Returns True when the container should exit now.

    probe: {"ready": bool, "busy": bool, "last_activity_at": float | None}
    """
    key = container_key(container_id)
    record = store.get(key, None) or {"started_at": now}
    record["heartbeat_at"] = now
    record["busy"] = bool(probe.get("busy"))
    seen = probe.get("last_activity_at")
    if seen:
        record["last_activity_at"] = max(record.get("last_activity_at") or 0, seen)
    if probe.get("ready") and not record.get("ready_at"):
        record["ready_at"] = now

    exit_now = False
    request = store.get(release_key(container_id), None)
    if request is not None:
        newer_activity = bool(seen) and seen > request["at"]
        if not request["force"] and (record["busy"] or newer_activity):
            # Work arrived after the request; the request is stale.
            store.pop(release_key(container_id), None)
        else:
            record["exited_at"] = now
            store.pop(release_key(container_id), None)
            exit_now = True
    store.put(key, record)
    return exit_now
