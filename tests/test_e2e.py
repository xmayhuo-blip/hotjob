#!/usr/bin/env python3
"""端到端数据链路验证 — 模拟 HTTP 请求，验证 stats 与 jobs 一致。

运行方式：
  1. 确保服务器在运行（本地或远程）
  2. python3 tests/test_e2e.py [base_url]

  默认 base_url=http://localhost:8787，可传自定义地址。

验证项：
  - 每家公司 stats.count == jobs 数组长度（去重一致性）
  - 每家公司岗位数不低于阈值（数据真实性）
  - 每个岗位必含 title/company/url/id
  - 总岗位数合理（防御 parser 整体降级）
"""
import sys, os, json, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787"
MIN_PER_COMPANY = {"tencent": 10, "bytedance": 500, "alibaba": 10,
                   "highflyer": 1, "zhipu": 1, "moonshot": 1,
                   "minimax": 1, "kuaishou": 5, "lilith": 1, "kurogame": 1}
MIN_TOTAL = 50

PASS = 0; FAIL = 0
def ok(label):
    global PASS; PASS += 1; print(f"  OK  {label}")
def fail(label, detail):
    global FAIL; FAIL += 1; print(f"  FAIL {label}: {detail}")

# Step 1: fetch /api/jobs
print(f"[e2e] Fetching {BASE}/api/jobs ...")
try:
    resp = urllib.request.urlopen(f"{BASE}/api/jobs", timeout=30)
    data = json.loads(resp.read())
except Exception as e:
    fail("server reachable", str(e))
    sys.exit(1)

total = data.get("total", 0)
stats = data.get("stats", {}).get("by_company", {})
jobs = data.get("jobs", [])

# Step 2: verify total
ok(f"server responds (total={total})")
if total >= MIN_TOTAL:
    ok(f"total jobs >= {MIN_TOTAL}")
else:
    fail("total jobs", f"{total} < {MIN_TOTAL}")

# Step 3: per-company checks
for cid, info in sorted(stats.items()):
    name = info.get("name", cid)
    stat_count = info.get("count", 0)
    deduped = sum(1 for j in jobs if j.get("_company_id") == cid)
    
    # 3a: stats.count matches actual job count
    if stat_count == deduped:
        ok(f"{name}: stats.count={stat_count} == jobs count={deduped}")
    else:
        fail(f"{name} count mismatch", f"stats={stat_count} vs jobs={deduped}")
    
    # 3b: minimum threshold
    threshold = MIN_PER_COMPANY.get(cid, 1)
    if deduped >= threshold:
        ok(f"{name}: {deduped} jobs >= {threshold}")
    else:
        fail(f"{name} below threshold", f"{deduped} < {threshold}")
    
    # 3c: required fields on first job
    cid_jobs = [j for j in jobs if j.get("_company_id") == cid]
    if cid_jobs:
        j0 = cid_jobs[0]
        for field in ["title", "company", "url", "id"]:
            if j0.get(field):
                ok(f"{name}: job has '{field}'")
            else:
                fail(f"{name}: job missing '{field}'", "")

print(f"\n{'='*40}")
print(f"e2e: {PASS}/{PASS+FAIL} passed, {FAIL}/{FAIL+FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
