#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hiring_radar local-parser：字节跳动官方招聘 API → JSON(stdout)。
用法:  python3 bytedance.py [keyword] [pages]"""
import os
import sys
import json
import ssl
import urllib.request
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

def fetch(keyword="", pages=4, limit=30):
    out = []
    for p in range(pages):
        body = {
            "keyword": keyword, "limit": limit, "offset": p * limit,
            "job_category_id_list": [], "location_code_list": [],
            "subject_id_list": [], "recruitment_id_list": [],
        }
        req = urllib.request.Request(API, data=json.dumps(body).encode(), headers=HEAD)
        d = json.load(urllib.request.urlopen(req, timeout=25, context=CTX))
        posts = ((d.get("data") or {}).get("job_post_list")) or []
        if not posts:
            break
        for j in posts:
            jid = str(j.get("id", ""))
            city = (j.get("city_info") or {}).get("name", "")
            cat = j.get("job_category") or {}
            dept = cat.get("name", "") if isinstance(cat, dict) else ""
            jd = "\n\n".join(x for x in [j.get("description", ""), j.get("requirement", "")] if x)
            # Convert millisecond timestamp to formatted date
            pt = j.get("publish_time", "")
            if isinstance(pt, (int, float)) or (isinstance(pt, str) and pt.isdigit()):
                try:
                    ts = int(pt) / 1000 if int(pt) > 1e12 else int(pt)
                    pt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
                except Exception:
                    pass
            out.append({
                "title": j.get("title", ""),
                "company": "字节跳动",
                "location": city,
                "dept": dept,
                "date": pt,
                "jd": jd,
                "url": f"https://jobs.bytedance.com/experienced/position/{jid}/detail",
                "id": jid,
            })
        if len(posts) < limit:
            break
    return out

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    print(json.dumps(fetch(kw, pg), ensure_ascii=False))
