#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hiring_radar local-parser：阿里巴巴官方招聘 API → JSON(stdout)。
用法: python3 alibaba.py [keyword] [pages] [domain]
  domain 默认 talent.alibaba.com（阿里巴巴集团）；可传 talent-holding.alibaba.com 等
原理：GET 页面提取 __token__ + XSRF-TOKEN cookie，再 POST /position/search。
纯标准库，无需 Playwright/Baxia 绕过。"""
import os
import sys
import json
import re
import ssl
import html as _html
import urllib.request
import http.cookiejar
from datetime import datetime, timezone

CTX = ssl.create_default_context()
if os.environ.get("HIRING_RADAR_INSECURE") == "1":
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _strip(s):
    if not s:
        return ""
    t = re.sub(r"(?i)<br\s*/?>", "\n", str(s))
    t = re.sub(r"(?i)</(p|li|div|h[1-6])>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", t).strip()


def _fmt_ts(ts):
    if not ts:
        return ""
    s = str(ts)
    if s.isdigit():
        v = int(s)
        if v > 1e12:
            v /= 1000
        try:
            return datetime.fromtimestamp(v, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return s
    return s


def _get_token_and_cookies(domain):
    """GET 页面，提取 __token__ 和 cookies。"""
    cj = http.cookiejar.CookieJar()
    https_handler = urllib.request.HTTPSHandler(context=CTX)
    opener = urllib.request.build_opener(https_handler, urllib.request.HTTPCookieProcessor(cj))
    url = f"https://{domain}/off-campus/position-list?lang=zh"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    resp = opener.open(req, timeout=25)
    html_text = resp.read().decode("utf-8", "replace")

    m = re.search(r'__token__\s*:\s*"([^"]+)"', html_text)
    token = m.group(1) if m else ""

    m2 = re.search(r'"portalOfficialChannel"\s*:\s*"([^"]+)"', html_text)
    channel = m2.group(1) if m2 else ""

    xsrf = ""
    for c in cj:
        if c.name == "XSRF-TOKEN":
            xsrf = c.value

    return token, xsrf, channel, opener


def fetch(keyword="", pages=1, size=500, domain="talent.alibaba.com"):
    token, xsrf, channel, opener = _get_token_and_cookies(domain)
    if not token:
        sys.stderr.write(f"[alibaba] 未能从 {domain} 提取 __token__，页面结构可能已变\n")
        return []

    out = []
    seen = set()
    for pg in range(1, pages + 1):
        body = json.dumps({
            "pageNo": pg,
            "pageSize": size,
            "channel": channel or "group_official_site",
            "language": "zh",
            "__token__": token,
            "keyword": keyword or "",
        }).encode()

        headers = {
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Referer": f"https://{domain}/off-campus/position-list?lang=zh",
            "Origin": f"https://{domain}",
            "X-XSRF-TOKEN": xsrf or token,
        }

        req = urllib.request.Request(
            f"https://{domain}/position/search",
            data=body, headers=headers
        )
        try:
            resp = opener.open(req, timeout=25)
            d = json.loads(resp.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            sys.stderr.write(f"[alibaba] HTTP {e.code} at page {pg}: {e.read().decode('utf-8','replace')[:200]}\n")
            break

        content = d.get("content") or {}
        datas = content.get("datas") or []
        total = content.get("totalCount", 0)

        if not datas:
            break

        for j in datas:
            jid = str(j.get("id", ""))
            if jid in seen:
                continue
            seen.add(jid)
            locs = j.get("workLocations") or []
            location = ", ".join(locs) if isinstance(locs, list) else str(locs)
            cats = j.get("categories") or []
            dept = ", ".join(cats) if isinstance(cats, list) else str(cats)
            jd = "\n\n".join(x for x in [
                _strip(j.get("description", "")),
                _strip(j.get("requirement", "")),
            ] if x)
            # Extract raw fields from API response for _normalize_local to find
            raw_url = j.get("url") or j.get("applyUrl") or j.get("apply_url") or j.get("link") or j.get("jobUrl") or j.get("job_url") or j.get("detailUrl") or j.get("postUrl") or j.get("href") or ""
            constructed_url = ""
            if not raw_url and jid and jid.isdigit() and jid != "0":
                # Holding: detail page works. Main: try multiple formats.
                if "holding" in domain:
                    constructed_url = f"https://{domain}/off-campus/position-detail?lang=zh&positionId={jid}"
                else:
                    # Main site: try positionId-first (original format), then off-campus, then direct
                    # Main Alibaba site has NO position-detail route in JS bundle
                    # (confirmed by JS analysis: only position-list routes exist)
                    constructed_url = f"https://{domain}/off-campus/position-list?lang=zh"
            
            out.append({
                "title": j.get("name", ""),
                "company": "阿里巴巴",
                "location": location,
                "dept": dept,
                "date": _fmt_ts(j.get("publishTime", "")),
                "date_updated": _fmt_ts(j.get("modifyTime", "")),
                "jd": jd,
                "responsibility": _strip(j.get("description", "")),
                "requirement": _strip(j.get("requirement", "")),
                "url": raw_url or constructed_url,
                "applyUrl": j.get("applyUrl") or "",
                "apply_url": j.get("apply_url") or "",
                "jobUrl": j.get("jobUrl") or j.get("job_url") or "",
                "detailUrl": j.get("detailUrl") or j.get("postUrl") or "",
                "link": j.get("link") or j.get("href") or "",
                "id": jid,
            })

        if len(datas) < size or pg * size >= total:
            break

    return out


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    dom = sys.argv[3] if len(sys.argv) > 3 else "talent.alibaba.com"
    if not re.fullmatch(r"[a-z0-9.\-]+", dom):
        sys.exit("[alibaba] domain 非法（防 SSRF）")
    print(json.dumps(fetch(kw, pg, domain=dom), ensure_ascii=False))
