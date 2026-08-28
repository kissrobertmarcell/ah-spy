"""Bonus ID lookups — same source as WoWPay2Win (raidbots bonuses.json)."""

from __future__ import annotations

from dataclasses import dataclass

import requests

RAIDBOTS_BONUSES_URL = "https://www.raidbots.com/static/data/live/bonuses.json"

# WoWPay2Win secondary keys
CRIT, HASTE, MASTERY, VERS = 0, 1, 2, 3
LFR, NORMAL, HEROIC, MYTHIC = 0, 1, 2, 3

STAT_NAME_TO_SECONDARY = {
    "Crit": CRIT,
    "Haste": HASTE,
    "Mastery": MASTERY,
    "Vers": VERS,
}

# Item modifier types for crafted/modified stats (from item link spec)
MODIFIER_STAT_1 = 29
MODIFIER_STAT_2 = 30
MODIFIER_VALUE_CRIT = 32
MODIFIER_VALUE_HASTE = 36
MODIFIER_VALUE_MASTERY = 49
MODIFIER_VALUE_VERS = 40

MODIFIER_VALUE_TO_SECONDARY = {
    MODIFIER_VALUE_CRIT: CRIT,
    MODIFIER_VALUE_HASTE: HASTE,
    MODIFIER_VALUE_MASTERY: MASTERY,
    MODIFIER_VALUE_VERS: VERS,
}


@dataclass
class BonusData:
    socket_bonus_ids: set[int]
    secondary_bonus_ids: dict[int, list[int]]
    difficulty_bonus_ids: dict[int, int]


def fetch_bonus_data() -> BonusData:
    resp = requests.get(
        RAIDBOTS_BONUSES_URL,
        timeout=60,
        headers={"User-Agent": "smallscraper/1.0 (wow ah alert)"},
    )
    resp.raise_for_status()
    bonus_json = resp.json()

    socket_ids: set[int] = set()
    secondary_ids: dict[int, list[int]] = {}
    difficulty_ids: dict[int, int] = {}

    for entry in bonus_json.values():
        if not isinstance(entry, dict):
            continue

        bonus_id = entry.get("id")
        if bonus_id is None:
            continue

        if "socket" in entry:
            socket_ids.add(bonus_id)

        raw_stats = entry.get("rawStats")
        if isinstance(raw_stats, list):
            secondaries = [
                STAT_NAME_TO_SECONDARY[s["name"]]
                for s in raw_stats
                if isinstance(s, dict) and s.get("name") in STAT_NAME_TO_SECONDARY
            ]
            if secondaries:
                secondary_ids[bonus_id] = secondaries

        tag = entry.get("tag", "")
        if isinstance(tag, str):
            difficulty = None
            if "Raid Finder" in tag:
                difficulty = LFR
            elif "Heroic" in tag:
                difficulty = HEROIC
            elif "Mythic" in tag and "Mythic+" not in tag:
                difficulty = MYTHIC
            if difficulty is not None:
                difficulty_ids[bonus_id] = difficulty

    return BonusData(socket_ids, secondary_ids, difficulty_ids)


def has_socket(bonus_ids: list[int], data: BonusData) -> bool:
    return any(bid in data.socket_bonus_ids for bid in bonus_ids)


def get_difficulty(bonus_ids: list[int], data: BonusData) -> int:
    for bid in bonus_ids:
        if bid in data.difficulty_bonus_ids:
            return data.difficulty_bonus_ids[bid]
    return NORMAL


def get_secondaries_from_bonus_ids(bonus_ids: list[int], data: BonusData) -> list[int]:
    for bid in bonus_ids:
        if bid in data.secondary_bonus_ids:
            return data.secondary_bonus_ids[bid]
    return []


def get_secondaries_from_modifiers(modifiers: list[dict] | None) -> list[int]:
    if not modifiers:
        return []

    secondaries: list[int] = []
    for mod in modifiers:
        mod_type = mod.get("type")
        if mod_type not in (MODIFIER_STAT_1, MODIFIER_STAT_2):
            continue
        value = mod.get("value")
        if value in MODIFIER_VALUE_TO_SECONDARY:
            secondaries.append(MODIFIER_VALUE_TO_SECONDARY[value])
    return secondaries


def get_auction_secondaries(auction_item: dict, data: BonusData) -> list[int]:
    bonus_ids = auction_item.get("bonus_lists") or []
    modifiers = auction_item.get("modifiers")
    return get_secondaries_from_bonus_ids(bonus_ids, data) + get_secondaries_from_modifiers(modifiers)


SECONDARY_LABELS = {CRIT: "Crit", HASTE: "Haste", MASTERY: "Mastery", VERS: "Vers"}
DIFFICULTY_LABELS = {LFR: "LFR", NORMAL: "Normal", HEROIC: "Heroic", MYTHIC: "Mythic"}


def format_secondaries(secondaries: list[int]) -> str:
    return " + ".join(SECONDARY_LABELS.get(s, str(s)) for s in sorted(secondaries))
