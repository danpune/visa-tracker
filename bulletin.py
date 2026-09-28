"""Visa bulletin cutoffs for EB1/EB2/EB3/F2A (stdlib only).

build.py imports shape(). Run directly (daily in CI) to refresh just the bulletin inside data.json:
travel.state.gov blocks scripts, so this reads a public mirror that was cross-checked against the
original State Department pages (see README).
"""
import json, sys, urllib.request
from datetime import datetime, timezone

MIRROR = "https://raw.githubusercontent.com/MOOnLyer/PR-ETA-data/main/us_visa_bulletin.json"
CATS, AREAS = ["EB1", "EB2", "EB3", "F2A"], ["worldwide", "india", "china", "mexico", "philippines"]


def shape(vb):
    months = sorted({x["bulletinMonth"] for x in vb if x["bulletinMonth"] >= "2016-01"})
    look = {(x["bulletinMonth"], x["table"], x["category"], x["area"]): x["status"] for x in vb}
    ym = [int(m[:4]) * 12 + int(m[5:]) for m in months]
    assert ym == list(range(ym[0], ym[-1] + 1)), "visa bulletin has a missing month"
    series = {c: {t: {a: [look.get((m, t, c, a)) for m in months] for a in AREAS}
                  for t in ["finalAction", "datesForFiling"]} for c in CATS}
    assert all(series[c]["finalAction"]["worldwide"][-1] for c in CATS), "latest bulletin month is empty"
    return {"months": months, "series": series}


if __name__ == "__main__":
    with urllib.request.urlopen(MIRROR, timeout=60) as r:
        new = shape(json.load(r))
    data = json.load(open("data.json"))
    if new["months"][-1] < data["bulletin"]["months"][-1]:
        sys.exit("mirror is older than what we have; keeping data.json")
    if new != data["bulletin"]:
        data["bulletin"] = new
        data["updated"]["bulletin"] = new["months"][-1]
        data["updated"]["site"] = datetime.now(timezone.utc).date().isoformat()
        json.dump(data, open("data.json", "w"), separators=(",", ":"))
    print("bulletin through", new["months"][-1])
