# One place for settings shared across scripts.

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DATA = "https://data-api.polymarket.com/v2"
WS_MARKET = "wss://ws-subscriptions-clob.polymarket.com/ws/market"

DB_PATH = "data/polybot.db"

ECON_KEYWORDS = ["fed ", "federal reserve", "rate cut", "interest rate", "fomc",
                 "inflation", "cpi", "unemployment", "payroll", "recession", "gdp"]

# Main markets for research (label -> "Yes" token ID)
MARKETS = {
    "Dec hike 25":   "111662129652828266889360374468657435151479595863413519836161861837506140152890",
    "Dec no change": "42865728742506860386768556888821101266630139112044622335353850919229585308601",
}