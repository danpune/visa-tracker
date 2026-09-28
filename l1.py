"""L-1 data from USCIS (stdlib only). build.py imports employer() and national().

raw/l1/l1_<FY>.csv        "Approved L-1 Petitions by Employer", FY2015-FY2019 (USCIS stopped publishing after FY2019)
raw/l1/i129_rfe_*.xlsx    "Nonimmigrant Worker Petitions by Case Status and RFE" quarterly workbooks (L-1A, L-1B, blanket L)
"""
import csv, glob, io, re, zipfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
norm = lambda s: re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()


def _num(s):
    s = s.replace(",", "").strip()
    return int(float(s)) if re.fullmatch(r"\d+(\.\d+)?", s) else None  # "D"/"H" = withheld by USCIS


def employer(owner):
    """owner: {normalized L-1 filer name: company id} -> ({id: {FY: stats}}, {FY: national total}, top filers FY2019)."""
    per, totals, top = defaultdict(dict), {}, []
    for path in sorted(glob.glob("raw/l1/l1_*.csv")):
        fy = int(re.search(r"(\d{4})", path).group(1))
        rows = list(csv.reader(io.StringIO(open(path, "rb").read().decode("cp1252"))))
        start = next(i for i, r in enumerate(rows) if len(r) > 1 and "NAME" in r[1].upper()) + 1
        stats, blocks, cid = defaultdict(Counter), Counter(), None
        for r in rows[start:]:
            if len(r) < 7:
                continue
            name = r[1].strip()
            if name.upper() in ("TOTAL", "GRAND TOTAL") or r[0].strip().upper() == "TOTAL":
                totals[fy] = _num(r[3]) or _num(r[6])
                continue
            if name:  # first row of an employer block carries its name and total
                cid = owner.get(norm(name))
                t = _num(r[3])
                blocks["@" + cid if cid else name] += t or 0  # our companies rolled up, others as filed
                if cid:
                    stats[cid]["total"] += t or 0
                    stats[cid]["withheld"] += t is None
            n = _num(r[6])
            if cid and n:
                cls = r[5].replace("-", "").upper()
                stats[cid][{"L1A": "l1a", "L1B": "l1b"}.get(cls, "other")] += n
                stats[cid]["initial" if r[4].strip().upper() == "INITIAL" else "continuing"] += n
        for cid, s in stats.items():
            per[cid][fy] = dict(s)
        if fy == 2019:
            top = [[n, v] for n, v in blocks.most_common(15)]
    return per, totals, top


def _col(ref):  # "C12" -> 2
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def _sheets(path):
    z = zipfile.ZipFile(path)
    names = [s.get("name") for s in ET.fromstring(z.read("xl/workbook.xml")).iter(NS + "sheet")]
    ss = ["".join(t.text or "" for t in si.iter(NS + "t")) for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si")]
    for i, n in enumerate(names, 1):
        rows = []
        for r in ET.fromstring(z.read(f"xl/worksheets/sheet{i}.xml")).iter(NS + "row"):
            cells = {}
            for c in r.iter(NS + "c"):
                v = c.find(NS + "v")
                cells[_col(c.get("r"))] = (ss[int(v.text)] if c.get("t") == "s" else v.text) if v is not None else ""
            rows.append([cells.get(j, "") for j in range(max(cells) + 1)] if cells else [])
        yield n, rows


def national():
    """{kind: {FY: {received, approved, denied, rfe}}} for L-1A, L-1B, blanket L and H-1B (for scale)."""
    kinds = {"l1a": "l1a", "l1b": "l1b", "blanket_l": "blanket", "h1b": "h1b"}
    out = defaultdict(lambda: defaultdict(Counter))
    for path in sorted(glob.glob("raw/l1/i129_rfe_*.xlsx")):
        for name, rows in _sheets(path):
            kind = next((v for k, v in kinds.items() if name.lower().endswith(k) or f"_{k}_" in name.lower() + "_"), None)
            if not kind:
                continue
            hdr = next(r for r in rows if r and r[0].strip() == "Fiscal Year")
            col = {k: next(i for i, h in enumerate(hdr) if h.strip().startswith(label))
                   for k, label in [("received", "Petitions Received"), ("approved", "Initially Approved"),
                                    ("denied", "Initially Denied"), ("rfe", "Completions with RFE")]}
            fy = None
            for r in rows[rows.index(hdr) + 1:]:
                if not r or r[0].strip().upper() == "TOTAL":
                    continue
                if re.fullmatch(r"\d{4}", r[0].strip()):  # first month of a fiscal year carries the year
                    fy = int(r[0])
                if fy and len(r) > max(col.values()) and r[1].strip():  # monthly rows only; skip "2017 Total" subtotals
                    for k, i in col.items():
                        v = _num(r[i]) if r[i] else None
                        if v is not None:
                            out[kind][fy][k] += v
    return {k: {fy: dict(v) for fy, v in sorted(d.items())} for k, d in out.items()}


def entries():
    """DHS yearbook FY2024 I-94 L-1 admissions: total, top countries of citizenship, top destination states.
    Admissions are arrival events, not people (frequent border crossers count many times); cells rounded to 10."""
    pretty = {"China, People's Republic": "China", "Korea, South": "South Korea"}
    out = {}
    for name, rows in _sheets("raw/l1/ohss_yearbook_ni_fy2024.xlsx"):
        key = {"NISuppTable1": "countries", "NISuppTable3": "states"}.get(name)
        if not key:
            continue
        hdr = next(r for r in rows if r and r[0].strip() == "Class")
        l1 = next(r for r in rows if r and r[0].strip() == "L1")
        out["total"] = _num(l1[2])
        vals = [(re.sub(r"\d+$", "", h).strip(), _num(v)) for h, v in zip(hdr[3:], l1[3:]) if _num(v)]
        vals = [(pretty.get(n, n), v) for n, v in vals if n not in ("Unknown", "Total")]
        out[key] = sorted(vals, key=lambda x: -x[1])[:8]
    return out


if __name__ == "__main__":  # self-check against totals USCIS prints in its own files
    import json
    nat = national()
    assert nat["h1b"][2026]["approved"] == 270419, nat["h1b"][2026]      # FY2026 Q3 workbook TOTAL row
    assert nat["l1a"][2025]["received"] == 26551, nat["l1a"][2025]      # FY2025 Q4 workbook TOTAL row
    assert sum(v["approved"] for fy, v in nat["l1a"].items() if 2017 <= fy <= 2024) == 171654
    owner = {norm(n): c["id"] for c in json.load(open("companies.json")) for n in c["l1_names"]}
    per, totals, top = employer(owner)
    assert totals[2019] == 30431 and totals[2017] == 36315, totals
    print(json.dumps({k: {fy: v for fy, v in nat[k].items()} for k in nat})[:600])
    for cid, ys in per.items():
        print(cid, {fy: (s["total"], s.get("withheld", 0), s.get("l1a", 0), s.get("l1b", 0)) for fy, s in sorted(ys.items())})
    print(totals, top[:8])
    e = entries()
    assert e["total"] == 598330 and e["countries"][0] == ("Canada", 156760) and e["states"][0] == ("Texas", 94530), e
    print(e)
