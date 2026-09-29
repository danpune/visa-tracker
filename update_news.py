#!/usr/bin/env python3
"""Build news.json from USCIS alerts (stdlib only). Adapted from danpune/greencard-checklist; run daily by .github/workflows/refresh.yml."""
import json, os, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
ALERTS = "https://www.uscis.gov/news/rss-feed/22984"
# Flags items that matter to work-visa holders and employers.
HIT = re.compile(r"h-?1b|h-?4|\bl-?1|\bl-?2|\bo-?1|\btn\b|e-?3|perm|labor certification|prevailing wage|"
                 r"visa bulletin|priority date|green card|adjustment of status|i-485|i-140|i-129|i-765|\bead\b|"
                 r"employment|employer|worker|opt\b|f-?1|stem|lottery|registration|\bcap\b|\bfees?\b", re.I)
ALLOWED = ("https://www.uscis.gov/",)

def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()

def item(title, url, date, source):
    title = " ".join(title.split())
    if not title or not url.startswith(ALLOWED):
        return None
    return {"title": title[:200], "url": url, "date": date, "source": source, "hit": bool(HIT.search(title))}

def alerts():
    out = []
    for it in ET.fromstring(get(ALERTS)).iter("item"):
        d = parsedate_to_datetime(it.findtext("pubDate")).date().isoformat()
        out.append(item(it.findtext("title") or "", (it.findtext("link") or "").strip(), d, "USCIS alert"))
    return out[:10]

items, failed = [], []
for fn in (alerts,):  # ponytail: one feed today; add sources to this tuple
    try:
        items += [i for i in fn() if i]
    except Exception as e:  # one source down must not wipe the other
        failed.append(f"{fn.__name__}: {e}")
print("failed:", failed or "none", "| items:", len(items))
if not items:
    sys.exit(1)  # keep the previous news.json
items.sort(key=lambda i: i["date"], reverse=True)

new = {"updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "items": items}
try:
    old = json.load(open("news.json"))
    if old.get("items") == items:
        new["updated"] = old["updated"]  # no churn commits when nothing changed
except (OSError, ValueError):
    pass
with open("news.json.tmp", "w") as f:
    json.dump(new, f, indent=1, ensure_ascii=False)
os.replace("news.json.tmp", "news.json")  # atomic write
