import json
import os
import sys
from datetime import datetime, timezone, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"


def search(query):
    """Find markets matching a search and print their token IDs."""
    resp = requests.get(f"{GAMMA}/public-search", params={"q": query}, timeout=15)
    data = resp.json()
    for event in data.get("events", []):
        for m in event.get("markets", []):
            tokens = json.loads(m.get("clobTokenIds") or "[]")
            outcomes = json.loads(m.get("outcomes") or "[]")
            print(m.get("question"))
            for name, tok in zip(outcomes, tokens):
                print(f"   {name}: {tok}")
            print()


def chart(token_id, event_time_str, label):
    """Download price history around an event, chart it, and measure the reaction."""
    event_time = datetime.strptime(event_time_str, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
    start = event_time - timedelta(hours=3)
    end = event_time + timedelta(hours=3)

    resp = requests.get(f"{CLOB}/prices-history", params={
        "market": token_id,
        "startTs": int(start.timestamp()),
        "endTs": int(end.timestamp()),
        "fidelity": 1,  # 1-minute data points
    }, timeout=15)
    history = resp.json().get("history", [])
    if not history:
        print("No price history returned:", resp.text[:200])
        return

    times = [datetime.fromtimestamp(h["t"], tz=timezone.utc) for h in history]
    prices = [float(h["p"]) * 100 for h in history]

    def price_at(t):
        best = min(range(len(times)), key=lambda i: abs((times[i] - t).total_seconds()))
        return prices[best]

    before = price_at(event_time - timedelta(minutes=5))
    after_1h = price_at(event_time + timedelta(hours=1))
    total_move = after_1h - before

    print(f"Data points: {len(prices)}")
    print(f"Price 5 min before: {before:.1f}%")
    for mins in [1, 5, 15, 30, 60]:
        p = price_at(event_time + timedelta(minutes=mins))
        print(f"Price +{mins} min:      {p:.1f}%  (move {p - before:+.1f})")

    if abs(total_move) >= 1:
        for t, p in zip(times, prices):
            if t >= event_time and abs(p - before) >= 0.9 * abs(total_move):
                mins = (t - event_time).total_seconds() / 60
                print(f"Reached 90% of its 1-hour move after {mins:.0f} minutes")
                break
    else:
        print("Move was under 1 point: market barely reacted (news was likely already priced in).")

    os.makedirs("charts", exist_ok=True)
    plt.figure(figsize=(10, 5))
    plt.plot(times, prices)
    plt.axvline(event_time, color="red", linestyle="--", label="News released")
    plt.title(label)
    plt.ylabel("Market probability (%)")
    plt.legend()
    plt.tight_layout()
    path = f"charts/{event_time.strftime('%Y%m%d_%H%M')}.png"
    plt.savefig(path)
    print(f"Chart saved to {path}")


if __name__ == "__main__":
    if sys.argv[1] == "search":
        search(" ".join(sys.argv[2:]))
    elif sys.argv[1] == "chart":
        chart(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Event study")
        