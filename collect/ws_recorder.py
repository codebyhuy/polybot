import asyncio
import json
import sqlite3
import time

import requests
import websockets

from config import DB_PATH, ECON_KEYWORDS, GAMMA, WS_MARKET

REFRESH_SECONDS = 3600   # re-discover markets and reconnect every hour


def discover_markets():
    """Find open economics markets once; return {yes_token_id: question}."""
    found, offset = {}, 0
    while offset <= 2000:
        batch = requests.get(f"{GAMMA}/markets", params={
            "active": "true", "closed": "false", "limit": 100, "offset": offset}, timeout=15).json()
        if not isinstance(batch, list) or not batch:
            break
        for m in batch:
            q = (m.get("question") or "").lower()
            tokens = json.loads(m.get("clobTokenIds") or "[]")
            if tokens and any(k in q for k in ECON_KEYWORDS):
                found[tokens[0]] = m.get("question")
        offset += len(batch)
    return found


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS markets (asset_id TEXT PRIMARY KEY, question TEXT);
        CREATE TABLE IF NOT EXISTS quotes (recv_ts REAL, server_ts INTEGER, asset_id TEXT,
                                           best_bid REAL, best_ask REAL);
        CREATE TABLE IF NOT EXISTS trades (recv_ts REAL, server_ts INTEGER, asset_id TEXT,
                                           price REAL, size REAL, side TEXT);
        CREATE INDEX IF NOT EXISTS idx_quotes ON quotes (asset_id, recv_ts);
        CREATE INDEX IF NOT EXISTS idx_trades ON trades (asset_id, recv_ts);
    """)
    return conn


def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def handle(conn, msg, tracked, counts):
    now = time.time()
    etype = msg.get("event_type")
    server_ts = int(msg.get("timestamp") or 0)

    if etype == "book":
        bids = [to_float(b.get("price")) for b in msg.get("bids", [])]
        asks = [to_float(a.get("price")) for a in msg.get("asks", [])]
        bids, asks = [b for b in bids if b], [a for a in asks if a]
        if msg.get("asset_id") in tracked and bids and asks:
            conn.execute("INSERT INTO quotes VALUES (?,?,?,?,?)",
                         (now, server_ts, msg["asset_id"], max(bids), min(asks)))
            counts["quotes"] += 1

    elif etype == "price_change":
        for pc in msg.get("price_changes", []):
            if pc.get("asset_id") in tracked:
                conn.execute("INSERT INTO quotes VALUES (?,?,?,?,?)",
                             (now, server_ts, pc["asset_id"],
                              to_float(pc.get("best_bid")), to_float(pc.get("best_ask"))))
                counts["quotes"] += 1

    elif etype == "last_trade_price":
        if msg.get("asset_id") in tracked:
            conn.execute("INSERT INTO trades VALUES (?,?,?,?,?,?)",
                         (now, server_ts, msg["asset_id"], to_float(msg.get("price")),
                          to_float(msg.get("size")), msg.get("side")))
            counts["trades"] += 1


async def heartbeat(ws):
    while True:
        await asyncio.sleep(10)
        await ws.send("PING")


async def session(conn):
    tracked = discover_markets()
    conn.executemany("INSERT OR REPLACE INTO markets VALUES (?,?)", tracked.items())
    conn.commit()
    print(f"Tracking {len(tracked)} economics markets", flush=True)

    async with websockets.connect(WS_MARKET, ping_interval=None, max_size=None) as ws:
        await ws.send(json.dumps({"assets_ids": list(tracked), "type": "market"}))
        pinger = asyncio.create_task(heartbeat(ws))
        counts, start, last_report = {"quotes": 0, "trades": 0}, time.time(), time.time()
        try:
            async for raw in ws:
                if raw == "PONG":
                    continue
                data = json.loads(raw)
                for msg in (data if isinstance(data, list) else [data]):
                    handle(conn, msg, tracked, counts)
                if time.time() - last_report > 30:
                    conn.commit()
                    print(f"{time.strftime('%H:%M:%S')}  +{counts['quotes']} quotes, "
                          f"+{counts['trades']} trades (last 30s)", flush=True)
                    counts, last_report = {"quotes": 0, "trades": 0}, time.time()
                if time.time() - start > REFRESH_SECONDS:
                    break
        finally:
            pinger.cancel()
            conn.commit()


async def main():
    conn = init_db()
    while True:
        try:
            await session(conn)
        except Exception as e:
            print("Connection error, reconnecting in 5s:", e, flush=True)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
    