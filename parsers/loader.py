#!/usr/bin/env python3
"""hotjob parser loader — 直接导入 parser 模块调用 fetch()，消除子进程开销。

对 10 家 MVP 公司使用 import-based 直调，对 seed 表扩展公司可作为后续 fallback。
"""
import os
# Parser modules check this at import time to bypass SSL verification
if os.environ.get("HIRING_RADAR_INSECURE") != "1":
    os.environ["HIRING_RADAR_INSECURE"] = "1"
import importlib
import threading
import sys

# 10 家 MVP 公司配置
# (module_name, fetch_func_name, args_tuple)
PARSER_CONFIG = {
    "tencent":    ("parsers.tencent",    "fetch",   ()),
    "bytedance":  ("parsers.bytedance",   "fetch",   ()),
    "alibaba":    ("parsers.alibaba",    "fetch",   ("", 1, 500, "talent.alibaba.com")),
    "highflyer":  ("parsers.moka",        "fetch",   ("high-flyer", 140576, "DeepSeek")),
    "zhipu":      ("parsers.feishu",     "fetch",   ("zhipu-ai.jobs.feishu.cn", "智谱AI")),
    "moonshot":   ("parsers.moka",        "fetch",   ("moonshot", 148506, "月之暗面")),
    "minimax":    ("parsers.feishu",     "fetch",   ("vrfi1sk8a0.jobs.feishu.cn", "MiniMax")),
    "kuaishou":   ("parsers.kuaishou",   "fetch",   ()),
    "lilith":     ("parsers.feishu",     "fetch",   ("lilithgames.jobs.feishu.cn", "莉莉丝")),
    "kurogame":   ("parsers.feishu",     "fetch",   ("kurogame.jobs.feishu.cn", "库洛游戏")),
}

_module_cache = {}
_lock = threading.Lock()


def _ensure_module(modname):
    """线程安全地导入并缓存模块。"""
    if modname in _module_cache:
        return _module_cache[modname]
    with _lock:
        if modname in _module_cache:
            return _module_cache[modname]
        mod = importlib.import_module(modname)
        _module_cache[modname] = mod
        return mod


def fetch_company(company_id, keyword=""):
    """直接导入 parser 模块并调用其 fetch()，返回 job list。

    Args:
        company_id: 公司标识，如 "tencent", "bytedance"
        keyword: 搜索关键词

    Returns:
        list[dict]: 岗位列表，失败时返回空列表
    """
    cfg = PARSER_CONFIG.get(company_id)
    if not cfg:
        raise ValueError(f"[loader] 未知公司: {company_id}，可选: {list(PARSER_CONFIG.keys())}")

    modname, fn_name, base_args = cfg
    try:
        mod = _ensure_module(modname)
        fn = getattr(mod, fn_name)
        args = list(base_args)
        if keyword:
            if args:
                args[0] = keyword
            else:
                args.append(keyword)
        return list(fn(*args))
    except Exception as e:
        sys.stderr.write(f"[loader] {company_id} error: {type(e).__name__}: {e}\n")
        return []


def fetch_all(keyword="", max_concurrent=3):
    """并行抓取所有 MVP 公司。

    Args:
        keyword: 搜索关键词
        max_concurrent: 最大并发数

    Returns:
        dict: {company_id: [jobs]}
    """
    results = {}
    errors = {}
    sem = threading.Semaphore(max_concurrent)
    lock = threading.Lock()

    def _fetch(cid):
        with sem:
            try:
                jobs = fetch_company(cid, keyword)
                with lock:
                    results[cid] = jobs
            except Exception as e:
                with lock:
                    errors[cid] = str(e)

    threads = []
    for cid in PARSER_CONFIG:
        t = threading.Thread(target=_fetch, args=(cid,), daemon=True)
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    return results, errors


def available_companies():
    return list(PARSER_CONFIG.keys())


def is_known(company_id):
    return company_id in PARSER_CONFIG
