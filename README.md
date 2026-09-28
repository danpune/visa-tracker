# US Work Visa Tracker (prototype)

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
| Layoffs | [layoffs.fyi](https://layoffs.fyi/) company pages (free to use with attribution) | Hand-copied into `layoffs.json` (2026-09-27). Tech companies only; Infosys/TCS/Cognizant/HCL aren't tracked. |
| Headcount by country | Company 10-K / 20-F / annual reports / earnings releases | Hand-curated in `headcount.json` (Sept 2026), one source link per number; `null` = not disclosed. Full research notes, including how each figure was checked, in `headcount_research.json`. Microsoft and Cognizant figures re-checked word for word against the SEC filings. |

Then `python3 build.py` → `data.json` (it asserts the data still looks sane).

## Things that are easy to get wrong

- **Approvals ≠ H-1B employees.** Nobody publishes a company's current H-1B headcount. USCIS approvals include extensions and transfers of existing workers.
- **LCA filings ≠ hires.** Maps and salaries use certified LCAs (filings), counted once each. `TOTAL_WORKER_POSITIONS` is ignored for geography: blanket LCAs (Qualcomm files ~42k "positions" in San Diego) would swamp the map.
- **Legal entity roll-up is an explicit allow-list** in `companies.json`. Fuzzy matching pulls in unrelated firms ("Platinum Infosys Inc", "HCL Global Systems Inc").
- **FY2026 is partial** (USCIS through Q3, LCAs through June 2026).
- The Visa Guide carries dated legal content ("last reviewed September 2026"): the $100k H-1B fee litigation and the wage-weighted lottery will keep changing.
