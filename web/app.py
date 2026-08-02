#!/usr/bin/env python3
"""
hotjob — Web Server
直接读取招聘网站 ATS，实时返回岗位发布时间
"""

import http.server
import importlib.util
import json
import os
import ssl as _ssl
import subprocess
import sys
import os
# Ensure project root is on sys.path for parsers package
_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_DIR = os.path.dirname(_APP_DIR)
if _PROJ_DIR not in sys.path:
    sys.path.insert(0, _PROJ_DIR)
import threading
import time
import urllib.request as _urllib
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import re
from parsers import loader as prs_loader

PYTHON_BIN = sys.executable
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
PORT = int(os.environ.get("PORT", "8787"))

# ===== Startup barrier =====
# HTTP server blocks until initial prewarm completes
_startup_ready = threading.Event()

# ===== Page view stats =====",
STATS_DB = "/tmp/hotjob_pageviews.db"
_CACHE_PATH = "/tmp/hotjob_cache.json"

# Minimum realistic job thresholds — must be defined BEFORE _load_cache()
# so that poisoned cache data (e.g., 1 job for Alibaba due to old dedup bug)
# is rejected on load, not silently served to users.
MIN_JOBS_THRESHOLD = {
    "tencent": 10, "bytedance": 300, "alibaba": 10, "highflyer": 1, "zhipu": 1,
    "moonshot": 1, "minimax": 1, "kuaishou": 5, "lilith": 1, "kurogame": 1,
}

def _save_cache():
    import json
    with _cache_lock:
        data = {}
        for k, v in _cache.items():
            if v.get("failed") or not v.get("data"):
                continue
            cache_entry = {"data": v["data"]}
            if v.get("meta"):
                cache_entry["meta"] = v["meta"]
            data[k] = cache_entry
    if data:
        try:
            with open(_CACHE_PATH, "w") as f:
                json.dump({"cache": data, "ts": time.time()}, f, ensure_ascii=False)
        except Exception as e:
            sys.stderr.write("[cache] save failed: %s\n" % e)

def _load_cache():
    """Load cached data from disk into _cache, but ONLY if data passes
    MIN_JOBS_THRESHOLD validation. Poisoned cache data (e.g., from old
    dedup bugs, SSL failures, API changes) is silently rejected."""
    import json, os
    if not os.path.exists(_CACHE_PATH):
        return
    try:
        with open(_CACHE_PATH) as f:
            blob = json.load(f)
    except Exception as e:
        sys.stderr.write(f"[cache] load failed: {e}\n")
        return
    cached = blob.get("cache", {})
    saved_ts = blob.get("ts", 0)
    now = time.time()
    loaded = 0
    rejected = 0
    with _cache_lock:
        for cid, entry in cached.items():
            if isinstance(entry, dict) and "data" in entry:
                jobs = entry["data"]
                min_ok = MIN_JOBS_THRESHOLD.get(cid, 1)
                # Reject poisoned cache: data below threshold or empty
                if len(jobs) < min_ok:
                    sys.stderr.write(
                        f"[cache] REJECTED {cid}: only {len(jobs)} jobs "
                        f"(min={min_ok}) — poisoned data, skipping\n")
                    rejected += 1
                    continue
                age = now - saved_ts
                _cache[cid] = {
                    "time": now - age,
                    "data": jobs,
                    "failed": False,
                    "meta": entry.get("meta", {}),
                }
                loaded += 1
    sys.stderr.write(
        f"[cache] loaded {loaded} companies from disk "
        f"(age {int(now - saved_ts)}s, rejected {rejected} poisoned)\n")

def _get_stats():
    """Lazy-import and return the stats module."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("_s", os.path.join(BASE_DIR, "stats.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
_stats_mod = _get_stats()

# Cache storage (defined early so _load_cache can use it)
_cache = {}
_cache_lock = threading.Lock()

# Load disk cache for instant warm restart
_load_cache()

# ===== Simple per-IP rate limiter =====
# Limits: 30 req/min per IP (enough for normal browsing, blocks abuse)
_rate_map = {}          # ip -> [timestamp, timestamp, ...]
_rate_lock = threading.Lock()
RATE_WINDOW = 60        # seconds
RATE_MAX = 30           # max requests per window per IP

def _rate_limit_ok(client_ip):
    """Returns True if request is within rate limit."""
    now = time.time()
    with _rate_lock:
        hits = _rate_map.get(client_ip, [])
        # Prune old entries
        hits = [t for t in hits if now - t < RATE_WINDOW]
        if len(hits) >= RATE_MAX:
            _rate_map[client_ip] = hits
            return False
        hits.append(now)
        _rate_map[client_ip] = hits
        return True
def _build_companies():
    return {
        "tencent":    {"name": "腾讯",     "color": "#00A4FF", "url": "https://careers.tencent.com/", "recruit_type": "社招", "max_count": 600},
        "bytedance":  {"name": "字节跳动",  "color": "#2B2B2B", "url": "https://jobs.bytedance.com/", "recruit_type": "社招", "max_count": 1000},
        "alibaba":    {"name": "阿里巴巴",  "color": "#FF6A00", "url": "https://talent.alibaba.com/", "recruit_type": "社招", "max_count": 500},
        "highflyer":  {"name": "DeepSeek", "color": "#6C5CE7", "url": "https://app.mokahr.com/social-recruitment/high-flyer/140576", "recruit_type": "社招", "max_count": 500},
        "zhipu":      {"name": "智谱AI",   "color": "#00B894", "url": "https://zhipu-ai.jobs.feishu.cn/", "recruit_type": "社招", "max_count": 400},
        "moonshot":   {"name": "月之暗面",  "color": "#E84393", "url": "https://app.mokahr.com/apply/moonshot/148506", "max_count": 500},
        "minimax":    {"name": "MiniMax",  "color": "#0984E3", "url": "https://www.minimaxi.com/careers", "max_count": 400},
        "kuaishou":   {"name": "快手",     "color": "#E17055", "url": "https://zhaopin.kuaishou.cn/", "recruit_type": "社招", "max_count": 300},
        "lilith":     {"name": "莉莉丝",   "color": "#9B59B6", "url": "https://lilithgames.jobs.feishu.cn/", "recruit_type": "社招", "max_count": 400},
        "kurogame":   {"name": "库洛游戏", "color": "#F39C12", "url": "https://kurogame.jobs.feishu.cn/", "recruit_type": "社招", "max_count": 400},
    }

COMPANIES = _build_companies()

PREWARM_LIMIT = 10      # max companies to prewarm / load by default
REFRESH_INTERVAL = 3600  # seconds between full data refreshes (1 hour)
_last_refresh = 0        # timestamp of last completed refresh cycle

CACHE_TTL = 600         # 10 min — reduces API call frequency by 50% vs 5 min
STALE_TTL = 86400       # 24 hours — serve stale cache when fresh fetch fails
FAIL_CACHE_TTL = 300    # 5 min — cache failed fetches so they don't retry infinitely
_inflight = {}
_inflight_lock = threading.Lock()
_FAIL_COUNTER = {}
_FAIL_LOCK = threading.Lock()


# ===== 职类归并映射 =====
_DEPT_CAT = [
    ("运营", [r'运营']),
    ("策划", [r'策划']),
    ("产品经理", [r'产品']),
    ("技术-开发", [r'后端', r'前端', r'客户端', r'研发', r'开发', r'工程', r'全栈', r'ios', r'android', r'服务端', r'server', r'技术类', r'技术-']),
    ("技术-算法", [r'算法', r'算法类', r'nlp', r'推荐', r'搜索', r'广告', r'cv', r'大模型', r'llm']),
    ("技术-其他", [r'测试', r'qa', r'运维', r'devops', r'sre', r'安全', r'数据', r'基础设施']),
    ("设计", [r'设计', r'ui', r'ux', r'视觉', r'交互', r'创意']),
    ("美术", [r'美术', r'美术类', r'3d', r'ta', r'原画', r'模型', r'特效']),
    ("策划", [r'策划']),
    ("市场营销", [r'市场', r'营销', r'bd', r'品牌', r'公关', r'媒介', r'商务']),
    ("职能", [r'人力', r'hr', r'行政', r'财务', r'法务', r'战略', r'投资']),
    ("销售", [r'销售']),
    ("项目管理", [r'项目']),
    ("音视频", [r'音视频', r'音频', r'视频', r'编码']),
]

_TITLE_CAT = [
    ("运营", [r'运营']),
    ("策划", [r'策划']),
    ("产品经理", [r'产品']),
    ("技术-算法", [r'算法', r'ai', r'ml', r'nlp', r'cv', r'大模型', r'llm', r'推荐', r'搜索']),
    ("技术-开发", [r'前端', r'后端', r'开发', r'工程师', r'架构', r'go', r'java', r'python', r'c\+\+', r'全栈', r'ios', r'android', r'客户端', r'服务端']),
    ("设计", [r'设计', r'ui', r'ux', r'视觉']),
    ("美术", [r'美术', r'原画', r'3d', r'模型']),
    ("策划", [r'策划']),
    ("市场营销", [r'市场', r'营销', r'bd', r'ua']),
    ("技术-其他", [r'测试', r'qa', r'运维', r'安全']),
    ("项目管理", [r'项目']),
    ("音视频", [r'音视频', r'音频', r'视频']),
    ("职能", [r'人力', r'hr', r'行政', r'财务']),
    ("销售", [r'销售']),
]

def _classify_category(dept, title):
    dept = (dept or "").strip().lower()
    title = (title or "").strip().lower()
    # 1. Title-specific operations/planning keywords take priority
    #    (prevents "商业化运营" being misclassified via generic "产品" dept)
    if title:
        for cat, patterns in _TITLE_CAT:
            for p in patterns:
                if re.search(p, title):
                    return cat
    # 2. Dept-based mapping (only if title didn't match)
    if dept:
        for cat, patterns in _DEPT_CAT:
            for p in patterns:
                if re.search(p, dept):
                    return cat
    return "其他"

def fetch_company(company_id, force_refresh=False):
    """Fetch via parsers/loader direct import with cache + in-flight dedup.

    Args:
        company_id: company identifier
        force_refresh: if True, skip cache check and always fetch fresh data.
                       Used by periodic_refresh_loop to ensure real re-fetch.
    """
    cached = False

    # 1. Check fresh cache (skip if force_refresh)
    if not force_refresh:
        with _cache_lock:
            if company_id in _cache:
                entry = _cache[company_id]
                age = time.time() - entry["time"]
                if age < CACHE_TTL:
                    return company_id, entry["data"], True

    # 2. In-flight dedup (skip during force_refresh)
    if not force_refresh:
        with _inflight_lock:
            event = _inflight.get(company_id)
            if event:
                event.wait(timeout=45)
                with _cache_lock:
                    if company_id in _cache:
                        return company_id, _cache[company_id]["data"], True
                return company_id, [], False
            event = threading.Event()
            _inflight[company_id] = event

    # 3. Fetch via direct import (no subprocess)
    try:
        jobs, meta = prs_loader.fetch_company_with_meta(company_id)
        if not meta.get("ok", True):
            raise RuntimeError(
                f"fetch incomplete: page_failures={meta.get('page_failures')}")
        min_ok = MIN_JOBS_THRESHOLD.get(company_id, 1)
        # Guard: reject suspiciously low data (INCLUDING 0 jobs)
        if len(jobs) < min_ok:
            sys.stderr.write(
                f"[{company_id}] SUSPICIOUS: only {len(jobs)} jobs (min={min_ok})\n")
            with _cache_lock:
                if company_id in _cache:
                    entry = _cache[company_id]
                    stale_jobs = entry.get("data", [])
                    # Only keep stale cache if IT is also good data
                    if len(stale_jobs) >= min_ok and time.time() - entry["time"] < STALE_TTL:
                        return company_id, stale_jobs, True
                    else:
                        sys.stderr.write(
                            f"[{company_id}] stale cache also bad "
                            f"({len(stale_jobs)} jobs), not serving it\n")
                # Cache suspicious data with failed=True (expires via FAIL_CACHE_TTL)
                _cache[company_id] = {"time": time.time(), "data": jobs, "failed": True, "meta": meta}
            return company_id, jobs, cached
        with _cache_lock:
            _cache[company_id] = {"time": time.time(), "data": jobs, "meta": meta}
        return company_id, jobs, cached
    except Exception as e:
        sys.stderr.write(f"[{company_id}] FETCH FAILED: {e}, using stale cache\n")
        with _cache_lock:
            if company_id in _cache:
                entry = _cache[company_id]
                if time.time() - entry["time"] < STALE_TTL:
                    return company_id, entry["data"], True
            _cache[company_id] = {"time": time.time(), "data": [], "failed": True, "meta": {}}
        return company_id, [], cached
    finally:
        if not force_refresh:
            with _inflight_lock:
                _inflight.pop(company_id, None)
            event.set()

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


def extract_experience(requirement, jd=""):
    """Extract years of experience from job requirement text.
    
    Returns a dict with:
      _exp_min: min years required (0 = 应届/无要求, -1 = 未识别)
      _exp_label: display label like "1-3年"
    """
    import re as _re
    text = (requirement or "") + " " + (jd or "")
    if not text.strip():
        return {"_exp_min": -1, "_exp_label": ""}
    
    # Check for 应届/实习/毕业生
    if _re.search(r'应届|毕业生|实习|校招|无经验|不限经验', text):
        return {"_exp_min": 0, "_exp_label": "应届"}
    
    # Normalize: remove spaces around numbers
    text = _re.sub(r'(\d+)\s*年', r'\1年', text)
    
    # Pattern 1: "N年及以上" / "N年以上" / "N年以上经验"
    m = _re.search(r'(\d+)\s*年\s*(?:及\s*)?以\s*上', text)
    if m:
        n = int(m.group(1))
        if n <= 1: return {"_exp_min": 1, "_exp_label": "1-3年"}
        if n <= 3: return {"_exp_min": n, "_exp_label": f"{n}-5年"}
        if n <= 5: return {"_exp_min": n, "_exp_label": f"{n}-10年"}
        return {"_exp_min": n, "_exp_label": f"{n}年+"}
    
    # Pattern 2: "N-N年" / "N至N年" / "N~N年"
    m = _re.search(r'(\d+)\s*[-~至到]\s*(\d+)\s*年', text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if hi <= 1: return {"_exp_min": 0, "_exp_label": "应届"}
        if hi <= 3: return {"_exp_min": lo, "_exp_label": "1-3年"}
        if hi <= 5: return {"_exp_min": lo, "_exp_label": "3-5年"}
        if hi <= 10: return {"_exp_min": lo, "_exp_label": "5-10年"}
        return {"_exp_min": lo, "_exp_label": "10年+"}
    
    # Pattern 3: "N年经验" / "N年相关" / "N年以上"
    m = _re.search(r'(\d+)\s*年', text)
    if m:
        n = int(m.group(1))
        if n <= 1: return {"_exp_min": 0, "_exp_label": "应届"}
        if n <= 3: return {"_exp_min": n, "_exp_label": "1-3年"}
        if n <= 5: return {"_exp_min": n, "_exp_label": "3-5年"}
        if n <= 10: return {"_exp_min": n, "_exp_label": "5-10年"}
        return {"_exp_min": n, "_exp_label": "10年+"}
    
    # Pattern 4: "经验丰富" / "有经验" without number
    if _re.search(r'经验丰富|有相关经验|有\w+经验', text):
        return {"_exp_min": 1, "_exp_label": "1-3年"}
    
    return {"_exp_min": -1, "_exp_label": ""}

def days_ago(dt):
    if dt is None:
        return 9999
    return (datetime.now() - dt).days


def _global_time_stats():
    """Metric cards are global: count all cached jobs regardless of filters."""
    today = d3 = d7 = d30 = 0
    with _cache_lock:
        for cid, entry in _cache.items():
            if cid not in COMPANIES:
                continue
            for j in (entry.get("data") or []):
                days = days_ago(parse_date(j.get("date", "")))
                if days == 0:
                    today += 1
                if days < 3:
                    d3 += 1
                if days < 7:
                    d7 += 1
                if days < 30:
                    d30 += 1
    return today, d3, d7, d30

# ===== URL → company / job id parsing for link lookup =====
URL_PATTERNS = [
    # (company_id, domain_keyword, [id_regex_patterns])
    ("tencent",     "careers.tencent.com",        [r"[?&]postId=([0-9]+)", r"[?&]id=([0-9]+)", r"/post/([0-9]+)\\.html", r"/post/([0-9]+)"]),
    ("bytedance",   "jobs.bytedance.com",         [r"/position/([0-9]+)/detail", r"/position/([0-9]+)"]),
    ("alibaba",     "talent.alibaba.com",         [r"[?&]positionId=([0-9a-zA-Z]+)", r"/position/([0-9a-zA-Z]+)"]),
    ("kuaishou",    "zhaopin.kuaishou.cn",        [r"[?&]id=([0-9a-zA-Z-]+)", r"/job/([0-9a-zA-Z-]+)", r"#/job/([0-9a-zA-Z-]+)"]),
    ("highflyer",   "app.mokahr.com",             [r"#/job/([0-9a-zA-Z-]+)", r"/job/([0-9a-zA-Z-]+)"]),
    ("moonshot",    "app.mokahr.com",             [r"#/job/([0-9a-zA-Z-]+)", r"/job/([0-9a-zA-Z-]+)"]),
    # Feishu: each company has its own subdomain — use full subdomain to disambiguate
    ("zhipu",       "zhipu-ai.jobs.feishu.cn",    [r"[?&]id=([0-9a-zA-Z-]+)", r"/position/([0-9a-zA-Z-]+)"]),
    ("minimax",     "vrfi1sk8a0.jobs.feishu.cn",  [r"[?&]id=([0-9a-zA-Z-]+)", r"/position/([0-9a-zA-Z-]+)"]),
    ("lilith",      "lilithgames.jobs.feishu.cn", [r"[?&]id=([0-9a-zA-Z-]+)", r"/position/([0-9a-zA-Z-]+)"]),
    ("kurogame",    "kurogame.jobs.feishu.cn",    [r"[?&]id=([0-9a-zA-Z-]+)", r"/position/([0-9a-zA-Z-]+)"]),
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
    if "lilith" in url_lower or "lilithgames" in url_lower:
        return "lilith"
    if "kurogame" in url_lower or "kuro" in url_lower:
        return "kurogame"
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
    _MAX_FALLBACK_SECS = 10

    try:
        if cid == "tencent":
            # Tencent Detail API deprecated (404) — page through Query API
            import urllib.parse as up
            for pg in range(1, 6):
                if time.time() - _t0 > _MAX_FALLBACK_SECS: break
                q = up.urlencode({"keyword": "", "pageIndex": pg, "pageSize": 100, "language": "zh-cn"})
                req = _urllib.Request(f"https://careers.tencent.com/tencentcareer/api/post/Query?{q}", headers=ua)
                d = json.load(_urllib.urlopen(req, timeout=10, context=ctx))
                posts = ((d.get("Data") or {}).get("Posts")) or []
                if not posts:
                    break
                for j in posts:
                    if str(j.get("PostId", "")) == job_id:
                        return {"title": j.get("RecruitPostName", ""), "company": "腾讯",
                                "location": j.get("LocationName", ""),
                                "dept": j.get("CategoryName", "") or j.get("BGName", ""),
                                "date": j.get("LastUpdateTime", ""),
                                "jd": j.get("Responsibility", ""),
                                "url": j.get("PostURL", url), "id": job_id}
                count = ((d.get("Data") or {}).get("Count") or 0)
                if len(posts) < 100 or pg * 100 >= count:
                    break
            return None

        elif cid == "bytedance":
            # Page through search API starting from page 0
            api = "https://jobs.bytedance.com/api/v1/search/job/posts"
            head = {**ua, "Content-Type": "application/json", "portal-channel": "office", "portal-platform": "pc"}
            for page in range(0, 8):
                if time.time() - _t0 > _MAX_FALLBACK_SECS: break
                body = json.dumps({"keyword": "", "limit": 30, "offset": page * 30,
                        "job_category_id_list": [], "location_code_list": [],
                        "subject_id_list": [], "recruitment_id_list": []}).encode()
                req = _urllib.Request(api, data=body, headers=head)
                d = json.load(_urllib.urlopen(req, timeout=10, context=ctx))
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

        elif cid == "kuaishou":
            # Page through Kuaishou signed API starting from page 1
            import hmac, hashlib
            SECRET = "652f962a-0575-4575-98d2-f04e2291bee2"
            for page in range(1, 8):
                if time.time() - _t0 > _MAX_FALLBACK_SECS: break
                params = {"pageSize": "20", "pageNumber": str(page), "jobType": "2", "cityCode": "", "keyword": ""}
                canonical = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
                ts = str(int(time.time() * 1000))
                sign = hmac.new(SECRET.encode(), (ts + canonical + SECRET).encode(), hashlib.sha256).hexdigest()
                query = canonical + f"&signTimestamp={ts}&sign={sign}"
                req = _urllib.Request(f"https://zhaopin.kuaishou.cn/recruit/e/api/v1/open/positions/simple?{query}", headers=ua)
                d = json.load(_urllib.urlopen(req, timeout=10, context=ctx))
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
            # Moka companies - direct API fetch (first 2 pages only for speed)
            org_id = "high-flyer" if cid == "highflyer" else "moonshot"
            site_id = "140576" if cid == "highflyer" else "148506"
            from Crypto.Cipher import AES
            from Crypto.Util.Padding import unpad
            import base64
            IV = b'de7c21ed8d6f50fe'
            moka_head = {**ua, "Content-Type": "application/json", "Accept": "application/json", "Origin": "https://app.mokahr.com"}
            for offset in (0, 50):
                if time.time() - _t0 > _MAX_FALLBACK_SECS: break
                body = json.dumps({"orgId": org_id, "siteId": int(site_id), "locale": "zh-CN", "limit": 50, "offset": offset}).encode()
                req = _urllib.Request("https://app.mokahr.com/api/outer/ats-apply/website/jobs/v2", data=body, headers=moka_head)
                resp = json.load(_urllib.urlopen(req, timeout=10, context=ctx))
                if "necromancer" in resp:
                    key = resp["necromancer"].encode()
                    pt = unpad(AES.new(key, AES.MODE_CBC, IV).decrypt(base64.b64decode(resp["data"])), 16)
                    resp = json.loads(pt.decode("utf-8"))
                data = resp.get("data", resp)
                jobs = data.get("jobs") or data.get("list") or []
                if not jobs:
                    break
                for j in jobs:
                    if str(j.get("id", "")) == job_id:
                        return {**j, "url": url, "id": job_id}
            return None

        elif cid in ("zhipu", "minimax"):
            # Feishu companies - direct API paging starting from page 0
            subdomain = "zhipu-ai" if cid == "zhipu" else "vrfi1sk8a0"
            api = f"https://{subdomain}.jobs.feishu.cn/api/v1/search/job/posts"
            for page in range(0, 8):
                if time.time() - _t0 > _MAX_FALLBACK_SECS: break
                body = json.dumps({"keyword": "", "offset": page * 30, "limit": 30}).encode()
                req = _urllib.Request(api, data=body, headers={**ua, "Content-Type": "application/json"})
                d = json.load(_urllib.urlopen(req, timeout=10, context=ctx))
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
            # Alibaba - single large page request (pageSize=500)
            env = os.environ.copy()
            env["HIRING_RADAR_INSECURE"] = "1"
            result = subprocess.run(
                [PYTHON_BIN, os.path.join(PROJECT_DIR, "parsers/alibaba.py"), "", "1", "talent.alibaba.com"],
                capture_output=True, text=True, timeout=15, cwd=PROJECT_DIR, env=env
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
        return None, f"无法识别链接所属公司，目前支持{len(COMPANIES)}家公司，可通过选择公司筛选"

    # Get id patterns for this company
    patterns = []
    for c, _, pats in URL_PATTERNS:
        if c == cid:
            patterns = pats
            break
    job_id = extract_job_id(url, patterns)

    # Step 1: Check cache (fast if warm)
    match = None
    cached_jobs = None
    with _cache_lock:
        if cid in _cache and time.time() - _cache[cid]["time"] < CACHE_TTL:
            cached_jobs = _cache[cid]["data"]

    if cached_jobs:
        if job_id:
            for j in cached_jobs:
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
            for j in cached_jobs:
                job_url = j.get("url", "") or ""
                if job_url and job_url in url:
                    match = j; break

    # Step 2: If not in cache, try fallback directly (skip slow full-company fetch)
    if not match and job_id:
        sys.stderr.write(f"[lookup] cache miss for {cid} job_id={job_id}, trying direct API...\n")
        match = fetch_job_detail_fallback(cid, job_id, url)

    if not match:
        return None, f"未在 {COMPANIES[cid]['name']} 找到该链接对应的职位，可能已下架"

    return _enrich_match(match, cid, url)


def _enrich_match(match, cid, url):
    """Add company metadata and computed fields to a matched job."""
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
    exp = extract_experience(match.get("requirement", ""), match.get("jd", ""))
    match["_exp_min"] = exp["_exp_min"]
    match["_exp_label"] = exp["_exp_label"]
    return match, None

class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body, ct="application/json; charset=utf-8"):
        import gzip as _gz
        if isinstance(body, str) and ct.startswith("text"):
            data = body.encode("utf-8")
        elif isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        else:
            data = body if isinstance(body, bytes) else str(body).encode("utf-8")
        use_gz = len(data) > 1024 and self.headers.get("Accept-Encoding", "").find("gzip") >= 0
        if use_gz:
            data = _gz.compress(data)
        self.send_response(code)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        if use_gz:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        # Rate limit check (skip for static files)
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/") and path != "/api/health":
            client_ip = self.client_address[0]
            if not _rate_limit_ok(client_ip):
                self._send(429, {"error": "请求过于频繁，请稍后再试"})
                return

        qs = parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            _stats_mod.record_view(path)
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

        if path == "/api/job-detail":
            _dcid = qs.get("cid", [""])[0].strip()
            _djobid = qs.get("id", [""])[0].strip()
            _found = None
            _company_ids = list(COMPANIES.keys())
            if _dcid and _dcid in _company_ids:
                with _cache_lock:
                    entry = _cache.get(_dcid)
                    if entry:
                        for _ej in (entry.get("data") or []):
                            if str(_ej.get("id", "")) == _djobid:
                                _found = _ej
                                break
                # Tencent: try detail API for full JD including Requirement
                # Tencent: ALWAYS try detail API for full JD (cache lacks Requirement)
                if _dcid == "tencent":
                    try:
                        from parsers.tencent import fetch_detail as _tc_detail
                        _detail = _tc_detail(_djobid)
                        if _detail:
                            _found = _detail
                    except Exception:
                        pass
            if _found:
                self._send(200, _found)
            else:
                self._send(404, {"error": "job not found", "cid": _dcid, "jid": _djobid})
            return
        
        if path == "/api/cache-debug":
            debug = {}
            with _cache_lock:
                import copy
                for cid in list(COMPANIES.keys()):
                    entry = _cache.get(cid)
                    if entry:
                        data = entry.get("data", [])
                        debug[cid] = {"age": round(time.time() - entry.get("time", 0), 1), "count": len(data), "failed": entry.get("failed", False), "has_jd": bool(data and bool(data[0].get("jd"))) if data else False, "sample_ids": [str(j.get("id","")) for j in data[:3]], "meta": entry.get("meta", {})}
            self._send(200, {"cache": debug})
            return
        
        if path == "/api/health":
            self._send(200, {"status": "ok", "time": datetime.now().isoformat()})
            return
        
        if path == "/api/stats":
            self._send(200, _stats_mod.get_stats())
            return

        if path == "/api/health/parsers":
            status = {}
            for cid, info in COMPANIES.items():
                with _cache_lock:
                    if cid in _cache:
                        entry = _cache[cid]
                        age = time.time() - entry["time"]
                        failed = entry.get("failed", False)
                        count = len(entry.get("data", []))
                        status[cid] = {
                            "name": info["name"],
                            "jobs": count,
                            "age_seconds": round(age, 1),
                            "status": "failed" if failed else ("stale" if age > CACHE_TTL else "ok"),
                        }
                    else:
                        status[cid] = {"name": info["name"], "jobs": 0, "age_seconds": 0, "status": "pending"}
            self._send(200, {
                "total_companies": len(COMPANIES),
                "ok": sum(1 for s in status.values() if s["status"] == "ok"),
                "failed": sum(1 for s in status.values() if s["status"] == "failed"),
                "pending": sum(1 for s in status.values() if s["status"] == "pending"),
                "total_jobs": sum(s["jobs"] for s in status.values()),
                "last_refresh": _last_refresh,
                "companies": status,
            })
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
        companies_param = qs.get("companies", ["tencent,bytedance,alibaba,highflyer,zhipu,moonshot,minimax,kuaishou,lilith,kurogame"])[0]
        keyword = qs.get("keyword", [""])[0].strip()
        days_str = qs.get("days", ["0"])[0]
        try:
            days = int(days_str)
        except ValueError:
            days = 0
        city = qs.get("city", [""])[0].strip()
        category = qs.get("category", [""])[0].strip()

        def _int_param(name, default, lo, hi):
            try:
                val = int(qs.get(name, [str(default)])[0])
            except (TypeError, ValueError):
                return default
            return max(lo, min(hi, val))

        page = _int_param("page", 1, 1, 10 ** 9)
        page_size = _int_param("page_size", 100, 1, 200)

        if companies_param == "all":
            company_ids = list(COMPANIES.keys())[:PREWARM_LIMIT]
        else:
            company_ids = [c.strip() for c in companies_param.split(",") if c.strip() in COMPANIES]

        if not company_ids:
            self._send(200, {
                "jobs": [], "total": 0, "page": page, "page_size": page_size,
                "total_pages": 1, "stats": {}, "companies": {}, "errors": {},
                "loading": [], "last_refresh": _last_refresh,
                "fetch_time": 0, "cached": True, "truncated": False,
            })
            return

        t0 = time.time()
        results = {}
        errors = {}
        loading = []

        # Stale-while-revalidate: return cached data immediately,
        # trigger background fetch for uncached companies
        for cid in company_ids:
            with _cache_lock:
                if cid in _cache:
                    entry = _cache[cid]
                    age = time.time() - entry["time"]
                    # Check for failed cache entry
                    if entry.get("failed"):
                        if age < FAIL_CACHE_TTL:
                            results[cid] = entry["data"]
                            errors[cid] = "fetch failed"
                            with _FAIL_LOCK:
                                _FAIL_COUNTER[cid] = _FAIL_COUNTER.get(cid, 0) + 1
                                if _FAIL_COUNTER[cid] >= 3:
                                    errors[cid] = "连续3次获取失败，已标记为故障"
                            continue
                        # Failure cache expired — retry
                    elif age < CACHE_TTL:
                        with _FAIL_LOCK:
                            _FAIL_COUNTER.pop(cid, None)
                        results[cid] = entry["data"]
                        continue
                    elif age < STALE_TTL:
                        # Serve stale, revalidate in background
                        results[cid] = entry["data"]
                        if cid not in _inflight:
                            threading.Thread(target=fetch_company, args=(cid,), daemon=True).start()
                        continue
            # Not cached or failed cache expired — serve empty, mark error
            # (but don't add to loading, preventing infinite frontend retries)
            results[cid] = []
            errors[cid] = "no cached data"
            with _inflight_lock:
                if cid in _inflight:
                    pass  # Don't add to loading, periodic refresh handles it
                else:
                    pass  # Don't add to loading

        all_jobs = []
        company_stats = {}
        seen_urls = set()
        for cid in company_ids:
            jobs = results.get(cid, [])
            _dedup_count = 0
            cinfo = COMPANIES[cid]
            company_stats[cid] = {"name": cinfo["name"], "color": cinfo["color"],
                                   "count": 0, "url": cinfo["url"],
                                   "max_count": cinfo.get("max_count", 0)}
            for j in jobs:
                # Deduplicate by company+id (URL is unreliable: Alibaba gives same URL to all jobs)
                dedup_key = f"{cid}:{j.get('id', '')}"
                if dedup_key in seen_urls:
                    continue
                _dedup_count += 1
                seen_urls.add(dedup_key)
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
                if dt:
                    j["date"] = dt.strftime("%Y-%m-%d")
                exp = extract_experience(j.get("requirement", ""), j.get("jd", ""))
                j["_exp_min"] = exp["_exp_min"]
                j["_exp_label"] = exp["_exp_label"]
                # 校招/实习强制归为应届（检查岗位自身type，不依赖公司级recruit_type）
                job_type = str(j.get("type", "") or "").strip()
                if "校" in job_type or "实习" in job_type:
                    j["_exp_min"] = 0
                    j["_exp_label"] = "应届"
                elif rt in ("校招", "实习"):
                    j["_exp_min"] = 0
                    j["_exp_label"] = "应届"
                j["_category"] = _classify_category(j.get("dept", ""), j.get("title", ""))
                all_jobs.append(j)
            company_stats[cid]["count"] = _dedup_count
            company_stats[cid]["limit_reached"] = _dedup_count >= company_stats[cid].get("max_count", 0) > 0

        if keyword:
            kw = keyword.lower()
            all_jobs = [j for j in all_jobs if kw in j.get("title", "").lower()
                       or kw in j.get("description", "").lower()
                       or kw in j.get("dept", "").lower()]

        city_set = set()
        for j in all_jobs:
            for c in re.split(r"[,，]", str(j.get("location", "") or "")):
                c = c.strip()
                if c and c != "未知" and len(c) <= 10:
                    city_set.add(c)
        all_cities = sorted(city_set)
        all_categories = sorted({j.get("_category") for j in all_jobs if j.get("_category")})

        if city:
            all_jobs = [j for j in all_jobs if any(
                c.strip() == city for c in re.split(r"[,，]", str(j.get("location", "") or "")))]
        if category:
            all_jobs = [j for j in all_jobs if j.get("_category") == category]

        # Metric cards are global and never follow request filters.
        stat_today, stat_3day, stat_7day, stat_30day = _global_time_stats()

        if days > 0:
            all_jobs = [j for j in all_jobs if j["_days_ago"] < days]

        for _cid in company_stats:
            company_stats[_cid]["count"] = sum(1 for j in all_jobs if j.get("_company_id") == _cid)

        all_jobs.sort(key=lambda x: x.get("_days_ago", 9999))
        total = len(all_jobs)
        total_pages = (total + page_size - 1) // page_size if total else 1
        if page > total_pages:
            page = total_pages
        if page < 1:
            page = 1
        start = (page - 1) * page_size
        page_jobs = all_jobs[start:start + page_size]

        self._send(200, {
            "jobs": page_jobs,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "stats": {
                "total": total,
                "today": stat_today,
                "d3": stat_3day,
                "d7": stat_7day,
                "d30": stat_30day,
                "by_company": company_stats,
                "cities": all_cities,
                "categories": all_categories,
            },
            "errors": errors,
            "loading": loading,
            "last_refresh": _last_refresh,
            "fetch_time": round(time.time() - t0, 1),
            "cached": all(f"{cid}" in _cache for cid in company_ids),
            "truncated": False,
        })

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[{self.log_date_time_string()}] {fmt % args}\n")

def periodic_refresh_loop():
    global _last_refresh
    """Background thread: refresh all companies on startup, then every REFRESH_INTERVAL.

    All user requests read from cache only -- no on-demand fetches.
    This keeps response times instant and reduces ATS API call frequency.
    """
    company_list = list(COMPANIES.keys())[:PREWARM_LIMIT]
    first_run = True

    while True:
        label = "initial fetch" if first_run else "periodic refresh"
        sys.stderr.write(f"[refresh] {label} of {len(company_list)} companies\n")

        failed = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(fetch_company, cid, True): cid for cid in company_list}
            for fut in as_completed(futures):
                cid = futures[fut]
                try:
                    _, data, _ = fut.result()
                    if not data:
                        failed.append(cid)
                except Exception as e:
                    sys.stderr.write(f"[refresh] {cid} error: {e}\n")
                    failed.append(cid)

        # Retry failed companies once after clearing failure cache
        if failed:
            sys.stderr.write(f"[refresh] retrying {len(failed)} failed companies...\n")
            time.sleep(5)
            # Clear failure cache so retry actually re-fetches
            with _cache_lock:
                for cid in failed:
                    if cid in _cache and _cache[cid].get("failed"):
                        del _cache[cid]
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(fetch_company, cid, True): cid for cid in failed}
                still_failed = []
                for fut in as_completed(futures):
                    cid = futures[fut]
                    try:
                        _, data, _ = fut.result()
                        if not data:
                            sys.stderr.write(f"[refresh] {cid} failed (attempt 2): returned empty\n")
                            still_failed.append(cid)
                    except Exception as e:
                        sys.stderr.write(f"[refresh] {cid} failed (attempt 2): {e}\n")
                        still_failed.append(cid)
                done = len(company_list) - len(still_failed)
        else:
            done = len(company_list)
            still_failed = []

        _last_refresh = time.time()
        _save_cache()
        if still_failed:
            sys.stderr.write(f"[refresh] cycle complete: {done}/{len(company_list)} ok, {len(still_failed)} failed (will retry in {REFRESH_INTERVAL}s)\n")
        else:
            sys.stderr.write(f"[refresh] cycle complete: {done}/{len(company_list)} ok, next in {REFRESH_INTERVAL}s\n")

        if first_run:
            first_run = False
            _startup_ready.set()
            sys.stderr.write("[refresh] initial prewarm complete, server ready\n")

        # Add jitter (0-300s) to avoid synchronized bursts across deployments
        import random as _r
        time.sleep(REFRESH_INTERVAL + _r.randint(0, 300))


def _kill_zombie_servers():
    """Kill any process already listening on our port before we start.
    This prevents the #1 cause of 'fix doesn't work': old server processes
    serving stale code/data while the user thinks they're hitting the new one."""
    import subprocess
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{PORT}"],
            capture_output=True, text=True, timeout=5
        )
        pids = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
        if pids:
            sys.stderr.write(f"[startup] killing {len(pids)} zombie process(es) on port {PORT}: {pids}\n")
            for pid in pids:
                try:
                    os.kill(int(pid), 9)
                except Exception:
                    pass
            time.sleep(1)
    except Exception as e:
        sys.stderr.write(f"[startup] zombie check skipped: {e}\n")


def main():
    # Kill any old server on the same port FIRST
    _kill_zombie_servers()

    # Wait for initial prewarm before accepting connections
    t = threading.Thread(target=periodic_refresh_loop, daemon=True)
    t.start()
    sys.stderr.write("[startup] waiting for initial data prewarm...\n")
    _startup_ready.wait()

    # Post-prewarm validation: verify all companies have realistic data
    bad = []
    with _cache_lock:
        for cid in COMPANIES:
            if cid in _cache:
                count = len(_cache[cid].get("data", []))
                min_ok = MIN_JOBS_THRESHOLD.get(cid, 1)
                if count < min_ok:
                    bad.append(f"{cid}: {count} jobs (min={min_ok})")
    if bad:
        sys.stderr.write(f"[startup] WARNING: data validation failed for: {'; '.join(bad)}\n")
        sys.stderr.write("[startup] server will start but some companies may show stale/empty data\n")
    else:
        sys.stderr.write("[startup] data validation passed: all companies have realistic job counts\n")

    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"hotjob running on http://localhost:{PORT}")
    print(f"  Companies: {', '.join(COMPANIES.keys())}")
    print(f"  Cache TTL: {CACHE_TTL}s | Stale TTL: {STALE_TTL}s")

    # Periodic data refresh in background (startup + every REFRESH_INTERVAL)
    print(f"  Background refresh every {REFRESH_INTERVAL}s")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()

if __name__ == "__main__":
    main()
