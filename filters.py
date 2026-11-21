# Rules for which news releases are likely to move prediction markets.

IMPORTANT_KEYWORDS = {
    "fed": [
        "fomc statement",
        "federal open market committee",
        "monetary policy",
        "minutes of the",
        "interest rate",
    ],
}

EXCLUDE_KEYWORDS = ["schedule", "discount rate meetings"]


def is_important(source, title):
    # Every entry in the BLS report feeds (CPI, jobs, PPI, JOLTS) is a real release
    if source.startswith("bls_"):
        return True

    title = (title or "").lower()
    if any(k in title for k in EXCLUDE_KEYWORDS):
        return False
    return any(k in title for k in IMPORTANT_KEYWORDS.get(source, []))