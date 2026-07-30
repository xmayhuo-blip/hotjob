#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hotjob local-parser: 字节跳动官方招聘 API -> JSON(stdout).
默认 pages=20(600条)，并发抓取保持 <=8s。"""
import os
import sys
import json
import ssl
import urllib.request
import concurrent.futures
from datetime import datetime, timezone

CTX = ssl.create_default_context()
if os.environ.get("HIRING_RADAR_INSECURE") == "1":
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE
API = "https://jobs.bytedance.com/api/v1/search/job/posts"
HEAD = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Content-Type": "application/json",
    "portal-channel": "office",
    "portal-platform": "pc",
}

def _fetch_page(page, keyword, limit):
    """Fetch a single page. Returns list of jobs or empty on failure."""
    try:
        body = {
            "keyword": keyword, "limit": limit, "offset": page * limit,
            "job_category_id_list": [], "location_code_list": [],
            "subject_id_list": [], "recruitment_id_list": [],
        }
        req = urllib.request.Request(API, data=json.dumps(body).encode(), headers=HEAD)
        d = json.load(urllib.request.urlopen(req, timeout=25, context=CTX))
        posts = ((d.get("data") or {}).get("job_post_list")) or []
        out = []
        for j in posts:
            jid = str(j.get("id", ""))
            city = (j.get("city_info") or {}).get("name", "")
            cat = j.get("job_category") or {}
            dept = cat.get("name", "") if isinstance(cat, dict) else ""
            desc = j.get("description", "")
            req_text = j.get("requirement", "")
            jd = "\n\n".join(x for x in [desc, req_text] if x)
            pt = j.get("publish_time", "")
            if isinstance(pt, (int, float)) or (isinstance(pt, str) and pt.isdigit()):
                try:
                    ts = int(pt) / 1000 if int(pt) > 1e12 else int(pt)
                    pt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass
            out.append({
                "title": j.get("title", ""),
                "company": "\u5b57\u8282\u8df3\u52a8",
                "location": city,
                "dept": dept,
                "date": pt,
                "jd": jd,
                "responsibility": desc,
                "requirement": req_text,
                "url": f"https://jobs.bytedance.com/experienced/position/{jid}/detail",
                "id": jid,
            })
        return out
    except Exception as e:
        sys.stderr.write(f"[bytedance] page {page} failed: {e}\n")
        return []

def fetch(keyword="", pages=20, limit=30):
    out = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(_fetch_page, p, keyword, limit) for p in range(pages)]
        for f in concurrent.futures.as_completed(futures):
            out.extend(f.result())
    out.sort(key=lambda x: x.get("date", ""), reverse=True)
    seen = set()
    deduped = []
    for j in out:
        jid = j.get("id", "")
        if jid and jid not in seen:
            seen.add(jid)
            deduped.append(j)
    return deduped

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 20
    print(json.dumps(fetch(kw, pg), ensure_ascii=False))
