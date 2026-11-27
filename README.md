Order-to-Audit System
A working prototype for a small food manufacturer: salesman order → GST invoice → dispatch → stock, and raw material → BOM production run → finished goods → costing → auditor reports. Every transaction is entered once and flows into stock, production, costing and accounts.
Overview
DEMO_SCRIPT.md lists the clicks for the section 5 scenario, and python benchmark.py runs the same scenario headlessly and prints every expected number.
Setup
Code
Or run docker compose up. To reset the demo data, delete factory.db and start again.
Test logins (password demo123): salesA, salesB (salesman), admin, prod (production), auditor (accountant, read-only), owner.
Stack and why
Python, Flask and SQLite with mobile-friendly server-rendered pages and a small service worker for offline orders. It needs no build step, runs with one command, and uses a real relational database. All business rules are in core.py so they can be tested without the web layer; app.py handles screens only.
What is built (section 6 tiers)
Must have: login with roles, masters (products, customers, raw materials, BOM), mobile order entry and admin approval, GST invoice PDF, production runs that update raw and finished stock, planned vs actual variance, stock summary and ledger, sales register and stock report with CSV/Excel export.
Should have: purchases and suppliers, payments, outstanding and ageing, cost per packet with overheads, GST summary (GSTR-1 and GSTR-3B style), variance alerts, owner dashboard.
Stretch: offline orders with sync, batch and expiry with first-expiry-first-out, reorder alerts, production planning, GPS visit log, Tally XML export, mock e-invoice and e-way bill, Tamil interface.
Also: work-in-progress stage, partial dispatch and returns, credit notes, stock adjustments, audit log, customer-specific prices, PDF export of reports.
Benchmark results
Check
Expected
System
Flour / oil / pouches closing
120 kg / 19.5 L / 306
120 / 19.5 / 306
Finished goods after run / after dispatch
238 / 88
238 / 88
Yield variance
−6%, flagged
−6.00%, flagged
Oil variance
+5%, flagged
+5.00%, flagged
Retailer A invoice
7,500 + 187.50 + 187.50 = 7,875
same
Retailer A outstanding
3,875
3,875.00
Distributor B
shortage 32; IGST if invoiced
approval blocked, short by 32; IGST ₹220.00 on 88 packets
Cost per packet
own figure
₹31.14 (margin ₹18.86)
Notes: cartons used (9 vs standard 10) is −10% and is flagged. Pouches (194 vs 200) is −3% and is not flagged, because the tolerance is "beyond 3%". Spice closes at 3.8 kg and cartons at 21.
Costing method: weighted-average cost. Flour = (100×42 + 60×45) ÷ 160 = ₹43.125/kg. Material for the run = ₹4,055.00; adding labour ₹1,200 and gas/power ₹600 gives ₹5,855.00; divided by 188 good packets = ₹31.14. Overheads booked on a run go to that run's product. Monthly overheads are shared across the month's runs in proportion to good packets produced.
Assumptions
The factory is in Tamil Nadu; sales to other states use IGST. GST is 5% and HSN is 19059090 for the demo.
Money is stored in integer paise and quantities in integer milli-units. GST is rounded half-up per line.
Approving an order and raising its invoice are separate steps. Approval is blocked when finished goods are short; the admin edits the quantity or rejects.
Pouches issued = good + damaged (194); the 6 damaged are logged as wastage.
Opening stock has no expiry and is dispatched first.
A posted invoice is never edited or deleted; it is cancelled with a credit note.
e-Invoice and e-Way Bill output is a mock with a fake reference number.
Scope notes
Offline support covers order entry: orders are queued on the phone and sent when the network returns.
e-Invoice and e-Way Bill are simulated outputs in the government JSON shape, with no live government API.
SQLite is used for single-factory deployment; the same schema ports to PostgreSQL for larger setups.
The Tamil interface covers fixed screen text; names and notes stay as entered.
Section 5 scenario walkthrough
prod → Purchases: flour, 60 kg at ₹45.
prod → Production → Murukku: issue flour 40, oil 10.5, spice mix 1.2, pouches 194, cartons 9; good packets 188, damaged pouches 6. The run page shows the yield and oil variances flagged.
salesA (on a phone): new order for Retailer A, 150 packets.
admin: approve, raise the GST invoice (₹7,875), record dispatch (finished goods fall to 88).
salesB: order for Distributor B, 120 packets. admin sees the 32-packet shortage and approval is blocked.
admin: record a ₹4,000 payment on Retailer A's invoice (outstanding ₹3,875).
prod: on the run page, add labour ₹1,200 and gas/power ₹600 to see the cost per packet (₹31.14).
auditor / owner: open Reports (sales register, GST, stock ledger, production variance, outstanding) and the owner dashboard.
More documents
DESIGN.pdf / DESIGN.md (data model, stock and BOM logic, costing), DEMO_SCRIPT.md (demo steps).
