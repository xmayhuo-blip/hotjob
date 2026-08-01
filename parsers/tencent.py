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

def fetch(keyword="", pages=6, size=100, recruit_type="social"):
    """Fetch Tencent jobs. recruit_type: 'social' or 'campus'."""
    out = []
    # Try to fetch both social and campus when recruit_type='all'
    types_to_fetch = ["social", "campus"] if recruit_type == "all" else [recruit_type]
    for rtype in types_to_fetch:
        for p in range(1, pages + 1):
            params = {"keyword": keyword, "pageIndex": p, "pageSize": size, "language": "zh-cn"}
            if rtype == "campus":
                params["recruitType"] = "2"
                params["campus"] = "1"
            q = urllib.parse.urlencode(params)
            url = f"https://careers.tencent.com/tencentcareer/api/post/Query?{q}"
            try:
                d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25, context=CTX))
            except Exception:
                continue
            posts = ((d.get("Data") or {}).get("Posts")) or []
            if not posts:
                break
            for j in posts:
                desc = j.get("Responsibility", "") or ""
                # Try multiple requirement field names
                req = (j.get("Requirement", "") or j.get("requirement", "")
                       or j.get("Qualifications", "") or j.get("qualifications", "")
                       or j.get("JobRequirement", "") or j.get("jobRequirement", "") or "")
                # Detect recruit type from response
                j_rt = str(j.get("RecruitType", "") or j.get("recruitType", "") or "")
                if rtype == "campus" or "校" in j_rt or "campus" in j_rt.lower():
                    j_type = "校招"
                else:
                    j_type = "社招"
                # If no separate requirement field, try splitting Responsibility text
                if not req.strip() and desc.strip():
                    _d, _r = split_jd(desc)
                    if _r.strip():
                        desc = _d
                        req = _r
                out.append({
                    "title": j.get("RecruitPostName", ""),
                    "company": "腾讯",
                    "type": j_type,
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

def fetch_detail(post_id, language="zh-cn"):
    """Fetch full job detail via Tencent ByPostId API."""
    import time as _t
    detail_headers = {
        **UA,
        "Referer": "https://careers.tencent.com/jobdesc.html",
        "Accept": "application/json, text/plain, */*",
    }
    url = (f"https://careers.tencent.com/tencentcareer/api/post/ByPostId"
           f"?timestamp={int(_t.time())}&postId={post_id}&language={language}")
    try:
        d = json.load(urllib.request.urlopen(
            urllib.request.Request(url, headers=detail_headers), timeout=15, context=CTX))
        data = d.get("Data") or {}
        desc = data.get("Responsibility", "") or ""
        req = (data.get("Requirement", "") or data.get("requirement", "")
               or data.get("Qualifications", "") or data.get("qualifications", "") or "")
        if desc or req:
            return {
                "title": data.get("RecruitPostName", "") or data.get("PostName", ""),
                "location": data.get("LocationName", ""),
                "dept": data.get("CategoryName", "") or data.get("BGName", ""),
                "date": data.get("LastUpdateTime", ""),
                "jd": "\n\n".join(x for x in [desc, req] if x),
                "responsibility": desc,
                "requirement": req,
                "url": data.get("PostURL", ""),
                "id": str(post_id),
            }
    except Exception as _e:
        sys.stderr.write(f"[tencent] detail API error: {_e}\n")
    return None

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    print(json.dumps(fetch(kw, pg), ensure_ascii=False))
