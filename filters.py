# Rules for which news releases are likely to move prediction markets.

IMPORTANT_KEYWORDS = {
    "fed": [
        "fomc statement",
        "federal open market committee",
        "monetary policy",
        "minutes of the",
        "discount rate",
        "interest rate",
    ],
    "bls": [
        "consumer price index",
        "employment situation",
        "producer price index",
        "job openings",
        "jolts",
        "real earnings",
        "employment cost index",
        "unemployment",
    ],
}


def is_important(source, title):
    title = (title or "").lower()
    return any(k in title for k in IMPORTANT_KEYWORDS.get(source, []))
