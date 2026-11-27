"""Runs the section-5 scenario end to end through the same service layer the web app uses."""
import core
from decimal import Decimal as D
def run(c):
    R, g = {}, lambda n: c.execute("select id from items where name=?", (n,)).fetchone()[0]
    fl, oil, sp, po, ca, mu = (g(n) for n in ["Flour", "Cooking oil", "Salt and spice mix", "200 g pouch", "Carton (20 packets)", "Murukku 200 g"])
    core.purchase(c, "prod", fl, 60, 45, "Demo Mills", "B-001")                                              # 1
    rid = core.make_run(c, "prod", mu, 1, {fl: 40, oil: "10.5", sp: "1.2", po: 194, ca: 9}, good=188, damaged=6)  # 2-3
    R["run"] = rid; B = lambda i: core.Q(core.bal(c, i))
    R.update(flour=B(fl), oil=B(oil), spice=B(sp), pouches=B(po), cartons=B(ca), fg_after_run=B(mu))
    r = c.execute("select * from runs where id=?", (rid,)).fetchone(); R["yield_var"] = r["yield_var"]
    R["oil_var"] = c.execute("select var_pct from run_lines where run_id=? and item_id=?", (rid, oil)).fetchone()[0]
    oa = core.create_order(c, "salesA", 1, 1, [(mu, 150)]); core.approve(c, "admin", oa); ia = core.raise_invoice(c, "admin", oa); core.dispatch(c, "admin", ia)  # 4-5
    R["fg_after_dispatch"] = B(mu); inv = c.execute("select * from invoices where id=?", (ia,)).fetchone()
    R["invoice_A"] = (inv["no"], inv["taxable"], inv["cgst"], inv["sgst"], inv["igst"], inv["total"])
    ob = core.create_order(c, "salesB", 2, 2, [(mu, 120)])                                                    # 6
    R["B_shortage"] = [s["short"] for s in core.stock_check(c, ob)]
    try: core.approve(c, "admin", ob)
    except ValueError as e: R["B_blocked"] = str(e)
    R["B_igst_if_88"] = core.tax([(88 * 5000, 5)], True)
    core.pay(c, "admin", ia, 4000)                                                                           # 7
    R["outstanding_A"] = core.due(c, ia)
    core.add_overhead(c, "prod", rid, 1200, 600)                                                             # 8
    R["cost_per_packet"], R["margin"], R["margin_pct"] = core.cost_per_packet(c, rid)
    c.commit(); return R
if __name__ == "__main__":
    import seed; core.init(); c = core.conn(); seed.seed(c)
    for k, v in run(c).items(): print(f"{k:20} {v}")
