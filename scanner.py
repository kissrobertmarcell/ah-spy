"""Scan all EU connected realms for matching auctions."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Callable

from blizzard import BlizzardClient
from bonus_data import (
    BonusData,
    format_secondaries,
    get_auction_secondaries,
    get_difficulty,
    has_socket,
)
import config


@dataclass
class Match:
    auction_id: int
    connected_realm_id: int
    realm_names: str
    buyout_gold: int
    secondaries: list[int]
    difficulty: int
    item_id: int

    def to_dict(self) -> dict:
        return {
            "auction_id": self.auction_id,
            "connected_realm_id": self.connected_realm_id,
            "realm_names": self.realm_names,
            "buyout_gold": self.buyout_gold,
            "secondaries": format_secondaries(self.secondaries),
            "wowhead_url": f"https://www.wowhead.com/item={self.item_id}",
        }


ProgressCallback = Callable[[dict], None] | None


def _load_realms_cache() -> dict[str, list[dict]] | None:
    if not os.path.exists(config.REALMS_CACHE_FILE):
        return None
    with open(config.REALMS_CACHE_FILE, encoding="utf-8") as f:
        return json.load(f)


def _save_realms_cache(cache: dict[str, list[dict]]) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.REALMS_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def _realm_label(realms: list[dict]) -> str:
    return ", ".join(r.get("name", "?") for r in realms)


def ensure_realm_cache(client: BlizzardClient, on_progress: ProgressCallback | None = None) -> dict[int, list[dict]]:
    cached = _load_realms_cache()
    if cached and cached.get("realm_ids"):
        return {int(k): v for k, v in cached["realms"].items()}

    if on_progress:
        on_progress({"kind": "caching_start"})
    else:
        print("Building EU connected realm cache (one-time, ~2 min)...")

    realm_ids = client.get_connected_realm_ids()
    realms_map: dict[int, list[dict]] = {}

    for i, cr_id in enumerate(realm_ids, 1):
        realms = client.get_connected_realm_realms(cr_id)
        realms_map[cr_id] = realms
        if on_progress:
            on_progress({"kind": "caching", "index": i, "total": len(realm_ids)})
        elif i % 10 == 0 or i == len(realm_ids):
            print(f"  Cached {i}/{len(realm_ids)} connected realms")

    _save_realms_cache({"realm_ids": realm_ids, "realms": {str(k): v for k, v in realms_map.items()}})
    if on_progress:
        on_progress({"kind": "caching_done", "total": len(realm_ids)})
    return realms_map


def _matches_filters(auction: dict, bonus_data: BonusData) -> tuple[bool, list[int], int]:
    item = auction.get("item") or {}
    if item.get("id") != config.ITEM_ID:
        return False, [], 0

    buyout = auction.get("buyout") or 0
    if buyout <= 0:
        return False, [], 0

    buyout_gold = buyout // 10_000
    if buyout_gold > config.MAX_BUYOUT_GOLD:
        return False, [], 0

    bonus_ids = item.get("bonus_lists") or []

    if config.MUST_HAVE_SOCKET and not has_socket(bonus_ids, bonus_data):
        return False, [], 0

    difficulty = get_difficulty(bonus_ids, bonus_data)
    if difficulty != config.DIFFICULTY:
        return False, [], 0

    secondaries = get_auction_secondaries(item, bonus_data)
    secondary_set = frozenset(secondaries)
    if secondary_set not in config.ACCEPTED_SECONDARY_SETS:
        return False, [], 0

    return True, secondaries, buyout_gold


def scan_eu(
    client: BlizzardClient,
    bonus_data: BonusData,
    on_progress: ProgressCallback | None = None,
) -> list[Match]:
    def emit(kind: str, **data) -> None:
        if on_progress:
            on_progress({"kind": kind, **data})

    realms_map = ensure_realm_cache(client, on_progress=on_progress)
    realm_ids = list(realms_map.keys())
    matches: list[Match] = []
    started = time.time()

    emit("scan_start", total=len(realm_ids))
    if not on_progress:
        print(f"Scanning {len(realm_ids)} EU connected realms for item {config.ITEM_ID}...")

    for i, cr_id in enumerate(realm_ids, 1):
        label = _realm_label(realms_map[cr_id])
        emit("realm_start", index=i, total=len(realm_ids), realm=label)

        try:
            auctions = client.get_auctions(cr_id)
        except Exception as exc:
            emit("realm_error", index=i, total=len(realm_ids), realm=label, error=str(exc))
            if not on_progress:
                print(f"  [{i}/{len(realm_ids)}] CR {cr_id}: ERROR — {exc}")
            continue

        found = 0
        for auction in auctions:
            ok, secondaries, buyout_gold = _matches_filters(auction, bonus_data)
            if not ok:
                continue

            found += 1
            match = Match(
                auction_id=auction["id"],
                connected_realm_id=cr_id,
                realm_names=label,
                buyout_gold=buyout_gold,
                secondaries=secondaries,
                difficulty=config.DIFFICULTY,
                item_id=config.ITEM_ID,
            )
            matches.append(match)
            emit("match", match=match.to_dict())

        emit("realm_done", index=i, total=len(realm_ids), realm=label, found=found)
        if not on_progress:
            status = f"{found} match(es)" if found else "—"
            print(f"  [{i}/{len(realm_ids)}] {label}: {status}")

    elapsed = time.time() - started
    emit("scan_complete", elapsed=elapsed, match_count=len(matches), matches=[m.to_dict() for m in matches])
    if not on_progress:
        print(f"Scan done in {elapsed:.0f}s — {len(matches)} total match(es)")
        for m in matches:
            print(
                f"  ★ {m.realm_names} — {m.buyout_gold:,}g — {format_secondaries(m.secondaries)} "
                f"(auction #{m.auction_id})"
            )

    return matches
