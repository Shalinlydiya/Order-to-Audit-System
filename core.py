"""Business logic. Money = integer paise. Quantities = integer milli-units in the ledger. No floats."""
import os, sqlite3, math, hashlib, datetime as dt
from decimal import Decimal as D, ROUND_HALF_UP
from xml.sax.saxutils import escape as X
DB = os.environ.get("DB_PATH", "factory.db")
STATE = "Tamil Nadu"
FACTORY = os.environ.get("FACTORY_NAME", "Sri Murugan Snacks (demo)"); FGSTIN = os.environ.get("FACTORY_GSTIN", "33AAAAA0000A1Z5")
TOL = D(os.environ.get("VARIANCE_TOLERANCE", "3"))  # percent
SCHEMA = """
create table if not exists users(id integer primary key,username text unique,pw text,role text,name text);
create table if not exists items(id integer primary key,name text unique,kind text,unit text,hsn text,price integer default 0,gst integer default 5,wac text default '0',yield_qty integer default 0,carton_size integer default 20,shelf_life integer default 0,reorder_m integer default 0);
create table if not exists bom(id integer primary key,product_id int,item_id int,qty text,unit text);
create table if not exists ledger(id integer primary key,date text,item_id int,qty_m integer,rate text,ref_type text,ref_id int,note text,user text,batch text default '',expiry text default '');
create table if not exists suppliers(id integer primary key,name text unique,gstin text,phone text);
create table if not exists customers(id integer primary key,name text,gstin text,state text,kind text,salesman_id int);
create table if not exists customer_prices(customer_id int,item_id int,price integer,primary key(customer_id,item_id));
create table if not exists purchases(id integer primary key,date text,supplier text,bill_no text,item_id int,qty_m int,rate_p text,amount_p int,batch text,gst_rate int default 0,gst_p int default 0);
create table if not exists adjustments(id integer primary key,date text,item_id int,qty_m int,reason text,user text);
create table if not exists runs(id integer primary key,date text,product_id int,batches int,expected int,good int,damaged int,mat_p int,labour_p int default 0,oh_p int default 0,yield_var text,flag int,user text,batch text,status text default 'completed');
create table if not exists run_lines(id integer primary key,run_id int,item_id int,planned_m int,actual_m int,var_pct text,flag int,cost_p int);
create table if not exists monthly_overheads(id integer primary key,month text,kind text,amount_p int,note text);
create table if not exists orders(id integer primary key,date text,customer_id int,salesman_id int,status text,note text,client_id text unique);
create table if not exists order_lines(id integer primary key,order_id int,item_id int,qty int,price int);
create table if not exists invoices(id integer primary key,no text unique,date text,order_id int,customer_id int,taxable int,cgst int,sgst int,igst int,total int,status text,dispatched int default 0);
create table if not exists invoice_lines(id integer primary key,invoice_id int,item_id int,hsn text,qty int,price int,taxable int,rate int,disp_qty int default 0,ret_qty int default 0);
create table if not exists payments(id integer primary key,date text,invoice_id int,customer_id int,amount int,mode text);
create table if not exists credit_notes(id integer primary key,no text,date text,invoice_id int,amount int,reason text,kind text default 'cancel',taxable int default 0,tax int default 0);
create table if not exists visits(id integer primary key,ts text,salesman_id int,customer_id int,lat text,lng text,note text);
create table if not exists audit(id integer primary key,ts text,user text,action text,entity text,entity_id int,detail text);
"""
def conn():
    c = sqlite3.connect(DB, timeout=15); c.row_factory = sqlite3.Row; return c
def init():
    c = conn(); c.execute("pragma journal_mode=wal"); c.executescript(SCHEMA); c.commit(); c.close()
def today(): return dt.date.today().isoformat()
def M(x): return int((D(str(x).strip()) * 1000).quantize(D(1), ROUND_HALF_UP))
def Q(m):
    s = f"{D(m)/1000:.3f}".rstrip("0").rstrip("."); return s or "0"
def rs(p): return f"{D(p)/100:,.2f}"
def P(x): return int((D(str(x).strip()) * 100).quantize(D(1), ROUND_HALF_UP))   # rupees -> paise
def rnd(x): return int(D(x).quantize(D(1), ROUND_HALF_UP))
def audit(c, user, action, ent, eid, detail=""):
    c.execute("insert into audit(ts,user,action,entity,entity_id,detail) values(?,?,?,?,?,?)",
              (dt.datetime.now().isoformat(timespec="seconds"), user, action, ent, eid, detail))
def item(c, i): return c.execute("select * from items where id=?", (i,)).fetchone()

# ---- units -------------------------------------------------------------
UN = {"kg": ("m", 1000), "g": ("m", 1), "l": ("v", 1000), "ml": ("v", 1), "pcs": ("c", 1), "packet": ("c", 1)}
def conv(q, fu, tu, carton=20):
    q = D(str(q))
    if fu == "carton": q, fu = q * carton, "packet"
    if tu == "carton":
        if fu != "packet": raise ValueError("cannot convert to carton")
        return q / carton
    if UN[fu][0] != UN[tu][0]: raise ValueError(f"cannot convert {fu} to {tu}")
    return q * UN[fu][1] / UN[tu][1]

# ---- stock ledger (balances are always derived) --------------------------
def bal(c, i, upto=None):
    sql, a = "select coalesce(sum(qty_m),0) from ledger where item_id=?", [i]
    if upto: sql += " and date<=?"; a.append(upto)
    return c.execute(sql, a).fetchone()[0]
def post(c, i, qty_m, rtype, rid, rate="", note="", user="", date=None, batch="", expiry=""):
    c.execute("insert into ledger(date,item_id,qty_m,rate,ref_type,ref_id,note,user,batch,expiry) values(?,?,?,?,?,?,?,?,?,?)",
              (date or today(), i, qty_m, str(rate), rtype, rid, note, user, batch, expiry))
def batches(c, i):
    return c.execute("select batch,expiry,sum(qty_m) q from ledger where item_id=? group by batch,expiry having sum(qty_m)>0 order by expiry,batch", (i,)).fetchall()
def issue(c, i, qty_m, rtype, rid, rate="", note="", user="", date=None):
    """Issue stock first-expiry-first-out (unknown/opening expiry first). One ledger row per batch touched."""
    need = qty_m
    for b in batches(c, i):
        if need <= 0: break
        t = min(need, b["q"]); post(c, i, -t, rtype, rid, rate, note, user, date, b["batch"], b["expiry"]); need -= t
    if need > 0: raise ValueError(f"Insufficient stock of {item(c, i)['name']}")
def opening(c, i, qty, rate_rs=0):
    post(c, i, M(qty), "opening", 0, P(rate_rs), "Opening balance", "seed", None, "OPENING", "")
    c.execute("update items set wac=? where id=?", (str(P(rate_rs)), i))
def adjust(c, user, i, qty, reason, expiry="", date=None):
    if not (reason or "").strip(): raise ValueError("Reason is required for an adjustment")
    q = M(qty)
    if q == 0: raise ValueError("Quantity is zero")
    aid = c.execute("insert into adjustments(date,item_id,qty_m,reason,user) values(?,?,?,?,?)", (date or today(), i, q, reason, user)).lastrowid
    if q > 0: post(c, i, q, "adjustment", aid, "", reason, user, date, f"ADJ{aid}", expiry)
    else: issue(c, i, -q, "adjustment", aid, "", reason, user, date)
    audit(c, user, "adjust", "item", i, f"{qty} ({reason})"); return aid
def low_stock(c):
    return [(r["name"], Q(bal(c, r["id"])), Q(r["reorder_m"]), r["unit"]) for r in c.execute("select * from items where reorder_m>0") if bal(c, r["id"]) < r["reorder_m"]]
def near_expiry(c, days=30):
    lim = (dt.date.today() + dt.timedelta(days=days)).isoformat()
    return [(r["name"], r["batch"], r["expiry"], Q(r["q"])) for r in c.execute("select i.name,l.batch,l.expiry,sum(l.qty_m) q from ledger l join items i on i.id=l.item_id where l.expiry!='' and l.expiry<=? group by l.item_id,l.batch,l.expiry having q>0 order by l.expiry", (lim,))]

# ---- purchases / costing ------------------------------------------------
def purchase(c, user, i, qty, rate_rs, supplier="", bill_no="", date=None, batch="", expiry="", gst_rate=0):
    """Weighted-average costing: wac updated on every receipt."""
    it = item(c, i); old, q, p = D(bal(c, i)), D(M(qty)), D(P(rate_rs))
    if q <= 0 or p < 0: raise ValueError("Invalid quantity or rate")
    wac = (old * D(it["wac"]) + q * p) / (old + q) if old + q else p
    amt = rnd(q / 1000 * p); gst_rate = int(gst_rate or 0)
    pid = c.execute("insert into purchases(date,supplier,bill_no,item_id,qty_m,rate_p,amount_p,gst_rate,gst_p) values(?,?,?,?,?,?,?,?,?)",
                    (date or today(), supplier, bill_no, i, int(q), str(p), amt, gst_rate, (amt * gst_rate + 50) // 100)).lastrowid
    batch = batch or f"P{pid}"; c.execute("update purchases set batch=? where id=?", (batch, pid))
    post(c, i, int(q), "purchase", pid, p, supplier, user, date, batch, expiry)
    c.execute("update items set wac=? where id=?", (str(wac), i))
    audit(c, user, "create", "purchase", pid, f"{it['name']} {qty} @ {rate_rs}"); return pid

# ---- production ---------------------------------------------------------
def _var(act, plan): return (D(act - plan) / plan * 100).quantize(D("0.01"), ROUND_HALF_UP) if plan else D(0)
def wip_item(c, product):
    """Work-in-progress is stocked per product in 'batches' (one batch = one BOM multiple)."""
    n = "WIP – " + item(c, product)["name"]; r = c.execute("select id from items where name=?", (n,)).fetchone()
    return r[0] if r else c.execute("insert into items(name,kind,unit,gst) values(?, 'wip','batch',0)", (n,)).lastrowid
def start_run(c, user, product, batches_n, actuals, date=None):
    """Stage 1: issue raw/packaging per BOM (FEFO) and move the batches into WIP. actuals: {item_id: qty in item base unit}; missing -> planned."""
    date = date or today(); prod = item(c, product)
    bl = c.execute("select b.*,i.unit iu,i.name,i.wac from bom b join items i on i.id=b.item_id where product_id=?", (product,)).fetchall()
    if not bl or not prod["yield_qty"]: raise ValueError("Product needs a BOM and an expected yield")
    if batches_n < 1: raise ValueError("Invalid quantities")
    exp, lines, mat = prod["yield_qty"] * batches_n, [], D(0)
    for b in bl:
        plan = M(conv(b["qty"], b["unit"], b["iu"], prod["carton_size"]) * batches_n)
        act = M(actuals[b["item_id"]]) if b["item_id"] in actuals else plan
        if bal(c, b["item_id"]) < act: raise ValueError(f"Insufficient stock of {b['name']}")
        cost = D(act) / 1000 * D(b["wac"]); mat += cost; v = _var(act, plan)
        lines.append((b["item_id"], plan, act, str(v), int(abs(v) > TOL), rnd(cost)))
    rid = c.execute("insert into runs(date,product_id,batches,expected,good,damaged,mat_p,yield_var,flag,user,status) values(?,?,?,?,0,0,?,'',0,?,'open')",
                    (date, product, batches_n, exp, rnd(mat), user)).lastrowid
    batch = f"B{date.replace('-', '')}-{rid}"; c.execute("update runs set batch=? where id=?", (batch, rid))
    for i, plan, act, v, f, cost in lines:
        c.execute("insert into run_lines(run_id,item_id,planned_m,actual_m,var_pct,flag,cost_p) values(?,?,?,?,?,?,?)", (rid, i, plan, act, v, f, cost))
        issue(c, i, act, "production", rid, "", "Issued to run", user, date)
    post(c, wip_item(c, product), batches_n * 1000, "production", rid, "", "Batches into WIP", user, date, batch, "")
    audit(c, user, "start", "production_run", rid, f"batches={batches_n}"); return rid
def complete_run(c, user, rid, good, damaged=0, date=None):
    """Stage 2: record actual output and wastage; WIP is cleared and finished goods go up."""
    r = c.execute("select * from runs where id=?", (rid,)).fetchone(); date = date or today(); prod = item(c, r["product_id"])
    if r["status"] != "open": raise ValueError("Run is already completed")
    if good < 0 or damaged < 0: raise ValueError("Invalid quantities")
    yv = _var(good, r["expected"])
    c.execute("update runs set good=?,damaged=?,yield_var=?,flag=?,status='completed' where id=?", (good, damaged, str(yv), int(abs(yv) > TOL), rid))
    expiry = (dt.date.fromisoformat(date) + dt.timedelta(days=prod["shelf_life"])).isoformat() if prod["shelf_life"] else ""
    post(c, wip_item(c, r["product_id"]), -r["batches"] * 1000, "production", rid, "", "WIP completed", user, date, r["batch"], "")
    post(c, r["product_id"], good * 1000, "production", rid, "", "Good output", user, date, r["batch"], expiry)
    audit(c, user, "complete", "production_run", rid, f"good={good} damaged={damaged}")
def make_run(c, user, product, batches_n, actuals, good, damaged=0, date=None):
    """Convenience: start and complete in one go (same-day run)."""
    rid = start_run(c, user, product, batches_n, actuals, date); complete_run(c, user, rid, good, damaged, date); return rid
def edit_run(c, user, rid, actuals, good, damaged=0):
    """Correct a saved run. Only the difference is posted to the ledger; old and new values go to the audit trail."""
    r = c.execute("select * from runs where id=?", (rid,)).fetchone(); changes = []
    if r["status"] != "completed": raise ValueError("Complete the run before editing it")
    if good < 0 or damaged < 0: raise ValueError("Invalid quantities")
    for l in c.execute("select l.*,i.wac,i.name from run_lines l join items i on i.id=l.item_id where run_id=?", (rid,)).fetchall():
        new = M(actuals[l["item_id"]]) if l["item_id"] in actuals else l["actual_m"]; d = new - l["actual_m"]
        if d == 0: continue
        if d > 0: issue(c, l["item_id"], d, "production", rid, "", "Run edit", user)
        else: post(c, l["item_id"], -d, "production", rid, "", "Run edit (returned)", user, None, "ADJ", "")
        unit = D(l["cost_p"]) / l["actual_m"] if l["actual_m"] else D(l["wac"]) / 1000; v = _var(new, l["planned_m"])
        c.execute("update run_lines set actual_m=?,var_pct=?,flag=?,cost_p=? where id=?", (new, str(v), int(abs(v) > TOL), rnd(unit * new), l["id"]))
        changes.append(f"{l['name']} {Q(l['actual_m'])}->{Q(new)}")
    dg = good - r["good"]
    if dg:
        if dg < 0 and bal(c, r["product_id"]) < -dg * 1000: raise ValueError("Cannot reduce output: finished goods already dispatched")
        ex = c.execute("select expiry from ledger where ref_type='production' and ref_id=? and item_id=? and qty_m>0", (rid, r["product_id"])).fetchone()
        post(c, r["product_id"], dg * 1000, "production", rid, "", "Run edit (output)", user, None, r["batch"], ex[0] if ex else "")
        changes.append(f"good {r['good']}->{good}")
    if damaged != r["damaged"]: changes.append(f"damaged {r['damaged']}->{damaged}")
    yv = _var(good, r["expected"]); mat = c.execute("select coalesce(sum(cost_p),0) from run_lines where run_id=?", (rid,)).fetchone()[0]
    c.execute("update runs set good=?,damaged=?,mat_p=?,yield_var=?,flag=? where id=?", (good, damaged, mat, str(yv), int(abs(yv) > TOL), rid))
    audit(c, user, "edit", "production_run", rid, "; ".join(changes) or "no change")
def add_overhead(c, user, rid, labour_rs, power_rs):
    c.execute("update runs set labour_p=labour_p+?,oh_p=oh_p+? where id=?", (P(labour_rs or 0), P(power_rs or 0), rid))
    audit(c, user, "update", "production_run", rid, f"labour={labour_rs} power/gas={power_rs}")
def add_monthly_overhead(c, user, month, kind, amount_rs, note=""):
    c.execute("insert into monthly_overheads(month,kind,amount_p,note) values(?,?,?,?)", (month, kind, P(amount_rs), note)); audit(c, user, "create", "monthly_overhead", 0, f"{month} {kind} {amount_rs}")
def cost_per_packet(c, rid):
    """Per-run cost: material (weighted avg) + overheads booked on the run, divided by good packets."""
    r = c.execute("select r.*,i.price from runs r join items i on i.id=r.product_id where r.id=?", (rid,)).fetchone()
    total = r["mat_p"] + r["labour_p"] + r["oh_p"]
    cpp = (D(total) / r["good"]).quantize(D("0.01"), ROUND_HALF_UP) if r["good"] else D(0)
    return cpp, D(r["price"]) - cpp, ((D(r["price"]) - cpp) / r["price"] * 100).quantize(D("0.1")) if r["price"] else D(0)
def costing_rows(c, frm, to):
    """Monthly costing: material + run overheads + monthly overhead pool allocated to runs in proportion to good packets."""
    rows = []
    for m in [x[0] for x in c.execute("select distinct substr(date,1,7) from runs where status='completed' and date between ? and ? order by 1", (frm, to))]:
        pool = c.execute("select coalesce(sum(amount_p),0) from monthly_overheads where month=?", (m,)).fetchone()[0]
        tot = c.execute("select coalesce(sum(good),0) from runs where status='completed' and substr(date,1,7)=?", (m,)).fetchone()[0]
        for p in c.execute("select i.id,i.name,i.price,sum(r.good) g,sum(r.mat_p) mat,sum(r.labour_p+r.oh_p) oh from runs r join items i on i.id=r.product_id where r.status='completed' and substr(r.date,1,7)=? group by i.id", (m,)):
            alloc = D(pool) * p["g"] / tot if tot else D(0); total = D(p["mat"] + p["oh"]) + alloc
            cpp = (total / p["g"]).quantize(D("0.01"), ROUND_HALF_UP) if p["g"] else D(0); mg = D(p["price"]) - cpp
            rows.append([m, p["name"], p["g"], rs(p["mat"]), rs(p["oh"]), rs(alloc.quantize(D(1), ROUND_HALF_UP)), rs(total.quantize(D(1), ROUND_HALF_UP)), rs(cpp), rs(p["price"]),
                         rs(mg), f"{(mg / p['price'] * 100).quantize(D('0.1')) if p['price'] else 0}%"])
    return rows

# ---- sales -------------------------------------------------------------
def create_order(c, user, salesman, customer, lines, client_id=None):
    if client_id:
        ex = c.execute("select id from orders where client_id=?", (client_id,)).fetchone()
        if ex: return ex[0]        # offline re-sync is idempotent
    lines = [(int(i), int(q)) for i, q in lines if int(q) > 0]
    if not lines: raise ValueError("Add at least one product")
    oid = c.execute("insert into orders(date,customer_id,salesman_id,status,client_id) values(?,?,?, 'submitted',?)", (today(), customer, salesman, client_id)).lastrowid
    for i, q in lines:
        cp = c.execute("select price from customer_prices where customer_id=? and item_id=?", (customer, i)).fetchone()
        c.execute("insert into order_lines(order_id,item_id,qty,price) values(?,?,?,?)", (oid, i, q, cp[0] if cp else item(c, i)["price"]))
    audit(c, user, "create", "order", oid); return oid
def stock_check(c, oid):
    return [dict(item=r["name"], qty=r["qty"], avail=int(bal(c, r["item_id"]) / 1000), short=max(0, r["qty"] - int(bal(c, r["item_id"]) / 1000)))
            for r in c.execute("select l.*,i.name from order_lines l join items i on i.id=l.item_id where order_id=?", (oid,))]
def tax(lines, inter):
    """lines: [(taxable_p, rate)] -> (taxable, cgst, sgst, igst) in paise; half-up per line."""
    tx = sum(t for t, _ in lines); g = sum((t * r + 50) // 100 for t, r in lines)
    return (tx, 0, 0, g) if inter else (tx, (g + 1) // 2, g - (g + 1) // 2, 0)
def approve(c, user, oid, edits=None):
    o = c.execute("select * from orders where id=?", (oid,)).fetchone()
    if o["status"] != "submitted": raise ValueError("Order already processed")
    ch = []
    for i, (q, p) in (edits or {}).items():
        old = c.execute("select l.qty,l.price,i.name from order_lines l join items i on i.id=l.item_id where order_id=? and item_id=?", (oid, i)).fetchone()
        if old and (old["qty"], old["price"]) != (q, p): ch.append(f"{old['name']} qty {old['qty']}->{q} price {rs(old['price'])}->{rs(p)}")
        if q <= 0: c.execute("delete from order_lines where order_id=? and item_id=?", (oid, i))
        else: c.execute("update order_lines set qty=?,price=? where order_id=? and item_id=?", (q, p, oid, i))
    sc = stock_check(c, oid)
    if not sc: raise ValueError("Order has no lines")
    short = [s for s in sc if s["short"]]
    if short: raise ValueError("Insufficient finished-goods stock: " + ", ".join(f"{s['item']} short by {s['short']}" for s in short))
    c.execute("update orders set status='approved' where id=?", (oid,)); audit(c, user, "approve", "order", oid, "; ".join(ch))
def raise_invoice(c, user, oid):
    o = c.execute("select * from orders where id=?", (oid,)).fetchone()
    if o["status"] != "approved": raise ValueError("Approve the order first")
    cu = c.execute("select * from customers where id=?", (o["customer_id"],)).fetchone()
    inter = cu["state"].strip().lower() != STATE.lower()
    ls = c.execute("select l.*,i.hsn,i.gst from order_lines l join items i on i.id=l.item_id where order_id=?", (oid,)).fetchall()
    tl = [(l["qty"] * l["price"], l["gst"]) for l in ls]; tx, cg, sg, ig = tax(tl, inter)
    d = today(); y = int(d[:4]) if d[5:7] >= "04" else int(d[:4]) - 1; fy = f"{y}-{str(y+1)[2:]}"
    seq = c.execute("select count(*) from invoices where no like ?", (f"INV/{fy}/%",)).fetchone()[0] + 1
    iid = c.execute("insert into invoices(no,date,order_id,customer_id,taxable,cgst,sgst,igst,total,status) values(?,?,?,?,?,?,?,?,?,'posted')",
                    (f"INV/{fy}/{seq:04d}", d, oid, o["customer_id"], tx, cg, sg, ig, tx + cg + sg + ig)).lastrowid
    for l, (t, r) in zip(ls, tl):
        c.execute("insert into invoice_lines(invoice_id,item_id,hsn,qty,price,taxable,rate) values(?,?,?,?,?,?,?)", (iid, l["item_id"], l["hsn"], l["qty"], l["price"], t, r))
    c.execute("update orders set status='invoiced' where id=?", (oid,)); audit(c, user, "invoice", "order", oid, f"invoice {iid}"); return iid
def reject(c, user, oid, why=""):
    c.execute("update orders set status='rejected',note=? where id=? and status in ('submitted','approved')", (why, oid)); audit(c, user, "reject", "order", oid, why)
def dispatch(c, user, iid, qtys=None):
    """qtys: {invoice_line_id: qty}; default = everything not yet dispatched. Partial dispatch supported."""
    inv = c.execute("select * from invoices where id=?", (iid,)).fetchone()
    if inv["status"] != "posted": raise ValueError("Invoice is not active")
    ls = c.execute("select * from invoice_lines where invoice_id=?", (iid,)).fetchall(); total = 0
    for l in ls:
        rem = l["qty"] - l["disp_qty"]; q = rem if qtys is None else int(qtys.get(l["id"], 0))
        if q < 0 or q > rem: raise ValueError("Dispatch quantity exceeds invoiced quantity")
        if q: issue(c, l["item_id"], q * 1000, "invoice", iid, "", inv["no"], user); c.execute("update invoice_lines set disp_qty=disp_qty+? where id=?", (q, l["id"])); total += q
    if not total: raise ValueError("Nothing to dispatch")
    full = c.execute("select count(*) from invoice_lines where invoice_id=? and disp_qty<qty", (iid,)).fetchone()[0] == 0
    c.execute("update invoices set dispatched=? where id=?", (2 if full else 1, iid))
    c.execute("update orders set status=? where id=?", ("dispatched" if full else "part-dispatched", inv["order_id"])); audit(c, user, "dispatch", "invoice", iid, f"{total} units")
def _restock(c, i, qty_m, iid, note, user):
    need = qty_m
    for r in c.execute("select batch,expiry,sum(qty_m) q from ledger where item_id=? and ref_id=? and ref_type in ('invoice','credit_note') group by batch,expiry having sum(qty_m)<0 order by expiry", (i, iid)).fetchall():
        if need <= 0: break
        t = min(need, -r["q"]); post(c, i, t, "credit_note", iid, "", note, user, None, r["batch"], r["expiry"]); need -= t
    if need > 0: post(c, i, need, "credit_note", iid, "", note, user, None, "RET", "")
def _cn_no(c): return f"CN/{c.execute('select count(*) from credit_notes').fetchone()[0] + 1:04d}"
def return_goods(c, user, iid, qtys, reason="Sales return"):
    """Partial return: stock goes back into the batches originally dispatched; a credit note reduces the receivable."""
    inv = c.execute("select * from invoices where id=?", (iid,)).fetchone()
    if inv["status"] != "posted": raise ValueError("Invoice is not active")
    tl = []
    for l in c.execute("select * from invoice_lines where invoice_id=?", (iid,)).fetchall():
        q = int(qtys.get(l["id"], 0))
        if q < 0 or q > l["disp_qty"] - l["ret_qty"]: raise ValueError("Return quantity exceeds dispatched quantity")
        if q: tl.append((l, q))
    if not tl: raise ValueError("Nothing to return")
    tx = sum(l["price"] * q for l, q in tl); tg = sum((l["price"] * q * l["rate"] + 50) // 100 for l, q in tl)
    for l, q in tl: _restock(c, l["item_id"], q * 1000, iid, "Return on " + inv["no"], user); c.execute("update invoice_lines set ret_qty=ret_qty+? where id=?", (q, l["id"]))
    c.execute("insert into credit_notes(no,date,invoice_id,amount,reason,kind,taxable,tax) values(?,?,?,?,?,'return',?,?)", (_cn_no(c), today(), iid, tx + tg, reason, tx, tg))
    audit(c, user, "return", "invoice", iid, f"credit {tx + tg}")
def pay(c, user, iid, amount_rs, mode="cash", date=None):
    inv = c.execute("select * from invoices where id=?", (iid,)).fetchone(); a = P(amount_rs)
    if inv["status"] != "posted" or a <= 0 or a > due(c, iid): raise ValueError("Invalid payment amount")
    c.execute("insert into payments(date,invoice_id,customer_id,amount,mode) values(?,?,?,?,?)", (date or today(), iid, inv["customer_id"], a, mode))
    audit(c, user, "payment", "invoice", iid, f"{a}")
def due(c, iid):
    t = c.execute("select total from invoices where id=?", (iid,)).fetchone()[0]
    p = c.execute("select coalesce(sum(amount),0) from payments where invoice_id=?", (iid,)).fetchone()[0]
    return t - p - c.execute("select coalesce(sum(amount),0) from credit_notes where invoice_id=? and kind='return'", (iid,)).fetchone()[0]
def cancel_invoice(c, user, iid, reason):
    inv = c.execute("select * from invoices where id=?", (iid,)).fetchone()
    if inv["status"] != "posted": raise ValueError("Already cancelled")
    if c.execute("select 1 from payments where invoice_id=?", (iid,)).fetchone() or c.execute("select 1 from credit_notes where invoice_id=?", (iid,)).fetchone():
        raise ValueError("Invoice has payments or returns; cannot cancel")
    for l in c.execute("select * from invoice_lines where invoice_id=?", (iid,)).fetchall():
        if l["disp_qty"] - l["ret_qty"] > 0: _restock(c, l["item_id"], (l["disp_qty"] - l["ret_qty"]) * 1000, iid, "Cancelled " + inv["no"], user)
    c.execute("insert into credit_notes(no,date,invoice_id,amount,reason,kind,taxable,tax) values(?,?,?,?,?,'cancel',?,?)",
              (_cn_no(c), today(), iid, inv["total"], reason, inv["taxable"], inv["cgst"] + inv["sgst"] + inv["igst"]))
    c.execute("update invoices set status='cancelled' where id=?", (iid,)); c.execute("update orders set status='cancelled' where id=?", (inv["order_id"],))
    audit(c, user, "cancel", "invoice", iid, reason)
def visit(c, user, salesman, customer, lat="", lng="", note=""):
    c.execute("insert into visits(ts,salesman_id,customer_id,lat,lng,note) values(?,?,?,?,?,?)", (dt.datetime.now().isoformat(timespec="seconds"), salesman, customer, lat, lng, note)); audit(c, user, "visit", "customer", customer, f"{lat},{lng}")

# ---- planning ----------------------------------------------------------
def plan(c):
    fg, raw = [], []
    for p in c.execute("select * from items where kind='fg' and yield_qty>0").fetchall():
        dem = c.execute("select coalesce(sum(l.qty),0) from order_lines l join orders o on o.id=l.order_id where l.item_id=? and o.status in ('submitted','approved')", (p["id"],)).fetchone()[0] + \
              c.execute("select coalesce(sum(l.qty-l.disp_qty),0) from invoice_lines l join invoices i on i.id=l.invoice_id where l.item_id=? and i.status='posted'", (p["id"],)).fetchone()[0]
        st = int(bal(c, p["id"]) / 1000); wip = c.execute("select coalesce(sum(expected),0) from runs where product_id=? and status='open'", (p["id"],)).fetchone()[0]
        short = max(0, dem - st - wip); nb = math.ceil(short / p["yield_qty"]) if short else 0
        fg.append([p["name"], dem, st, wip, short, nb])
        for b in c.execute("select b.*,i.name,i.unit iu from bom b join items i on i.id=b.item_id where product_id=?", (p["id"],)):
            need = M(conv(b["qty"], b["unit"], b["iu"], p["carton_size"]) * nb); av = bal(c, b["item_id"])
            if nb: raw.append([p["name"], b["name"], Q(need), Q(av), Q(max(0, need - av)) + " " + b["iu"]])
    return fg, raw

# ---- reports -----------------------------------------------------------
def month_range():
    t = dt.date.today(); return t.replace(day=1).isoformat(), t.isoformat()
def _lines(c, frm, to):
    out = []
    for x in c.execute("select i.id iid,i.no,i.date,i.total,cu.gstin,cu.name cn,cu.state,l.hsn,l.qty,l.taxable,l.rate from invoice_lines l join invoices i on i.id=l.invoice_id join customers cu on cu.id=i.customer_id where i.status!='cancelled' and i.date between ? and ? order by i.id,l.id", (frm, to)):
        out.append(dict(x) | {"inter": x["state"].strip().lower() != STATE.lower()})
    return out
def _split(t, inter): return (0, 0, t) if inter else ((t + 1) // 2, t // 2, 0)   # cgst, sgst, igst
REPORTS = ["sales_register", "customer_sales", "product_sales", "gstr1_b2b", "gstr1_hsn", "gstr1_cdnr", "gstr3b", "purchase_register", "stock_summary", "stock_batches",
           "stock_ledger", "production", "costing", "collections", "outstanding", "visits", "audit_log"]
def report(c, name, frm, to):
    r = lambda sql, *a: [list(x) for x in c.execute(sql, a).fetchall()]
    if name == "sales_register":
        return ["Invoice", "Date", "Customer", "GSTIN", "Taxable", "CGST", "SGST", "IGST", "Total", "Status"], \
            [[x[0], x[1], x[2], x[3]] + [rs(v) for v in x[4:9]] + [x[9]] for x in r("select i.no,i.date,c.name,c.gstin,taxable,cgst,sgst,igst,total,i.status from invoices i join customers c on c.id=i.customer_id where i.date between ? and ? order by i.id", frm, to)]
    if name == "customer_sales":
        return ["Customer", "Invoices", "Taxable", "Total"], [[x[0], x[1], rs(x[2]), rs(x[3])] for x in r("select c.name,count(*),sum(taxable),sum(total) from invoices i join customers c on c.id=i.customer_id where i.status!='cancelled' and i.date between ? and ? group by c.id", frm, to)]
    if name == "product_sales":
        return ["Product", "Qty", "Taxable"], [[x[0], x[1], rs(x[2])] for x in r("select p.name,sum(l.qty),sum(l.taxable) from invoice_lines l join invoices i on i.id=l.invoice_id join items p on p.id=l.item_id where i.status!='cancelled' and i.date between ? and ? group by p.id", frm, to)]
    if name == "gstr1_b2b":   # GSTR-1 table 4A/4B: invoice-wise B2B supplies by rate
        g = {}
        for l in _lines(c, frm, to): g.setdefault((l["iid"], l["rate"]), []).append(l)
        rows = []
        for (_, rate), ls in g.items():
            l0 = ls[0]; t, cg, sg, ig = tax([(l["taxable"], l["rate"]) for l in ls], l0["inter"])
            rows.append([l0["gstin"], l0["cn"], l0["no"], l0["date"], rs(l0["total"]), l0["state"], f"{rate}%", rs(t), rs(ig), rs(cg), rs(sg)])
        return ["Recipient GSTIN", "Receiver", "Invoice", "Date", "Invoice value", "Place of supply", "Rate", "Taxable", "IGST", "CGST", "SGST"], rows
    if name == "gstr1_hsn":   # GSTR-1 table 12: HSN-wise summary
        g = {}
        for l in _lines(c, frm, to):
            a = g.setdefault(l["hsn"], [0, 0, 0, 0, 0]); t = (l["taxable"] * l["rate"] + 50) // 100; cg, sg, ig = _split(t, l["inter"])
            a[0] += l["qty"]; a[1] += l["taxable"]; a[2] += ig; a[3] += cg; a[4] += sg
        return ["HSN", "UQC", "Qty", "Taxable", "IGST", "CGST", "SGST", "Total value"], [[h, "PKT", a[0], rs(a[1]), rs(a[2]), rs(a[3]), rs(a[4]), rs(a[1] + a[2] + a[3] + a[4])] for h, a in g.items()]
    if name == "gstr1_cdnr":  # GSTR-1 table 9B: credit notes
        return ["Recipient GSTIN", "Note no", "Date", "Invoice", "Type", "Taxable", "Tax", "Note value"], [[x[0], x[1], x[2], x[3], x[4], rs(x[5]), rs(x[6]), rs(x[7])] for x in r("select cu.gstin,n.no,n.date,i.no,n.kind,n.taxable,n.tax,n.amount from credit_notes n join invoices i on i.id=n.invoice_id join customers cu on cu.id=i.customer_id where n.date between ? and ?", frm, to)]
    if name == "gstr3b":      # GSTR-3B table 3.1(a): outward taxable supplies, net of credit notes
        s = c.execute("select coalesce(sum(taxable),0),coalesce(sum(igst),0),coalesce(sum(cgst),0),coalesce(sum(sgst),0) from invoices where status!='cancelled' and date between ? and ?", (frm, to)).fetchone()
        cn = [0, 0, 0, 0]
        for x in c.execute("select n.taxable,n.tax,cu.state from credit_notes n join invoices i on i.id=n.invoice_id join customers cu on cu.id=i.customer_id where n.kind='return' and n.date between ? and ?", (frm, to)):
            cg, sg, ig = _split(x[1], x[2].strip().lower() != STATE.lower()); cn[0] += x[0]; cn[1] += ig; cn[2] += cg; cn[3] += sg
        f = lambda v: [rs(a) for a in v]; net = [s[i] - cn[i] for i in range(4)]
        itc = [0, 0, 0, 0]    # 4(A)(5) all other ITC: GST on purchases; inter-state when the supplier GSTIN state code != 33
        for x in c.execute("select p.amount_p,p.gst_p,coalesce(s.gstin,'') g from purchases p left join suppliers s on s.name=p.supplier where p.gst_p>0 and p.date between ? and ?", (frm, to)):
            cg, sg, ig = _split(x[1], bool(x[2]) and x[2][:2] != "33"); itc[0] += x[0]; itc[1] += ig; itc[2] += cg; itc[3] += sg
        pay = [net[0], max(0, net[1] - itc[1]), max(0, net[2] - itc[2]), max(0, net[3] - itc[3])]
        return ["Table", "Taxable", "IGST", "CGST", "SGST"], [["3.1(a) Gross outward supplies"] + f(s), ["3.1(a) Less: sales-return credit notes"] + f(cn), ["3.1(a) Net outward supplies"] + f(net),
                                                              ["4(A) Input tax credit (purchases)"] + f(itc), ["Net tax payable (no cross-utilisation)", ""] + f(pay[1:])]
    if name == "purchase_register":
        return ["Date", "Supplier", "Bill", "Item", "Batch", "Qty", "Rate/unit", "Taxable", "GST", "Total"], [[x[0], x[1], x[2], x[3], x[4], Q(x[5]), rs(D(x[6])), rs(x[7]), rs(x[8]), rs(x[7] + x[8])] for x in r("select p.date,supplier,bill_no,i.name,p.batch,qty_m,rate_p,amount_p,gst_p from purchases p join items i on i.id=item_id where p.date between ? and ?", frm, to)]
    if name == "stock_summary":
        rows = []
        for it in c.execute("select * from items order by kind,name").fetchall():
            f = lambda cond, *a: c.execute(f"select coalesce(sum(qty_m),0) from ledger where item_id=? and {cond}", (it["id"], *a)).fetchone()[0]
            op = f("(date<? or ref_type='opening')", frm); rc = f("qty_m>0 and ref_type!='opening' and date between ? and ?", frm, to)
            iss = f("qty_m<0 and date between ? and ?", frm, to); cl = bal(c, it["id"], to)
            rows.append([it["name"], it["kind"], it["unit"], Q(op), Q(rc), Q(iss), Q(cl), "LOW" if it["reorder_m"] and cl < it["reorder_m"] else "", "OK" if op + rc + iss == cl else "MISMATCH"])
        return ["Item", "Type", "Unit", "Opening", "Receipts", "Issues/Sales", "Closing", "Alert", "Check"], rows
    if name == "stock_batches":
        t = dt.date.today(); return ["Item", "Batch", "Expiry", "Qty", "Days to expiry"], [[b["name"], b["batch"], b["expiry"] or "-", Q(b["q"]), (dt.date.fromisoformat(b["expiry"]) - t).days if b["expiry"] else "-"]
            for b in c.execute("select i.name,l.batch,l.expiry,sum(l.qty_m) q from ledger l join items i on i.id=l.item_id group by l.item_id,l.batch,l.expiry having q>0 order by i.name,l.expiry")]
    if name == "stock_ledger":
        out, run = [], {}
        for x in c.execute("select l.*,i.name from ledger l join items i on i.id=l.item_id order by l.id").fetchall():
            run[x["item_id"]] = run.get(x["item_id"], 0) + x["qty_m"]
            if frm <= x["date"] <= to or x["ref_type"] == "opening": out.append([x["date"], x["name"], Q(x["qty_m"]), x["ref_type"], x["ref_id"], x["batch"], x["note"], x["user"], Q(run[x["item_id"]])])
        return ["Date", "Item", "Movement", "Source", "Doc#", "Batch", "Note", "User", "Running bal"], out
    if name == "production":
        a = [[x[0], x[1], x[2], x[3], Q(x[4]), Q(x[5]), x[6] + "%", "FLAG" if x[7] else ""] for x in r("select r.id,r.date,p.name,i.name,l.planned_m,l.actual_m,l.var_pct,l.flag from run_lines l join runs r on r.id=l.run_id join items p on p.id=r.product_id join items i on i.id=l.item_id where r.date between ? and ?", frm, to)]
        b = [[x[0], x[1], x[2], "YIELD (packets)", x[3], x[4], x[5] + "%", "FLAG" if x[6] else ""] for x in r("select r.id,r.date,p.name,expected,good,yield_var,flag from runs r join items p on p.id=r.product_id where r.status='completed' and r.date between ? and ?", frm, to)]
        w = [[x[0], x[1], x[2], "WASTAGE (damaged pouches)", "", x[3], "", ""] for x in r("select r.id,r.date,p.name,damaged from runs r join items p on p.id=r.product_id where damaged>0 and r.date between ? and ?", frm, to)]
        return ["Run", "Date", "Product", "Item", "Planned", "Actual", "Var %", "Flag"], a + b + w
    if name == "costing":
        return ["Month", "Product", "Packets", "Material ₹", "Run overheads ₹", "Monthly overhead share ₹", "Total ₹", "Cost/packet ₹", "Price ₹", "Margin ₹", "Margin %"], costing_rows(c, frm, to)
    if name == "collections":
        return ["Date", "Invoice", "Customer", "Amount", "Mode"], [[x[0], x[1], x[2], rs(x[3]), x[4]] for x in r("select p.date,i.no,c.name,p.amount,mode from payments p join invoices i on i.id=invoice_id join customers c on c.id=p.customer_id where p.date between ? and ?", frm, to)]
    if name == "outstanding":
        rows, tdy = [], dt.date.today()
        for i in c.execute("select i.*,c.name cn from invoices i join customers c on c.id=i.customer_id where i.status='posted' order by c.name,i.id").fetchall():
            d = due(c, i["id"]); age = (tdy - dt.date.fromisoformat(i["date"])).days
            if d: rows.append([i["cn"], i["no"], i["date"], rs(i["total"]), rs(d), "0-30" if age <= 30 else "31-60" if age <= 60 else "60+"])
        return ["Customer", "Invoice", "Date", "Total", "Outstanding", "Ageing (days)"], rows
    if name == "visits":
        return ["Time", "Salesman", "Customer", "Lat", "Lng", "Note"], r("select v.ts,u.name,c.name,v.lat,v.lng,v.note from visits v join users u on u.id=v.salesman_id join customers c on c.id=v.customer_id where substr(v.ts,1,10) between ? and ? order by v.id desc", frm, to)
    if name == "audit_log":
        return ["Time", "User", "Action", "Entity", "ID", "Detail"], r("select ts,user,action,entity,entity_id,detail from audit where substr(ts,1,10) between ? and ? order by id desc", frm, to)
    raise KeyError(name)

# ---- exports: Tally XML, e-invoice / e-way bill (mock) --------------------
def tally_xml(c, frm, to):
    def v(vt, no, dt_, party, entries):
        e = "".join(f"<ALLLEDGERENTRIES.LIST><LEDGERNAME>{X(n)}</LEDGERNAME><ISDEEMEDPOSITIVE>{'Yes' if a < 0 else 'No'}</ISDEEMEDPOSITIVE><AMOUNT>{D(a)/100:.2f}</AMOUNT></ALLLEDGERENTRIES.LIST>" for n, a in entries)
        return f'<TALLYMESSAGE xmlns:UDF="TallyUDF"><VOUCHER VCHTYPE="{vt}" ACTION="Create"><DATE>{dt_.replace("-", "")}</DATE><VOUCHERTYPENAME>{vt}</VOUCHERTYPENAME><VOUCHERNUMBER>{X(no)}</VOUCHERNUMBER><PARTYLEDGERNAME>{X(party)}</PARTYLEDGERNAME>{e}</VOUCHER></TALLYMESSAGE>'
    out = []
    for i in c.execute("select i.*,cu.name cn from invoices i join customers cu on cu.id=i.customer_id where i.status!='cancelled' and i.date between ? and ?", (frm, to)):
        en = [(i["cn"], -i["total"]), ("Sales", i["taxable"])] + [(n, a) for n, a in (("Output CGST", i["cgst"]), ("Output SGST", i["sgst"]), ("Output IGST", i["igst"])) if a]
        out.append(v("Sales", i["no"], i["date"], i["cn"], en))
    for p in c.execute("select * from purchases where date between ? and ?", (frm, to)):
        out.append(v("Purchase", p["bill_no"] or f"P{p['id']}", p["date"], p["supplier"] or "Cash purchase", [("Purchases", -p["amount_p"])] + ([("Input GST", -p["gst_p"])] if p["gst_p"] else []) + [(p["supplier"] or "Cash purchase", p["amount_p"] + p["gst_p"])]))
    return '<?xml version="1.0" encoding="UTF-8"?><ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME></REQUESTDESC><REQUESTDATA>' + "".join(out) + "</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"
def _inv_ctx(c, iid):
    inv = c.execute("select * from invoices where id=?", (iid,)).fetchone(); cu = c.execute("select * from customers where id=?", (inv["customer_id"],)).fetchone()
    return inv, cu, c.execute("select l.*,p.name,p.unit from invoice_lines l join items p on p.id=l.item_id where invoice_id=?", (iid,)).fetchall(), cu["state"].strip().lower() != STATE.lower()
def einvoice(c, iid):
    """MOCK of the NIC e-invoice (IRP) payload and response. No government API is called."""
    inv, cu, ls, inter = _inv_ctx(c, iid); y = int(inv["date"][:4]) if inv["date"][5:7] >= "04" else int(inv["date"][:4]) - 1
    irn = hashlib.sha256(f"{FGSTIN}{y}-{str(y+1)[2:]}INV{inv['no']}".encode()).hexdigest(); dd = lambda d: f"{d[8:]}/{d[5:7]}/{d[:4]}"; items = []
    for n, l in enumerate(ls, 1):
        t, cg, sg, ig = tax([(l["taxable"], l["rate"])], inter)
        items.append({"SlNo": str(n), "PrdDesc": l["name"], "IsServc": "N", "HsnCd": l["hsn"], "Qty": l["qty"], "Unit": "PAC", "UnitPrice": rs(l["price"]).replace(",", ""), "TotAmt": rs(t).replace(",", ""), "AssAmt": rs(t).replace(",", ""),
                      "GstRt": l["rate"], "IgstAmt": rs(ig), "CgstAmt": rs(cg), "SgstAmt": rs(sg), "TotItemVal": rs(t + cg + sg + ig).replace(",", "")})
    return {"MOCK": True, "Version": "1.1", "Irn": irn, "AckNo": int(irn[:8], 16) % 10**12, "AckDt": inv["date"] + " 00:00:00", "TranDtls": {"TaxSch": "GST", "SupTyp": "B2B", "RegRev": "N"},
            "DocDtls": {"Typ": "INV", "No": inv["no"], "Dt": dd(inv["date"])}, "SellerDtls": {"Gstin": FGSTIN, "LglNm": FACTORY, "Stcd": "33"},
            "BuyerDtls": {"Gstin": cu["gstin"], "LglNm": cu["name"], "Pos": (cu["gstin"] or "33")[:2], "Stcd": (cu["gstin"] or "33")[:2]}, "ItemList": items,
            "ValDtls": {"AssVal": rs(inv["taxable"]), "CgstVal": rs(inv["cgst"]), "SgstVal": rs(inv["sgst"]), "IgstVal": rs(inv["igst"]), "TotInvVal": rs(inv["total"])}}
def ewaybill(c, iid, vehicle="TN00AA0000", distance="0"):
    """MOCK e-way bill (Part A + Part B) JSON in the NIC bulk-upload shape."""
    inv, cu, ls, inter = _inv_ctx(c, iid)
    return {"MOCK": True, "supplyType": "O", "subSupplyType": 1, "docType": "INV", "docNo": inv["no"], "docDate": inv["date"], "fromGstin": FGSTIN, "fromStateCode": 33, "toGstin": cu["gstin"],
            "toStateCode": int((cu["gstin"] or "33")[:2]), "totalValue": rs(inv["taxable"]), "cgstValue": rs(inv["cgst"]), "sgstValue": rs(inv["sgst"]), "igstValue": rs(inv["igst"]), "totInvValue": rs(inv["total"]),
            "transMode": 1, "transDistance": distance, "vehicleNo": vehicle, "vehicleType": "R",
            "itemList": [{"productName": l["name"], "hsnCode": l["hsn"], "quantity": l["qty"], "qtyUnit": "PAC", "taxableAmount": rs(l["taxable"]), "cgstRate": 0 if inter else l["rate"] / 2, "sgstRate": 0 if inter else l["rate"] / 2, "igstRate": l["rate"] if inter else 0} for l in ls]}
