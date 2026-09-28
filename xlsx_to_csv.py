"""Stream a DOL LCA disclosure .xlsx into a slim CSV (stdlib only; the sheet XML is ~1.6 GB).

usage: python3 xlsx_to_csv.py raw/LCA_Disclosure_Data_FY2026_Q3.xlsx raw/lca.csv
"""
import csv, re, sys, zipfile
import xml.etree.ElementTree as ET
from datetime import date, timedelta

KEEP = ["CASE_STATUS", "RECEIVED_DATE", "VISA_CLASS", "JOB_TITLE", "SOC_TITLE", "FULL_TIME_POSITION",
        "TOTAL_WORKER_POSITIONS", "EMPLOYER_NAME", "EMPLOYER_STATE", "WORKSITE_CITY", "WORKSITE_COUNTY",
        "WORKSITE_STATE", "WAGE_RATE_OF_PAY_FROM", "WAGE_UNIT_OF_PAY", "PW_WAGE_LEVEL"]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def col_index(ref):  # "AB12" -> 27
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group():
        n = n * 26 + ord(ch) - 64
    return n - 1


def main(src, dst):
    z = zipfile.ZipFile(src)
    strings = []
    for _, el in ET.iterparse(z.open("xl/sharedStrings.xml")):
        if el.tag == NS + "si":
            strings.append("".join(t.text or "" for t in el.iter(NS + "t")))
            el.clear()
    out = csv.writer(open(dst, "w", newline=""))
    keep_idx, n = None, 0
    for _, el in ET.iterparse(z.open("xl/worksheets/sheet1.xml")):
        if el.tag != NS + "row":
            continue
        row = {}
        for c in el.iter(NS + "c"):
            v = c.find(NS + "v")
            if c.get("t") == "s":
                val = strings[int(v.text)]
            elif c.get("t") == "inlineStr":
                val = "".join(t.text or "" for t in c.iter(NS + "t"))
            else:
                val = v.text if v is not None else ""
            row[col_index(c.get("r"))] = val
        el.clear()
        if keep_idx is None:  # header row
            names = {v: k for k, v in row.items()}
            keep_idx = [names[k] for k in KEEP]
            out.writerow(KEEP)
            continue
        vals = [row.get(i, "") for i in keep_idx]
        rd = vals[1]  # RECEIVED_DATE arrives as an Excel serial number
        if re.fullmatch(r"\d+(\.\d+)?", rd):
            vals[1] = (date(1899, 12, 30) + timedelta(days=int(float(rd)))).isoformat()
        out.writerow(vals)
        n += 1
    print(f"{n} rows -> {dst}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
