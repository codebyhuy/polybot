import csv
from research.filters import is_important

for r in csv.DictReader(open("data/news.csv")):
    if is_important(r["source"], r["title"]):
        print(r["published"], "|", r["source"], "|", r["title"])
        