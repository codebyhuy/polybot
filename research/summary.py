import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MARKET = "Dec hike 25"   # main market to summarize
SIG_THRESHOLD = 2.0      # 95th percentile of random no-news moves (from placebo.py)


def event_type(source, title):
    t = title.lower()
    if source == "bls_cpi":
        return "CPI"
    if source == "bls_jobs":
        return "Jobs report"
    if source == "bls_ppi":
        return "PPI"
    if source == "bls_jolts":
        return "JOLTS"
    if "statement" in t:
        return "FOMC statement"
    if "minutes" in t:
        return "FOMC minutes"
    return "Other Fed"


groups = defaultdict(list)
for r in csv.DictReader(open("results/event_study.csv")):
    if r["market"] != MARKET:
        continue
    groups[event_type(r["source"], r["title"])].append(r)

rows = []
for etype, events in groups.items():
    moves = [abs(float(e["peak_move"])) for e in events]
    sig = [e for e in events if abs(float(e["peak_move"])) > SIG_THRESHOLD]
    speeds = [int(e["mins_to_peak"]) for e in sig]
    reversals = [int(e["reversal_pct"]) for e in sig if e["reversal_pct"] not in ("", "None")]
    rows.append({
        "type": etype,
        "events": len(events),
        "significant": f"{len(sig)}/{len(events)}",
        "avg_move_pts": round(sum(moves) / len(moves), 1),
        "avg_mins_to_peak": round(sum(speeds) / len(speeds), 1) if speeds else "-",
        "avg_reversal_pct": round(sum(reversals) / len(reversals)) if reversals else "-",
    })

rows.sort(key=lambda r: r["avg_move_pts"], reverse=True)

print(f"\nMarket: {MARKET}  |  significant = move > {SIG_THRESHOLD} pts (beats 95% of random moments)\n")
print(f"{'Type':16} {'Events':>6} {'Signif':>7} {'Avg move':>9} {'Mins to peak':>13} {'Reversal':>9}")
for r in rows:
    print(f"{r['type']:16} {r['events']:>6} {r['significant']:>7} {r['avg_move_pts']:>8} "
          f"{str(r['avg_mins_to_peak']):>13} {str(r['avg_reversal_pct']) + '%':>9}")

os.makedirs("results", exist_ok=True)
with open("results/summary.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

os.makedirs("charts", exist_ok=True)
plt.figure(figsize=(8, 4))
plt.bar([r["type"] for r in rows], [r["avg_move_pts"] for r in rows])
plt.axhline(SIG_THRESHOLD, color="red", linestyle="--", label="Random-noise threshold")
plt.ylabel("Avg peak move (pts)")
plt.title(f"How much each type of news moves '{MARKET}'")
plt.legend()
plt.tight_layout()
plt.savefig("charts/summary.png")
print("\nSaved results/summary.csv and charts/summary.png")