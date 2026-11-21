import csv
from collections import defaultdict
from datetime import datetime, timedelta

from batch_study import load_events

KEYWORDS = ["fed", "rate cut", "interest rate", "fomc", "inflation", "cpi",
            "jobs", "unemployment", "payroll", "recession", "gdp"]
MAX_INVENTORY = 10           # max shares held either way
PULL_BEFORE = timedelta(minutes=5)
PULL_AFTER = timedelta(minutes=30)


def load_snapshots():
    """Group recorder rows by market: list of (time, bid, ask, mid) in cents."""
    markets = defaultdict(list)
    for r in csv.DictReader(open("data/prices.csv")):
        if r["outcome"] != "Yes" or not r["best_bid"] or not r["best_ask"]:
            continue
        if not any(k in r["question"].lower() for k in KEYWORDS):
            continue
        try:
            t = datetime.fromisoformat(r["timestamp"])
            bid, ask = float(r["best_bid"]) * 100, float(r["best_ask"]) * 100
        except ValueError:
            continue
        if 0 < bid < ask < 100:
            markets[r["question"]].append((t, bid, ask, (bid + ask) / 2))
    return markets


def in_danger(t, event_times):
    return any(e - PULL_BEFORE <= t <= e + PULL_AFTER for e in event_times)


def simulate(snaps, event_times, protect):
    """Quote 1 share at the best bid and ask. Conservative fill model:
    we only get filled if the next mid moves through our price
    (i.e. we're filled when the market moves against us)."""
    cash, inv, fills = 0.0, 0, 0
    for (t, bid, ask, _), (_, _, _, next_mid) in zip(snaps, snaps[1:]):
        if protect and in_danger(t, event_times):
            continue
        if next_mid <= bid and inv < MAX_INVENTORY:      # someone sold to us
            cash -= bid; inv += 1; fills += 1
        elif next_mid >= ask and inv > -MAX_INVENTORY:   # someone bought from us
            cash += ask; inv -= 1; fills += 1
    final_mid = snaps[-1][3]
    return cash + inv * final_mid, fills   # mark leftover inventory at the last mid


def main():
    event_times = [e[0] for e in load_events()]
    markets = load_snapshots()
    print(f"Simulating {len(markets)} econ markets\n")

    totals = {"naive": [0.0, 0], "protected": [0.0, 0]}
    for question, snaps in markets.items():
        if len(snaps) < 50:
            continue
        for mode in totals:
            pnl, fills = simulate(snaps, event_times, protect=(mode == "protected"))
            totals[mode][0] += pnl
            totals[mode][1] += fills

    for mode, (pnl, fills) in totals.items():
        print(f"{mode:10} | P&L {pnl:+8.1f} cents | fills {fills:5} | "
              f"per fill {pnl / fills if fills else 0:+.2f} cents")


if __name__ == "__main__":
    main()
    