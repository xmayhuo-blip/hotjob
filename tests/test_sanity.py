#!/usr/bin/env python3
"""Business sanity tests — verifies live data against realistic expectations.

Run: HIRING_RADAR_INSECURE=1 python3 tests/test_sanity.py
"""
import sys, os, re
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parsers import loader

def _parse_date(s):
    if not s or s == "\u672a\u77e5": return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y\u5e74%m\u6708%d\u65e5"):
        try: return datetime.strptime(s.strip(), fmt)
        except: pass
    return None

PASS, FAIL, ERRS = 0, 0, []
def check(label, cond, detail=""):
    global PASS, FAIL
    if cond: PASS += 1
    else: FAIL += 1; print(f"  FAIL: {label}" + (f"  ({detail})" if detail else "")); ERRS.append(label)
def check_gt(label, got, mn):
    return check(label, got > mn, f"got={got}, min={mn}")

MIN_JOBS = {"tencent": 100, "bytedance": 300, "alibaba": 50, "highflyer": 1, "zhipu": 1,
            "moonshot": 1, "minimax": 1, "kuaishou": 10, "lilith": 1, "kurogame": 1}

print("Business sanity test: verifying job counts against live ATS APIs")
for cid, mn in MIN_JOBS.items():
    try:
        jobs = loader.fetch_company(cid)
        check_gt(f"{cid} job count", len(jobs), mn)
        if jobs:
            j = jobs[0]
            check(f"{cid} title", bool(j.get("title")))
            check(f"{cid} company", bool(j.get("company")))
            check(f"{cid} url", bool(j.get("url")))
            check(f"{cid} id", bool(j.get("id")))
    except Exception as e:
        check(f"{cid} no exception", False, str(e)[:80])

print()
print("Date parseability (>50% of dates should parse)")
for cid in MIN_JOBS:
    jobs = loader.fetch_company(cid)
    if not jobs: continue
    ok = sum(1 for j in jobs if j.get("date") and _parse_date(j["date"]))
    check(f"{cid} date parseability", ok / len(jobs) > 0.5, f"{ok}/{len(jobs)}")

total = PASS + FAIL
print(f"\n{PASS}/{total} passed, {FAIL}/{total} failed")
sys.exit(0 if FAIL == 0 else 1)
