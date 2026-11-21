import random
from datetime import datetime, timezone, timedelta

from batch_study import MARKETS, analyze, get_history, load_events

START = datetime(2026, 10, 1, tzinfo=timezone.utc)
END = datetime(2026, 11, 19, tzinfo=timezone.utc)
N_SAMPLES = 300
random.seed(42)  # same random times every run, so results are reproducible


def fetch_full(token):
    """Download minute-level history one day at a time."""
    series, day = [], START
    while day < END:
        series += get_history(token, day, day + timedelta(days=1))
        day += timedelta(days=1)
    return sorted(set(series))


def random_time(event_times):
    """A random time during US trading hours, at least 3 hours from any real event."""
    while True:
        day = START + timedelta(days=random.randrange((END - START).days))
        t = day.replace(hour=random.randint(14, 21), minute=random.randint(0, 59))
        if all(abs((t - e).total_seconds()) > 3 * 3600 for e in event_times):
            return t


def window(series, t):
    return [(ts, p) for ts, p in series if t - timedelta(hours=2) <= ts <= t + timedelta(hours=2)]


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(q * len(values)))]


def main():
    events = load_events()
    event_times = [e[0] for e in events]

    for label, token in MARKETS:
        print(f"\n=== {label} ===")
        print("Downloading history (takes a minute)...")
        series = fetch_full(token)

        placebo = []
        for _ in range(N_SAMPLES):
            t = random_time(event_times)
            w = window(series, t)
            if len(w) >= 20:
                r = analyze(w, t)
                if r:
                    placebo.append(abs(r["peak_move"]))

        print(f"Random no-news moments: {len(placebo)}")
        print(f"Typical move (median):  {pct(placebo, 0.5):.1f} pts")
        print(f"Big move (90th pct):    {pct(placebo, 0.9):.1f} pts")
        print(f"Rare move (95th pct):   {pct(placebo, 0.95):.1f} pts")

        print("\nReal events vs random moments:")
        for event_time, source, title in events:
            w = window(series, event_time)
            if len(w) < 20:
                continue
            r = analyze(w, event_time)
            if not r:
                continue
            move = abs(r["peak_move"])
            p_value = sum(1 for m in placebo if m >= move) / len(placebo)
            verdict = "SIGNIFICANT" if p_value < 0.05 else "not significant"
            print(f"  {event_time:%Y-%m-%d} | move {move:4.1f} pts | "
                  f"bigger than {100 * (1 - p_value):3.0f}% of random moments | {verdict}")


if __name__ == "__main__":
    main()