#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hiring_radar local-parser：小红书官方招聘 API → JSON(stdout)。
用法: python3 xiaohongshu.py [keyword] [pages]
无需 x-s 签名，直接 POST /websiterecruit/position/pageQueryPosition 即可。"""
import os
import sys
import json
import ssl
import urllib.request

CTX = ssl.create_default_context()
if os.environ.get("HIRING_RADAR_INSECURE") == "1":
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE

API = "https://job.xiaohongshu.com/websiterecruit/position/pageQueryPosition"
HEAD = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Referer": "https://job.xiaohongshu.com/social",
    "Origin": "https://job.xiaohongshu.com",
}


def fetch(keyword="", pages=9, size=100, recruit_type="social"):
    out = []
    for pg in range(1, pages + 1):
        body = json.dumps({
            "pageNo": pg,
            "pageSize": size,
            "recruitType": recruit_type,
            "keyword": keyword or "",
        }).encode()
        req = urllib.request.Request(API, data=body, headers=HEAD)
        d = json.load(urllib.request.urlopen(req, timeout=25, context=CTX))
        data = d.get("data") or {}
        items = data.get("list") or []
        if not items:
            break
        for j in items:
            pid = str(j.get("positionId", ""))
            duty = j.get("duty", "")
            qual = j.get("qualification", "")
            jd = "\n\n".join(x for x in [duty, qual] if x)
            out.append({
                "title": j.get("positionName", ""),
                "company": "小红书",
                "location": j.get("workplace", ""),
                "dept": j.get("jobType", ""),
                "date": j.get("publishTime", ""),
                "jd": jd,
                "url": f"https://job.xiaohongshu.com/{recruit_type}/position/{pid}" if pid else "",
                "id": pid,
            })
        total = data.get("total", 0)
        if len(items) < size or pg * size >= total:
            break
    return out


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    print(json.dumps(fetch(kw, pg), ensure_ascii=False))
