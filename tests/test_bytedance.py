#!/usr/bin/env python3
"""Byedance parser unit checks without live network.

Run: python3 tests/test_bytedance.py
"""
import os
import sys
import time
import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parsers import bytedance

PASS = 0
FAIL = 0

def check(label, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label} {detail}")

def fake_job(jid, days_ago):
    ts = int(time.time() * 1000) - days_ago * 86400 * 1000
    return {
        "id": jid,
        "title": f"job-{jid}",
        "company": "字节跳动",
        "location": "北京",
        "dept": "研发",
        "date": datetime.datetime.fromtimestamp(ts / 1000, tz=datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "jd": "",
        "url": f"https://jobs.bytedance.com/experienced/position/{jid}/detail",
        "_publish_ts": ts,
    }

def fake_ok(page, keyword, limit):
    if page == 0:
        posts = [fake_job("a", 10), fake_job("b", 30), fake_job("old1", 300)]
    else:
        posts = [fake_job("c", 20), fake_job("a", 10), fake_job("old2", 400)]
    return posts, 500, None

orig = bytedance._fetch_page_raw
bytedance._fetch_page_raw = fake_ok
jobs, meta = bytedance.fetch_with_meta(scan_limit=400, max_age_days=200)
bytedance._fetch_page_raw = orig

check("success meta ok", meta.get("ok") is True, str(meta))
check("scanned == 6 posts", meta.get("scanned") == 6, str(meta))
check("kept == 3 recent unique", meta.get("kept") == 3, f"jobs={[j['id'] for j in jobs]}")
check("all kept ids unique", len({j["id"] for j in jobs}) == len(jobs), str([j["id"] for j in jobs]))
check("sorted desc by date", jobs == sorted(jobs, key=lambda j: j.get("date", ""), reverse=True))
check("no _publish_ts leak", all("_publish_ts" not in j for j in jobs))

def fake_partial_fail(page, keyword, limit):
    if page == 1:
        return [], 500, "boom"
    return fake_ok(page, keyword, limit)

bytedance._fetch_page_raw = fake_partial_fail
partial_jobs, partial_meta = bytedance.fetch_with_meta(scan_limit=400, max_age_days=200)
check("partial fetch ok False", partial_meta.get("ok") is False, str(partial_meta))
check("partial fetch returns empty jobs", partial_jobs == [], str(partial_jobs))
check("page_failures counted", partial_meta.get("page_failures") == 1, str(partial_meta))

print(f"\ntest_bytedance: {PASS}/{PASS+FAIL} passed, {FAIL}/{PASS+FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
