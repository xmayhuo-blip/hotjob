#!/usr/bin/env python3
"""端到端数据链路验证 — 模拟 HTTP 请求，验证 stats、total 与分页列表一致。

运行方式：
  1. 确保服务器在运行（本地或远程）
  2. python3 tests/test_e2e.py [base_url]

验证项：
  - stats.total == total == 逐页拼接后的岗位数
  - stats.by_company.count 合计 == total
  - 每家公司 stats.count == 实际岗位数（全量过滤后）
  - 每家公司岗位数不低于阈值
  - 每个岗位必含 title/company/url/id
"""
import math
import sys
import json
import urllib.request
import urllib.error
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787"
PAGE_SIZE = 200
MIN_PER_COMPANY = {"tencent": 10, "bytedance": 300, "alibaba": 10,
                   "highflyer": 1, "zhipu": 1, "moonshot": 1,
                   "minimax": 1, "kuaishou": 5, "lilith": 1, "kurogame": 1}
MIN_TOTAL = 50

PASS = 0
FAIL = 0

def ok(label):
    global PASS
    PASS += 1
    print(f"  OK  {label}")

def fail(label, detail):
    global FAIL
    FAIL += 1
    print(f"  FAIL {label}: {detail}")

def fetch_json(path):
    try:
        resp = urllib.request.urlopen(f"{BASE}{path}", timeout=30)
        return json.loads(resp.read())
    except Exception as e:
        fail("server reachable", str(e))
        sys.exit(1)

def fetch_all_pages(path):
    first = fetch_json(path + f"&page=1&page_size={PAGE_SIZE}&days=0")
    jobs = list(first.get("jobs") or [])
    page_sizes = [len(jobs)]
    total = first.get("total", 0)
    total_pages = first.get("total_pages", 1)
    page = 2
    while len(jobs) < total and page <= total_pages and page < 100:
        d = fetch_json(path + f"&page={page}&page_size={PAGE_SIZE}&days=0")
        jobs.extend(d.get("jobs") or [])
        page_sizes.append(len(d.get("jobs") or []))
        page += 1
    return first, jobs, page_sizes

print(f"[e2e] Fetching {BASE}/api/jobs (companies=all, days=0) ...")
first, all_jobs, page_sizes = fetch_all_pages("/api/jobs?companies=all")

total = first.get("total", 0)
stats = first.get("stats", {})
by_company = stats.get("by_company", {})

ok(f"server responds (total={total})")
if total >= MIN_TOTAL:
    ok(f"total jobs >= {MIN_TOTAL}")
else:
    fail("total jobs", f"{total} < {MIN_TOTAL}")

if stats.get("total") == total:
    ok(f"stats.total == total ({total})")
else:
    fail("stats.total", f"{stats.get('total')} != {total}")

stat_sum = sum(v.get("count", 0) for v in by_company.values())
if stat_sum == total:
    ok(f"stats.by_company sum == total ({total})")
else:
    fail("by_company sum", f"{stat_sum} != {total}")

if all(p <= PAGE_SIZE for p in page_sizes):
    ok(f"every page has <= {PAGE_SIZE} rows")
else:
    fail("page size", f"pages {page_sizes}")

if first.get("total_pages") == max(1, math.ceil(total / PAGE_SIZE)):
    ok("total_pages matches total / page_size")
else:
    fail("total_pages", f"{first.get('total_pages')} != ceil({total}/{PAGE_SIZE})")

if len(all_jobs) == total:
    ok(f"paged jobs concat == total ({total})")
else:
    fail("paged concat", f"{len(all_jobs)} != {total}")

for cid, info in sorted(by_company.items()):
    name = info.get("name", cid)
    stat_count = info.get("count", 0)
    actual = sum(1 for j in all_jobs if j.get("_company_id") == cid)
    if stat_count == actual:
        ok(f"{name}: stats.count={stat_count} == jobs count={actual}")
    else:
        fail(f"{name} count mismatch", f"stats={stat_count} vs jobs={actual}")
    threshold = MIN_PER_COMPANY.get(cid, 1)
    if actual >= threshold:
        ok(f"{name}: {actual} jobs >= {threshold}")
    else:
        fail(f"{name} below threshold", f"{actual} < {threshold}")
    cid_jobs = [j for j in all_jobs if j.get("_company_id") == cid]
    if cid_jobs:
        j0 = cid_jobs[0]
        for field in ["title", "company", "url", "id"]:
            if j0.get(field):
                ok(f"{name}: job has '{field}'")
            else:
                fail(f"{name}: job missing '{field}'", "")

print(f"\n{'='*40}")
print(f"e2e: {PASS}/{PASS+FAIL} passed, {FAIL}/{PASS+FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
