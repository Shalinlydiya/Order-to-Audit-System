import unittest, json, datetime as dt
from decimal import Decimal as D
from base import core, fresh, gid
import benchmark
def setup():
    c = fresh(); R = benchmark.run(c); return c, R, gid(c, "Murukku 200 g"), gid(c, "Flour")
class Features(unittest.TestCase):
    def test_batches_fefo_expiry(self):
        c, R, mu, fl = setup(); b = {x["batch"]: x for x in core.batches(c, mu)}
        self.assertEqual(core.Q(sum(x["q"] for x in b.values())), "88"); self.assertTrue(any(k.startswith("B") and v["expiry"] for k, v in b.items()))
        self.assertNotIn("OPENING", b)   # opening stock (unknown expiry) is dispatched first
    def test_partial_dispatch_and_return(self):
        c, R, mu, fl = setup(); o = core.create_order(c, "s", 1, 1, [(mu, 80)]); core.approve(c, "a", o); i = core.raise_invoice(c, "a", o)
        lid = c.execute("select id from invoice_lines where invoice_id=?", (i,)).fetchone()[0]
        core.dispatch(c, "a", i, {lid: 30}); self.assertEqual(c.execute("select dispatched from invoices where id=?", (i,)).fetchone()[0], 1); self.assertEqual(core.Q(core.bal(c, mu)), "58")
        core.dispatch(c, "a", i); self.assertEqual(c.execute("select status from orders where id=?", (o,)).fetchone()[0], "dispatched")
        before = core.due(c, i); core.return_goods(c, "a", i, {lid: 10}); self.assertEqual(core.Q(core.bal(c, mu)), "18")
        self.assertEqual(before - core.due(c, i), 10 * 5000 * 105 // 100)
        with self.assertRaises(ValueError): core.return_goods(c, "a", i, {lid: 999})
        g = core.report(c, "gstr3b", *core.month_range())[1]; self.assertEqual(g[1][1], core.rs(50000))
    def test_cancel_credit_note_restocks(self):
        c, R, mu, fl = setup(); inv = c.execute("select id from invoices").fetchone()[0]
        with self.assertRaises(ValueError): core.cancel_invoice(c, "a", inv, "x")   # has a payment
        o = core.create_order(c, "s", 1, 1, [(mu, 10)]); core.approve(c, "a", o); i = core.raise_invoice(c, "a", o); core.dispatch(c, "a", i); self.assertEqual(core.Q(core.bal(c, mu)), "78")
        core.cancel_invoice(c, "a", i, "wrong"); self.assertEqual(core.Q(core.bal(c, mu)), "88"); self.assertEqual(c.execute("select status from invoices where id=?", (i,)).fetchone()[0], "cancelled")
        self.assertEqual(c.execute("select count(*) from credit_notes").fetchone()[0], 1)
    def test_adjustment_and_low_stock(self):
        c, R, mu, fl = setup(); core.adjust(c, "p", fl, "-100", "spillage"); self.assertEqual(core.Q(core.bal(c, fl)), "20")
        self.assertIn("Flour", [x[0] for x in core.low_stock(c)])
        with self.assertRaises(ValueError): core.adjust(c, "p", fl, "-1", "")
        with self.assertRaises(ValueError): core.adjust(c, "p", fl, "-1000", "too much")
    def test_edit_run_logged(self):
        c, R, mu, fl = setup(); core.edit_run(c, "p", R["run"], {fl: 41}, 190, 6)
        self.assertEqual(core.Q(core.bal(c, fl)), "119"); self.assertEqual(core.Q(core.bal(c, mu)), "90")
        self.assertIn("Flour 40->41", c.execute("select detail from audit where action='edit' and entity='production_run'").fetchone()[0])
    def test_monthly_overhead_allocation(self):
        c, R, mu, fl = setup(); core.add_monthly_overhead(c, "p", core.today()[:7], "rent", 1000)
        row = core.costing_rows(c, *core.month_range())[0]; self.assertEqual(row[5], "1,000.00"); self.assertEqual(row[7], core.rs(D(585500 + 100000) / 188))
    def test_offline_idempotent_and_customer_price(self):
        c, R, mu, fl = setup(); c.execute("insert into customer_prices values(1,?,4500)", (mu,))
        a = core.create_order(c, "s", 1, 1, [(mu, 5)], "uuid-1"); b = core.create_order(c, "s", 1, 1, [(mu, 5)], "uuid-1"); self.assertEqual(a, b)
        self.assertEqual(c.execute("select price from order_lines where order_id=?", (a,)).fetchone()[0], 4500)
    def test_planning(self):
        c, R, mu, fl = setup(); fg, raw = core.plan(c)  # benchmark left Distributor B 120 pending; self.assertEqual(fg[0][1:], [120, 88, 0, 32, 1]); self.assertTrue(raw)
    def test_exports(self):
        c, R, mu, fl = setup(); x = core.tally_xml(c, *core.month_range()); self.assertIn("<VOUCHER VCHTYPE=\"Sales\"", x); self.assertIn("Output CGST", x)
        inv = c.execute("select id from invoices").fetchone()[0]; e = core.einvoice(c, inv); self.assertEqual(len(e["Irn"]), 64); self.assertEqual(e["ValDtls"]["TotInvVal"], "7,875.00"); self.assertEqual(core.ewaybill(c, inv)["docNo"], e["DocDtls"]["No"])
        for n in core.REPORTS: core.report(c, n, *core.month_range())   # every report runs
if __name__ == "__main__": unittest.main()
class Wip(unittest.TestCase):
    def test_two_stage_run(self):
        c = fresh(); mu, fl = gid(c, "Murukku 200 g"), gid(c, "Flour"); rid = core.start_run(c, "p", mu, 1, {})
        w = gid(c, "WIP – Murukku 200 g"); self.assertEqual((core.Q(core.bal(c, fl)), core.Q(core.bal(c, mu)), core.Q(core.bal(c, w))), ("60", "50", "1"))
        self.assertEqual(core.plan(c)[0][0][3], 200)                      # open batch counts as expected supply
        with self.assertRaises(ValueError): core.edit_run(c, "p", rid, {}, 10)
        core.complete_run(c, "p", rid, 190, 4); self.assertEqual((core.Q(core.bal(c, mu)), core.Q(core.bal(c, w))), ("240", "0"))
        with self.assertRaises(ValueError): core.complete_run(c, "p", rid, 1)
        self.assertTrue(all(r[-1] == "OK" for r in core.report(c, "stock_summary", *core.month_range())[1]))
class GstPurchase(unittest.TestCase):
    def test_itc_in_gstr3b(self):
        c = fresh(); fl = gid(c, "Flour"); core.purchase(c, "p", fl, 100, 10, "Demo Mills", "B1", gst_rate=5)       # 1,000 + 50 GST, intra-state supplier
        core.purchase(c, "p", fl, 100, 10, "Pack Supplies", "B2", gst_rate=5)                                         # Karnataka supplier -> IGST
        rows = core.report(c, "gstr3b", *core.month_range())[1]; itc = [r for r in rows if r[0].startswith("4(A)")][0]
        self.assertEqual(itc[1:], ["2,000.00", "50.00", "25.00", "25.00"]); self.assertIn("Input GST", core.tally_xml(c, *core.month_range()))

class InterState(unittest.TestCase):
    def test_hsn_and_split_igst_only(self):
        c = fresh(); mu = gid(c, "Murukku 200 g"); core.make_run(c, "p", mu, 1, {}, 200)
        o = core.create_order(c, "s", 2, 2, [(mu, 100)]); core.approve(c, "a", o); core.raise_invoice(c, "a", o)
        row = core.report(c, "gstr1_hsn", *core.month_range())[1][0]; self.assertEqual(row[4:7], ["250.00", "0.00", "0.00"])   # IGST 5% of 5,000; no CGST/SGST
        self.assertEqual(core._split(50, True), (0, 0, 50)); self.assertEqual(core._split(51, False), (26, 25, 0))
