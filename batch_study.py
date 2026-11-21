import csv
import os
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import requests

from filters import is_important
from zoneinfo import ZoneInfo

CLOB = "https://clob.polymarket.com"

# Markets to test against every event: (label, "Yes" token ID)
MARKETS = [
    ("Dec no change", "42865728742506860386768556888821101266630139112044622335353850919229585308601"),
    ("Dec hike 25",   "111662129652828266889360374468657435151479595863413519836161861837506140152890")
]

WINDOW_BEFORE = timedelta(hours=2)
WINDOW_AFTER = timedelta(hours=2)
PEAK_WINDOW = timedelta(minutes=30)

def parse_time(source, published):
    """Read either date format; snap BLS releases to their official 8:30 AM Eastern time."""
    try:
        t = parsedate_to_datetime(published)
    except (ValueError, TypeError):
        t = datetime.fromisoformat(published)
    if source.startswith("bls_"):
        eastern = t.astimezone(ZoneInfo("America/New_York"))
        t = eastern.replace(hour=8, minute=30, second=0, microsecond=0)
    return t.astimezone(timezone.utc)

def load_events():
    events = []
    for r in csv.DictReader(open("data/news.csv")):
        if is_important(r["source"], r["title"]) and r["published"]:
            t = parse_time(r["source"], r["published"])
            events.append((t, r["source"], r["title"]))
    return sorted(events)


def get_history(token, start, end):
    resp = requests.get(f"{CLOB}/prices-history", params={
        "market": token, "startTs": int(start.timestamp()),
        "endTs": int(end.timestamp()), "fidelity": 1}, timeout=15)
    hist = resp.json().get("history", [])
    return [(datetime.fromtimestamp(h["t"], tz=timezone.utc), float(h["p"]) * 100) for h in hist]


def price_at(series, t):
    return min(series, key=lambda x: abs((x[0] - t).total_seconds()))[1]


def analyze(series, event_time):
    pre = [p for t, p in series if event_time - timedelta(minutes=10) <= t < event_time]
    if not pre:
        return None
    before = sorted(pre)[len(pre) // 2]  # median of the 10 minutes before

    after = [(t, p) for t, p in series if event_time <= t <= event_time + PEAK_WINDOW]
    if not after:
        return None
    peak_t, peak_p = max(after, key=lambda x: abs(x[1] - before))
    peak_move = peak_p - before
    move_60 = price_at(series, event_time + timedelta(minutes=60)) - before

    reversal = None
    if abs(peak_move) >= 1:
        reversal = round(100 * (peak_move - move_60) / peak_move)

    return {
        "before": round(before, 1),
        "move_1m": round(price_at(series, event_time + timedelta(minutes=1)) - before, 1),
        "move_5m": round(price_at(series, event_time + timedelta(minutes=5)) - before, 1),
        "move_15m": round(price_at(series, event_time + timedelta(minutes=15)) - before, 1),
        "peak_move": round(peak_move, 1),
        "mins_to_peak": round((peak_t - event_time).total_seconds() / 60),
        "move_60m": round(move_60, 1),
        "reversal_pct": reversal,
    }


def save_chart(series, event_time, title, path):
    plt.figure(figsize=(10, 5))
    plt.plot([t for t, _ in series], [p for _, p in series])
    plt.axvline(event_time, color="red", linestyle="--", label="News released")
    plt.title(title[:90])
    plt.ylabel("Market probability (%)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def main():
    os.makedirs("charts", exist_ok=True)
    os.makedirs("results", exist_ok=True)
    rows = []

    for event_time, source, title in load_events():
        for label, token in MARKETS:
            try:
                series = get_history(token, event_time - WINDOW_BEFORE, event_time + WINDOW_AFTER)
            except Exception as e:
                print(f"Error fetching {label}: {e}")
                continue
            if len(series) < 20:
                print(f"skip  {event_time:%Y-%m-%d} | {label}: not enough data ({len(series)} points)")
                continue
            result = analyze(series, event_time)
            if result is None:
                print(f"skip  {event_time:%Y-%m-%d} | {label}: no data right around the event")
                continue

            row = {"event_time": event_time.isoformat(), "source": source,
                   "title": title, "market": label, **result}
            rows.append(row)
            print(f"ok    {event_time:%Y-%m-%d} | {label:14} | before {result['before']:5}% | "
                  f"peak {result['peak_move']:+5} at {result['mins_to_peak']:>2} min | "
                  f"60m {result['move_60m']:+5} | reversal {result['reversal_pct']}%")

            chart_path = f"charts/{event_time:%Y%m%d_%H%M}_{label.replace(' ', '_')}.png"
            save_chart(series, event_time, f"{label} | {title}", chart_path)

    if rows:
        with open("results/event_study.csv", "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nSaved {len(rows)} results to results/event_study.csv")
    else:
        print("\nNo results. The markets may not have existed yet at these event times.")


if __name__ == "__main__":
    main()