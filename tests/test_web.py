import unittest, json, io
from base import core, fresh, gid
import benchmark
class Web(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c = fresh(); benchmark.run(c); c.close()
        import app; cls.app = app.app
    def cl(self, u):
        x = self.app.test_client(); x.post("/login", data={"u": u, "p": "demo123"}); return x
    def test_pages_by_role(self):
        pages = {"admin": ["/orders", "/orders/1", "/invoices/1", "/invoices/1/pdf", "/invoices/1/einvoice.json", "/invoices/1/ewaybill.json", "/masters", "/planning", "/adjustments", "/export/tally.xml"] + ["/reports/" + r for r in core.REPORTS],
                 "prod": ["/production", "/production?product=6", "/production/1", "/production/1/edit", "/purchases", "/adjustments", "/masters", "/planning", "/reports/stock_batches"],
                 "owner": ["/dashboard", "/production/1", "/planning"], "salesA": ["/orders/new", "/orders", "/visits"], "auditor": ["/reports", "/reports/audit_log", "/invoices/1/pdf", "/export/tally.xml"]}
        for u, ps in pages.items():
            x = self.cl(u)
            for p in ps: self.assertEqual(x.get(p).status_code, 200, (u, p))
    def test_exports_formats(self):
        x = self.cl("admin")
        for f, mt in [("csv", "text/csv"), ("xlsx", "spreadsheet"), ("pdf", "application/pdf")]:
            r = x.get(f"/reports/sales_register?fmt={f}"); self.assertEqual(r.status_code, 200); self.assertIn(mt, r.content_type)
        self.assertTrue(x.get("/reports/stock_summary?fmt=pdf").data.startswith(b"%PDF"))
    def test_html_not_escaped(self):
        a = self.cl("admin")
        for p in ["/invoices/1", "/masters", "/planning", "/orders/2"]: self.assertNotIn("&lt;", a.get(p).get_data(as_text=True), p)
        p = self.cl("prod"); self.assertNotIn("&lt;", p.get("/production/1").get_data(as_text=True))
    def test_rbac(self):
        self.assertEqual(self.cl("salesA").get("/reports").status_code, 403); self.assertEqual(self.cl("salesA").get("/masters").status_code, 403)
        self.assertEqual(self.cl("auditor").post("/production", data={}).status_code, 403); self.assertEqual(self.cl("prod").get("/reports/sales_register").status_code, 404)
        self.assertEqual(self.cl("prod").post("/masters/user_add", data={"un": "x", "pw": "123456", "name": "x", "role": "admin"}).status_code, 403)
        self.assertEqual(self.app.test_client().get("/orders").status_code, 302)
    def test_offline_api(self):
        x = self.cl("salesA"); d = {"client_id": "abc-1", "cust": 1, "lines": [[6, 3]]}
        a = x.post("/api/orders", json=d).get_json(); b = x.post("/api/orders", json=d).get_json(); self.assertTrue(a["ok"]); self.assertEqual(a["order_id"], b["order_id"])
        self.assertEqual(x.post("/api/orders", json={"cust": 1, "lines": []}).status_code, 400); self.assertEqual(self.app.test_client().post("/api/orders", json=d).status_code, 401)
        self.assertEqual(x.get("/sw.js").status_code, 200)
    def test_order_flow_ui(self):
        s, a = self.cl("salesA"), self.cl("admin"); s.post("/orders/new", data={"cust": "1", "q_6": "10"})
        oid = core.conn().execute("select max(id) from orders").fetchone()[0]
        a.post(f"/orders/{oid}", data={"a": "approve", "q_6": "10", "p_6": "50"}); r = a.post(f"/orders/{oid}", data={"a": "invoice"}); self.assertEqual(r.status_code, 302)
        iid = int(r.headers["Location"].rsplit("/", 1)[1]); a.post(f"/invoices/{iid}", data={"a": "dispatch"}); self.assertIn("dispatched", a.get(f"/invoices/{iid}").get_data(as_text=True))
    def test_masters_and_tamil(self):
        a = self.cl("admin"); a.post("/masters/item_add", data={"name": "Mixture 200 g", "kind": "fg", "unit": "packet", "hsn": "19059090", "price": "55", "gst": "5", "yield": "100", "carton": "20", "shelf": "60", "reorder": "0"})
        self.assertIn("Mixture 200 g", a.get("/masters").get_data(as_text=True))
        p = self.cl("prod"); p.get("/lang/ta"); self.assertIn("உற்பத்தி", p.get("/production").get_data(as_text=True))
        for u, paths, words in [("salesA", ["/orders/new", "/orders", "/visits"], ["புதிய ஆர்டர்", "சமர்ப்பி"]), ("admin", ["/orders/2", "/invoices/1", "/masters", "/planning"], ["அங்கீகரி", "விலைப்பட்டியல்", "பொருட்கள்", "தேவை"]), ("owner", ["/dashboard"], ["முகப்பு"])]:
            x = self.cl(u); x.get("/lang/ta"); html = "".join(x.get(q).get_data(as_text=True) for q in paths)
            for w in words: self.assertIn(w, html, (u, w))
    def test_wip_ui(self):
        p = self.cl("prod"); r = p.post("/production", data={"pid": "6", "batches": "1", "mode": "start"}); rid = int(r.headers["Location"].rsplit("/", 1)[1])
        self.assertIn("In progress", p.get(f"/production/{rid}").get_data(as_text=True)); p.post(f"/production/{rid}", data={"a": "complete", "good": "199", "damaged": "1"})
        self.assertNotIn("In progress", p.get(f"/production/{rid}").get_data(as_text=True)); self.assertEqual(p.get(f"/production/{rid}/edit").status_code, 200)
if __name__ == "__main__": unittest.main()
