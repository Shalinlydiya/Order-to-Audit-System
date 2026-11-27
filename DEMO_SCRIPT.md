# Demo script (max 8 min) — section-5 scenario
Start fresh: delete `factory.db`, `python app.py`. Phone-size window for salesman steps.
1. `prod` → **Purchases**: Flour, 60, ₹45 (Demo Mills).
2. `prod` → **Production** → Murukku → Start run: batches 1, flour 40, oil 10.5, spice 1.2, pouches 194, cartons 9, good 188, damaged 6 → Save. Show run page: oil +5% FLAG, yield −6% FLAG, carton −10% FLAG.
3. `salesA` (phone view): New order → Retailer A, 150 → Submit. (Optional: go offline in dev tools, submit, go online → syncs.)
4. `admin`: open order → Approve → Raise GST invoice (₹7,875 = 7,500 + 187.50 + 187.50) → Record dispatch → FG 88.
5. `salesB`: order 120 for Distributor B. `admin` opens it: SHORT 32, approval blocked; edit qty to 88 to show IGST.
6. `admin`: invoice A → Record payment ₹4,000 → outstanding ₹3,875.
7. `prod`: run page → Labour 1,200, Power/gas 600 → cost per packet ₹31.14 + margin.
8. `auditor`: Reports → Stock summary, Stock ledger, Sales register, GSTR-1/3B, Production, Outstanding → CSV/Excel/PDF. `owner`: Dashboard.
9. Extras (30 s each): WIP — Production → *Start run only (WIP)*, then *Complete run* on the run page; Masters, Adjustments, Planning, Visits check-in, EN/தமிழ் toggle, Audit log, Tally XML.
