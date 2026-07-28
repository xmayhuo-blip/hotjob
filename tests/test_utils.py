#!/usr/bin/env python3
"""hotjob utility function tests (pure logic, no module imports)."""
import sys, re
from datetime import datetime, timezone

# Inline helpers matching web/app.py and hiring_radar.py logic

def _parse_date(date_str):
    if not date_str or date_str == "\u672a\u77e5":
        return None
    s = str(date_str).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y\u5e74%m\u6708%d\u65e5"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    if " " in s or "T" in s:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt)
            except Exception:
                pass
    if "\u5e74" not in s:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(s[:10], fmt)
            except Exception:
                pass
    try:
        ts = float(s)
        if ts > 1e12: ts /= 1000
        return datetime.fromtimestamp(ts)
    except Exception:
        return None

def _days_ago_src(d):
    if not d: return None
    s = str(d)
    if s.isdigit():
        try:
            ts = int(s)
            if ts > 1e12: ts /= 1000
            return (datetime.now(timezone.utc) - datetime.fromtimestamp(ts, tz=timezone.utc)).days
        except Exception:
            return None
    m = re.search(r"(\d{4})\u5e74(\d{1,2})\u6708(\d{1,2})\u65e5", s)
    if m:
        try: return (datetime.now(timezone.utc) - datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)).days
        except Exception: pass
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if m:
        try: return (datetime.now(timezone.utc) - datetime.strptime(m.group(0), "%Y-%m-%d").replace(tzinfo=timezone.utc)).days
        except Exception: return None
    sl = s.lower()
    if "today" in sl: return 0
    if "yesterday" in sl: return 1
    m = re.search(r"(\d+)\+?\s*day", sl)
    if m: return int(m.group(1))
    return None

def _extract_experience(requirement, jd=""):
    text = (requirement or "") + " " + (jd or "")
    if not text.strip():
        return {"_exp_min": -1, "_exp_label": ""}
    if re.search(r'\u5e94\u5c4a|\u6bd5\u4e1a\u751f|\u5b9e\u4e60|\u6821\u62db|\u65e0\u7ecf\u9a8c|\u4e0d\u9650\u7ecf\u9a8c', text):
        return {"_exp_min": 0, "_exp_label": "\u5e94\u5c4a"}
    text = re.sub(r'(\d+)\s*\u5e74', lambda m: m.group(1) + '\u5e74', text)
    m = re.search(r'(\d+)\s*\u5e74\s*(?:\u53ca\s*)?\u4ee5\s*\u4e0a', text)
    if m:
        n = int(m.group(1))
        if n <= 1: return {"_exp_min": 1, "_exp_label": "1-3\u5e74"}
        if n <= 3: return {"_exp_min": n, "_exp_label": f"{n}-5\u5e74"}
        if n <= 5: return {"_exp_min": n, "_exp_label": f"{n}-10\u5e74"}
        return {"_exp_min": n, "_exp_label": f"{n}\u5e74+"}
    m = re.search(r'(\d+)\s*[-\~\u81f3\u5230]\s*(\d+)\s*\u5e74', text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if hi <= 1: return {"_exp_min": 0, "_exp_label": "\u5e94\u5c4a"}
        if hi <= 3: return {"_exp_min": lo, "_exp_label": "1-3\u5e74"}
        if hi <= 5: return {"_exp_min": lo, "_exp_label": "3-5\u5e74"}
        if hi <= 10: return {"_exp_min": lo, "_exp_label": "5-10\u5e74"}
        return {"_exp_min": lo, "_exp_label": "10\u5e74+"}
    m = re.search(r'(\d+)\s*\u5e74', text)
    if m:
        n = int(m.group(1))
        if n <= 1: return {"_exp_min": 0, "_exp_label": "\u5e94\u5c4a"}
        if n <= 3: return {"_exp_min": n, "_exp_label": "1-3\u5e74"}
        if n <= 5: return {"_exp_min": n, "_exp_label": "3-5\u5e74"}
        if n <= 10: return {"_exp_min": n, "_exp_label": "5-10\u5e74"}
        return {"_exp_min": n, "_exp_label": "10\u5e74+"}
    return {"_exp_min": -1, "_exp_label": ""}

def days_ago_web(dt):
    return 9999 if dt is None else (datetime.now() - dt).days

# ---- Tests ----
PASS = 0; FAIL = 0
def check_eq(label, got, expected):
    global PASS, FAIL
    if got == expected:
        PASS += 1
    else:
        FAIL += 1; print(f"  FAIL: {label}  got={got!r} expected={expected!r}")

print("[test] parse_date")
check_eq("ISO datetime", str(_parse_date("2026-07-23 14:30:00")), "2026-07-23 14:30:00")
check_eq("ISO date", str(_parse_date("2026-07-23")), "2026-07-23 00:00:00")
check_eq("Chinese date", str(_parse_date("2026\u5e7407\u670823\u65e5")), "2026-07-23 00:00:00")
check_eq("Slash date", str(_parse_date("2026/07/23")), "2026-07-23 00:00:00")
check_eq("None", _parse_date(None), None)
check_eq("Empty", _parse_date(""), None)

print("[test] _days_ago")
from datetime import timedelta, timezone
_t = datetime.now(timezone.utc)
_y = _t - timedelta(days=1)
_w = _t - timedelta(days=7)
check_eq("ISO today", _days_ago_src(_t.strftime("%Y-%m-%d")), 0)
check_eq("ISO -1d", _days_ago_src(_y.strftime("%Y-%m-%d")), 1)
check_eq("ISO -7d", _days_ago_src(_w.strftime("%Y-%m-%d")), 7)
check_eq("Today kw", _days_ago_src("Today"), 0)
check_eq("Yesterday", _days_ago_src("Yesterday"), 1)
check_eq("Empty", _days_ago_src(""), None)

print("[test] extract_experience")
check_eq("\u5e94\u5c4a", _extract_experience("\u5e94\u5c4a\u6bd5\u4e1a\u751f\u4f18\u5148")["_exp_label"], "\u5e94\u5c4a")
check_eq("3\u5e74\u4ee5\u4e0a", _extract_experience("3\u5e74\u4ee5\u4e0a\u5f00\u53d1\u7ecf\u9a8c")["_exp_label"], "3-5\u5e74")
check_eq("1-3\u5e74", _extract_experience("1-3\u5e74\u7ecf\u9a8c")["_exp_label"], "1-3\u5e74")
check_eq("5\u5e74", _extract_experience("5\u5e74\u76f8\u5173\u7ecf\u9a8c")["_exp_label"], "3-5\u5e74")
check_eq("\u4e0d\u9650\u7ecf\u9a8c", _extract_experience("\u4e0d\u9650\u7ecf\u9a8c")["_exp_min"], 0)
check_eq("\u7a7a\u6587\u672c", _extract_experience("")["_exp_min"], -1)

print("[test] days_ago")
check_eq("today", days_ago_web(datetime.now()), 0)
check_eq("None", days_ago_web(None), 9999)

total = PASS + FAIL
print(f"\nResults: {PASS}/{total} passed, {FAIL}/{total} failed")
sys.exit(0 if FAIL == 0 else 1)
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def _parse_date(date_str):
    if not date_str or date_str == "\u672a\u77e5":
        return None
    s = str(date_str).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d", "%Y\u5e74%m\u6708%d\u65e5"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    if " " in s or "T" in s:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(s[:19], fmt)
            except Exception:
                pass
    if "\u5e74" not in s:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(s[:10], fmt)
            except Exception:
                pass
    try:
        ts = float(s)
        if ts > 1e12:
            ts /= 1000
        return datetime.fromtimestamp(ts)
    except Exception:
        return None

def _days_ago_src(d):
    if not d:
        return None
    s = str(d)
    if s.isdigit():
        try:
            ts = int(s)
            if ts > 1e12:
                ts /= 1000
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days
        except Exception:
            return None
    m = re.search(r"(\d{4})\u5e74(\d{1,2})\u6708(\d{1,2})\u65e5", s)
    if m:
        try:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days
        except Exception:
            pass
    m = re.search(r"\d{4}-\d{2}-\d{2}", s)
    if m:
        try:
            dt = datetime.strptime(m.group(0), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days
        except Exception:
            return None
    sl = s.lower()
    if "today" in sl:
        return 0
    if "yesterday" in sl:
        return 1
    m = re.search(r"(\d+)\+?\s*day", sl)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\+?\s*month", sl)
    if m:
        return int(m.group(1)) * 30
    return None

def _extract_experience(requirement, jd=""):
    text = (requirement or "") + " " + (jd or "")
    if not text.strip():
        return {"_exp_min": -1, "_exp_label": ""}
    if re.search(r'\u5e94\u5c4a|\u6bd5\u4e1a\u751f|\u5b9e\u4e60|\u6821\u62db|\u65e0\u7ecf\u9a8c|\u4e0d\u9650\u7ecf\u9a8c', text):
        return {"_exp_min": 0, "_exp_label": "\u5e94\u5c4a"}
    text = re.sub(r'(\d+)\s*\u5e74', r'\1\u5e74', text)
    m = re.search(r'(\d+)\s*\u5e74\s*(?:\u53ca\s*)?\u4ee5\s*\u4e0a', text)
    if m:
        n = int(m.group(1))
        if n <= 1: return {"_exp_min": 1, "_exp_label": "1-3\u5e74"}
        if n <= 3: return {"_exp_min": n, "_exp_label": f"{n}-5\u5e74"}
        if n <= 5: return {"_exp_min": n, "_exp_label": f"{n}-10\u5e74"}
        return {"_exp_min": n, "_exp_label": f"{n}\u5e74+"}
    m = re.search(r'(\d+)\s*[-\~\u81f3\u5230]\s*(\d+)\s*\u5e74', text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if hi <= 1: return {"_exp_min": 0, "_exp_label": "\u5e94\u5c4a"}
        if hi <= 3: return {"_exp_min": lo, "_exp_label": "1-3\u5e74"}
        if hi <= 5: return {"_exp_min": lo, "_exp_label": "3-5\u5e74"}
        if hi <= 10: return {"_exp_min": lo, "_exp_label": "5-10\u5e74"}
        return {"_exp_min": lo, "_exp_label": "10\u5e74+"}
    m = re.search(r'(\d+)\s*\u5e74', text)
    if m:
        n = int(m.group(1))
        if n <= 1: return {"_exp_min": 0, "_exp_label": "\u5e94\u5c4a"}
        if n <= 3: return {"_exp_min": n, "_exp_label": "1-3\u5e74"}
        if n <= 5: return {"_exp_min": n, "_exp_label": "3-5\u5e74"}
        if n <= 10: return {"_exp_min": n, "_exp_label": "5-10\u5e74"}
        return {"_exp_min": n, "_exp_label": "10\u5e74+"}
    if re.search(r'\u7ecf\u9a8c\u4e30\u5bcc|\u6709\u76f8\u5173\u7ecf\u9a8c|\u6709\w+\u7ecf\u9a8c', text):
        return {"_exp_min": 1, "_exp_label": "1-3\u5e74"}
    return {"_exp_min": -1, "_exp_label": ""}

def days_ago_web(dt):
    if dt is None:
        return 9999
    return (datetime.now() - dt).days

PASS = 0
FAIL = 0
def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}")
def check_eq(label, got, expected):
    global PASS, FAIL
    if got == expected:
        PASS += 1
    else:
        FAIL += 1
        print(f"  FAIL: {label}  (got={got!r}, expected={expected!r})")

print("[test] parse_date")
check_eq("ISO datetime", str(_parse_date("2026-07-23 14:30:00")), "2026-07-23 14:30:00")
check_eq("ISO date only", str(_parse_date("2026-07-23")), "2026-07-23 00:00:00")
check_eq("Chinese date", str(_parse_date("2026\u5e7407\u670823\u65e5")), "2026-07-23 00:00:00")
check_eq("None input", _parse_date(None), None)
check_eq("Empty string", _parse_date(""), None)

print("[test] _days_ago")
check_eq("Chinese today", _days_ago_src("2026\u5e7407\u670827\u65e5"), 0)
check_eq("Chinese -1d", _days_ago_src("2026\u5e7407\u670826\u65e5"), 1)
check_eq("ISO today", _days_ago_src("2026-07-27"), 0)
check_eq("ISO -1d", _days_ago_src("2026-07-26"), 1)
check_eq("ISO -7d", _days_ago_src("2026-07-20"), 7)
check_eq("Empty input", _days_ago_src(""), None)
check_eq("Today keyword", _days_ago_src("Today"), 0)
check_eq("Yesterday", _days_ago_src("Yesterday"), 1)

print("[test] extract_experience")
check_eq("\u5e94\u5c4a\u8bc6\u522b", _extract_experience("\u5e94\u5c4a\u6bd5\u4e1a\u751f\u4f18\u5148")["_exp_label"], "\u5e94\u5c4a")
check_eq("3\u5e74\u4ee5\u4e0a", _extract_experience("3\u5e74\u4ee5\u4e0a\u5f00\u53d1\u7ecf\u9a8c")["_exp_label"], "3-5\u5e74")
check_eq("1-3\u5e74", _extract_experience("1-3\u5e74\u7ecf\u9a8c")["_exp_label"], "1-3\u5e74")
check_eq("5\u5e74\u7ecf\u9a8c", _extract_experience("5\u5e74\u76f8\u5173\u7ecf\u9a8c")["_exp_label"], "3-5\u5e74")
check_eq("\u4e0d\u9650\u7ecf\u9a8c", _extract_experience("\u7ecf\u9a8c\u4e0d\u9650")["_exp_min"], 0)
check_eq("\u7a7a\u6587\u672c", _extract_experience("")["_exp_min"], -1)

print("[test] days_ago")
dt = datetime.now()
check_eq("today", days_ago_web(dt), 0)
check_eq("None", days_ago_web(None), 9999)

total = PASS + FAIL
print(f"\nResults: {PASS}/{total} passed, {FAIL}/{total} failed")
sys.exit(0 if FAIL == 0 else 1)
