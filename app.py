"""Local web UI — live scan progress + browser alerts."""

from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import config
from state import hub
from worker import run_scan_loop

STATIC_DIR = Path(__file__).parent / "static"
_stop_event = threading.Event()
_worker_thread: threading.Thread | None = None


class DynamicConfig:
    """Runtime-modifiable config wrapper."""

    def __init__(self):
        self.item_id = config.ITEM_ID
        self.max_buyout_gold = config.MAX_BUYOUT_GOLD
        self.must_have_socket = config.MUST_HAVE_SOCKET
        self.difficulty = config.DIFFICULTY
        self.accepted_secondary_sets = config.ACCEPTED_SECONDARY_SETS

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


_dynamic_config = DynamicConfig()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    hub.bind_loop(asyncio.get_running_loop())
    global _worker_thread
    _stop_event.clear()
    _worker_thread = threading.Thread(
        target=run_scan_loop, args=(_stop_event, _dynamic_config), daemon=True
    )
    _worker_thread.start()
    yield
    _stop_event.set()
    if _worker_thread:
        _worker_thread.join(timeout=5)


app = FastAPI(title="WoW AH Alert", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
async def get_config() -> dict:
    return {
        "item_id": _dynamic_config.item_id,
        "max_buyout_gold": _dynamic_config.max_buyout_gold,
        "poll_interval_seconds": config.POLL_INTERVAL_SECONDS,
        "region": config.REGION,
        "must_have_socket": _dynamic_config.must_have_socket,
        "difficulty": _dynamic_config.difficulty,
        "difficulty_label": config.DIFFICULTY_LABELS.get(_dynamic_config.difficulty, "Unknown"),
        "accepted_secondary_sets": [sorted(stats) for stats in _dynamic_config.accepted_secondary_sets],
        "filter_summary": _get_filter_summary(),
    }


def _get_filter_summary() -> str:
    socket_text = "socket required" if _dynamic_config.must_have_socket else "no socket requirement"
    stats_text = ", ".join(
        "/".join(config.SECONDARY_STAT_NAMES[s] for s in sorted(stat_set))
        for stat_set in _dynamic_config.accepted_secondary_sets
    ) or "no stat filter"
    difficulty = config.DIFFICULTY_LABELS.get(_dynamic_config.difficulty, "Unknown")
    return f"Item {_dynamic_config.item_id} • {difficulty} • {socket_text} • {stats_text}"


@app.post("/api/settings")
async def update_settings(data: dict) -> dict:
    """Update search settings at runtime."""
    try:
        item_id = data.get("item_id")
        max_buyout_gold = data.get("max_buyout_gold")
        difficulty = data.get("difficulty")
        must_have_socket = data.get("must_have_socket")
        accepted_secondary_sets = data.get("accepted_secondary_sets")

        if item_id is not None:
            _dynamic_config.item_id = int(item_id)
        if max_buyout_gold is not None:
            _dynamic_config.max_buyout_gold = int(max_buyout_gold)
        if difficulty is not None:
            _dynamic_config.difficulty = int(difficulty)
        if must_have_socket is not None:
            _dynamic_config.must_have_socket = bool(must_have_socket)

        if accepted_secondary_sets:
            # Convert stat names to IDs
            sets = []
            for stat_names in accepted_secondary_sets:
                if isinstance(stat_names, str):
                    stat_names = [stat_names]
                stat_ids = frozenset({config.SECONDARY_STAT_IDS.get(s.lower(), 3) for s in stat_names})
                if stat_ids:
                    sets.append(stat_ids)
            if sets:
                _dynamic_config.accepted_secondary_sets = sets

        return {
            "status": "ok",
            "message": "Settings updated",
            "filter_summary": _get_filter_summary(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}, 400


@app.get("/api/state")
async def get_state() -> dict:
    return hub.snapshot()


@app.get("/api/events")
async def events(request: Request) -> StreamingResponse:
    queue = hub.subscribe()

    async def stream():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            hub.unsubscribe(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8765"))
    print(f"Open http://{host}:{port} — watching item {config.ITEM_ID} on EU")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
