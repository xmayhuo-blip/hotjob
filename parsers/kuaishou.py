#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hiring_radar local-parser：快手招聘(zhaopin.kuaishou.cn) → JSON(stdout)。
用法: python3 kuaishou.py [keyword] [pages]
API: GET /recruit/e/api/v1/open/positions/simple
签名: HMAC-SHA256(signTimestamp + canonicalQuery + SECRET, SECRET)
"""
import sys, json, re, ssl, hmac, hashlib, urllib.request, urllib.parse, os
import sys as _sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from jd_splitter import split_jd

DOMAIN = "zhaopin.kuaishou.cn"
BASE_URL = f"https://{DOMAIN}"
API_PREFIX = "/recruit/e"
SIGN_SECRET = "652f962a-0575-4575-98d2-f04e2291bee2"

CTX = ssl.create_default_context()
if os.environ.get("HIRING_RADAR_INSECURE") == "1":
    CTX.check_hostname = False
    CTX.verify_mode = ssl.CERT_NONE
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
      "Accept": "application/json, text/plain, */*",
      "Referer": f"{BASE_URL}/"}

# 快手地点 code → 中文名
LOCATION_MAP = {
    "Beijing": "北京", "Shanghai": "上海", "Guangzhou": "广州", "Shenzhen": "深圳",
    "Tianjin": "天津", "Hangzhou": "杭州", "Chengdu": "成都", "Wuhan": "武汉",
    "qingdao": "青岛", "Yantai": "烟台", "Xian": "西安", "Shenyang": "沈阳",
    "shijiazhuang": "石家庄", "Wuxi": "无锡", "Zhuhai": "珠海",
    "huhehaote": "呼和浩特", "Los Angeles": "洛杉矶", "saopaulo": "圣保罗",
    "huaian": "淮安", "tongren": "铜仁", "jishou": "吉首",
    "wulanchabu": "乌兰察布", "chengmai": "澄迈",
}

CATEGORY_MAP = {
    "J0012": "工程类", "J0011": "算法类", "J0005": "产品类", "J0004": "运营类",
    "J0003": "设计类", "J0014": "分析类", "J0013": "战略类", "J0006": "市场类",
    "J0002": "职能类", "J0007": "客服类", "J0008": "审核类", "J0009": "内容评级类",
    "J0015": "销售及支持类", "J0010": "其它类",
}


def _canonical_query(params):
    """与 jobhunt-cli 一致的 canonical query 签名输入。"""
    pairs = []
    for key in sorted(params.keys()):
        value = params[key]
        if value is None or value == "":
            continue
        encoded = urllib.parse.quote(str(value), safe="").replace("%20", "+")
        pairs.append(f"{key}={encoded}")
    return "&".join(pairs)


def _sign_headers(params):
    """生成快手 API 所需的 sign + signTimestamp 头。"""
    import time
    sign_ts = str(int(time.time() * 1000))
    cq = _canonical_query(params)
    sign_input = f"{sign_ts}{cq}{SIGN_SECRET}"
    sign = hmac.new(SIGN_SECRET.encode(), sign_input.encode(), hashlib.sha256).hexdigest()
    return {"sign": sign, "signTimestamp": sign_ts}


def _api(endpoint, params=None, signed=True):
    params = params or {}
    # 清理空值
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    url = f"{BASE_URL}{API_PREFIX}{endpoint}"
    if clean:
        url += "?" + urllib.parse.urlencode(clean)
    headers = dict(UA)
    if signed:
        headers.update(_sign_headers(clean))
    req = urllib.request.Request(url, headers=headers)
    resp = json.load(urllib.request.urlopen(req, timeout=25, context=CTX))
    if resp.get("code") != 0:
        sys.stderr.write(f"[kuaishou] API error: code={resp.get('code')}, msg={resp.get('message', '')}\n")
        return {}
    return resp.get("result", {})


def _strip(s):
    if not s:
        return ""
    import html as _html
    t = re.sub(r"(?i)<br\s*/?>", "\n", str(s))
    t = re.sub(r"(?i)</(p|li|div|h[1-6])>", "\n", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = _html.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n\s*\n\s*\n+", "\n\n", t).strip()


def fetch(keyword="", pages=3, page_size=100):
    out = []
    for pg in range(1, pages + 1):
        params = {
            "pageNum": pg,
            "pageSize": page_size,
            "positionNatureCode": "C001",  # 全职=社招
        }
        if keyword:
            params["name"] = keyword
        result = _api("/api/v1/open/positions/simple", params)
        jobs = result.get("list", [])
        if not jobs:
            break
        for j in jobs:
            jid = str(j.get("id", ""))
            # 地点
            loc_codes = j.get("workLocationsCode") or []
            if not loc_codes and j.get("workLocationCode"):
                loc_codes = [j["workLocationCode"]]
            loc_names = [LOCATION_MAP.get(c, c) for c in loc_codes if c]
            # 更新时间: "2026.07.23T20:48:08-000+08:00" → "2026-07-23"
            upd = str(j.get("updateTime", "") or "")
            date = upd.replace(".", "-")[:10] if upd else ""
            # 部门
            dept = j.get("departmentCode", "") or ""
            # 职位类别
            cat_code = j.get("positionCategoryCode", "") or ""
            cat_name = CATEGORY_MAP.get(cat_code, cat_code)
            desc_raw = j.get("description", "") or j.get("duty", "") or j.get("jobDescription", "") or ""
            req_raw = (j.get("requirement", "") or j.get("qualification", "")
                       or j.get("Requirement", "") or j.get("jobRequirement", "") or "")
            # If no separate requirement, split by headers or sentence keywords
            if not req_raw.strip() and desc_raw.strip():
                _d, _r = split_jd(desc_raw)
                if _r.strip():
                    desc_raw = _d
                    req_raw = _r
            out.append({
                "title": j.get("name", ""),
                "company": "快手",
                "location": ", ".join(loc_names),
                "dept": cat_name or dept,
                "type": "全职",
                "date": date,
                "comp": "",
                "jd": "\n\n".join(x for x in [_strip(desc_raw), _strip(req_raw)] if x),
                "responsibility": _strip(desc_raw),
                "requirement": _strip(req_raw),
                "url": f"{BASE_URL}/#/official/social/job-info/{jid}",
                "id": jid,
            })
        total = result.get("total", 0)
        if len(out) >= total or len(jobs) < page_size:
            break
    return out


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else ""
    pg = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    print(json.dumps(fetch(kw, pg), ensure_ascii=False))
