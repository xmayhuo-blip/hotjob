#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hotjob local-parser: 字节跳动官方招聘 API -> JSON(stdout).
默认扫描前 1000 条，只保留 publish_time 近 200 日的岗位。"""
import os
import sys
import json
import ssl
import urllib.request
import concurrent.futures
import math
import time
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

BYTEDANCE_SCAN_LIMIT = 1000
BYTEDANCE_PAGE_LIMIT = 200
BYTEDANCE_MAX_AGE_DAYS = 200
BYTEDANCE_MAX_WORKERS = 3


def _fetch_page_raw(page, keyword, limit):
    """Fetch one page. Returns (jobs, total_count, error)."""
    try:
        body = {
            "keyword": keyword, "limit": limit, "offset": page * limit,
            "job_category_id_list": [], "location_code_list": [],
            "subject_id_list": [], "recruitment_id_list": [],
        }
        req = urllib.request.Request(API, data=json.dumps(body).encode(), headers=HEAD)
        d = json.load(urllib.request.urlopen(req, timeout=25, context=CTX))
        data = d.get("data") or {}
        posts = data.get("job_post_list") or []
        total = data.get("count") or 0
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
            ts_ms = None
            if isinstance(pt, (int, float)) or (isinstance(pt, str) and pt.isdigit()):
                try:
                    raw = int(pt)
                    if raw > 1e12:
                        ts_ms = raw
                        ts_s = raw / 1000
                    else:
                        ts_ms = raw * 1000
                        ts_s = raw
                    pt = datetime.fromtimestamp(ts_s, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    ts_ms = None
            out.append({
                "title": j.get("title", ""),
                "company": "字节跳动",
                "location": city,
                "dept": dept,
                "date": pt,
                "jd": jd,
                "responsibility": desc,
                "requirement": req_text,
                "url": f"https://jobs.bytedance.com/experienced/position/{jid}/detail",
                "id": jid,
                "_publish_ts": ts_ms,
            })
        return out, total, None
    except Exception as e:
        sys.stderr.write(f"[bytedance] page {page} failed: {e}\n")
        return [], None, str(e)


def _fetch_page(page, keyword, limit):
    """Fetch a single page. Returns list of jobs or empty on failure."""
    posts, _, err = _fetch_page_raw(page, keyword, limit)
    return [] if err else posts


def _fetch_page_retry(page, keyword, limit):
    """Fetch a page with one retry. Returns (jobs, total_count) or (None, None)."""
    for attempt in range(2):
        posts, total, err = _fetch_page_raw(page, keyword, limit)
        if err is None:
            return posts, total
        time.sleep(0.5 * (attempt + 1))
    return None, None


def fetch_with_meta(keyword="", scan_limit=BYTEDANCE_SCAN_LIMIT,
                    max_age_days=BYTEDANCE_MAX_AGE_DAYS):
    """Fetch up to scan_limit posts, keeping only publish_time within max_age_days.

    Returns (jobs, meta). meta["ok"] is False when any page failed twice, so the
    caller can keep the previous cache instead of serving partial data.
    """
    limit = min(BYTEDANCE_PAGE_LIMIT, max(1, scan_limit))
    cutoff_ms = int(time.time() * 1000) - max_age_days * 86400 * 1000
    cutoff_iso = datetime.fromtimestamp(cutoff_ms / 1000, tz=timezone.utc).isoformat()

    first, total, err = _fetch_page_raw(0, keyword, limit)
    if err is not None:
        first, total = _fetch_page_retry(0, keyword, limit)
    if first is None:
        return [], {
            "ok": False,
            "total_available": total or 0,
            "scanned": 0,
            "kept": 0,
            "cutoff": cutoff_iso,
            "page_failures": 1,
        }

    total = total or 0
    available = min(int(total), scan_limit) if total else scan_limit
    pages = max(1, math.ceil(available / limit))
    all_posts = list(first)
    page_failures = 0

    def _fetch_one(p):
        posts, _ = _fetch_page_retry(p, keyword, limit)
        return p, posts

    if pages > 1:
        with concurrent.futures.ThreadPoolExecutor(max_workers=BYTEDANCE_MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_one, p): p for p in range(1, pages)}
            for fut in concurrent.futures.as_completed(futures):
                p, posts = fut.result()
                if posts is None:
                    page_failures += 1
                else:
                    all_posts.extend(posts)

    if page_failures:
        return [], {
            "ok": False,
            "total_available": total,
            "scanned": len(all_posts),
            "kept": 0,
            "cutoff": cutoff_iso,
            "page_failures": page_failures,
        }

    recent = [j for j in all_posts
              if j.get("_publish_ts") is not None and j["_publish_ts"] >= cutoff_ms]
    seen = set()
    deduped = []
    for j in recent:
        jid = j.get("id", "")
        if jid and jid not in seen:
            seen.add(jid)
            j.pop("_publish_ts", None)
            deduped.append(j)
    deduped.sort(key=lambda x: x.get("date", ""), reverse=True)

    meta = {
        "ok": True,
        "total_available": total,
        "scanned": len(all_posts),
        "kept": len(deduped),
        "cutoff": cutoff_iso,
        "page_failures": 0,
    }
    return deduped, meta


def fetch(keyword="", pages=BYTEDANCE_SCAN_LIMIT // BYTEDANCE_PAGE_LIMIT,
          limit=BYTEDANCE_PAGE_LIMIT, max_age_days=BYTEDANCE_MAX_AGE_DAYS):
    """Backwards-compatible wrapper: returns only the job list."""
    jobs, _ = fetch_with_meta(keyword, pages * limit, max_age_days)
    return jobs

if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print(json.dumps(fetch(kw, pg), ensure_ascii=False))
