#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Beisen (zhiye.com) parser -- NOT YET IMPLEMENTED.

The companies in companies.seed marked as 'beisen' type use Beisen iTalent SPA
(modern client-rendered portal, e.g. dreame.zhiye.com, boe.zhiye.com).

These portals load data via internal JS APIs served from CDN
(acdn.bstatics.com) and do NOT expose a simple public REST endpoint.

A working parser would require either:
  1. Playwright / headless browser to render the SPA and intercept API calls
  2. Reverse-engineering the internal API from the JS chunk files

Until one of those paths is implemented, beisen-type companies are skipped
during seed loading. See web/app.py:_load_seed_companies().
"""
import sys
import json

if __name__ == "__main__":
    sys.stderr.write(
        "[beisen] Beisen iTalent SPA portals are not supported by pure-urllib.\n"
        "[beisen] These portals need Playwright/headless browser support.\n"
        "[beisen] Companies of type 'beisen' are skipped during seed loading.\n"
    )
    print(json.dumps([]))
