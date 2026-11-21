from research.batch_study import load_events
from sim.mm_sim2 import MARKETS, MAX_INV, QUOTE_SIZE, condition_for, fetch_trades, in_danger


def simulate(trades, event_times, protect, skew, half_spread=1.0, fill_share=0.10):
    """skew = how many cents to shift quotes when inventory is at its max.
    Long inventory -> lower both prices (sell more easily, buy less).
    Short inventory -> raise both prices."""
    cash, inv, fills, max_inv_seen = 0.0, 0.0, 0, 0.0
    ref = trades[0][2]
    for t, side, price, size in trades:
        if not (protect and in_danger(t, event_times)):
            center = ref - skew * (inv / MAX_INV)
            bid, ask = center - half_spread, center + half_spread
            qty = min(QUOTE_SIZE, size * fill_share)
            if side == "SELL" and price <= bid and inv + qty <= MAX_INV:
                cash -= bid * qty; inv += qty; fills += 1
            elif side == "BUY" and price >= ask and inv - qty >= -MAX_INV:
                cash += ask * qty; inv -= qty; fills += 1
            max_inv_seen = max(max_inv_seen, abs(inv))
        ref = price
    return (cash + inv * ref) / 100, fills, max_inv_seen   # P&L in dollars


def main():
    event_times = [e[0] for e in load_events()]
    for label, token in MARKETS.items():
        trades = fetch_trades(condition_for(token))
        print(f"\n=== {label} ({len(trades)} trades) ===")

        print("\n Strategy comparison (spread 1c, 10% fill share):")
        print(f" {'mode':10} {'skew':>5} {'P&L':>9} {'fills':>6} {'max inv':>8}")
        for protect in [False, True]:
            for skew in [0, 1, 2, 4]:
                pnl, fills, mx = simulate(trades, event_times, protect, skew)
                mode = "protected" if protect else "naive"
                print(f" {mode:10} {skew:>5} {pnl:>+9.2f} {fills:>6} {mx:>8.0f}")

        print("\n Sensitivity (protected, skew 2):")
        print(f" {'spread':>7} {'fill %':>7} {'P&L':>9} {'fills':>6}")
        for half_spread in [1.0, 2.0]:
            for fill_share in [0.05, 0.10, 0.20]:
                pnl, fills, _ = simulate(trades, event_times, True, 2, half_spread, fill_share)
                print(f" {half_spread:>6.0f}c {fill_share * 100:>6.0f}% {pnl:>+9.2f} {fills:>6}")


if __name__ == "__main__":
    main()
    