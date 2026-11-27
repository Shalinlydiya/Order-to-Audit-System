import unittest
from decimal import Decimal as D
from base import core, fresh, gid
import benchmark
class Benchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.R = benchmark.run(fresh())
    def test_stock(self):
        R = self.R; self.assertEqual((R["flour"], R["oil"], R["spice"], R["pouches"], R["cartons"]), ("120", "19.5", "3.8", "306", "21"))
        self.assertEqual((R["fg_after_run"], R["fg_after_dispatch"]), ("238", "88"))
    def test_variance(self): self.assertEqual((self.R["yield_var"], self.R["oil_var"]), ("-6.00", "5.00"))
    def test_invoice(self): self.assertEqual(self.R["invoice_A"][1:], (750000, 18750, 18750, 0, 787500))
    def test_outstanding_and_shortage(self):
        R = self.R; self.assertEqual((R["outstanding_A"], R["B_shortage"]), (387500, [32])); self.assertIn("short by 32", R["B_blocked"]); self.assertEqual(R["B_igst_if_88"], (440000, 0, 0, 22000))
    def test_cost(self): self.assertEqual(self.R["cost_per_packet"], D("3114.36"))
class Maths(unittest.TestCase):
    def test_units(self):
        self.assertEqual(core.conv(1200, "g", "kg"), D("1.2")); self.assertEqual(core.conv(2, "carton", "packet", 20), 40); self.assertEqual(core.conv(500, "ml", "l"), D("0.5")); self.assertEqual(core.conv(40, "packet", "carton", 20), 2)
        with self.assertRaises(ValueError): core.conv(1, "kg", "l")
    def test_tax_no_drift(self):
        self.assertEqual(core.tax([(333, 5), (333, 5)], False), (666, 17, 17, 0)); self.assertEqual(core.tax([(100, 5)], False), (100, 3, 2, 0)); self.assertEqual(core.tax([(100, 5)], True), (100, 0, 0, 5))
    def test_money_exact(self): self.assertEqual(core.P("0.1") + core.P("0.2"), core.P("0.3")); self.assertEqual(core.M("1.2"), 1200)
class Ledger(unittest.TestCase):
    def test_reconciles_and_traceable(self):
        c = fresh(); benchmark.run(c); h, rows = core.report(c, "stock_summary", *core.month_range())
        self.assertTrue(all(r[-1] == "OK" for r in rows))
        self.assertEqual(c.execute("select count(*) from ledger where ref_type!='opening' and (ref_id is null or ref_id=0)").fetchone()[0], 0)
if __name__ == "__main__": unittest.main()
