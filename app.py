import os, io, csv, json
from decimal import Decimal as D
from functools import wraps
from flask import Flask, request, session, redirect, flash, render_template_string, send_file, abort, get_flashed_messages, jsonify, Response
from markupsafe import Markup, escape as E
from werkzeug.security import check_password_hash, generate_password_hash
import core, seed
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
app = Flask(__name__); app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
FACTORY, FGSTIN = core.FACTORY, core.FGSTIN
NAV = {"salesman": [("New order", "/orders/new"), ("My orders", "/orders"), ("Visits", "/visits")],
       "admin": [("Orders", "/orders"), ("Masters", "/masters"), ("Planning", "/planning"), ("Adjustments", "/adjustments"), ("Reports", "/reports"), ("Audit log", "/reports/audit_log")],
       "production": [("Production", "/production"), ("Purchases", "/purchases"), ("Adjustments", "/adjustments"), ("Planning", "/planning"), ("Masters", "/masters"), ("Stock", "/reports/stock_summary")],
       "accountant": [("Reports", "/reports"), ("Audit log", "/reports/audit_log"), ("Tally export", "/export/tally.xml")],
       "owner": [("Dashboard", "/dashboard"), ("Reports", "/reports"), ("Production", "/production"), ("Planning", "/planning")]}
HOME = {"salesman": "/orders/new", "admin": "/orders", "production": "/production", "accountant": "/reports", "owner": "/dashboard"}
TA = {
 # menus
 "New order": "புதிய ஆர்டர்", "My orders": "என் ஆர்டர்கள்", "Visits": "வருகைகள்", "Orders": "ஆர்டர்கள்", "Masters": "அடிப்படை தரவு", "Planning": "திட்டமிடல்", "Adjustments": "இருப்பு சரிசெய்தல்",
 "Reports": "அறிக்கைகள்", "Audit log": "தணிக்கைப் பதிவு", "Production": "உற்பத்தி", "Purchases": "கொள்முதல்", "Stock": "இருப்பு", "Tally export": "டேலி ஏற்றுமதி", "Dashboard": "முகப்புப் பலகை", "Logout": "வெளியேறு",
 "Login": "உள்நுழை", "Invalid login": "தவறான உள்நுழைவு", "Owner dashboard": "உரிமையாளர் முகப்பு", "Visit log": "வருகைப் பதிவு", "GPS check-in": "ஜிபிஎஸ் வருகைப் பதிவு",
 # sales
 "Customer": "வாடிக்கையாளர்", "Customers": "வாடிக்கையாளர்கள்", "Product": "பொருள்", "List price": "பட்டியல் விலை", "Qty": "எண்ணிக்கை", "Submit order": "ஆர்டரைச் சமர்ப்பி", "Date": "தேதி", "Amount (pre-tax)": "தொகை (வரிக்கு முன்)",
 "Status": "நிலை", "Customer-wise sales": "வாடிக்கையாளர் வாரி விற்பனை", "Sales (pre-tax)": "விற்பனை (வரிக்கு முன்)", "open": "திற", "Approve": "அங்கீகரி", "Reject": "நிராகரி", "Raise GST invoice": "ஜிஎஸ்டி விலைப்பட்டியல் உருவாக்கு",
 "Price ₹": "விலை ₹", "FG stock": "தயாரிப்பு இருப்பு", "Stock check": "இருப்புச் சரிபார்ப்பு", "OK": "சரி", "Dispatch": "அனுப்புதல்", "Record dispatch": "அனுப்பியதைப் பதிவு செய்", "Return": "திரும்பப் பெறுதல்",
 "Record return (credit note)": "திரும்பப்பெறலைப் பதிவு செய் (கிரெடிட் நோட்)", "Record payment": "பணம் பெற்றதைப் பதிவு செய்", "Cancel invoice (credit note)": "விலைப்பட்டியலை ரத்து செய் (கிரெடிட் நோட்)",
 "Payments": "பணம் பெறுதல்கள்", "Credit notes": "கிரெடிட் நோட்டுகள்", "HSN": "எச்எஸ்என்", "Taxable": "வரிக்குரிய மதிப்பு", "GST": "ஜிஎஸ்டி", "Dispatched": "அனுப்பப்பட்டது", "Returned": "திரும்பியது", "Amount": "தொகை",
 "Mode": "முறை", "Type": "வகை", "Total": "மொத்தம்", "No": "எண்", "Time": "நேரம்", "Note": "குறிப்பு", "Name": "பெயர்", "Rate": "விலை", "Item": "பொருள்", "Reason": "காரணம்", "Quantity": "அளவு",
 "submitted": "சமர்ப்பிக்கப்பட்டது", "approved": "அங்கீகரிக்கப்பட்டது", "invoiced": "விலைப்பட்டியல் இடப்பட்டது", "dispatched": "அனுப்பப்பட்டது", "part-dispatched": "பகுதி அனுப்பப்பட்டது", "rejected": "நிராகரிக்கப்பட்டது",
 "cancelled": "ரத்து செய்யப்பட்டது", "posted": "பதிவானது", "open ": "நடப்பில்", "completed": "முடிந்தது", "cash": "ரொக்கம்", "upi": "யுபிஐ", "bank": "வங்கி",
 # production floor
 "Start run": "உற்பத்தியைத் தொடங்கு", "Save run": "உற்பத்தியைச் சேமி", "Complete run": "உற்பத்தியை முடி", "Start run only (WIP)": "தொடக்கம் மட்டும் (நடப்பு உற்பத்தி)", "In progress": "நடப்பில்", "Batches": "தொகுதிகள்",
 "Good packets": "நல்ல பாக்கெட்டுகள்", "Damaged pouches (wastage)": "சேதமடைந்த பைகள் (வீணடிப்பு)", "Material": "மூலப்பொருள்", "BOM per batch": "ஒரு தொகுதிக்கான அளவு", "Actual issued": "உண்மையில் வழங்கியது",
 "Runs": "உற்பத்தி பதிவுகள்", "Expected": "எதிர்பார்ப்பு", "Good": "நல்லவை", "Yield var": "விளைச்சல் மாறுபாடு", "Record receipt": "பெறுதலைப் பதிவு செய்", "Supplier": "விநியோகஸ்தர்", "Save adjustment": "சரிசெய்தலைச் சேமி",
 "Planned": "திட்டமிட்டது", "Actual": "உண்மை", "Variance": "மாறுபாடு", "Add overheads": "செலவுகளைச் சேர்", "Labour": "கூலி", "Power/gas": "மின்/எரிவாயு", "Save changes": "மாற்றங்களைச் சேமி", "Edit run": "உற்பத்தியைத் திருத்து",
 "Batch": "தொகுதி எண்", "Expiry": "காலாவதி", "Bill no": "பில் எண்", "Flag": "எச்சரிக்கை", "FLAG": "எச்சரிக்கை", "FLAGGED": "எச்சரிக்கை", "Cost ₹": "செலவு ₹", "User": "பயனர்", "GST %": "ஜிஎஸ்டி %",
 # planning / dashboard / masters
 "Demand": "தேவை", "Stock ": "இருப்பு", "WIP": "நடப்பு உற்பத்தி", "Shortfall": "பற்றாக்குறை", "Batches to make": "தயாரிக்க வேண்டிய தொகுதிகள்", "Needed": "தேவை", "Available": "கிடைப்பது", "Short": "குறைவு",
 "Raw materials for those batches": "அந்தத் தொகுதிகளுக்கான மூலப்பொருட்கள்", "Stock levels": "இருப்பு நிலை", "Low-stock alerts": "குறைந்த இருப்பு எச்சரிக்கைகள்", "Near-expiry (30 days)": "காலாவதி நெருங்குபவை (30 நாட்கள்)",
 "Variance alerts": "மாறுபாடு எச்சரிக்கைகள்", "Cost per packet (per run)": "ஒரு பாக்கெட் செலவு (உற்பத்திக்கு)", "Balance": "இருப்பு", "Reorder level": "மறுஆர்டர் நிலை", "Unit": "அலகு", "Alert": "எச்சரிக்கை", "Run": "உற்பத்தி",
 "Items": "பொருட்கள்", "BOM": "மூலப்பொருள் பட்டியல் (BOM)", "Suppliers": "விநியோகஸ்தர்கள்", "Users": "பயனர்கள்", "Add item": "பொருளைச் சேர்", "Add BOM line": "BOM வரி சேர்", "Add supplier": "விநியோகஸ்தரைச் சேர்",
 "Add customer": "வாடிக்கையாளரைச் சேர்", "Add user": "பயனரைச் சேர்", "Add overhead": "செலவைச் சேர்", "Set price": "விலையை அமை", "Delete": "நீக்கு", "Saved": "சேமிக்கப்பட்டது", "Apply": "பயன்படுத்து", "From": "முதல்", "To": "வரை",
 "Reports": "அறிக்கைகள்", "Edit": "திருத்து", "Customer-specific prices": "வாடிக்கையாளர் சிறப்பு விலைகள்", "Role": "பங்கு", "Username": "பயனர் பெயர்", "Offline": "இணையமில்லை"}
PREFIX = {"Order #": "ஆர்டர் #", "Invoice ": "விலைப்பட்டியல் ", "Run #": "உற்பத்தி #", "Edit run #": "உற்பத்தி திருத்தம் #"}
def T(s): return TA.get(s, s) if session.get("lang") == "ta" else s
import re
def ta_html(h):
    """Translate every known UI string in a rendered page (menus, headings, labels, buttons, placeholders, table headers, statuses). Data entered by users is left as typed."""
    def tx(m):
        t = m.group(1); k = t.strip()
        if k in TA: return ">" + t.replace(k, TA[k]) + "<"
        for p, q in PREFIX.items():
            if k.startswith(p): return ">" + t.replace(p, q, 1) + "<"
        return m.group(0)
    h = re.sub(r">([^<>]+)<", tx, h)
    return re.sub(r"placeholder=('[^']*'|\"[^\"]*\"|[^\s>]+)", lambda m: "placeholder='" + TA.get(m.group(1).strip("'\""), m.group(1).strip("'\"")) + "'", h)
BASE = """<!doctype html><meta name=viewport content="width=device-width,initial-scale=1"><link rel=manifest href=/manifest.json><title>{{t}}</title>
<style>body{font:16px system-ui,'Noto Sans Tamil',sans-serif;margin:0;background:#f5f5f2}nav{background:#7a3b0c;padding:10px;display:flex;gap:14px;flex-wrap:wrap}nav a,nav span{color:#fff;text-decoration:none}
main{max-width:1000px;margin:auto;padding:12px}table{border-collapse:collapse;width:100%;background:#fff;display:block;overflow-x:auto}td,th{border:1px solid #ddd;padding:6px 8px;text-align:left}th{background:#eee}
input,select,button{font:inherit;padding:8px;margin:3px 0;max-width:100%}button,.btn{background:#7a3b0c;color:#fff;border:0;border-radius:6px;padding:9px 14px;text-decoration:none;display:inline-block;margin:3px 0}
.err{color:#a00}.ok{color:#060}.msg{background:#fff;border-left:4px solid #7a3b0c;padding:8px;margin:6px 0}.card{background:#fff;padding:10px;margin:8px 0;border-radius:6px}</style>
<nav><b style=color:#fff>Order-to-Audit</b>{% for n,u in nav %}<a href="{{u}}">{{n}}</a>{% endfor %}<span><a href=/lang/ta>தமிழ்</a> <a href=/lang/en>EN</a>{% if user %} | {{user}} ({{role}}) <a href=/logout>{{lo}}</a>{% endif %}</span></nav>
<main>{% for m in msgs %}<div class=msg>{{m}}</div>{% endfor %}<h2>{{t}}</h2>{{body}}</main>
<script>if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').then(()=>navigator.serviceWorker.ready).then(()=>{ {% if role=='salesman' %}fetch('/orders/new',{credentials:'same-origin'}).catch(()=>{}); {% endif %} }).catch(()=>{})</script>"""
def page(t, body):
    h = render_template_string(BASE, t=t, body=Markup(body), nav=[(T(n), u) for n, u in NAV.get(session.get("role"), [])], user=session.get("name"), role=session.get("role"), lo=T("Logout"), msgs=get_flashed_messages())
    return ta_html(h) if session.get("lang") == "ta" else h
def need(*roles):
    def d(f):
        @wraps(f)
        def w(*a, **k):
            if "uid" not in session: return redirect("/login")
            if session["role"] not in roles: abort(403)
            c = core.conn()
            try: return f(c, *a, **k)
            except (ValueError, KeyError) as e: c.rollback(); flash(str(e) or "Invalid input"); return redirect(request.referrer or "/")
            finally: c.close()
        return w
    return d
def table(h, rows):   # returns plain str on purpose: str + Markup would HTML-escape the str side
    cell = lambda x: x if isinstance(x, Markup) else E("" if x is None else x)
    return "<table><tr>" + "".join(f"<th>{E(x)}</th>" for x in h) + "</tr>" + "".join("<tr>" + "".join(f"<td>{cell(x)}</td>" for x in r) + "</tr>" for r in rows) + "</table>"
def opts(rows): return "".join(f"<option value={r[0]}>{E(r[1])}</option>" for r in rows)
def A(href, txt): return Markup(f'<a href="{href}">{E(txt)}</a>')
core.init(); _c = core.conn(); seed.seed(_c); _c.close()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        c = core.conn(); u = c.execute("select * from users where username=?", (request.form["u"],)).fetchone(); c.close()
        if u and check_password_hash(u["pw"], request.form["p"]):
            lang = session.get("lang"); session.clear(); session.update(uid=u["id"], role=u["role"], name=u["name"], un=u["username"], lang=lang); return redirect(HOME[u["role"]])
        flash("Invalid login")
    return page("Login", "<form method=post><input name=u placeholder=username><br><input name=p type=password placeholder=password><br><button>Login</button></form><p>Demo: salesA, salesB, admin, prod, auditor, owner / demo123</p>")
@app.route("/logout")
def logout(): session.clear(); return redirect("/login")
@app.route("/lang/<l>")
def lang(l): session["lang"] = "ta" if l == "ta" else "en"; return redirect(request.referrer or "/")
@app.route("/")
def home(): return redirect(HOME.get(session.get("role"), "/login"))
@app.route("/manifest.json")
def manifest(): return jsonify(name="Order-to-Audit", short_name="Orders", start_url="/orders/new", display="standalone", background_color="#f5f5f2", theme_color="#7a3b0c", icons=[])
@app.route("/sw.js")
def sw():
    js = """self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));
self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;e.respondWith(fetch(e.request).then(r=>{if(r.ok&&r.type==='basic'&&!r.redirected){const k=r.clone();caches.open('oas1').then(c=>c.put(e.request,k))}return r}).catch(()=>caches.match(e.request).then(r=>r||new Response('Offline - open this page once while online first',{status:503}))))});"""
    return Response(js, mimetype="application/javascript", headers={"Service-Worker-Allowed": "/"})

# ---- orders (salesman: mobile + offline queue) -----------------------------
@app.route("/api/orders", methods=["POST"])
def api_orders():
    if session.get("role") != "salesman": return jsonify(error="login required"), 401
    c = core.conn(); d = request.get_json(force=True, silent=True) or {}
    try:
        oid = core.create_order(c, session["un"], session["uid"], int(d["cust"]), d["lines"], d.get("client_id")); c.commit(); return jsonify(ok=True, order_id=oid)
    except (ValueError, KeyError, TypeError) as e: c.rollback(); return jsonify(error=str(e) or "invalid order"), 400
    finally: c.close()
OFFLINE_JS = """<div id=pend class=msg style=display:none></div><script>
const K='oas_pending',gq=()=>JSON.parse(localStorage.getItem(K)||'[]'),sq=q=>localStorage.setItem(K,JSON.stringify(q));
function show(m){const q=gq(),d=document.getElementById('pend');d.style.display=(q.length||m)?'block':'none';d.textContent=m||(q.length+' order(s) saved offline - will sync when the network returns')}
async function sync(){let rest=[],ok=0;for(const o of gq()){try{const r=await fetch('/api/orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});
if(r.ok)ok++;else if(r.status>=400&&r.status<500&&r.status!==401){alert('Order rejected: '+((await r.json()).error||''))}else rest.push(o)}catch(e){rest.push(o)}}sq(rest);show(ok&&!rest.length?'Order submitted':'');return ok}
document.getElementById('of').addEventListener('submit',ev=>{ev.preventDefault();const f=ev.target,lines=[];f.querySelectorAll('input[name^=q_]').forEach(i=>{if(+i.value>0)lines.push([+i.name.slice(2),+i.value])});
if(!lines.length){alert('Add at least one product');return}sq(gq().concat([{client_id:(crypto.randomUUID?crypto.randomUUID():Date.now()+'-'+Math.random()),cust:+f.cust.value,lines}]));f.reset();sync()});
window.addEventListener('online',sync);show();if(navigator.onLine)sync();</script>"""
@app.route("/orders/new", methods=["GET", "POST"])
@need("salesman")
def new_order(c):
    if request.method == "POST":
        lines = [(int(k[2:]), v) for k, v in request.form.items() if k.startswith("q_") and v.strip().isdigit()]
        oid = core.create_order(c, session["un"], session["uid"], int(request.form["cust"]), lines); c.commit(); flash(f"Order #{oid} submitted"); return redirect("/orders")
    cu = c.execute("select id,name from customers where salesman_id=?", (session["uid"],)).fetchall() or c.execute("select id,name from customers").fetchall()
    rows = [[r["name"], "₹" + core.rs(r["price"]), Markup(f"<input name=q_{r['id']} type=number min=0 inputmode=numeric style=width:80px>")] for r in c.execute("select * from items where kind='fg'")]
    return page("New order", f"<form method=post id=of>Customer<br><select name=cust>{opts(cu)}</select>{table(['Product','List price','Qty'], rows)}<button>Submit order</button></form>" + OFFLINE_JS)
@app.route("/orders")
@need("salesman", "admin")
def orders(c):
    sal = session["role"] == "salesman"
    rs_ = c.execute("select o.*,c.name cn,(select sum(qty*price) from order_lines where order_id=o.id) amt from orders o join customers c on c.id=o.customer_id" + (" where o.salesman_id=?" if sal else "") + " order by o.id desc", ((session["uid"],) if sal else ())).fetchall()
    body = table(["#", "Date", "Customer", "Amount (pre-tax)", "Status", ""], [[o["id"], o["date"], o["cn"], core.rs(o["amt"] or 0), o["status"], A(f"/orders/{o['id']}", "open") if not sal else ""] for o in rs_])
    if sal:
        cs = c.execute("select c.name,sum(l.qty*l.price) from order_lines l join orders o on o.id=l.order_id join customers c on c.id=o.customer_id where o.salesman_id=? and o.status not in ('rejected','cancelled') group by c.id", (session["uid"],)).fetchall()
        body += "<h3>Customer-wise sales</h3>" + table(["Customer", "Sales (pre-tax)"], [[x[0], core.rs(x[1])] for x in cs])
    return page("Orders", body)
@app.route("/orders/<int:oid>", methods=["GET", "POST"])
@need("admin")
def order(c, oid):
    o = c.execute("select o.*,c.name cn,c.state from orders o join customers c on c.id=o.customer_id where o.id=?", (oid,)).fetchone()
    if request.method == "POST":
        a = request.form["a"]
        if a == "reject": core.reject(c, session["un"], oid, request.form.get("why", ""))
        elif a == "approve": core.approve(c, session["un"], oid, {int(k[2:]): (int(v), core.P(request.form["p_" + k[2:]])) for k, v in request.form.items() if k.startswith("q_")})
        elif a == "invoice": iid = core.raise_invoice(c, session["un"], oid); c.commit(); return redirect(f"/invoices/{iid}")
        c.commit(); return redirect(f"/orders/{oid}")
    sc = {s["item"]: s for s in core.stock_check(c, oid)}; rows = []; sub = o["status"] == "submitted"
    for l in c.execute("select l.*,i.name from order_lines l join items i on i.id=l.item_id where order_id=?", (oid,)):
        s = sc[l["name"]]; stat = Markup(f"<b class=err>SHORT {s['short']}</b>") if s["short"] else Markup("<span class=ok>OK</span>")
        rows.append([l["name"], Markup(f"<input name=q_{l['item_id']} value={l['qty']} type=number style=width:80px>") if sub else l["qty"], Markup(f"<input name=p_{l['item_id']} value={D(l['price'])/100} style=width:80px>") if sub else core.rs(l["price"]), s["avail"], stat])
    btn = {"submitted": "<button name=a value=approve>Approve</button> <input name=why placeholder='reject reason'><button name=a value=reject>Reject</button>",
           "approved": "<button name=a value=invoice>Raise GST invoice</button> <button name=a value=reject>Reject</button>"}.get(o["status"], "")
    sup = "Inter-state: IGST" if o["state"].lower() != core.STATE.lower() else "Intra-state: CGST+SGST"
    return page(f"Order #{oid} — {o['cn']} ({o['status']})", f"<p>Place of supply: {E(o['state'])} → {sup}</p><form method=post>{table(['Product','Qty','Price ₹','FG stock','Stock check'], rows)}{btn}</form>")

# ---- invoices ----------------------------------------------------------
@app.route("/invoices/<int:iid>", methods=["GET", "POST"])
@need("admin")
def invoice(c, iid):
    if request.method == "POST":
        a, u, f = request.form["a"], session["un"], request.form
        if a == "dispatch": core.dispatch(c, u, iid, {int(k[2:]): int(v or 0) for k, v in f.items() if k.startswith("d_")})
        if a == "return": core.return_goods(c, u, iid, {int(k[2:]): int(v or 0) for k, v in f.items() if k.startswith("r_")}, f.get("why") or "Sales return")
        if a == "pay": core.pay(c, u, iid, f["amt"], f.get("mode", "cash"))
        if a == "cancel": core.cancel_invoice(c, u, iid, f.get("why") or "cancelled")
        c.commit(); return redirect(f"/invoices/{iid}")
    i = c.execute("select i.*,c.name cn from invoices i join customers c on c.id=i.customer_id where i.id=?", (iid,)).fetchone(); L = c.execute("select l.*,p.name from invoice_lines l join invoices i2 on i2.id=l.invoice_id join items p on p.id=l.item_id where invoice_id=?", (iid,)).fetchall()
    ls = [[l["name"], l["hsn"], l["qty"], core.rs(l["price"]), core.rs(l["taxable"]), f"{l['rate']}%", l["disp_qty"], l["ret_qty"]] for l in L]
    pays = [[p["date"], core.rs(p["amount"]), p["mode"]] for p in c.execute("select * from payments where invoice_id=?", (iid,))]
    cns = [[n["no"], n["date"], n["kind"], core.rs(n["amount"]), n["reason"]] for n in c.execute("select * from credit_notes where invoice_id=?", (iid,))]
    st = {0: "no", 1: "partial", 2: "yes"}[i["dispatched"]]; btns = ""
    if i["status"] == "posted":
        if i["dispatched"] < 2: btns += "<form method=post class=card><input type=hidden name=a value=dispatch><b>Dispatch</b> " + "".join(f"{E(l['name'])} <input name=d_{l['id']} value={l['qty']-l['disp_qty']} type=number style=width:70px> " for l in L) + "<button>Record dispatch</button></form>"
        if i["dispatched"]: btns += "<form method=post class=card><input type=hidden name=a value=return><b>Return</b> " + "".join(f"{E(l['name'])} <input name=r_{l['id']} value=0 type=number style=width:70px> " for l in L) + "<input name=why placeholder=reason><button>Record return (credit note)</button></form>"
        btns += "<form method=post class=card><input type=hidden name=a value=pay><input name=amt placeholder='₹ amount' size=8><select name=mode><option>cash<option>upi<option>bank</select><button>Record payment</button></form>"
        btns += "<form method=post class=card><input type=hidden name=a value=cancel><input name=why placeholder=reason><button>Cancel invoice (credit note)</button></form>"
    wa = f"https://wa.me/?text=Invoice%20{i['no']}%20total%20Rs%20{core.rs(i['total'])}"
    outd = core.rs(core.due(c, iid)) if i["status"] == "posted" else "0.00"
    return page(f"Invoice {i['no']} — {i['status']}", f"<div class=card>{E(i['cn'])} · {i['date']} · dispatched: {st}</div>" + table(["Item", "HSN", "Qty", "Rate", "Taxable", "GST", "Dispatched", "Returned"], ls) +
                f"<div class=card>Taxable ₹{core.rs(i['taxable'])} · CGST ₹{core.rs(i['cgst'])} · SGST ₹{core.rs(i['sgst'])} · IGST ₹{core.rs(i['igst'])}<br><b>Total ₹{core.rs(i['total'])}</b> · Outstanding ₹{outd}</div>{btns}"
                f"<p><a class=btn href=/invoices/{iid}/pdf>PDF</a> <a class=btn href='{wa}'>WhatsApp</a> <a class=btn href=/invoices/{iid}/einvoice.json>e-Invoice (mock)</a> <a class=btn href=/invoices/{iid}/ewaybill.json>e-Way bill (mock)</a></p><h3>Payments</h3>" + table(["Date", "Amount", "Mode"], pays) + "<h3>Credit notes</h3>" + table(["No", "Date", "Type", "Amount", "Reason"], cns))
@app.route("/invoices/<int:iid>/<doc>.json")
@need("admin", "accountant")
def invoice_json(c, iid, doc):
    d = core.einvoice(c, iid) if doc == "einvoice" else core.ewaybill(c, iid, request.args.get("vehicle", "TN00AA0000")) if doc == "ewaybill" else abort(404)
    return Response(json.dumps(d, indent=2, ensure_ascii=False), mimetype="application/json")
@app.route("/invoices/<int:iid>/pdf")
@need("admin", "accountant")
def invoice_pdf(c, iid):
    i = c.execute("select i.*,c.name cn,c.gstin,c.state from invoices i join customers c on c.id=i.customer_id where i.id=?", (iid,)).fetchone(); b = io.BytesIO(); p = canvas.Canvas(b, pagesize=A4); y = 800
    def ln(t, sz=10, x=40):
        nonlocal y; p.setFont("Helvetica", sz); p.drawString(x, y, t); y -= sz + 6
    ln("TAX INVOICE" + ("  (CANCELLED)" if i["status"] == "cancelled" else ""), 16); ln(f"{FACTORY} | GSTIN {FGSTIN} | Tamil Nadu"); ln(f"Invoice No: {i['no']}   Date: {i['date']}"); ln(f"Bill to: {i['cn']} | GSTIN {i['gstin']} | Place of supply: {i['state']}"); y -= 10
    ln("Item                      HSN        Qty     Rate     Taxable    GST%", 10)
    for l in c.execute("select l.*,p.name from invoice_lines l join items p on p.id=l.item_id where invoice_id=?", (iid,)): ln(f"{l['name'][:24]:26}{l['hsn']:11}{l['qty']:<8}{core.rs(l['price']):>8}{core.rs(l['taxable']):>11}{l['rate']:>6}")
    y -= 10; ln(f"Taxable value: Rs {core.rs(i['taxable'])}")
    if i["igst"]: ln(f"IGST: Rs {core.rs(i['igst'])}")
    else: ln(f"CGST: Rs {core.rs(i['cgst'])}   SGST: Rs {core.rs(i['sgst'])}")
    ln(f"Invoice total: Rs {core.rs(i['total'])}", 12); p.save(); b.seek(0); return send_file(b, mimetype="application/pdf", download_name=i["no"].replace("/", "_") + ".pdf")

# ---- production / purchases / adjustments --------------------------------
@app.route("/production", methods=["GET", "POST"])
@need("production", "owner")
def production(c):
    ro = session["role"] == "owner"
    if request.method == "POST" and not ro:
        pid = int(request.form["pid"]); act = {int(k[2:]): v for k, v in request.form.items() if k.startswith("a_") and v}
        if request.form.get("mode") == "start": rid = core.start_run(c, session["un"], pid, int(request.form["batches"]), act)
        else: rid = core.make_run(c, session["un"], pid, int(request.form["batches"]), act, int(request.form["good"]), int(request.form.get("damaged") or 0))
        c.commit(); return redirect(f"/production/{rid}")
    pid = request.args.get("product"); form = ""
    if not ro:
        form = f"<form><select name=product>{opts(c.execute('select id,name from items where kind=?', ('fg',)).fetchall())}</select><button>{T('Start run')}</button></form>"
        if pid:
            p = c.execute("select * from items where id=?", (pid,)).fetchone()
            rows = [[b["name"], f"{b['qty']} {b['unit']}", Markup(f"<input name=a_{b['item_id']} value={b['qty'] if b['unit']==b['iu'] else ''} placeholder='{b['iu']}' size=8>")] for b in c.execute("select b.*,i.name,i.unit iu from bom b join items i on i.id=b.item_id where product_id=?", (pid,))]
            form += f"<form method=post><input type=hidden name=pid value={pid}>{T('Batches')} <input name=batches value=1 type=number min=1 style=width:60px>{table([T('Material'), T('BOM per batch'), T('Actual issued')], rows)}{T('Good packets')} ({T('Expected')} {p['yield_qty']}/batch) <input name=good type=number><br>{T('Damaged pouches (wastage)')} <input name=damaged type=number><br><button name=mode value=complete>{T('Save run')}</button> <button name=mode value=start>{T('Start run only (WIP)')}</button></form>"
    runs = [[r["id"], r["date"], r["pn"], r["expected"], r["good"] if r["status"] == "completed" else "-", (r["yield_var"] + "%" + (" ⚠" if r["flag"] else "")) if r["status"] == "completed" else T("In progress"), A(f"/production/{r['id']}", "open")] for r in c.execute("select r.*,i.name pn from runs r join items i on i.id=r.product_id order by r.id desc")]
    return page(T("Production"), form + f"<h3>{T('Runs')}</h3>" + table(["#", T("Date"), T("Product"), T("Expected"), T("Good"), T("Yield var"), ""], runs))
@app.route("/production/<int:rid>", methods=["GET", "POST"])
@need("production", "owner", "admin", "accountant")
def run_detail(c, rid):
    if request.method == "POST" and session["role"] == "production":
        if request.form.get("a") == "complete":
            core.complete_run(c, session["un"], rid, int(request.form["good"]), int(request.form.get("damaged") or 0)); c.commit(); return redirect(f"/production/{rid}")
        core.add_overhead(c, session["un"], rid, request.form.get("labour") or 0, request.form.get("power") or 0); c.commit(); return redirect(f"/production/{rid}")
    r = c.execute("select r.*,i.name pn from runs r join items i on i.id=r.product_id where r.id=?", (rid,)).fetchone()
    ls = [[l["name"], core.Q(l["planned_m"]), core.Q(l["actual_m"]), l["var_pct"] + "%", Markup("<b class=err>FLAG</b>") if l["flag"] else "ok", core.rs(l["cost_p"])] for l in c.execute("select l.*,i.name from run_lines l join items i on i.id=l.item_id where run_id=?", (rid,))]
    cpp, mg, mp = core.cost_per_packet(c, rid); prod_ = session["role"] == "production"; done = r["status"] == "completed"
    wipf = "" if done or not prod_ else f"<form method=post class=card><input type=hidden name=a value=complete><b>{T('In progress')}</b> — {T('Good packets')} <input name=good type=number> {T('Damaged pouches (wastage)')} <input name=damaged type=number><button>{T('Complete run')}</button></form>"
    return page(f"Run #{rid} — {r['pn']}", wipf + table([T("Material"), T("Planned"), T("Actual"), T("Variance"), "Flag", "Cost ₹"], ls) +
                f"<div class=card>Yield: expected {r['expected']} vs actual {r['good'] if done else '— (in progress)'} {f"({r['yield_var']}%)" if done else ''} {'<b class=err>FLAGGED</b>' if r['flag'] else ''}<br>Damaged pouches: {r['damaged']} · Batch {r['batch']}<br>Material ₹{core.rs(r['mat_p'])} · Labour ₹{core.rs(r['labour_p'])} · Power/gas ₹{core.rs(r['oh_p'])}<br><b>Cost per packet ₹{core.rs(cpp)}</b> · margin ₹{core.rs(mg)} ({mp}%) <small>(weighted-average material cost + run overheads ÷ good packets)</small></div>"
                + (f"<form method=post>{T('Labour')} ₹<input name=labour size=6> {T('Power/gas')} ₹<input name=power size=6><button>{T('Add overheads')}</button></form><a class=btn href=/production/{rid}/edit>{T('Edit run')}</a>" if prod_ and done else ""))
@app.route("/production/<int:rid>/edit", methods=["GET", "POST"])
@need("production")
def run_edit(c, rid):
    if request.method == "POST":
        core.edit_run(c, session["un"], rid, {int(k[2:]): v for k, v in request.form.items() if k.startswith("a_") and v}, int(request.form["good"]), int(request.form.get("damaged") or 0)); c.commit(); flash("Run updated (logged in audit trail)"); return redirect(f"/production/{rid}")
    r = c.execute("select * from runs where id=?", (rid,)).fetchone()
    rows = [[l["name"], core.Q(l["planned_m"]), Markup(f"<input name=a_{l['item_id']} value={core.Q(l['actual_m'])} size=8>")] for l in c.execute("select l.*,i.name from run_lines l join items i on i.id=l.item_id where run_id=?", (rid,))]
    return page(f"{T('Edit run')} #{rid}", f"<form method=post>{table([T('Material'), T('Planned'), T('Actual')], rows)}{T('Good packets')} <input name=good type=number value={r['good']}><br>{T('Damaged pouches (wastage)')} <input name=damaged type=number value={r['damaged']}><br><button>{T('Save changes')}</button></form>")
@app.route("/purchases", methods=["GET", "POST"])
@need("production")
def purchases(c):
    if request.method == "POST":
        f = request.form; core.purchase(c, session["un"], int(f["item"]), f["qty"], f["rate"], f["sup"], f["bill"], None, f.get("batch", ""), f.get("expiry", ""), f.get("gst") or 0); c.commit(); flash("Purchase recorded"); return redirect("/purchases")
    its = c.execute("select id,name||' ('||unit||')' from items where kind in ('raw','pack')").fetchall(); sups = "".join(f"<option>{E(s[0])}" for s in c.execute("select name from suppliers order by name"))
    return page(T("Purchases"), f"<form method=post><select name=item>{opts(its)}</select><br><select name=sup>{sups}</select><br><input name=qty placeholder='{T('Quantity')}'><input name=rate placeholder='₹ {T('Rate')}'><br><input name=gst placeholder='{T('GST %')}' size=5><input name=bill placeholder='{T('Bill no')}'><input name=batch placeholder='{T('Batch')} (opt)'><br>{T('Expiry')} <input type=date name=expiry><br><button>{T('Record receipt')}</button></form>" + table(*core.report(c, "purchase_register", "2000-01-01", "2999-12-31")))
@app.route("/adjustments", methods=["GET", "POST"])
@need("production", "admin")
def adjustments(c):
    if request.method == "POST":
        f = request.form; core.adjust(c, session["un"], int(f["item"]), f["qty"], f["reason"], f.get("expiry", "")); c.commit(); flash("Adjustment posted"); return redirect("/adjustments")
    its = c.execute("select id,name||' ('||unit||')' from items where kind!='wip'").fetchall()
    rows = [[a["date"], a["name"], core.Q(a["qty_m"]), a["reason"], a["user"]] for a in c.execute("select a.*,i.name from adjustments a join items i on i.id=a.item_id order by a.id desc")]
    return page(T("Adjustments"), f"<form method=post><select name=item>{opts(its)}</select><br><input name=qty placeholder='+ / - {T('Quantity')}'><input name=reason placeholder='{T('Reason')}'><br>{T('Expiry')} <input type=date name=expiry><br><button>{T('Save adjustment')}</button></form>" + table([T("Date"), T("Item"), T("Quantity"), T("Reason"), "User"], rows))
@app.route("/planning")
@need("admin", "production", "owner")
def planning(c):
    fg, raw = core.plan(c)
    return page(T("Planning"), "<p>Demand = pending orders + invoiced-but-undispatched, against finished-goods stock + batches in WIP.</p>" + table(["Product", "Demand", "Stock", "WIP", "Shortfall", "Batches to make"], fg) + "<h3>Raw materials for those batches</h3>" + table(["Product", "Material", "Needed", "Available", "Short"], raw))

# ---- masters ------------------------------------------------------------
def form(act, fields, btn="Add"):
    s = f"<form method=post action=/masters/{act} class=card>"
    for n, ph, *o in fields: s += f"<select name={n}>{o[0]}</select> " if o else f"<input name={n} placeholder='{ph}' size=11> "
    return s + f"<button>{btn}</button></form>"
@app.route("/masters")
@need("admin", "production")
def masters(c):
    adm = session["role"] == "admin"; its = c.execute("select id,name from items where kind!='wip'").fetchall(); fgs = c.execute("select id,name from items where kind='fg'").fetchall()
    kinds = "<option>raw<option>pack<option>fg"; units = "".join(f"<option>{u}" for u in core.UN)
    b = "<h3>Items</h3>" + table(["ID", "Name", "Type", "Unit", "HSN", "Price ₹", "GST%", "Yield/batch", "Shelf life (d)", "Reorder level"], [[r["id"], r["name"], r["kind"], r["unit"], r["hsn"], core.rs(r["price"]), r["gst"], r["yield_qty"], r["shelf_life"], core.Q(r["reorder_m"])] for r in c.execute("select * from items")])
    b += form("item_add", [("name", "name"), ("kind", "", kinds), ("unit", "", units), ("hsn", "HSN"), ("price", "price ₹"), ("gst", "GST % (5)"), ("yield", "yield/batch"), ("carton", "packets/carton"), ("shelf", "shelf life days"), ("reorder", "reorder level")], "Add item")
    b += form("item_edit", [("id", "", opts(its)), ("price", "new price ₹"), ("gst", "GST %"), ("yield", "yield"), ("shelf", "shelf days"), ("reorder", "reorder level")], "Update (blank = keep)")
    b += "<h3>BOM</h3>" + table(["Product", "Material", "Qty/batch", "Unit", ""], [[r["pn"], r["name"], r["qty"], r["unit"], Markup(f"<form method=post action=/masters/bom_del><input type=hidden name=id value={r['id']}><button>Delete</button></form>")] for r in c.execute("select b.*,p.name pn,i.name from bom b join items p on p.id=b.product_id join items i on i.id=b.item_id order by p.name")])
    b += form("bom_add", [("product", "", opts(fgs)), ("item", "", opts([i for i in its])), ("qty", "qty per batch"), ("unit", "", units)], "Add BOM line")
    b += "<h3>Suppliers</h3>" + table(["Name", "GSTIN", "Phone"], [[r["name"], r["gstin"], r["phone"]] for r in c.execute("select * from suppliers")]) + form("sup_add", [("name", "name"), ("gstin", "GSTIN"), ("phone", "phone")], "Add supplier")
    b += "<h3>Monthly overheads (allocated to products by packets produced)</h3>" + table(["Month", "Kind", "Amount ₹", "Note"], [[r["month"], r["kind"], core.rs(r["amount_p"]), r["note"]] for r in c.execute("select * from monthly_overheads")]) + form("ovh_add", [("month", "YYYY-MM"), ("kind", "labour/power/gas/rent"), ("amount", "amount ₹"), ("note", "note")], "Add overhead")
    if adm:
        users = c.execute("select id,name from users where role='salesman'").fetchall(); cus = c.execute("select id,name from customers").fetchall()
        b += "<h3>Customers</h3>" + table(["Name", "GSTIN", "State", "Type", "Salesman"], [[r["name"], r["gstin"], r["state"], r["kind"], r["sn"]] for r in c.execute("select c.*,u.name sn from customers c left join users u on u.id=c.salesman_id")])
        b += form("cust_add", [("name", "name"), ("gstin", "GSTIN"), ("state", "state"), ("kind", "", "<option>retailer<option>distributor"), ("sales", "", opts(users))], "Add customer")
        b += "<h3>Customer-specific prices</h3>" + table(["Customer", "Product", "Price ₹"], [[r["cn"], r["name"], core.rs(r["price"])] for r in c.execute("select p.*,c.name cn,i.name from customer_prices p join customers c on c.id=p.customer_id join items i on i.id=p.item_id")])
        b += form("cust_price", [("cust", "", opts(cus)), ("item", "", opts(fgs)), ("price", "price ₹ (blank = remove)")], "Set price")
        b += "<h3>Users</h3>" + table(["Username", "Name", "Role"], [[r["username"], r["name"], r["role"]] for r in c.execute("select * from users")]) + form("user_add", [("un", "username"), ("pw", "password"), ("name", "full name"), ("role", "", "<option>salesman<option>admin<option>production<option>accountant<option>owner")], "Add user")
    return page(T("Masters"), b)
@app.route("/masters/<act>", methods=["POST"])
@need("admin", "production")
def masters_post(c, act):
    f, u = request.form, session["un"]; ex = lambda sql, *a: c.execute(sql, a)
    if act in ("cust_add", "cust_price", "user_add") and session["role"] != "admin": abort(403)
    if act == "item_add":
        if not f["name"].strip(): raise ValueError("Name required")
        i = ex("insert into items(name,kind,unit,hsn,price,gst,yield_qty,carton_size,shelf_life,reorder_m) values(?,?,?,?,?,?,?,?,?,?)", f["name"].strip(), f["kind"], f["unit"], f["hsn"], core.P(f["price"] or 0), int(f["gst"] or 5), int(f["yield"] or 0), int(f["carton"] or 20), int(f["shelf"] or 0), core.M(f["reorder"] or 0)).lastrowid; core.audit(c, u, "create", "item", i, f["name"])
    elif act == "item_edit":
        i = int(f["id"]); old = core.item(c, i)
        for col, key, fn in [("price", "price", core.P), ("gst", "gst", int), ("yield_qty", "yield", int), ("shelf_life", "shelf", int), ("reorder_m", "reorder", core.M)]:
            if f.get(key, "").strip(): ex(f"update items set {col}=? where id=?", fn(f[key]), i)
        core.audit(c, u, "edit", "item", i, f"{old['name']} price {core.rs(old['price'])}->{core.rs(core.item(c, i)['price'])}")
    elif act == "bom_add":
        core.conv(1, f["unit"], core.item(c, int(f["item"]))["unit"], 20); ex("insert into bom(product_id,item_id,qty,unit) values(?,?,?,?)", int(f["product"]), int(f["item"]), str(D(f["qty"])), f["unit"]); core.audit(c, u, "edit", "bom", int(f["product"]), "line added")
    elif act == "bom_del": ex("delete from bom where id=?", int(f["id"])); core.audit(c, u, "edit", "bom", int(f["id"]), "line deleted")
    elif act == "sup_add": ex("insert into suppliers(name,gstin,phone) values(?,?,?)", f["name"].strip(), f["gstin"], f["phone"]); core.audit(c, u, "create", "supplier", 0, f["name"])
    elif act == "ovh_add": core.add_monthly_overhead(c, u, f["month"], f["kind"], f["amount"], f["note"])
    elif act == "cust_add": ex("insert into customers(name,gstin,state,kind,salesman_id) values(?,?,?,?,?)", f["name"].strip(), f["gstin"], f["state"].strip(), f["kind"], int(f["sales"])); core.audit(c, u, "create", "customer", 0, f["name"])
    elif act == "cust_price":
        if f["price"].strip(): ex("insert or replace into customer_prices values(?,?,?)", int(f["cust"]), int(f["item"]), core.P(f["price"]))
        else: ex("delete from customer_prices where customer_id=? and item_id=?", int(f["cust"]), int(f["item"]))
        core.audit(c, u, "edit", "customer_price", int(f["cust"]), f["price"])
    elif act == "user_add":
        if len(f["pw"]) < 6: raise ValueError("Password must be at least 6 characters")
        ex("insert into users(username,pw,role,name) values(?,?,?,?)", f["un"].strip(), generate_password_hash(f["pw"]), f["role"], f["name"]); core.audit(c, u, "create", "user", 0, f["un"])
    else: abort(404)
    c.commit(); flash("Saved"); return redirect("/masters")
@app.route("/visits", methods=["GET", "POST"])
@need("salesman")
def visits(c):
    if request.method == "POST":
        f = request.form; core.visit(c, session["un"], session["uid"], int(f["cust"]), f.get("lat", ""), f.get("lng", ""), f.get("note", "")); c.commit(); flash("Check-in recorded"); return redirect("/visits")
    cu = c.execute("select id,name from customers where salesman_id=?", (session["uid"],)).fetchall() or c.execute("select id,name from customers").fetchall()
    rows = [list(r) for r in c.execute("select v.ts,c.name,v.lat,v.lng,v.note from visits v join customers c on c.id=v.customer_id where v.salesman_id=? order by v.id desc", (session["uid"],))]
    return page("Visit log", f"<form method=post id=vf><select name=cust>{opts(cu)}</select><input name=note placeholder=note><input type=hidden name=lat><input type=hidden name=lng><button>GPS check-in</button></form>"
                "<script>document.getElementById('vf').addEventListener('submit',ev=>{const f=ev.target;if(f.lat.value||!navigator.geolocation)return;ev.preventDefault();navigator.geolocation.getCurrentPosition(p=>{f.lat.value=p.coords.latitude;f.lng.value=p.coords.longitude;f.submit()},()=>f.submit(),{timeout:8000})})</script>" + table(["Time", "Customer", "Lat", "Lng", "Note"], rows))

# ---- dashboard / reports / exports ---------------------------------------
@app.route("/dashboard")
@need("owner")
def dash(c):
    t = core.today(); n = c.execute("select count(*) from orders where date=?", (t,)).fetchone()[0]
    out = sum(core.due(c, r[0]) for r in c.execute("select id from invoices where status='posted'"))
    al = [[f"Run #{r['id']}", r["pn"], f"Yield {r['yield_var']}%"] for r in c.execute("select r.*,i.name pn from runs r join items i on i.id=r.product_id where flag=1")] + \
         [[f"Run #{r['run_id']}", r["name"], f"Consumption {r['var_pct']}%"] for r in c.execute("select l.*,i.name from run_lines l join items i on i.id=l.item_id where flag=1")]
    cp = [[r["pn"], f"Run #{r['id']}", "₹" + core.rs(core.cost_per_packet(c, r["id"])[0])] for r in c.execute("select r.id,i.name pn from runs r join items i on i.id=r.product_id")]
    return page("Owner dashboard", f"<div class=card>Orders today: <b>{n}</b> · Outstanding dues: <b>₹{core.rs(out)}</b></div><h3>Stock levels</h3>" + table(*core.report(c, "stock_summary", *core.month_range())) +
                "<h3>Low-stock alerts</h3>" + table(["Item", "Balance", "Reorder level", "Unit"], core.low_stock(c)) + "<h3>Near-expiry (30 days)</h3>" + table(["Item", "Batch", "Expiry", "Qty"], core.near_expiry(c)) +
                "<h3>Variance alerts</h3>" + table(["Run", "Item", "Alert"], al) + "<h3>Cost per packet (per run)</h3>" + table(["Product", "Run", "Cost"], cp))
@app.route("/reports")
@need("admin", "accountant", "owner")
def rindex(c): return page("Reports", "".join(f"<p><a class=btn href=/reports/{r}>{r.replace('_',' ').title()}</a></p>" for r in core.REPORTS))
def report_pdf(title, h, rows, f, t):
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    b = io.BytesIO(); st = getSampleStyleSheet()
    data = [[str(x) for x in h]] + [[str(x)[:60] for x in r] for r in rows]
    tb = Table(data, repeatRows=1); tb.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), .3, colors.grey), ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey)]))
    SimpleDocTemplate(b, pagesize=landscape(A4), leftMargin=20, rightMargin=20).build([Paragraph(f"{FACTORY} — {title} ({f} to {t})".replace("₹", "Rs"), st["Heading3"]), Spacer(1, 6), tb]); b.seek(0); return b
@app.route("/reports/<name>")
@need("admin", "accountant", "owner", "production")
def rep(c, name):
    if name not in core.REPORTS or (session["role"] == "production" and name not in ("stock_summary", "stock_batches", "stock_ledger", "purchase_register", "production")): abort(404)
    if name == "audit_log" and session["role"] not in ("admin", "accountant", "owner"): abort(403)
    f, t = request.args.get("from") or core.month_range()[0], request.args.get("to") or core.month_range()[1]; h, rows = core.report(c, name, f, t); fmt = request.args.get("fmt")
    if fmt == "csv":
        b = io.StringIO(); w = csv.writer(b); w.writerow(h); w.writerows(rows); return send_file(io.BytesIO(b.getvalue().encode("utf-8-sig")), mimetype="text/csv", download_name=name + ".csv")
    if fmt == "xlsx":
        import openpyxl; wb = openpyxl.Workbook(); ws = wb.active; ws.append(h); [ws.append(r) for r in rows]; b = io.BytesIO(); wb.save(b); b.seek(0); return send_file(b, download_name=name + ".xlsx")
    if fmt == "pdf": return send_file(report_pdf(name.replace("_", " ").title(), h, rows, f, t), mimetype="application/pdf", download_name=name + ".pdf")
    q = f"from={f}&to={t}"
    return page(name.replace("_", " ").title(), f"<form>From <input type=date name=from value={f}> To <input type=date name=to value={t}><button>Apply</button></form><p><a class=btn href='?{q}&fmt=csv'>CSV</a> <a class=btn href='?{q}&fmt=xlsx'>Excel</a> <a class=btn href='?{q}&fmt=pdf'>PDF</a></p>" + table(h, rows))
@app.route("/export/tally.xml")
@need("admin", "accountant")
def tally(c):
    f, t = request.args.get("from") or core.month_range()[0], request.args.get("to") or core.month_range()[1]
    return Response(core.tally_xml(c, f, t), mimetype="application/xml", headers={"Content-Disposition": "attachment; filename=tally_vouchers.xml"})
if __name__ == "__main__": app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
