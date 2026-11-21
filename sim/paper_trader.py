import asyncio
import csv
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import websockets

from config import DB_PATH, MARKETS, WS_MARKET
PAPER_DB = "data/paper.db"

from research.filters import is_important

QUOTE_SIZE = 10
MAX_INV = 100
HALF_SPREAD = 1.0
SKEW = 1.0
FILL_SHARE = 0.10
PULL_BEFORE = timedelta(minutes=5)
PULL_AFTER = timedelta(minutes=30)

TOKEN_TO_LABEL = {token: label for label, token in MARKETS.items()}


def load_danger_times():
    """Scheduled releases + any important release the news watcher just logged."""
    times = []
    if os.path.exists("events/schedule.csv"):
        for r in csv.DictReader(open("events/schedule.csv")):
            try:
                times.append(datetime.strptime(r["time_utc"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc))
            except ValueError:
                pass
    if os.path.exists("data/news.csv"):
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        for r in csv.DictReader(open("data/news.csv")):
            try:
                seen = datetime.fromisoformat(r["first_seen"])
            except ValueError:
                continue
            if seen > cutoff and is_important(r["source"], r["title"]):
                times.append(seen)
    return times


def in_danger(now, times):
    return any(t - PULL_BEFORE <= now <= t + PULL_AFTER for t in times)


def init_db():
    conn = sqlite3.connect(PAPER_DB, timeout=30)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS paper_state (market TEXT PRIMARY KEY, ref REAL, inv REAL,
                                                cash REAL, fills INTEGER);
        CREATE TABLE IF NOT EXISTS paper_fills (ts TEXT, market TEXT, side TEXT, price REAL,
                                                qty REAL, inv_after REAL, cash_after REAL);
    """)
    state = {label: {"ref": None, "inv": 0.0, "cash": 0.0, "fills": 0} for label in MARKETS}
    for market, ref, inv, cash, fills in conn.execute("SELECT * FROM paper_state"):
        if market in state:
            state[market] = {"ref": ref, "inv": inv, "cash": cash, "fills": fills}
    return conn, state


def on_trade(conn, state, label, side, price, size, danger):
    s = state[label]
    now = datetime.now(timezone.utc).isoformat()
    if s["ref"] is not None and not danger:
        center = s["ref"] - SKEW * (s["inv"] / MAX_INV)
        bid, ask = center - HALF_SPREAD, center + HALF_SPREAD
        qty = min(QUOTE_SIZE, size * FILL_SHARE)
        filled = None
        if side == "SELL" and price <= bid and s["inv"] + qty <= MAX_INV:
            s["cash"] -= bid * qty; s["inv"] += qty; filled = ("BUY", bid)
        elif side == "BUY" and price >= ask and s["inv"] - qty >= -MAX_INV:
            s["cash"] += ask * qty; s["inv"] -= qty; filled = ("SELL", ask)
        if filled:
            s["fills"] += 1
            conn.execute("INSERT INTO paper_fills VALUES (?,?,?,?,?,?,?)",
                         (now, label, filled[0], filled[1], qty, s["inv"], s["cash"]))
            print(f"{now[11:19]}  FILL {label:14} {filled[0]:4} {qty:5.1f} @ {filled[1]:5.1f}c  "
                  f"inv {s['inv']:+6.1f}", flush=True)
    s["ref"] = price
    conn.execute("INSERT OR REPLACE INTO paper_state VALUES (?,?,?,?,?)",
                 (label, s["ref"], s["inv"], s["cash"], s["fills"]))


def report(state, danger):
    print(f"\n--- {time.strftime('%H:%M:%S')}  {'PAUSED (news window)' if danger else 'quoting'} ---", flush=True)
    total = 0.0
    for label, s in state.items():
        if s["ref"] is None:
            print(f"  {label:14} waiting for first trade", flush=True)
            continue
        pnl = (s["cash"] + s["inv"] * s["ref"]) / 100
        total += pnl
        print(f"  {label:14} price {s['ref']:5.1f}c | inv {s['inv']:+6.1f} | fills {s['fills']:4} | P&L ${pnl:+.2f}", flush=True)
    print(f"  TOTAL P&L ${total:+.2f}\n", flush=True)


async def heartbeat(ws):
    while True:
        await asyncio.sleep(10)
        await ws.send("PING")


async def session(conn, state):
    async with websockets.connect(WS_MARKET, ping_interval=None, max_size=None) as ws:
        await ws.send(json.dumps({"assets_ids": list(TOKEN_TO_LABEL), "type": "market"}))
        pinger = asyncio.create_task(heartbeat(ws))
        danger_times, last_refresh, last_report = load_danger_times(), time.time(), 0
        try:
            async for raw in ws:
                if raw == "PONG":
                    continue
                now = datetime.now(timezone.utc)
                if time.time() - last_refresh > 30:
                    danger_times, last_refresh = load_danger_times(), time.time()
                danger = in_danger(now, danger_times)
                data = json.loads(raw)
                for msg in (data if isinstance(data, list) else [data]):
                    if msg.get("event_type") != "last_trade_price":
                        continue
                    label = TOKEN_TO_LABEL.get(msg.get("asset_id"))
                    if label:
                        on_trade(conn, state, label, msg.get("side"),
                                 float(msg["price"]) * 100, float(msg["size"]), danger)
                conn.commit()
                if time.time() - last_report > 300:
                    report(state, danger)
                    last_report = time.time()
        finally:
            pinger.cancel()


async def main():
    conn, state = init_db()
    print("Paper trader starting (no real money). Strategy: 1c spread, 1c skew, news protection.", flush=True)
    while True:
        try:
            await session(conn, state)
        except Exception as e:
            print("Connection error, reconnecting in 5s:", e, flush=True)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
    
    