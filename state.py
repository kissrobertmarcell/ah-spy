"""Shared scan state and SSE event broadcasting."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppState:
    status: str = "starting"  # starting | caching | scanning | waiting | error
    message: str = "Starting..."
    scan_number: int = 0
    realm_index: int = 0
    realm_total: int = 0
    current_realm: str = ""
    matches: list[dict[str, Any]] = field(default_factory=list)
    new_alerts: list[dict[str, Any]] = field(default_factory=list)
    log: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=200))
    next_scan_at: float | None = None
    last_scan_at: float | None = None
    last_scan_seconds: float | None = None
    error: str | None = None


class StateHub:
    def __init__(self) -> None:
        self.state = AppState()
        self._lock = threading.Lock()
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self._subscribers.append(queue)
        queue.put_nowait({"type": "snapshot", "data": self.snapshot()})
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "status": self.state.status,
                "message": self.state.message,
                "scan_number": self.state.scan_number,
                "realm_index": self.state.realm_index,
                "realm_total": self.state.realm_total,
                "current_realm": self.state.current_realm,
                "matches": list(self.state.matches),
                "new_alerts": list(self.state.new_alerts),
                "log": list(self.state.log),
                "next_scan_at": self.state.next_scan_at,
                "last_scan_at": self.state.last_scan_at,
                "last_scan_seconds": self.state.last_scan_seconds,
                "error": self.state.error,
            }

    def _broadcast(self, event: dict[str, Any]) -> None:
        if not self._loop or not self._loop.is_running():
            return
        for queue in list(self._subscribers):
            try:
                self._loop.call_soon_threadsafe(queue.put_nowait, event)
            except Exception:
                pass

    def emit(self, event_type: str, **payload: Any) -> None:
        event = {"type": event_type, **payload}
        with self._lock:
            if event_type == "log":
                self.state.log.append(payload)
            elif event_type == "status":
                self.state.status = payload.get("status", self.state.status)
                self.state.message = payload.get("message", self.state.message)
                if "error" in payload:
                    self.state.error = payload["error"]
            elif event_type == "progress":
                self.state.realm_index = payload.get("index", self.state.realm_index)
                self.state.realm_total = payload.get("total", self.state.realm_total)
                self.state.current_realm = payload.get("realm", self.state.current_realm)
            elif event_type == "scan_start":
                self.state.scan_number = payload.get("scan_number", self.state.scan_number)
                self.state.matches = []
                self.state.realm_index = 0
                self.state.realm_total = payload.get("total", 0)
                self.state.last_scan_at = time.time()
                self.state.error = None
            elif event_type == "scan_complete":
                self.state.matches = payload.get("matches", [])
                self.state.last_scan_seconds = payload.get("elapsed")
                self.state.realm_index = self.state.realm_total
            elif event_type == "waiting":
                self.state.next_scan_at = payload.get("next_scan_at")
            elif event_type == "alert":
                alert = payload.get("alert")
                if alert:
                    self.state.new_alerts.insert(0, alert)
                    self.state.new_alerts = self.state.new_alerts[:20]
        self._broadcast(event)
        if event_type != "snapshot":
            self._broadcast({"type": "snapshot", "data": self.snapshot()})


hub = StateHub()
