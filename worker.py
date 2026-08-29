"""Background scan loop for the web UI."""

from __future__ import annotations

import threading
import time
from datetime import datetime

import config
from alerts import alert_new_matches
from blizzard import BlizzardClient
from bonus_data import fetch_bonus_data
from scanner import scan_eu
from state import hub


def run_scan_loop(stop_event: threading.Event, dynamic_config=None) -> None:
    if dynamic_config is None:
        dynamic_config = config

    if not config.BLIZZARD_CLIENT_ID or not config.BLIZZARD_CLIENT_SECRET:
        hub.emit(
            "status",
            status="error",
            message="Missing Blizzard API credentials in .env",
            error="Missing credentials",
        )
        return

    try:
        hub.emit("status", status="starting", message="Loading bonus ID data...")
        bonus_data = fetch_bonus_data()
        client = BlizzardClient(config.BLIZZARD_CLIENT_ID, config.BLIZZARD_CLIENT_SECRET)
        hub.emit("log", level="info", text="Bonus data loaded — monitor ready")
    except Exception as exc:
        hub.emit("status", status="error", message=str(exc), error=str(exc))
        return

    while not stop_event.is_set():
        ts = datetime.now().strftime("%H:%M:%S")
        hub.emit("log", level="info", text=f"--- Scan at {ts} ---")
        scan_start = time.time()

        try:
            matches = scan_eu(client, bonus_data, on_progress=_on_scan_progress, dynamic_cfg=dynamic_config)
            new_matches = alert_new_matches(matches)

            for match in new_matches:
                alert = match.to_dict()
                hub.emit("alert", alert=alert)
                hub.emit(
                    "log",
                    level="alert",
                    text=f"ALERT: {match.realm_names} — {match.buyout_gold:,}g",
                )

            if not matches:
                hub.emit("status", status="waiting", message="No listings match — waiting for next scan")
            elif not new_matches:
                hub.emit(
                    "status",
                    status="waiting",
                    message=f"{len(matches)} listing(s) up (already alerted)",
                )
            else:
                hub.emit(
                    "status",
                    status="waiting",
                    message=f"Found {len(new_matches)} new listing(s)!",
                )
        except Exception as exc:
            hub.emit("status", status="error", message=str(exc), error=str(exc))
            hub.emit("log", level="error", text=f"Scan error: {exc}")

        elapsed = time.time() - scan_start
        wait = max(0, config.POLL_INTERVAL_SECONDS - elapsed)
        next_at = time.time() + wait
        hub.emit("waiting", next_scan_at=next_at, wait_seconds=wait)

        if wait > 0:
            hub.emit(
                "status",
                status="waiting",
                message=f"Next scan in {wait / 60:.1f} min",
            )
            hub.emit("log", level="info", text=f"Next scan in {wait / 60:.1f} minutes")

        if stop_event.wait(wait):
            break

    hub.emit("status", status="idle", message="Stopped")


def _on_scan_progress(event: dict) -> None:
    kind = event.get("kind")

    if kind == "caching_start":
        hub.emit("status", status="caching", message="Building EU realm cache (first run only)...")
        hub.emit("log", level="info", text="Building EU realm cache...")
    elif kind == "caching":
        hub.emit(
            "progress",
            index=event["index"],
            total=event["total"],
            realm=f"Caching realm {event['index']}/{event['total']}",
        )
    elif kind == "caching_done":
        hub.emit("log", level="info", text=f"Realm cache ready ({event['total']} connected realms)")
    elif kind == "scan_start":
        hub.emit("status", status="scanning", message="Scanning EU auction houses...")
        hub.emit("scan_start", scan_number=hub.state.scan_number + 1, total=event["total"])
        hub.emit("log", level="info", text=f"Scan #{hub.state.scan_number} started — {event['total']} realms")
    elif kind == "realm_start":
        hub.emit(
            "progress",
            index=event["index"],
            total=event["total"],
            realm=event["realm"],
        )
    elif kind == "realm_done":
        found = event.get("found", 0)
        text = f"[{event['index']}/{event['total']}] {event['realm']}"
        hub.emit("log", level="match" if found else "info", text=text + (f" — {found} match!" if found else ""))
    elif kind == "realm_error":
        hub.emit(
            "log",
            level="error",
            text=f"[{event['index']}/{event['total']}] {event['realm']} — {event['error']}",
        )
    elif kind == "match":
        hub.emit("log", level="match", text=f"★ {event['match']['realm_names']} — {event['match']['buyout_gold']:,}g")
    elif kind == "scan_complete":
        elapsed = event.get("elapsed", 0)
        count = event.get("match_count", 0)
        hub.emit(
            "scan_complete",
            elapsed=elapsed,
            matches=event.get("matches", []),
        )
        hub.emit(
            "log",
            level="info",
            text=f"Scan complete in {elapsed:.0f}s — {count} listing(s)",
        )
