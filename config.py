import os

from dotenv import load_dotenv

load_dotenv()

SECONDARY_STAT_IDS = {
    "crit": 0,
    "haste": 1,
    "mastery": 2,
    "vers": 3,
    "versatility": 3,
}
SECONDARY_STAT_NAMES = {
    0: "Crit",
    1: "Haste",
    2: "Mastery",
    3: "Versatility",
}
DIFFICULTY_LABELS = {
    0: "LFR",
    1: "Normal",
    2: "Heroic",
    3: "Mythic",
}


def _parse_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() not in {"", "0", "false", "no", "off"}


def _parse_stat_id(name: str) -> int:
    key = name.strip().lower().replace(" ", "")
    if key not in SECONDARY_STAT_IDS:
        valid = ", ".join(sorted(SECONDARY_STAT_IDS))
        raise ValueError(f"Unknown stat '{name}'. Valid values: {valid}")
    return SECONDARY_STAT_IDS[key]


def parse_secondary_set(value: str | list[str] | tuple[str, ...] | set[str] | None) -> frozenset[int]:
    if value is None:
        return frozenset()
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",") if part.strip()]
    else:
        items = [str(part).strip() for part in value if str(part).strip()]
    return frozenset({_parse_stat_id(part) for part in items})


def parse_secondary_sets(value: str | list[str] | None) -> list[frozenset[int]]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_groups = value
    elif isinstance(value, str):
        raw_groups = [group.strip() for group in value.split("|") if group.strip()]
    else:
        raw_groups = [str(value)]

    groups: list[frozenset[int]] = []
    for group in raw_groups:
        group_set = parse_secondary_set(group)
        if group_set:
            groups.append(group_set)
    return groups


def format_secondary_set(stat_set: frozenset[int]) -> str:
    if not stat_set:
        return "Any"
    return "/".join(SECONDARY_STAT_NAMES[s] for s in sorted(stat_set))


def filter_summary() -> str:
    socket_text = "socket required" if MUST_HAVE_SOCKET else "no socket requirement"
    stats_text = ", ".join(format_secondary_set(s) for s in ACCEPTED_SECONDARY_SETS) or "no stat filter"
    difficulty = DIFFICULTY_LABELS.get(DIFFICULTY, "Unknown")
    return f"Item {ITEM_ID} • {difficulty} • {socket_text} • {stats_text}"


# Target item — Midnight S2 plate BoE (matches wowpay2win.com link)
ITEM_ID = int(os.getenv("ITEM_ID", "271445"))
REGION = "eu"

# Filters (mirrors wowpay2win.com/?tier=t53&region=eu&boes=271445&mustHaveSocket=1&difficulty=2&secondaries=1,2)
MAX_BUYOUT_GOLD = int(os.getenv("MAX_BUYOUT_GOLD", "600000"))
MUST_HAVE_SOCKET = _parse_bool(os.getenv("MUST_HAVE_SOCKET"), True)
DIFFICULTY = int(os.getenv("DIFFICULTY", "2"))  # 0=LFR, 1=Normal, 2=Heroic, 3=Mythic

# Accepted secondary stat combos (WoWPay2Win keys: 0=Crit, 1=Haste, 2=Mastery, 3=Vers)
# User can override with env var ACCEPTED_SECONDARY_SETS, e.g. "crit,haste|crit,mastery|haste,mastery"
DEFAULT_ACCEPTED_SECONDARY_SETS = [
    frozenset({0, 1}),
    frozenset({0, 2}),
    frozenset({1, 2}),
]
ACCEPTED_SECONDARY_SETS: list[frozenset[int]] = parse_secondary_sets(
    os.getenv("ACCEPTED_SECONDARY_SETS", "crit,haste|crit,mastery|haste,mastery")
) or DEFAULT_ACCEPTED_SECONDARY_SETS

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "300"))

BLIZZARD_CLIENT_ID = os.getenv("BLIZZARD_CLIENT_ID", "")
BLIZZARD_CLIENT_SECRET = os.getenv("BLIZZARD_CLIENT_SECRET", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REALMS_CACHE_FILE = os.path.join(DATA_DIR, "eu_connected_realms.json")
ALERTED_AUCTIONS_FILE = os.path.join(DATA_DIR, "alerted_auctions.json")
