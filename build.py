"""Build data.json for the site from the raw government files (stdlib only).

Inputs (raw/ is gitignored, see README for where each comes from):
  raw/uscis_<FY>.csv              USCIS H-1B Employer Data Hub export, one per fiscal year
  raw/lca.csv                     DOL LCA disclosure, slimmed by xlsx_to_csv.py
  raw/visa_bulletin_mirror.json   State Dept visa bulletin, mirrored (cross-checked, see README)
  companies.json, layoffs.json, headcount.json (hand-curated, sourced)
"""
import csv, glob, json, re, statistics
from datetime import datetime, timezone

from bulletin import shape
import l1
from collections import Counter, defaultdict

YEARS = sorted(int(re.search(r"(\d{4})", f).group(1)) for f in glob.glob("raw/uscis_*.csv"))
PER_YEAR = {"Year": 1, "Hour": 2080, "Week": 52, "Bi-Weekly": 26, "Month": 12}


def norm(name):
    return re.sub(r"[^A-Z0-9]+", " ", name.upper()).strip()


companies = json.load(open("companies.json"))
owner = {n: c["id"] for c in companies for n in c["names"]}

# --- USCIS: approvals per employer per fiscal year -------------------------------------------
uscis = {c["id"]: {y: Counter() for y in YEARS} for c in companies}
national = {y: Counter() for y in YEARS}
for y in YEARS:
    for row in csv.DictReader(open(f"raw/uscis_{y}.csv", encoding="utf-8-sig")):
        v = int(row["Measure Values"].replace(",", "") or 0)
        m = row["Measure Names"]
        kind = "approvals" if m.endswith("Approval") else "denials"
        keys = [kind] + (["new"] if m == "New Employment Approval" else [])
        cid = owner.get(norm(row["Employer (Petitioner) Name"]))
        for k in keys:
            national[y][k] += v
            if cid:
                uscis[cid][y][k] += v

# --- DOL LCA: where H-1B jobs are and what they pay ---------------------------------------------
def annual(row):
    try:
        w = float(row["WAGE_RATE_OF_PAY_FROM"]) * PER_YEAR[row["WAGE_UNIT_OF_PAY"]]
    except (ValueError, KeyError):
        return None
    return w if 15_000 <= w <= 2_000_000 else None  # ponytail: drops typos like $1/yr; median barely moves


def summarize(rows):
    wages = sorted(w for w in (annual(r) for r in rows) if w)
    pos = lambda key: Counter({k: v for k, v in _count(rows, key).items() if k})
    q = statistics.quantiles(wages, n=4) if len(wages) > 3 else [None] * 3
    return {"lcas": len(rows), "positions": sum(_n(r) for r in rows),
            "wage_p25": q[0], "wage_median": q[1], "wage_p75": q[2],
            "levels": dict(_count(rows, "PW_WAGE_LEVEL")),
            "top_titles": pos("SOC_TITLE").most_common(6),
            "top_states": pos("WORKSITE_STATE").most_common(6),
            "counties": dict(_count(rows, "COUNTY"))}


def _n(r):
    try:
        return max(1, int(float(r["TOTAL_WORKER_POSITIONS"])))
    except ValueError:
        return 1


def _count(rows, key, positions=False):
    # ponytail: counts filings, not TOTAL_WORKER_POSITIONS; blanket LCAs (Qualcomm: ~42k "positions"
    # in San Diego) would otherwise dominate the map. Positions are slots, not hires, either way.
    c = Counter()
    for r in rows:
        c[r[key]] += _n(r) if positions else 1
    return c


lca_all, lca_by = [], defaultdict(list)
dates = []
for r in csv.DictReader(open("raw/lca.csv")):
    if r["VISA_CLASS"] != "H-1B" or r["CASE_STATUS"] != "Certified":
        continue
    r["COUNTY"] = f'{r["WORKSITE_STATE"]}|{r["WORKSITE_COUNTY"].upper().strip()}'
    lca_all.append(r)
    dates.append(r["RECEIVED_DATE"])
    cid = owner.get(norm(r["EMPLOYER_NAME"]))
    if cid:
        lca_by[cid].append(r)

nat = summarize(lca_all)
nat["states"] = {s: {"lcas": n, "wage_median": statistics.median(
    [w for w in (annual(r) for r in lca_all if r["WORKSITE_STATE"] == s) if w] or [0])}
    for s, n in _count(lca_all, "WORKSITE_STATE").items() if s}
cities = Counter()
for r in lca_all:
    cities[(r["WORKSITE_CITY"].strip().title(), r["WORKSITE_STATE"])] += 1
nat["top_cities"] = [[c, s, n] for (c, s), n in cities.most_common(20)]
dates.sort()

# --- Visa bulletin: EB1/EB2/EB3/F2A since 2016 (CI refreshes this part daily via bulletin.py) -----
bulletin = shape(json.load(open("raw/visa_bulletin_mirror.json")))
months = bulletin["months"]

# --- L-1: employer-level only FY2015-2019 (USCIS stopped publishing), national through the latest quarter --
l1_owner = {norm(n): c["id"] for c in companies for n in c.get("l1_names", [])}
l1_per, l1_totals, l1_top = l1.employer(l1_owner)
l1_nat = l1.national()

# --- Assemble ---------------------------------------------------------------------------------------
layoffs = json.load(open("layoffs.json"))
headcount = {h["id"]: h for h in json.load(open("headcount.json"))}
out = {
    "uscis_years": YEARS,
    "uscis_national": {y: dict(national[y]) for y in YEARS},
    "lca_period": [dates[0], dates[len(dates) // 2], dates[-1]],
    "lca_national": nat,
    "companies": [{
        "id": c["id"], "name": c["name"], "legal_names": c["names"], "l1_names": c.get("l1_names", []),
        "uscis": {y: dict(uscis[c["id"]][y]) for y in YEARS},
        "lca": summarize(lca_by[c["id"]]) if lca_by[c["id"]] else None,
        "layoffs": layoffs.get(c["layoffs"]) if c["layoffs"] else None,
        "headcount": headcount.get(c["id"]),
        "l1": l1_per.get(c["id"], {}),
    } for c in companies],
    "l1": {"employer_totals": l1_totals, "top_2019": l1_top, "national": l1_nat},
    "bulletin": bulletin,
    # when each source was last pulled; shown on the page so readers can judge freshness
    "updated": {"site": datetime.now(timezone.utc).date().isoformat(), "uscis": f"FY{YEARS[-1]} Q3", "lca": dates[-1],
                "bulletin": months[-1], "layoffs": "2026-09-27", "headcount": "2026-09-27",
                "l1_national": f"FY{max(l1_nat['l1a'])} Q3", "l1_employer": f"FY{max(l1_totals)}"},
}
json.dump(out, open("data.json", "w"), separators=(",", ":"))
print(f"FY{YEARS[0]}-{YEARS[-1]}; LCA {len(lca_all)} certified H-1B ({dates[0]}..{dates[-1]}); "
      f"bulletin {months[0]}..{months[-1]}")
for c in out["companies"]:
    print(f'  {c["name"]:28} approvals {[c["uscis"][y].get("approvals", 0) for y in YEARS]}  '
          f'LCA {c["lca"]["lcas"] if c["lca"] else 0}  median ${c["lca"]["wage_median"] or 0:,.0f}')

# --- sanity checks: fail loudly if a source changes shape ------------------------------------------
for c in out["companies"]:
    assert all(c["uscis"][y].get("approvals") for y in YEARS), f'{c["id"]}: a year has no USCIS approvals (renamed entity?)'
    assert c["lca"] and c["lca"]["lcas"] > 100, f'{c["id"]}: too few LCAs matched (renamed entity?)'
assert 50_000 < nat["wage_median"] < 250_000, "median wage looks wrong (unit parsing?)"
assert l1_nat["h1b"][YEARS[-1]]["approved"] == national[YEARS[-1]]["approvals"], "I-129 workbook and Employer Data Hub disagree on H-1B"
assert l1_per["tcs"][2019]["total"] == 1542, "L-1 employer parse changed"
