import json
import requests

URL = "https://gamma-api.polymarket.com/markets"

resp = requests.get(URL, params={"active": "true", "closed": "false", "limit": 500})
print("Status:", resp.status_code)

markets = resp.json()
print("Markets received:", len(markets))
print()

markets.sort(key=lambda m: float(m.get("volume24hr") or 0), reverse=True)

for m in markets[:15]:
    question = m.get("question", "")
    prices = json.loads(m.get("outcomePrices") or "[]")
    outcomes = json.loads(m.get("outcomes") or "[]")
    print(question)
    for name, price in zip(outcomes, prices):
        print(f"   {name}: {float(price) * 100:.1f}%")
    print()
    