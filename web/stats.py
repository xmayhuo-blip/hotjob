#!/usr/bin/env python3
"""hotjob page view counter using SQLite."""
import os
import sqlite3
import threading
import time
_DB_PATH = "/tmp/hotjob_pageviews.db"
_lock = threading.Lock()
def _get_conn():
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn
def _init():
    with _get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS pageviews (id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT NOT NULL DEFAULT '/', visited_at REAL NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS stats_meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL DEFAULT 0)")
        conn.execute("INSERT OR IGNORE INTO stats_meta (key, value) VALUES ('total_views', 0)")
        conn.commit()
def record_view(path="/"):
    with _lock:
        with _get_conn() as conn:
            conn.execute("INSERT INTO pageviews (path, visited_at) VALUES (?, ?)", (path, time.time()))
            conn.execute("UPDATE stats_meta SET value = value + 1 WHERE key = 'total_views'")
            conn.commit()
def get_total_views():
    with _lock:
        with _get_conn() as conn:
            row = conn.execute("SELECT value FROM stats_meta WHERE key = 'total_views'").fetchone()
            return row[0] if row else 0
def get_today_views():
    today_start = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, 0))
    with _lock:
        with _get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM pageviews WHERE visited_at >= ?", (today_start,)).fetchone()
            return row[0] if row else 0
def get_stats():
    return {"total_views": get_total_views(), "today_views": get_today_views()}
_init()
