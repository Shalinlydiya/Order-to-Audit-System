"""Loads section-5 master data. Idempotent: does nothing if users exist."""
from werkzeug.security import generate_password_hash as H
import core
def seed(c):
    if c.execute("select count(*) from users").fetchone()[0]: return
    for u, r, n in [("salesA", "salesman", "Salesman A"), ("salesB", "salesman", "Salesman B"), ("admin", "admin", "Factory Admin"),
                    ("prod", "production", "Production Supervisor"), ("auditor", "accountant", "Accountant/Auditor"), ("owner", "owner", "Owner")]:
        c.execute("insert into users(username,pw,role,name) values(?,?,?,?)", (u, H("demo123"), r, n))
    def ins(n, k, u, hsn="", price=0, y=0, shelf=0, ro=0):
        return c.execute("insert into items(name,kind,unit,hsn,price,gst,yield_qty,shelf_life,reorder_m) values(?,?,?,?,?,5,?,?,?)", (n, k, u, hsn, price, y, shelf, core.M(ro))).lastrowid
    fl, oil, sp = ins("Flour", "raw", "kg", ro=50), ins("Cooking oil", "raw", "l", ro=10), ins("Salt and spice mix", "raw", "kg", ro=2)
    po, ca = ins("200 g pouch", "pack", "pcs", ro=200), ins("Carton (20 packets)", "pack", "pcs", ro=10)
    mu = ins("Murukku 200 g", "fg", "packet", "19059090", 5000, 200, 90)
    for i, q, u in [(fl, 40, "kg"), (oil, 10, "l"), (sp, "1.2", "kg"), (po, 200, "pcs"), (ca, 10, "pcs")]:
        c.execute("insert into bom(product_id,item_id,qty,unit) values(?,?,?,?)", (mu, i, str(q), u))
    for i, q, r in [(fl, 100, 42), (oil, 30, 140), (sp, 5, 200), (po, 500, "2.50"), (ca, 30, 15), (mu, 50, 0)]: core.opening(c, i, q, r)
    c.execute("insert into customers(name,gstin,state,kind,salesman_id) values('Retailer A','33ABCDE1234F1Z5','Tamil Nadu','retailer',1)")
    c.execute("insert into customers(name,gstin,state,kind,salesman_id) values('Distributor B','29ABCDE5678G1Z3','Karnataka','distributor',2)")
    for s, g in [("Demo Mills", "33MILLS0000A1Z1"), ("Oil Traders", "33OILTR0000B1Z2"), ("Pack Supplies", "29PACKS0000C1Z3")]: c.execute("insert into suppliers(name,gstin) values(?,?)", (s, g))
    c.commit()
if __name__ == "__main__":
    core.init(); c = core.conn(); seed(c); print("seeded", core.DB)
