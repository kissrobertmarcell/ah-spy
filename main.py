#!/usr/bin/env python3
"""5-minute EU AH monitor for a single BoE — faster than wowpay2win.com (60 min)."""

from __future__ import annotations

import argparse
import io
import sys
import time
from datetime import datetime


def _configure_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding="utf-8",
            errors="replace",
            line_buffering=True,
        )

import config
from alerts import alert_new_matches
from blizzard import BlizzardClient
from bonus_data import fetch_bonus_data
from scanner import scan_eu


def _validate_credentials() -> None:
    if not config.BLIZZARD_CLIENT_ID or not config.BLIZZARD_CLIENT_SECRET:
        print(
            "Missing Blizzard API credentials.\n"
            "1. Create a client at https://develop.battle.net/access/clients\n"
            "2. Copy .env.example to .env and fill in BLIZZARD_CLIENT_ID / BLIZZARD_CLIENT_SECRET",
            file=sys.stderr,
        )
        sys.exit(1)


def run_once(client: BlizzardClient, bonus_data) -> None:
    matches = scan_eu(client, bonus_data)
    new = alert_new_matches(matches)
    if not matches:
        print("No matching listings right now.")
    elif not new:
        print(f"{len(matches)} listing(s) still up (already alerted).")


def main() -> None:
    _configure_stdout()
    parser = argparse.ArgumentParser(description="EU WoW AH alert for a specific item")
    parser.add_argument("--once", action="store_true", help="Run one scan and exit")
    parser.add_argument("--item-id", type=int, default=config.ITEM_ID, help="Item ID to monitor")
    parser.add_argument("--max-buyout-gold", type=int, default=config.MAX_BUYOUT_GOLD, help="Max buyout in gold")
    parser.add_argument(
        "--socket/--no-socket",
        dest="must_have_socket",
        default=config.MUST_HAVE_SOCKET,
        help="Require an item socket or allow any socket state",
    )
    parser.add_argument(
        "--difficulty",
        type=int,
        choices=sorted(config.DIFFICULTY_LABELS),
        default=config.DIFFICULTY,
        help="Item difficulty: 0=LFR, 1=Normal, 2=Heroic, 3=Mythic",
    )
    parser.add_argument(
        "--stats",
        default=None,
        help='Accepted secondary stat combo(s), e.g. "crit,haste|crit,mastery|haste,mastery"',
    )
    args = parser.parse_args()

    config.ITEM_ID = args.item_id
    config.MAX_BUYOUT_GOLD = args.max_buyout_gold
    config.MUST_HAVE_SOCKET = args.must_have_socket
    config.DIFFICULTY = args.difficulty
    if args.stats:
        config.ACCEPTED_SECONDARY_SETS = config.parse_secondary_sets(args.stats)

    _validate_credentials()

    print("Loading bonus ID data from raidbots...")
    bonus_data = fetch_bonus_data()
    print(
        f"Watching item {config.ITEM_ID} on EU — max {config.MAX_BUYOUT_GOLD:,}g, "
        f"{config.DIFFICULTY_LABELS.get(config.DIFFICULTY, 'Unknown')}, "
        f"{('socket required' if config.MUST_HAVE_SOCKET else 'socket optional')}, "
        f"{', '.join(config.format_secondary_set(s) for s in config.ACCEPTED_SECONDARY_SETS)} — every {config.POLL_INTERVAL_SECONDS}s"
    )

    client = BlizzardClient(config.BLIZZARD_CLIENT_ID, config.BLIZZARD_CLIENT_SECRET)

    if args.once:
        run_once(client, bonus_data)
        return

    while True:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n--- Scan at {ts} ---")
        scan_start = time.time()
        try:
            run_once(client, bonus_data)
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as exc:
            print(f"Scan error: {exc}", file=sys.stderr)

        elapsed = time.time() - scan_start
        wait = max(0, config.POLL_INTERVAL_SECONDS - elapsed)
        if wait > 0:
            print(f"Next scan in {wait / 60:.1f} minutes...")
        try:
            time.sleep(wait)
        except KeyboardInterrupt:
            print("\nStopped.")
            break


if __name__ == "__main__":
    main()
