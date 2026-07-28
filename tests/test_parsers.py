#!/usr/bin/env python3
"""Parser schema validation tests (runs live for tencent + kuaishou)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from parsers import loader
REQ = {"title", "company", "location", "dept", "date", "jd", "url", "id"}
PASS = 0; FAIL = 0
def check(label, cond):
    global PASS, FAIL
    if cond: PASS += 1
    else: FAIL += 1; print(f"  FAIL: {label}")
print("[test] loader config"); check("10 companies", len(loader.PARSER_CONFIG) == 10)
for cid in ["tencent", "kuaishou"]:
    jobs = loader.fetch_company(cid)
    if jobs:
        j = jobs[0]
        for f in REQ: check(f"{cid}: has {f}", f in j)
        check(f"{cid}: title", bool(j.get("title")))
    else:
        print(f"  SKIP {cid}: 0 jobs")
total = PASS + FAIL
print(f"\nResults: {PASS}/{total} passed, {FAIL}/{total} failed")
sys.exit(0 if FAIL == 0 else 1)
