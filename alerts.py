"""Alert delivery: Windows toast, console, optional Discord webhook."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import requests

import config
from bonus_data import format_secondaries
from scanner import Match


def _load_alerted() -> set[str]:
    if not os.path.exists(config.ALERTED_AUCTIONS_FILE):
        return set()
    with open(config.ALERTED_AUCTIONS_FILE, encoding="utf-8") as f:
        return set(json.load(f))


def _save_alerted(alerted: set[str]) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.ALERTED_AUCTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(alerted), f, indent=2)


def _auction_key(match: Match) -> str:
    return f"{match.connected_realm_id}:{match.auction_id}"


def _wowhead_link(item_id: int) -> str:
    return f"https://www.wowhead.com/item={item_id}"


def _format_message(match: Match) -> str:
    stats = format_secondaries(match.secondaries)
    return (
        f"{match.realm_names}\n"
        f"{match.buyout_gold:,}g — {stats} — Heroic + Socket\n"
        f"{_wowhead_link(match.item_id)}"
    )


def _windows_toast(title: str, message: str) -> None:
    try:
        from winotify import Notification, audio

        toast = Notification(
            app_id="WoW AH Alert",
            title=title,
            msg=message.replace("\n", " | "),
            duration="long",
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
    except Exception as exc:
        print(f"  (Windows toast failed: {exc})", file=sys.stderr)


def _discord_webhook(title: str, message: str) -> None:
    if not config.DISCORD_WEBHOOK_URL:
        return

    payload = {
        "embeds": [
            {
                "title": title,
                "description": message,
                "color": 0xFFD100,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]
    }
    try:
        resp = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=15)
        resp.raise_for_status()
    except Exception as exc:
        print(f"  (Discord webhook failed: {exc})", file=sys.stderr)


def alert_new_matches(matches: list[Match]) -> list[Match]:
    alerted = _load_alerted()
    new_matches: list[Match] = []

    for match in matches:
        key = _auction_key(match)
        if key in alerted:
            continue
        new_matches.append(match)
        alerted.add(key)

    if not new_matches:
        return []

    for match in new_matches:
        title = f"Item {match.item_id} — {match.buyout_gold:,}g on EU!"
        message = _format_message(match)

        print("\n" + "=" * 60)
        print(f"ALERT: {title}")
        print(message)
        print("=" * 60 + "\n")

        sys.stdout.write("\a")
        sys.stdout.flush()

        _windows_toast(title, message)
        _discord_webhook(title, message)

    _save_alerted(alerted)
    return new_matches
