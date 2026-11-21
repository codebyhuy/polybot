from datetime import timedelta

from batch_study import get_history, load_events, price_at

TOKEN = "111662129652828266889360374468657435151479595863413519836161861837506140152890"  # Dec hike 25
COST_LEVELS = [0, 1, 2]  # round-trip cost in points (spread + fees + slippage)


def event_type(source, title):
    t = title.lower()
    if source == "bls_cpi":
        return "CPI"
    if source == "bls_jobs":
        return "Jobs report"
    if source.startswith("bls_"):
        return "Other BLS"
    if "statement" in t:
        return "FOMC statement"
    if "minutes" in t:
        return "FOMC minutes"
    return "Other Fed"


STRATEGIES = {
    "momentum": {"types": {"CPI", "Jobs report", "FOMC statement"},
                 "entry_min": 2, "exit_min": 30, "min_move": 1.0, "direction": +1},
    "fade":     {"types": {"FOMC statement", "FOMC minutes"},
                 "entry_min": 10, "exit_min": 60, "min_move": 2.0, "direction": -1},
}


def run(name, s, events):
    trades = []
    for event_time, source, title in events:
        etype = event_type(source, title)
        if etype not in s["types"]:
            continue
        series = get_history(TOKEN, event_time - timedelta(hours=1), event_time + timedelta(hours=2))
        if len(series) < 20:
            continue
        before = price_at(series, event_time - timedelta(minutes=1))
        entry = price_at(series, event_time + timedelta(minutes=s["entry_min"]))
        exit_ = price_at(series, event_time + timedelta(minutes=s["exit_min"]))
        move = entry - before
        if abs(move) < s["min_move"]:
            continue
        side = s["direction"] * (1 if move > 0 else -1)  # +1 = bet odds go up, -1 = bet they go down
        pnl = side * (exit_ - entry)
        trades.append(pnl)
        print(f"  {event_time:%Y-%m-%d} {etype:15} entry {entry:5.1f} exit {exit_:5.1f} "
              f"bet {'UP  ' if side > 0 else 'DOWN'} pnl {pnl:+.1f} pts")

    print(f"\n  {name}: {len(trades)} trades")
    if not trades:
        return
    for cost in COST_LEVELS:
        net = [p - cost for p in trades]
        wins = sum(1 for p in net if p > 0)
        print(f"  cost {cost} pt: total {sum(net):+.1f} pts | avg {sum(net)/len(net):+.2f} | "
              f"win rate {100*wins/len(net):.0f}%")


def main():
    events = load_events()
    for name, s in STRATEGIES.items():
        print(f"\n=== {name.upper()} ===")
        run(name, s, events)


if __name__ == "__main__":
    main()
    