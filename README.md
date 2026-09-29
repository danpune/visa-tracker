# US Work Visa Tracker

Live at https://danpune.github.io/visa-tracker/

H-1B sponsors, where H-1B jobs are, what they pay, green card priority dates, and a plain-English visa guide.
Static site: `index.html` + `data.json`. No build tools, no API keys.

Run locally: `python3 -m http.server 8756`, then open http://localhost:8756

## Data sources

| What | Source | How it gets here |
|---|---|---|
| H-1B approvals by employer, FY2022–2026 | [USCIS H-1B Employer Data Hub](https://www.uscis.gov/tools/reports-and-studies/h-1b-employer-data-hub) | No official API. The hub is Tableau; its crosstab sheet exports CSV: `https://bigdataanalyticspub-sb.uscis.dhs.gov/views/H1BEmployerDataHub-Final/H1BPublic.csv?Fiscal%20Year%20%20%20=2025` (the field name really has 3 trailing spaces). Save as `raw/uscis_<FY>.csv`. |
| Worksites, salaries, job titles | [DOL LCA disclosure data](https://www.dol.gov/agencies/eta/foreign-labor/performance) | dol.gov blocks scripts, so download the xlsx in a browser, then `python3 xlsx_to_csv.py raw/LCA_Disclosure_Data_FY2026_Q3.xlsx raw/lca.csv` (~2 min). The FY2026 file is cumulative (Oct 2025 – Jun 2026). |
| Visa bulletin, 2016 onward | [State Dept Visa Bulletin](https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin.html) | travel.state.gov blocks scripts (Cloudflare). Mirrored from [MOOnLyer/PR-ETA-data](https://github.com/MOOnLyer/PR-ETA-data) `us_visa_bulletin.json` → `raw/visa_bulletin_mirror.json`. Cross-checked against 13 original bulletin pages (Jan 2025–Jan 2026): 520/520 cells match. Feb–Sep 2026 not independently checked. |
| L-1 by employer, FY2015–FY2019 | [USCIS "Approved L-1 Petitions by Employer"](https://www.uscis.gov/tools/reports-and-studies/immigration-and-citizenship-data) | CSVs saved as `raw/l1/l1_<FY>.csv`. USCIS stopped publishing these after FY2019. Names are truncated (~34 chars) and change over the years, so each company has an explicit `l1_names` list in `companies.json`; "IMB CORPORATION" (FY2019) is a USCIS typo for IBM, confirmed by matching tax-ID digits. "D"/"H" cells are counts USCIS withheld. |
| L-1 national, FY2017–FY2026 Q3 | USCIS "Nonimmigrant Worker Petitions by Case Status and RFE" quarterly workbooks | `raw/l1/i129_rfe_*.xlsx` (FY2017–24, FY2025, FY2026 Q3 editions). `python3 l1.py` self-checks the parse against totals printed in the files. Blanket-L workers who apply at consulates are not in any USCIS count. |
| L-1 border entries FY2024 | [DHS OHSS Yearbook 2024](https://ohss.dhs.gov/topics/immigration/yearbook/2024/NIsupptable1) (released June 2026) | `raw/l1/ohss_yearbook_ni_fy2024.xlsx`; supplemental tables 1 (country of citizenship) and 3 (destination state). Arrival events, not people; rounded to 10. The State Department L-1 visa figure (about 71,800, FY2024) is hand-entered in the page: travel.state.gov blocks scripts. |
| Layoffs | [layoffs.fyi](https://layoffs.fyi/) company pages (free to use with attribution) | Hand-copied into `layoffs.json` (2026-09-27). Tech companies only; Infosys/TCS/Cognizant/HCL aren't tracked. |
| Headcount by country | Company 10-K / 20-F / annual reports / earnings releases | Hand-curated in `headcount.json` (Sept 2026), one source link per number; `null` = not disclosed. Full research notes, including how each figure was checked, in `headcount_research.json`. Microsoft and Cognizant figures re-checked word for word against the SEC filings. |

Then `python3 build.py` → `data.json` and `employers.json` (it asserts the data still looks sane, including that every employer row adds up to the USCIS national totals).

`employers.json` (~6.5 MB, ~1.8 MB gzipped) lists every employer with at least one H-1B approval FY2022–FY2026 (≈126,000), named as filed and merged when names match after normalizing (drop &/AND, join spaced initials: "U S A" = "USA"). The page's search uses the same rule. The page fetches it only when someone uses the "Search every H-1B sponsor" box, so the home page stays small. Our tracked companies' rows carry a 10th field with the company id, which drives the "part of …" tag.

## Things that are easy to get wrong

- **Approvals ≠ H-1B employees.** Nobody publishes a company's current H-1B headcount. USCIS approvals include extensions and transfers of existing workers.
- **LCA filings ≠ hires.** Maps and salaries use certified LCAs (filings), counted once each. `TOTAL_WORKER_POSITIONS` is ignored for geography: blanket LCAs (Qualcomm files ~42k "positions" in San Diego) would swamp the map.
- **Legal entity roll-up is an explicit allow-list** in `companies.json`. Fuzzy matching pulls in unrelated firms ("Platinum Infosys Inc", "HCL Global Systems Inc").
- **FY2026 is partial** (USCIS through Q3, LCAs through June 2026).
- The Visa Guide carries dated legal content ("last reviewed September 2026"): the $100k H-1B fee litigation and the wage-weighted lottery will keep changing.

## Link preview and visit counts

- `og.png` is the 1200×630 preview WhatsApp, iMessage, Slack and LinkedIn show. Its source is `og.html`; to change it, edit that page, render it at 1200×630 (any browser screenshot at that size works) and save as `og.png`. Keep it under ~300 KB so WhatsApp shows it.
- Visits, where they came from, and which tabs get opened are counted with the free [Abacus](https://abacus.jasoncameron.dev/) API under `danpune-visa-tracker/*`: no cookies, once per browser session, live site only (`danpune.github.io`). See the totals at `/stats.html`. The Share buttons add `?s=wa` / `?s=link` so shared visits are attributed; the page strips it from the address bar.

