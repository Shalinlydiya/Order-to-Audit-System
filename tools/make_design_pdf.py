"""Builds DESIGN.pdf (2 pages max): ER diagram + stock/BOM/costing/GST notes."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.graphics.shapes import Drawing, Rect, String, Line
from reportlab.lib import colors
st = getSampleStyleSheet(); B = ParagraphStyle("b", parent=st["BodyText"], fontSize=8.6, leading=11); H = ParagraphStyle("h", parent=st["Heading3"], fontSize=10.5, spaceBefore=5, spaceAfter=2)
d = Drawing(520, 235)
BX = []
def box(x, y, w, t, fill="#fff3e0"):
    BX.append((x, y, w, t, fill)); return (x + w / 2, y + 12)
P = {}
for k, (x, y, w, t, f) in {"cust": (5, 190, 80, "customers", "#fff3e0"), "ord": (120, 190, 80, "orders", "#fff3e0"), "ol": (235, 190, 90, "order_lines", "#fff3e0"), "inv": (120, 130, 80, "invoices", "#e8f5e9"),
    "il": (235, 130, 90, "invoice_lines", "#e8f5e9"), "pay": (350, 130, 70, "payments", "#e8f5e9"), "cn": (350, 170, 70, "credit_notes", "#e8f5e9"), "items": (235, 70, 90, "items", "#e3f2fd"),
    "bom": (120, 70, 80, "bom", "#e3f2fd"), "led": (235, 5, 90, "LEDGER (stock)", "#ffebee"), "run": (350, 70, 70, "runs", "#f3e5f5"), "rl": (440, 70, 75, "run_lines", "#f3e5f5"), "pur": (440, 5, 75, "purchases", "#f3e5f5"),
    "adj": (350, 5, 70, "adjustments", "#f3e5f5"), "aud": (5, 70, 80, "audit", "#eeeeee"), "usr": (5, 130, 80, "users", "#eeeeee"), "cp": (440, 190, 75, "customer_prices", "#fff3e0"), "sup": (440, 130, 75, "suppliers", "#f3e5f5")}.items():
    P[k] = box(x, y, w, t, f)
for a, b in [("cust", "ord"), ("ord", "ol"), ("ord", "inv"), ("inv", "il"), ("inv", "pay"), ("inv", "cn"), ("ol", "items"), ("il", "items"), ("items", "bom"), ("items", "led"), ("run", "led"), ("run", "rl"), ("pur", "led"), ("adj", "led"), ("inv", "led"),
             ("run", "items"), ("cust", "cp"), ("pur", "sup"), ("usr", "ord"), ("cn", "led")]:
    d.add(Line(P[a][0], P[a][1], P[b][0], P[b][1], strokeColor=colors.HexColor("#999999"), strokeWidth=.6))
for x, y, w, t, fill in BX:   # boxes drawn after lines so text stays readable
    d.add(Rect(x, y, w, 24, fillColor=colors.HexColor(fill), strokeColor=colors.HexColor("#7a3b0c"))); d.add(String(x + 4, y + 9, t, fontSize=7.5))
d.add(String(5, 225, "Every stock-changing document writes rows to LEDGER (ref_type + ref_id + user + date + batch + expiry); balances are SUM(ledger).", fontSize=7.5, fillColor=colors.HexColor("#a00")))
S = [Paragraph("Design note — Order-to-Audit system", st["Heading2"]), Paragraph("<b>Data model</b> (SQLite). Colours: sales (orange/green), masters &amp; production (blue/purple), ledger (red).", B), d,
 Paragraph("Stock and ledger", H), Paragraph("No balance is stored. Balance = <b>SUM(ledger.qty_m)</b>; the stock summary proves opening + receipts − issues = closing for every item and prints MISMATCH otherwise. Quantities are integer milli-units, money integer paise (Decimal only for unit conversion and costing). Rows carry <b>batch + expiry</b>; issues are allocated <b>first-expiry-first-out</b>, one row per batch; returns/cancellations go back into the batches originally dispatched. Adjustments need a reason and are ledger rows too.", B),
 Paragraph("BOM consumption, WIP and variance", H), Paragraph("planned = BOM qty converted to the item's base unit (<i>conv</i>: kg/g, l/ml, pcs/packet/carton) × batches. <b>Stage 1</b> (start run): materials issued FEFO, batches posted into a per-product WIP item. <b>Stage 2</b> (complete): WIP cleared, good packets posted as a new finished-goods batch (expiry = date + shelf life); damaged pouches are logged as wastage. A same-day run does both in one call. Variance = (actual − planned)/planned, flagged when |v| &gt; 3 % (<i>VARIANCE_TOLERANCE</i>); yield compares good packets to yield × batches. Editing a completed run posts only the difference and logs old to new in the audit trail.", B),
 Paragraph("Costing and valuation", H), Paragraph("<b>Weighted average</b>: item cost is recomputed on every purchase (simple, smooths price swings, easy to audit; FIFO would need layer tracking). Run material cost = actual qty × WAC at run time. Per-run cost/packet = (material + labour + power/gas booked on the run) ÷ good packets. <b>Overhead rule</b>: monthly overheads (rent, salaries…) are allocated to runs of that month in proportion to good packets produced (Costing report). Benchmark: (Rs 4,055.00 + Rs 1,800.00) ÷ 188 = Rs 31.14; margin Rs 18.86 on Rs 50.", B),
 Paragraph("GST, audit and integrity", H), Paragraph("Place of supply from the customer's state: intra: CGST + SGST, inter: IGST; half-up rounding per line; numbers <i>INV/&lt;FY&gt;/&lt;seq&gt;</i>. Posted invoices are never edited or deleted — <b>cancellation or partial return creates a credit note</b> and restores stock. GSTR-1 (B2B, HSN, CDNR) and GSTR-3B 3.1(a)/4(A) are derived from invoices, credit notes and purchases (input GST). The <i>audit</i> table stores user, time, action, entity and detail for orders, price changes, invoices, payments, adjustments and run edits and is viewable in-app. Roles are enforced server-side (403/404). Offline orders carry a client UUID so a re-sync can never create duplicates.", B)]
SimpleDocTemplate("DESIGN.pdf", pagesize=A4, leftMargin=36, rightMargin=36, topMargin=30, bottomMargin=28).build(S)
import re; print("pages:", len(re.findall(rb"/Type /Page\b", open("DESIGN.pdf", "rb").read())))
