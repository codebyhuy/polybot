from datetime import datetime, timezone
import requests

DATA = "https://data-api.polymarket.com/v2"
CONDITION_ID = "0x8a4196617dcb703e49d9bb36d3847bf6a75fd364dbd19f8d408ac944bf1a03d8"  # Dec hike 25

resp = requests.get(f"{DATA}/trades", params={"condition": CONDITION_ID, "limit": 20}, timeout=15)
print("Status:", resp.status_code)
body = resp.json()
trades = body.get("data") or []
print("Trades returned:", len(trades))
print("More pages available:", body.get("pagination", {}).get("has_more"))
print()

for t in trades:
    ts = datetime.fromtimestamp(int(t["timestamp"]), tz=timezone.utc)
    print(f"{ts:%Y-%m-%d %H:%M:%S}  {t.get('side'):4}  {t.get('outcome'):4}  "
          f"price {float(t['price']) * 100:5.1f}  size {float(t['size']):8.1f}")
    