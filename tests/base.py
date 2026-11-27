import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
os.environ.setdefault("DB_PATH", tempfile.mktemp(suffix=".db"))
import core, seed
def fresh():
    core.DB = tempfile.mktemp(suffix=".db"); core.init(); c = core.conn(); seed.seed(c); return c
def gid(c, n): return c.execute("select id from items where name=?", (n,)).fetchone()[0]
