import csv
import os
from datetime import datetime, timezone, timedelta

import requests

from research.batch_study import load_events

GAMMA = "https://gamma-api.polymarket.com"
DATA = "https://data-api.polymarket.com/v2"
MARKETS = {
    "Dec hike 25":   "111662129652828266889360374468657435151479595863413519836161861837506140152890",
    "Dec no change": "42865728742506860386768556888821101266630139112044622335353850919229585308601",
}
START = datetime(2026, 10, 1, tzinfo=timezone.utc)
QUOTE_SIZE = 10        # shares per quote
MAX_INV = 100          # max shares held either way
HALF_SPREAD = 1.0      # quote 1 cent either side of the last trade
FILL_SHARE = 0.10      # we only get 10% of each trade (we're at the back of the queue)
PULL_BEFORE = timedelta(minutes=5)
PULL_AFTER = timedelta(minutes=30)


def condition_for(token):
    m = requests.get(f"{GAMMA}/markets", params={"clob_token_ids": token}, timeout=15).json()[0]
    return m["conditionId"]


def fetch_trades(condition):
    """Download all trades back to START (cached in data/), oldest first, as Yes-equivalent prices."""
    cache = f"data/trades_{condition[:10]}.csv"
    if os.path.exists(cache):
        return [(datetime.fromisoformat(r["t"]), r["side"], float(r["price"]), float(r["size"]))
                for r in csv.DictReader(open(cache))]

    trades, cursor = [], None
    while True:
        params = {"condition": condition, "limit": 1000}
        if cursor:
            params["cursor"] = cursor
        body = requests.get(f"{DATA}/trades", params=params, timeout=30).json()
        rows = body.get("data") or []
        for r in rows:
            t = datetime.fromtimestamp(int(r["timestamp"]), tz=timezone.utc)
            price, side = float(r["price"]) * 100, r["side"]
            if r["outcome"] == "No":                      # convert to Yes terms
                price = 100 - price
                side = "SELL" if side == "BUY" else "BUY"
            trades.append((t, side, price, float(r["size"])))
        cursor = (body.get("pagination") or {}).get("next_cursor")
        print(f"  downloaded {len(trades)} trades (back to {trades[-1][0]:%Y-%m-%d})" if trades else "  no trades")
        if not cursor or not rows or trades[-1][0] < START:
            break

    trades = sorted(t for t in trades if t[0] >= START)
    with open(cache, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "side", "price", "size"])
        for t in trades:
            w.writerow([t[0].isoformat(), *t[1:]])
    return trades


def in_danger(t, event_times):
    return any(e - PULL_BEFORE <= t <= e + PULL_AFTER for e in event_times)


def simulate(trades, event_times, protect):
    cash, inv, fills, event_pnl = 0.0, 0.0, 0, 0.0
    ref = trades[0][2]
    for t, side, price, size in trades:
        bid, ask = ref - HALF_SPREAD, ref + HALF_SPREAD
        danger = in_danger(t, event_times)
        if not (protect and danger):
            qty = min(QUOTE_SIZE, size * FILL_SHARE)
            before = cash + inv * ref
            if side == "SELL" and price <= bid and inv + qty <= MAX_INV:     # taker hit our bid
                cash -= bid * qty; inv += qty; fills += 1
            elif side == "BUY" and price >= ask and inv - qty >= -MAX_INV:   # taker lifted our ask
                cash += ask * qty; inv -= qty; fills += 1
            if danger:
                event_pnl += (cash + inv * price) - before
        ref = price                                                           # re-center on the latest trade
    return cash + inv * ref, fills, event_pnl


def main():
    event_times = [e[0] for e in load_events()]
    for label, token in MARKETS.items():
        print(f"\n=== {label} ===")
        trades = fetch_trades(condition_for(token))
        print(f"  {len(trades)} trades since {START:%Y-%m-%d}")
        for mode in ["naive", "protected"]:
            pnl, fills, ev = simulate(trades, event_times, protect=(mode == "protected"))
            dollars = pnl / 100
            print(f"  {mode:10} | P&L ${dollars:+8.2f} | fills {fills:5} | "
                  f"P&L during news windows ${ev / 100:+.2f}")


if __name__ == "__main__":
    main()
    