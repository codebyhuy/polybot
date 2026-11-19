import csv
import json
import os
import time
from datetime import datetime, timezone

import requests

URL = "https://gamma-api.polymarket.com/markets"
INTERVAL = 30          # seconds between snapshots
TOP_N = 50             # how many of the most-traded markets to track
OUTFILE = "data/prices.csv"

os.makedirs("data", exist_ok=True)
new_file = not os.path.exists(OUTFILE)

with open(OUTFILE, "a", newline="") as f:
    writer = csv.writer(f)
    if new_file:
        writer.writerow(["timestamp", "market_id", "question", "outcome",
                         "price", "best_bid", "best_ask", "volume_24h"])

    while True:
        try:
            resp = requests.get(URL, params={"active": "true", "closed": "false", "limit": 500}, timeout=10)
            markets = resp.json()
            markets.sort(key=lambda m: float(m.get("volume24hr") or 0), reverse=True)

            now = datetime.now(timezone.utc).isoformat()
            rows = 0
            for m in markets[:TOP_N]:
                outcomes = json.loads(m.get("outcomes") or "[]")
                prices = json.loads(m.get("outcomePrices") or "[]")
                for name, price in zip(outcomes, prices):
                    writer.writerow([now, m.get("id"), m.get("question"), name, price,
                                     m.get("bestBid"), m.get("bestAsk"), m.get("volume24hr")])
                    rows += 1
            f.flush()
            print(f"{now}  saved {rows} rows")
        except Exception as e:
            print("Error:", e)

        time.sleep(INTERVAL)
        