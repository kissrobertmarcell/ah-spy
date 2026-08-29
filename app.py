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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    hub.bind_loop(asyncio.get_running_loop())
    global _worker_thread
    _stop_event.clear()
    _worker_thread = threading.Thread(target=run_scan_loop, args=(_stop_event,), daemon=True)
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
        "item_id": config.ITEM_ID,
        "max_buyout_gold": config.MAX_BUYOUT_GOLD,
        "poll_interval_seconds": config.POLL_INTERVAL_SECONDS,
        "region": config.REGION,
        "must_have_socket": config.MUST_HAVE_SOCKET,
        "difficulty": config.DIFFICULTY,
        "difficulty_label": config.DIFFICULTY_LABELS.get(config.DIFFICULTY, "Unknown"),
        "accepted_secondary_sets": [sorted(stats) for stats in config.ACCEPTED_SECONDARY_SETS],
        "filter_summary": config.filter_summary(),
    }


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
