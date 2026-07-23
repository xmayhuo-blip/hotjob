#!/usr/bin/env python3
"""
OfferBoast 岗位雷达 — Web Server
直接读取招聘网站 ATS，实时返回岗位发布时间
"""

import http.server
import json
import os
import ssl as _ssl
import subprocess
import sys
import threading
import time
import urllib.request as _urllib
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import re

PYTHON_BIN = sys.executable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
HR_SCRIPT = os.path.join(PROJECT_DIR, "hiring_radar.py")
PORT = int(os.environ.get("PORT", "8787"))

COMPANIES = {
    "tencent":    {"name": "腾讯",     "color": "#00A4FF", "url": "https://careers.tencent.com/", "recruit_type": "社招"},
    "bytedance":  {"name": "字节跳动",  "color": "#2B2B2B", "url": "https://jobs.bytedance.com/", "recruit_type": "社招"},
    "xiaohongshu":{"name": "小红书",    "color": "#FF2442", "url": "https://job.xiaohongshu.com/", "recruit_type": "社招"},
    "alibaba":    {"name": "阿里巴巴",  "color": "#FF6A00", "url": "https://talent.alibaba.com/", "recruit_type": "社招"},
    "highflyer":  {"name": "DeepSeek", "color": "#6C5CE7", "url": "https://app.mokahr.com/social-recruitment/high-flyer/140576", "recruit_type": "社招"},
    "zhipu":      {"name": "智谱AI",   "color": "#00B894", "url": "https://zhipu-ai.jobs.feishu.cn/", "recruit_type": "社招"},
    "moonshot":   {"name": "月之暗面",  "color": "#E84393", "url": "https://app.mokahr.com/apply/moonshot/148506"},
    "minimax":    {"name": "MiniMax",  "color": "#0984E3", "url": "https://www.minimaxi.com/careers"},
    "kuaishou":   {"name": "快手",     "color": "#E17055", "url": "https://zhaopin.kuaishou.cn/", "recruit_type": "社招"},
}

# Companies without explicit recruit_type fall back to the `type` field from parser data
# (feishu.py returns "社招"/"校招" via recruit_type.name; moka.py returns "全职"/"兼职")

_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 300

def fetch_company(company_id):
    cached = False
    with _cache_lock:
        if company_id in _cache:
            entry = _cache[company_id]
            if time.time() - entry["time"] < CACHE_TTL:
                return company_id, entry["data"], True
    try:
        env = os.environ.copy()
        result = subprocess.run(
            [PYTHON_BIN, HR_SCRIPT, "--local", company_id, "--json", "--limit", "500"],
            capture_output=True, text=True, timeout=90,
            cwd=PROJECT_DIR, env=env
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            jobs = data.get("jobs", [])
            with _cache_lock:
                _cache[company_id] = {"time": time.time(), "data": jobs}
            return company_id, jobs, cached
        else:
            sys.stderr.write(f"[{company_id}] stderr: {result.stderr[:200]}\n")
            return company_id, [], cached
    except Exception as e:
        sys.stderr.write(f"[{company_id}] error: {e}\n")
        return company_id, [], cached

def parse_date(date_str):
    if not date_str or date_str == "未知":
        return None
    s = str(date_str).strip()
    # Try full string with all known formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    # Try truncated datetime (has space or T)
    if " " in s or "T" in s:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt)
            except Exception:
                pass
    # Try date-only truncated (ASCII only, not Chinese)
    if "年" not in s:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(s[:10], fmt)
            except Exception:
                pass
    # Try month only
    for fmt in ("%Y-%m", "%Y/%m"):
        try:
            return datetime.strptime(s[:7], fmt)
        except Exception:
            pass
    # Try timestamp (ms or s)
    try:
        ts = float(s)
        if ts > 1e12:
            ts /= 1000
        return datetime.fromtimestamp(ts)
    except Exception:
        return None

def days_ago(dt):
    if dt is None:
        return 9999
    return (datetime.now() - dt).days

# ===== URL → company / job id parsing for link lookup =====
URL_PATTERNS = [
    # (company_id, domain_keyword, [id_regex_patterns])
    ("tencent",     "careers.tencent.com",      [r"[?&]postId=([0-9]+)", r"[?&]id=([0-9]+)", r"/post/([0-9]+)\\.html", r"/post/([0-9]+)"]),
    ("bytedance",   "jobs.bytedance.com",       [r"/position/([0-9]+)/detail", r"/position/([0-9]+)"]),
    ("xiaohongshu", "job.xiaohongshu.com",      [r"[?&]positionId=([0-9a-zA-Z]+)", r"/position/([0-9a-zA-Z]+)"]),
    ("alibaba",     "talent.alibaba.com",       [r"[?&]positionId=([0-9a-zA-Z]+)", r"/position/([0-9a-zA-Z]+)"]),
    ("kuaishou",    "zhaopin.kuaishou.cn",      [r"[?&]id=([0-9a-zA-Z-]+)", r"/job/([0-9a-zA-Z-]+)", r"#/job/([0-9a-zA-Z-]+)"]),
    ("highflyer",   "app.mokahr.com",           [r"#/job/([0-9a-zA-Z-]+)", r"/job/([0-9a-zA-Z-]+)"]),
    ("moonshot",    "app.mokahr.com",           [r"#/job/([0-9a-zA-Z-]+)", r"/job/([0-9a-zA-Z-]+)"]),
    ("zhipu",       "jobs.feishu.cn",           [r"[?&]id=([0-9a-zA-Z-]+)", r"/position/([0-9a-zA-Z-]+)"]),
    ("minimax",     "jobs.feishu.cn",           [r"[?&]id=([0-9a-zA-Z-]+)", r"/position/([0-9a-zA-Z-]+)"]),
]

def identify_company(url):
    url_lower = url.lower()
    # Moka: both highflyer and moonshot use app.mokahr.com — disambiguate by org name in URL path
    if "app.mokahr.com" in url_lower:
        if "moonshot" in url_lower:
            return "moonshot"
        return "highflyer"
    for cid, domain, _ in URL_PATTERNS:
        if domain in url_lower:
            return cid
    # fallback: try company name keywords in host/path
    if "bytedance" in url_lower or "byte" in url_lower:
        return "bytedance"
    if "tencent" in url_lower:
        return "tencent"
    if "xiaohongshu" in url_lower or "xhs" in url_lower:
        return "xiaohongshu"
    if "alibaba" in url_lower or "ali" in url_lower:
        return "alibaba"
    if "kuaishou" in url_lower or "kwai" in url_lower:
        return "kuaishou"
    if "moonshot" in url_lower or "月之暗面" in url:
        return "moonshot"
    if "minimax" in url_lower:
        return "minimax"
    if "zhipu" in url_lower or "智谱" in url:
        return "zhipu"
    if "highflyer" in url_lower or "deepseek" in url_lower:
        return "highflyer"
    return None

def extract_job_id(url, patterns):
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return None

def _fmt_ts(pt):
    """Format millisecond/second timestamp to YYYY-MM-DD HH:MM:SS."""
    if isinstance(pt, (int, float)) or (isinstance(pt, str) and pt.isdigit()):
        try:
            ts = int(pt) / 1000 if int(pt) > 1e12 else int(pt)
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return str(pt) if pt else ""

def fetch_job_detail_fallback(cid, job_id, url):
    """When job not in cached list, fetch directly from company API."""
    ctx = _ssl.create_default_context()
    ua = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    _t0 = time.time()
    _MAX_FALLBACK_SECS = 20

    try:
        if cid == "bytedance":
            # Page through search API (start from page 11, up to 15 more pages = 450 extra jobs)
            api = "https://jobs.bytedance.com/api/v1/search/job/posts"
            head = {**ua, "Content-Type": "application/json", "portal-channel": "office", "portal-platform": "pc"}
            for page in range(10, 25):
                if time.time() - _t0 > _MAX_FALLBACK_SECS: break
                body = json.dumps({"keyword": "", "limit": 30, "offset": page * 30,
                        "job_category_id_list": [], "location_code_list": [],
                        "subject_id_list": [], "recruitment_id_list": []}).encode()
                req = _urllib.Request(api, data=body, headers=head)
                d = json.load(_urllib.urlopen(req, timeout=15, context=ctx))
                posts = (d.get("data") or {}).get("job_post_list") or []
                if not posts:
                    break
                for j in posts:
                    if str(j.get("id", "")) == job_id:
                        pt = _fmt_ts(j.get("publish_time", ""))
                        city = (j.get("city_info") or {}).get("name", "")
                        cat = j.get("job_category") or {}
                        dept = cat.get("name", "") if isinstance(cat, dict) else ""
                        jd = "\n\n".join(x for x in [j.get("description", ""), j.get("requirement", "")] if x)
                        return {"title": j.get("title", ""), "company": "字节跳动", "location": city,
                                "dept": dept, "date": pt, "jd": jd, "url": url, "id": job_id}
                if len(posts) < 30:
                    break
            return None

        elif cid == "tencent":
            # Tencent detail API
            detail_url = f"https://careers.tencent.com/tencentcareer/api/post/Detail?postId={job_id}&language=zh-cn"
            req = _urllib.Request(detail_url, headers=ua)
            d = json.load(_urllib.urlopen(req, timeout=15, context=ctx))
            post = (d.get("Data") or {})
            if post:
                return {"title": post.get("RecruitPostName", ""), "company": "腾讯",
                        "location": post.get("LocationName", ""),
                        "dept": post.get("CategoryName", "") or post.get("BGName", ""),
                        "date": post.get("LastUpdateTime", ""),
                        "jd": post.get("Responsibility", ""),
                        "url": post.get("PostURL", url), "id": job_id}
            return None

        elif cid == "xiaohongshu":
            # Page through Xiaohongshu API (start from page 4, up to 10 more pages)
            api = "https://job.xiaohongshu.com/websiterecruit/position/pageQueryPosition"
            for page in range(4, 15):
                if time.time() - _t0 > _MAX_FALLBACK_SECS: break
                body = json.dumps({"pageNo": page, "pageSize": 100, "keyword": ""}).encode()
                req = _urllib.Request(api, data=body, headers={**ua, "Content-Type": "application/json"})
                d = json.load(_urllib.urlopen(req, timeout=15, context=ctx))
                positions = d.get("data", {}).get("positionInfoList", [])
                if not positions:
                    break
                for j in positions:
                    if str(j.get("positionId", "")) == job_id:
                        pt = _fmt_ts(j.get("publishTime", ""))
                        return {"title": j.get("positionName", ""), "company": "小红书",
                                "location": j.get("workLocation", ""), "dept": j.get("department", ""),
                                "date": pt, "jd": j.get("jobDescription", ""), "url": url, "id": job_id}
                if len(positions) < 100:
                    break
            return None

        elif cid == "kuaishou":
            # Page through Kuaishou signed API (start from page 11, up to 15 more pages)
            import hmac, hashlib
            SECRET = "652f962a-0575-4575-98d2-f04e2291bee2"
            for page in range(11, 25):
                if time.time() - _t0 > _MAX_FALLBACK_SECS: break
                params = {"pageSize": "20", "pageNumber": str(page), "jobType": "2", "cityCode": "", "keyword": ""}
                canonical = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
                ts = str(int(time.time() * 1000))
                sign = hmac.new(SECRET.encode(), (ts + canonical + SECRET).encode(), hashlib.sha256).hexdigest()
                query = canonical + f"&signTimestamp={ts}&sign={sign}"
                req = _urllib.Request(f"https://zhaopin.kuaishou.cn/recruit/e/api/v1/open/positions/simple?{query}", headers=ua)
                d = json.load(_urllib.urlopen(req, timeout=15, context=ctx))
                positions = d.get("data", {}).get("positions", [])
                if not positions:
                    break
                for j in positions:
                    if str(j.get("id", "")) == job_id:
                        upd = str(j.get("updateTime", "") or "")
                        date = upd.replace(".", "-") if upd else ""
                        return {"title": j.get("name", ""), "company": "快手",
                                "location": j.get("workLocationName", ""), "dept": j.get("departmentName", ""),
                                "date": date, "jd": j.get("jobDescription", ""), "url": url, "id": job_id}
                if len(positions) < 20:
                    break
            return None

        elif cid in ("highflyer", "moonshot"):
            # Moka companies - use subprocess with more pages
            org_id = "high-flyer" if cid == "highflyer" else "moonshot"
            site_id = "140576" if cid == "highflyer" else "148506"
            env = os.environ.copy()
            result = subprocess.run(
                [PYTHON_BIN, os.path.join(PROJECT_DIR, "parsers/moka.py"), org_id, site_id, COMPANIES[cid]["name"], "", "20"],
                capture_output=True, text=True, timeout=60, cwd=PROJECT_DIR, env=env
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for j in data:
                    if str(j.get("id", "")) == job_id:
                        return {**j, "url": url, "id": job_id}
            return None

        elif cid in ("zhipu", "minimax"):
            # Feishu companies - direct API paging (start from page 11, up to 15 more pages)
            subdomain = "zhipu-ai" if cid == "zhipu" else "vrfi1sk8a0"
            api = f"https://{subdomain}.jobs.feishu.cn/api/v1/search/job/posts"
            for page in range(10, 25):
                if time.time() - _t0 > _MAX_FALLBACK_SECS: break
                body = json.dumps({"keyword": "", "offset": page * 30, "limit": 30}).encode()
                req = _urllib.Request(api, data=body, headers={**ua, "Content-Type": "application/json"})
                d = json.load(_urllib.urlopen(req, timeout=15, context=ctx))
                posts = d.get("data", {}).get("job_post_list", [])
                if not posts:
                    break
                for j in posts:
                    if str(j.get("id", "")) == job_id:
                        pt = _fmt_ts(j.get("publish_time", ""))
                        jf = j.get("job_function") or {}
                        cities = ",".join(c.get("name", "") for c in (j.get("city_list") or []) if isinstance(c, dict))
                        return {"title": j.get("title", ""), "company": COMPANIES[cid]["name"],
                                "location": cities, "dept": jf.get("name", "") if isinstance(jf, dict) else "",
                                "date": pt, "jd": j.get("description", ""), "url": url, "id": job_id}
                if len(posts) < 30:
                    break
            return None

        elif cid == "alibaba":
            # Alibaba - use subprocess with more pages
            env = os.environ.copy()
            result = subprocess.run(
                [PYTHON_BIN, os.path.join(PROJECT_DIR, "parsers/alibaba.py"), "", "40", "talent.alibaba.com"],
                capture_output=True, text=True, timeout=90, cwd=PROJECT_DIR, env=env
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                for j in data:
                    if str(j.get("id", "")) == job_id:
                        return {**j, "url": url, "id": job_id}
            return None

    except Exception as e:
        sys.stderr.write(f"[lookup fallback] {cid} error: {e}\n")

    return None

def lookup_job(url):
    cid = identify_company(url)
    if not cid or cid not in COMPANIES:
        return None, "无法识别链接所属公司，目前支持腾讯、字节、小红书、阿里、DeepSeek、智谱、月之暗面、MiniMax、快手"

    # Get id patterns for this company
    patterns = []
    for c, _, pats in URL_PATTERNS:
        if c == cid:
            patterns = pats
            break
    job_id = extract_job_id(url, patterns)

    # Fetch company jobs (uses cache)
    _, jobs, _ = fetch_company(cid)

    # Match by job id or URL containment
    match = None
    if jobs:
        if job_id:
            for j in jobs:
                if str(j.get("id", "")) == job_id:
                    match = j; break
                if str(j.get("post_id", "")) == job_id:
                    match = j; break
                if str(j.get("positionId", "")) == job_id:
                    match = j; break
                job_url = j.get("url", "") or ""
                if job_id in job_url:
                    match = j; break
        else:
            for j in jobs:
                job_url = j.get("url", "") or ""
                if job_url and job_url in url:
                    match = j; break

    # Fallback: fetch directly from company API
    if not match and job_id:
        sys.stderr.write(f"[lookup] cache miss for {cid} job_id={job_id}, trying direct API...\n")
        match = fetch_job_detail_fallback(cid, job_id, url)

    if not match:
        return None, f"未在 {COMPANIES[cid]['name']} 找到该链接对应的职位，可能已下架"

    # Enrich match same as in /api/jobs
    match["_company_id"] = cid
    match["_company_color"] = COMPANIES[cid]["color"]
    match["_company_name"] = COMPANIES[cid]["name"]
    rt = COMPANIES[cid].get("recruit_type", "")
    if not rt:
        t = str(match.get("type", "") or "").strip()
        if "校" in t: rt = "校招"
        elif "社" in t or "全职" in t or "full" in t.lower(): rt = "社招"
        elif "实习" in t or "兼职" in t: rt = "校招"
        elif t and t != "未知": rt = t
        else: rt = "未知"
    match["_recruit_type"] = rt
    dt = parse_date(match.get("date", ""))
    match["_days_ago"] = days_ago(dt)
    return match, None

class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ct="application/json; charset=utf-8"):
        if isinstance(body, str) and ct.startswith("text"):
            data = body.encode("utf-8")
        elif isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        else:
            data = body if isinstance(body, bytes) else str(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            html_path = os.path.join(BASE_DIR, "index.html")
            if os.path.exists(html_path):
                with open(html_path, "r", encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            else:
                self._send(404, "index.html not found")
            return

        if path == "/api/companies":
            self._send(200, {"companies": COMPANIES})
            return

        if path == "/api/jobs":
            self._handle_jobs(qs)
            return

        if path == "/api/health":
            self._send(200, {"status": "ok", "time": datetime.now().isoformat()})
            return

        if path == "/api/lookup":
            url = qs.get("url", [""])[0].strip()
            if not url:
                self._send(400, {"error": "缺少 url 参数"})
                return
            job, err = lookup_job(url)
            if err:
                self._send(404, {"error": err})
                return
            self._send(200, {
                "title": job.get("title", ""),
                "company_id": job.get("_company_id", ""),
                "company_name": job.get("_company_name", ""),
                "location": job.get("location", ""),
                "dept": job.get("dept", ""),
                "date": job.get("date", ""),
                "days_ago": job.get("_days_ago"),
                "recruit_type": job.get("_recruit_type", ""),
                "url": job.get("url", url),
            })
            return

        # Static files (favicon, etc.)
        static_ext_map = {
            ".ico": "image/x-icon",
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".js": "application/javascript",
            ".css": "text/css",
        }
        ext = os.path.splitext(path)[1].lower()
        if ext in static_ext_map:
            static_path = os.path.join(BASE_DIR, os.path.basename(path))
            if os.path.exists(static_path) and os.path.isfile(static_path):
                with open(static_path, "rb") as f:
                    self._send(200, f.read(), static_ext_map[ext])
                return

        self._send(404, {"error": "not found"})

    def _handle_jobs(self, qs):
        companies_param = qs.get("companies", ["tencent,bytedance,xiaohongshu,alibaba,highflyer,zhipu,moonshot,minimax,kuaishou"])[0]
        keyword = qs.get("keyword", [""])[0].strip()
        days_str = qs.get("days", ["0"])[0]
        try:
            days = int(days_str)
        except ValueError:
            days = 0

        if companies_param == "all":
            company_ids = list(COMPANIES.keys())
        else:
            company_ids = [c.strip() for c in companies_param.split(",") if c.strip() in COMPANIES]

        if not company_ids:
            self._send(200, {"jobs": [], "stats": {}, "companies": {}})
            return

        t0 = time.time()
        results = {}
        errors = {}

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {pool.submit(fetch_company, cid): cid for cid in company_ids}
            for fut in as_completed(futures):
                cid = futures[fut]
                try:
                    cid, jobs, cached = fut.result()
                    results[cid] = jobs
                except Exception as e:
                    errors[cid] = str(e)
                    results[cid] = []

        all_jobs = []
        company_stats = {}
        for cid in company_ids:
            jobs = results.get(cid, [])
            company_stats[cid] = {
                "name": COMPANIES[cid]["name"],
                "color": COMPANIES[cid]["color"],
                "count": len(jobs),
                "url": COMPANIES[cid]["url"],
            }
            for j in jobs:
                j["_company_id"] = cid
                j["_company_color"] = COMPANIES[cid]["color"]
                j["_company_name"] = COMPANIES[cid]["name"]
                # Determine recruit type: use company-level override, else parse from `type` field
                rt = COMPANIES[cid].get("recruit_type", "")
                if not rt:
                    t = str(j.get("type", "") or "").strip()
                    if "校" in t:
                        rt = "校招"
                    elif "社" in t or "全职" in t or "full" in t.lower():
                        rt = "社招"
                    elif "实习" in t or "兼职" in t:
                        rt = "校招"
                    elif t and t != "未知":
                        rt = t
                    else:
                        rt = "未知"
                j["_recruit_type"] = rt
                dt = parse_date(j.get("date", ""))
                j["_days_ago"] = days_ago(dt)
                all_jobs.append(j)

        if keyword:
            kw = keyword.lower()
            all_jobs = [j for j in all_jobs if kw in j.get("title", "").lower()
                       or kw in j.get("description", "").lower()
                       or kw in j.get("dept", "").lower()]

        if days > 0:
            all_jobs = [j for j in all_jobs if j["_days_ago"] < days]

        all_jobs.sort(key=lambda x: x.get("_days_ago", 9999))

        today = datetime.now().date()
        today_count = sum(1 for j in all_jobs if parse_date(j.get("date", "")) and parse_date(j.get("date", "")).date() == today)
        week_count = sum(1 for j in all_jobs if j.get("_days_ago", 9999) < 7)

        self._send(200, {
            "jobs": all_jobs,
            "total": len(all_jobs),
            "stats": {
                "total": len(all_jobs),
                "today": today_count,
                "this_week": week_count,
                "by_company": company_stats,
            },
            "errors": errors,
            "fetch_time": round(time.time() - t0, 1),
            "cached": all(f"{cid}" in _cache for cid in company_ids),
        })

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

def main():
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"OfferBoast 岗位雷达 running on http://localhost:{PORT}")
    print(f"  Python: {PYTHON_BIN}")
    print(f"  Engine: {HR_SCRIPT}")
    print(f"  Companies: {', '.join(COMPANIES.keys())}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()
