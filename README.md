# Order-to-Audit System — small food manufacturer

One system from salesman order → GST invoice → dispatch → stock, and raw material → BOM production run → finished goods → costing → auditor reports. Every transaction is entered once and flows into stock, production, costing and accounts.

## Run
```
pip install -r requirements.txt
python app.py                      # http://localhost:8000  (DB created + seeded with section-5 data on first start)
# or:  docker compose up           # same URL
python benchmark.py                # prints the section-5 numbers headlessly (same service layer as the UI)
python -m unittest discover -s tests   # 29 tests (pytest also works)
```
For a hosted demo: `Procfile`/`Dockerfile` run gunicorn (Render/Railway/Fly). Set `SECRET_KEY`; SQLite file path via `DB_PATH` (mount a volume).
Reset the demo: delete `factory.db` and restart.

**Test logins** (password `demo123`): `salesA`, `salesB` (salesman) · `admin` · `prod` (production supervisor) · `auditor` (accountant, read-only) · `owner`.

## Stack and why
Python + Flask + SQLite with server-rendered, mobile-friendly HTML and a small service worker (PWA) for offline orders. No build step and one-command run; a real relational DB with an explainable schema; all business rules live in `core.py` (testable without the web layer), `app.py` is routing and forms only. ReportLab produces PDFs, openpyxl Excel.

## Benchmark (`python benchmark.py`, steps 1–8; step 9 = Reports menu)
| Check | Expected | System |
|---|---|---|
| Flour / Oil / Pouches closing | 120 kg / 19.5 L / 306 | 120 / 19.5 / 306 |
| Spice / Cartons closing | – | 3.8 kg / 21 |
| FG after run / after dispatch | 238 / 88 | 238 / 88 |
| Yield variance | −6%, flagged | −6.00%, flagged |
| Oil variance | +5%, flagged | +5.00%, flagged |
| Retailer A invoice | 7,500 + 187.50 + 187.50 = 7,875 | identical |
| Retailer A outstanding | 3,875 | 3,875.00 |
| Distributor B | shortage 32; IGST if invoiced | approval blocked: short by 32; at 88 packets IGST = ₹220.00 |
| Cost per packet | own figure | **₹31.14**, margin ₹18.86 (37.7%) |

Differences, explained: cartons used 9 vs standard 10 is −10% and is flagged (beyond the 3% tolerance); pouches 194 vs 200 is −3% and not flagged ("beyond" 3%). Invoice numbers use the financial year of the day you run it.

### Costing method (cost per packet)
**Valuation: weighted average** (smooths purchase-price changes, simple to audit). Flour = (100×42 + 60×45)/160 = ₹43.125/kg. Run material = flour 1,725.00 + oil 1,470.00 + spice 240.00 + pouches 485.00 + cartons 135.00 = ₹4,055.00. Add labour 1,200 + gas/power 600 = ₹5,855.00 ÷ 188 good packets = **₹31.14**. Damaged pouches are consumed, so their cost is absorbed by good packets.
**Overhead rule:** overheads booked on a run are charged to that run's product. Monthly overheads (rent, supervisor salary, …) entered under Masters are allocated across the month's runs **in proportion to good packets produced**; see the *Costing* report.

## Requirement checklist (PDF → where)
| PDF section | Status | Where |
|---|---|---|
| 3 Roles & role-based access | ✅ 5 roles, each sees only its screens (403/404 otherwise, tested) | `need()` in `app.py` |
| 4.1 Mobile order entry, price list, customer prices/schemes, status, customer-wise sales | ✅ | `/orders/new`, `/orders`, Masters → customer prices |
| 4.1 Offline capture + sync | ✅ localStorage queue + service worker; idempotent `client_id` | `/orders/new`, `/api/orders`, `/sw.js` |
| 4.2 Admin edit/approve/reject, stock check before approval | ✅ approval blocked on shortage | `/orders/<id>` |
| 4.2 GST invoice: GSTIN, HSN, CGST/SGST vs IGST, FY numbering, PDF, WhatsApp link | ✅ | `core.raise_invoice`, `/invoices/<id>/pdf` |
| 4.2 Dispatch reduces stock; partial dispatch; returns | ✅ | `core.dispatch`, `core.return_goods` |
| 4.2 Payments, outstanding | ✅ | invoice page, Outstanding report |
| 4.3 BOM, run, auto stock updates, planned vs actual, tolerance flags, unit conversion | ✅ | `core.make_run`, `core.conv` |
| 4.4 Raw / packaging / finished goods balances; ledger with source docs; opening+receipts−issues±adj | ✅ derived from ledger; adjustments screen | `/adjustments`, Stock summary/ledger |
| 4.4 Work in progress | ✅ two-stage run: *Start run only (WIP)* issues materials into a WIP item, *Complete run* clears it and posts finished goods; planning counts WIP | `core.start_run/complete_run` |
| 4.4 Batch numbers + expiry, FEFO dispatch | ✅ | `core.issue`, Stock batches report |
| 4.5 Costing, valuation method, overhead allocation, cost/packet, margin | ✅ | run page, Costing report |
| 4.6 Sales register, customer/product sales, GST (GSTR-1 B2B/HSN/CDNR + GSTR-3B 3.1(a) and 4(A) ITC), purchase register, stock, production, collections, outstanding+ageing; date filter; Excel/CSV/PDF | ✅ | `/reports/*` |
| 4.6 Tally-compatible XML | ✅ sales + purchase vouchers (with input GST) | `/export/tally.xml` |
| 6 Stretch: offline, batch/expiry FEFO, reorder alerts, production planning, route/GPS visit log, Tally, e-invoice/e-way bill (mock), Tamil UI | ✅ all | Planning, Visits, dashboard, `/invoices/<id>/einvoice.json`, EN/தமிழ் toggle (every screen: menus, headings, labels, buttons, table headers, statuses; names/notes you type stay as typed) |
| 7 Real DB, ledger-derived stock, decimal/paise money, traceability | ✅ | `DESIGN.md`, tests |
| 7 Audit trail; invoices cancelled by credit note | ✅ user+time on orders, runs (old→new), prices, payments, adjustments; viewer at *Audit log* | `audit` table |
| 7 Seed data, run command, hosted option | ✅ `seed.py`, `docker compose up`, `Procfile` | |
| 8 Design note (≤2 pages, PDF + ER diagram) | ✅ `DESIGN.pdf`, `DESIGN.md` | |
| 8 Git history · demo video · live link | ⚠️ these need *you*: commit in small steps as you study the code, record the video following `DEMO_SCRIPT.md` (max 8 min), deploy with `render.yaml`/Docker and paste the URL + logins here | |

## Assumptions
- Factory in Tamil Nadu; IGST when the customer's state ≠ Tamil Nadu. GST 5%, HSN 19059090 for the demo.
- Money = integer paise; ledger quantities = integer milli-units; GST rounded half-up per line (CGST = ceil of half, SGST = remainder).
- Approve and "Raise GST invoice" are separate steps (statuses: submitted → approved → invoiced → part-dispatched/dispatched). Approval is blocked when finished goods are short; the admin edits the quantity (e.g. to 88) or rejects.
- Pouches issued = good + damaged (194); the 6 damaged are logged as run wastage.
- Opening stock has unknown expiry and is dispatched first under FEFO.
- Purchases take an optional GST % (default 0): it feeds the purchase register, Tally purchase voucher and GSTR-3B 4(A) ITC (IGST when the supplier's GSTIN state code ≠ 33).
- A posted invoice can't be edited; with payments or returns it can't be cancelled (refund/return first). Production runs can be corrected (ledger gets only the difference; old→new logged).
- e-Invoice / e-Way Bill output is a **mock** (deterministic fake IRN; no government API).

## Known gaps
No password-reset or user-disable UI; offline mode covers order entry only (needs the page opened once online); PDF reports truncate very long cells; GSTR-3B net payable ignores ITC cross-utilisation rules; SQLite suits a single-factory load, not many concurrent writers; Tamil covers fixed UI text only (not item/customer names or notes you type); translations are my best effort — have a floor supervisor review them.
