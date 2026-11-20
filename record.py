import csv
import json
import os
import time
from datetime import datetime, timezone

import requests

URL = "https://gamma-api.polymarket.com/markets"
INTERVAL = 15          # seconds between snapshots
TOP_N = 50
KEYWORDS = ["fed", "rate cut", "interest rate", "fomc", "powell", "inflation",
            "cpi", "jobs", "unemployment", "payroll", "recession", "gdp"]
OUTFILE = "data/prices.csv"

def fetch_all_markets():
    markets = []
    offset = 0
    while offset < 3000:
        print(f"  fetching from offset {offset}...", flush=True)
        resp = requests.get(URL, params={"active": "true", "closed": "false",
                                         "limit": 500, "offset": offset},
                            timeout=15)
        batch = resp.json()
        if not isinstance(batch, list) or not batch:
            print("  stopped:", str(batch)[:200], flush=True)
            break
        markets.extend(batch)
        offset += len(batch)
        print(f"  got {len(batch)} (total {len(markets)})", flush=True)
    return markets

def is_econ(m):
    q = (m.get("question") or "").lower()
    return any(k in q for k in KEYWORDS)

os.makedirs("data", exist_ok=True)
new_file = not os.path.exists(OUTFILE)

with open(OUTFILE, "a", newline="") as f:
    writer = csv.writer(f)
    if new_file:
        writer.writerow(["timestamp", "market_id", "question", "outcome",
                         "price", "best_bid", "best_ask", "volume_24h"])

    while True:
        try:
            markets = fetch_all_markets()
            markets.sort(key=lambda m: float(m.get("volume24hr") or 0), reverse=True)

            tracked = {m.get("id"): m for m in markets[:TOP_N]}
            for m in markets:
                if is_econ(m):
                    tracked[m.get("id")] = m

            now = datetime.now(timezone.utc).isoformat()
            rows = 0
            for m in tracked.values():
                outcomes = json.loads(m.get("outcomes") or "[]")
                prices = json.loads(m.get("outcomePrices") or "[]")
                for name, price in zip(outcomes, prices):
                    writer.writerow([now, m.get("id"), m.get("question"), name, price,
                                     m.get("bestBid"), m.get("bestAsk"), m.get("volume24hr")])
                    rows += 1
            f.flush()
            econ = sum(1 for m in tracked.values() if is_econ(m))
            print(f"{now}  scanned {len(markets)} markets, saved {rows} rows ({econ} econ markets)")
        except Exception as e:
            print("Error:", e)

        time.sleep(INTERVAL)
        