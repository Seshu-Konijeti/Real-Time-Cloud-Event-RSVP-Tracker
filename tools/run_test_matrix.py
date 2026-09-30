"""Run pytest and generate docs/test_matrix.md with REAL results.  Usage: python tools/run_test_matrix.py"""
import os, sys, re, importlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests")); sys.path.insert(0, os.path.join(ROOT, "backend")); sys.path.insert(0, ROOT)
import pytest

class Rec:
    def __init__(self): self.r = {}
    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.failed):
            self.r[report.nodeid.split("::")[-1]] = report

rec = Rec()
pytest.main(["-q", "-W", "ignore", "-p", "no:cacheprovider", os.path.join(ROOT, "tests")], plugins=[rec])
mod = importlib.import_module("test_app")
rows = ["| Test ID | Scenario | Input | Expected Result | Actual Result | Pass/Fail |", "|---|---|---|---|---|---|"]
for name in sorted(rec.r):
    m = re.match(r"test_(T\d+|X)_", name)
    if not m: continue
    doc = [d.strip() for d in (getattr(mod, name).__doc__ or "").split("|")] + ["", "", ""]
    ok = rec.r[name].passed
    tid = m.group(1) if m.group(1) != "X" else "EXTRA"
    rows.append(f"| {tid} | {doc[0] or name} | {doc[1]} | {doc[2]} | {'As expected' if ok else 'Mismatch'} | {'PASS' if ok else 'FAIL'} |")
open(os.path.join(ROOT, "docs", "test_matrix.md"), "w").write("# Test Matrix (generated from a real pytest run)\n\n" + "\n".join(rows) + "\n")
print(len(rows) - 2, "rows written")
