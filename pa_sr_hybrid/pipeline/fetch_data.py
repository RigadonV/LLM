"""Step 1: download Dukascopy bid and ask candles and build data/<symbol>_d1.csv.gz.

  python pipeline/fetch_data.py                  # yearly daily files 2007-2025 + monthly hourly files Jan-Sep 2026
  python pipeline/fetch_data.py --needed         # hourly months listed in results/hourly_needed.csv (from backtest.py)

Files are cached under data/raw/<symbol>/ so re-runs only fetch what is missing. The feed
rate-limits (HTTP 503) and drops slow connections, so requests go through a few threads with
jittered backoff; anything that still fails is reported and picked up by the next run.
"""
import argparse
import lzma
import os
import random
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from common import INSTRUMENTS, LAST_FULL_YEAR, RECENT_MONTHS, RESULTS_DIR, build_daily, raw_path, raw_url


def base_jobs(symbols):
    jobs = []
    for sym in symbols:
        for y in range(INSTRUMENTS[sym][4], LAST_FULL_YEAR + 1):
            jobs += [("d1", sym, side, y, None) for side in ("BID", "ASK")]
        jobs += [("h1", sym, side, p.year, p.month) for p in RECENT_MONTHS for side in ("BID", "ASK")]
    return jobs


def needed_jobs():
    need = pd.read_csv(os.path.join(RESULTS_DIR, "hourly_needed.csv"))
    return [("h1", r.symbol, side, int(r.year), int(r.month)) for r in need.itertuples() for side in ("BID", "ASK")]


def have(job):
    kind, sym, side, y, m = job
    fn = raw_path(sym, kind, side, y, m)
    return os.path.exists(fn) and os.path.getsize(fn) > 0


def fetch(job):
    kind, sym, side, y, m = job
    fn, url = raw_path(sym, kind, side, y, m), raw_url(sym, kind, side, y, m)
    if have(job):
        return "cached"
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    err = ""
    for attempt in range(20):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            if data:
                lzma.decompress(data)  # validate before saving
            with open(fn, "wb") as f:
                f.write(data if data else b"EMPTY")
            return "ok"
        except urllib.error.HTTPError as ex:
            if ex.code == 404:  # before the instrument's history starts
                with open(fn, "wb") as f:
                    f.write(b"MISSING")
                return "missing"
            err = f"HTTP {ex.code}"
        except Exception as ex:  # resets, timeouts, truncated files
            err = repr(ex)[:80]
        time.sleep(min(60, 2 + 1.5 * attempt) + random.uniform(0, 4))
    return "FAILED " + err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=list(INSTRUMENTS))
    ap.add_argument("--needed", action="store_true")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()
    jobs = needed_jobs() if args.needed else base_jobs(args.symbols)
    todo = [j for j in jobs if not have(j)]
    print(f"{len(jobs)} files, {len(todo)} to fetch", flush=True)
    counts, t0 = {}, time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        for i, res in enumerate(ex.map(fetch, todo), 1):
            key = res.split()[0]
            counts[key] = counts.get(key, 0) + 1
            if i % 25 == 0 or i == len(todo):
                print(f"{i}/{len(todo)} {counts} {time.time() - t0:.0f}s", flush=True)
    if counts.get("FAILED"):
        print("some files failed: run again to retry them", file=sys.stderr)
    if not args.no_build and not args.needed:
        for sym in args.symbols:
            print(sym, build_daily(sym), flush=True)


if __name__ == "__main__":
    main()
