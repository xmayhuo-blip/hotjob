#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hotjob local-parser：腾讯官方招聘 API → JSON(stdout)。"""
import os
import sys, json, ssl, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jd_splitter import split_jd

CTX = ssl.create_default_context()
if os.environ.get("HIRING_RADAR_INSECURE") == "1":
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

def fetch(keyword="", pages=6, size=100):
    out = []
    for p in range(1, pages + 1):
        q = urllib.parse.urlencode({"keyword": keyword, "pageIndex": p, "pageSize": size, "language": "zh-cn"})
        url = f"https://careers.tencent.com/tencentcareer/api/post/Query?{q}"
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25, context=CTX))
        posts = ((d.get("Data") or {}).get("Posts")) or []
        if not posts:
            break
        for j in posts:
            desc = j.get("Responsibility", "") or ""
            # Try multiple requirement field names
            req = (j.get("Requirement", "") or j.get("requirement", "")
                   or j.get("Qualifications", "") or j.get("qualifications", "")
                   or j.get("JobRequirement", "") or j.get("jobRequirement", "") or "")
            # If no separate requirement field, try splitting Responsibility text
            if not req.strip() and desc.strip():
                _d, _r = split_jd(desc)
                if _r.strip():
                    desc = _d
                    req = _r
            out.append({
                "title": j.get("RecruitPostName", ""),
                "company": "腾讯",
                "location": j.get("LocationName", ""),
                "dept": j.get("CategoryName", "") or j.get("BGName", ""),
                "date": j.get("LastUpdateTime", ""),
                "jd": "\n\n".join(x for x in [desc, req] if x),
                "responsibility": desc,
                "requirement": req,
                "url": j.get("PostURL", ""),
                "id": str(j.get("PostId", "")),
            })
        if len(posts) < size or len(out) >= ((d.get("Data") or {}).get("Count") or 0):
            break
    return out

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    print(json.dumps(fetch(kw, pg), ensure_ascii=False))
