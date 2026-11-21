import csv
import os
import time
from datetime import datetime, timezone

import feedparser
import requests

from research.filters import is_important

FEEDS = {
"bls_cpi": "https://www.bls.gov/feed/cpi.rss",
"bls_jobs": "https://www.bls.gov/feed/empsit.rss",
"bls_ppi": "https://www.bls.gov/feed/ppi.rss",
"bls_jolts": "https://www.bls.gov/feed/jolts.rss",
}
INTERVAL = 30
OUTFILE = "data/news.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (polybot research; contact: huychau.hcc@gmail.com)"}

os.makedirs("data", exist_ok=True)

# Remember headlines we've already logged so we only record new ones
seen = set()
if os.path.exists(OUTFILE):
    with open(OUTFILE) as f:
        for row in csv.DictReader(f):
            seen.add(row["link"])

new_file = not os.path.exists(OUTFILE)
first_run = len(seen) == 0

print(f"Watching {len(FEEDS)} feeds, {len(seen)} headlines already logged...", flush=True)

with open(OUTFILE, "a", newline="") as f:
    writer = csv.writer(f)
    if new_file:
        writer.writerow(["first_seen", "source", "published", "title", "link", "backfill"])

    while True:
        for source, url in FEEDS.items():
            try:
                resp = requests.get(url, headers=HEADERS, timeout=10)
                feed = feedparser.parse(resp.content)
                now = datetime.now(timezone.utc).isoformat()
                for entry in feed.entries:
                    link = entry.get("link", "")
                    if link in seen:
                        continue
                    seen.add(link)
                    writer.writerow([now, source, entry.get("published", ""),
                                     entry.get("title", ""), link, first_run])
                    if not first_run:
                                                title = entry.get("title", "")
                    tag = "IMPORTANT!!!!!!!!!" if is_important(source, title) else "noise"
                    print(f"{now}  NEW [{source}] ({tag}) {title}")
                f.flush()
            except Exception as e:
                print(f"Error ({source}):", e)

        if first_run:
            print(f"Loaded {len(seen)} existing headlines. Watching for new ones...")
            first_run = False
        time.sleep(INTERVAL)