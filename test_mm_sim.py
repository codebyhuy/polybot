from datetime import datetime, timedelta, timezone

from sim.mm_sim3 import simulate

T0 = datetime(2026, 11, 1, 15, 0, tzinfo=timezone.utc)


def trade(minutes, side, price, size=100):
    return (T0 + timedelta(minutes=minutes), side, price, size)


def test_buy_low_sell_high_earns_spread():
    # Quotes start at 49/51 around the first trade at 50.
    trades = [
        trade(0, "SELL", 50),    # inside our quotes: no fill
        trade(1, "SELL", 49),    # hits our 49 bid: we buy 10
        trade(2, "BUY", 50),     # quotes now 48/50: lifts our 50 ask, we sell 10
    ]
    pnl, fills, max_inv = simulate(trades, [], protect=False, skew=0)
    assert fills == 2
    assert max_inv == 10
    assert abs(pnl - 0.10) < 1e-9   # bought 10 at 49c, sold 10 at 50c = $0.10


def test_protection_skips_fills_near_news():
    event = T0 + timedelta(minutes=10)
    trades = [
        trade(0, "SELL", 50),
        trade(10, "SELL", 49),   # exactly at the news: protected bot must not trade
        trade(50, "BUY", 50),    # 40 min after: outside the window, can trade
    ]
    _, fills_naive, _ = simulate(trades, [event], protect=False, skew=0)
    _, fills_protected, _ = simulate(trades, [event], protect=True, skew=0)
    assert fills_naive == 2
    assert fills_protected == 1


def test_inventory_never_exceeds_limit():
    # A falling market: someone keeps selling into our bid.
    trades = [trade(i, "SELL", 50 - i, size=1000) for i in range(20)]
    _, fills, max_inv = simulate(trades, [], protect=False, skew=0)
    assert max_inv <= 100
    assert fills == 10   # 10 fills of 10 shares hits the 100-share cap


def test_skew_reduces_inventory():
    trades = [trade(i, "SELL", 50 - i, size=1000) for i in range(20)]
    _, _, inv_no_skew = simulate(trades, [], protect=False, skew=0)
    _, _, inv_skew = simulate(trades, [], protect=False, skew=4)
    assert inv_skew <= inv_no_skew
    