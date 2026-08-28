# WoW AH Alert — Item 271445 EU

Polls the **Blizzard Auction House API** every **5 minutes** for item **271445** on all EU connected realms. Same filter logic as [WoWPay2Win](https://github.com/Trinovantes/WoWPay2Win), but hourly → 5 min for this one item.

## Criteria

| Filter | Value |
|--------|-------|
| Item | 271445 (Midnight S2 plate BoE) |
| Region | EU |
| Max price | 600,000g |
| Socket | Required |
| Difficulty | Heroic |
| Stats | Crit+Haste, Crit+Mastery, or Haste+Mastery |

Matches [this WoWPay2Win search](https://www.wowpay2win.com/?tier=t53&region=eu&boes=271445&mustHaveSocket=1&difficulty=2&secondaries=1,2), extended to include Crit combos.

## Setup (~5 min)

1. **Blizzard API key** — [develop.battle.net/access/clients](https://develop.battle.net/access/clients) → Create Client → copy ID + Secret.

2. **Install**
   ```bash
   cd C:\Code\smallscraper
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
   Edit `.env` with your credentials.

3. **Optional:** set `DISCORD_WEBHOOK_URL` in `.env` for Discord alerts.

## Run

### Web UI (recommended)

```bash
python app.py
```

Open **http://127.0.0.1:8765** — live progress bar, log, and browser popup when a match appears. Click "Enable browser notifications" on first visit.

### Deploy to Railway

Push this repository to GitHub, create a new Railway project from the repository, and set
`BLIZZARD_CLIENT_ID`, `BLIZZARD_CLIENT_SECRET`, and optionally
`DISCORD_WEBHOOK_URL` as environment variables. Railway uses the included
`railway.json` start configuration. Generate a public domain from the Railway
service, then keep the browser tab open to receive browser alerts.

### CLI only

```bash
# Continuous 5-min polling
python main.py

# Single scan (test)
python main.py --once
```

First run builds an EU realm cache (~2 min). Each full scan hits ~90 connected realms and takes ~3–8 min depending on API speed.

## Alerts

When a new matching listing appears:

- Console output + beep
- Windows toast notification
- Discord embed (if webhook configured)

Already-alerted auction IDs are tracked in `data/alerted_auctions.json` so you won't get spammed for the same listing.

## Config

Edit `config.py` to change price cap, item ID, poll interval, or accepted stat combos.

## Why not scrape wowpay2win.com?

That site refreshes once per hour. This tool hits Blizzard directly — same data source WoWPay2Win uses — so you see new listings within 5 minutes.

## Credits

Filter logic ported from [Trinovantes/WoWPay2Win](https://github.com/Trinovantes/WoWPay2Win). Bonus ID data from [Raidbots](https://www.raidbots.com/).
