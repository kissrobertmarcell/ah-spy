import os
from dotenv import load_dotenv

load_dotenv()

# Target item — Midnight S2 plate BoE (matches wowpay2win.com link)
ITEM_ID = 271445
REGION = "eu"

# Filters (mirrors wowpay2win.com/?tier=t53&region=eu&boes=271445&mustHaveSocket=1&difficulty=2&secondaries=1,2)
MAX_BUYOUT_GOLD = 600_000
MUST_HAVE_SOCKET = True
DIFFICULTY = 2  # 0=LFR, 1=Normal, 2=Heroic, 3=Mythic

# Accepted secondary stat combos (WoWPay2Win keys: 0=Crit, 1=Haste, 2=Mastery, 3=Vers)
# User wants crit, haste, or mastery — any two-stat combo from those three.
ACCEPTED_SECONDARY_SETS: list[frozenset[int]] = [
    frozenset({0, 1}),  # Crit + Haste
    frozenset({0, 2}),  # Crit + Mastery
    frozenset({1, 2}),  # Haste + Mastery (URL default)
]

POLL_INTERVAL_SECONDS = 300  # 5 minutes

BLIZZARD_CLIENT_ID = os.getenv("BLIZZARD_CLIENT_ID", "")
BLIZZARD_CLIENT_SECRET = os.getenv("BLIZZARD_CLIENT_SECRET", "")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
REALMS_CACHE_FILE = os.path.join(DATA_DIR, "eu_connected_realms.json")
ALERTED_AUCTIONS_FILE = os.path.join(DATA_DIR, "alerted_auctions.json")
