"""Download Dukascopy 1-minute bid (and optionally ask) candles, one file per instrument and day.

  python pipeline/fetch_m1.py --symbols USATECHIDXUSD USA500IDXUSD --start 2024-09-02 --end 2026-09-30

Files are cached under data/raw/<symbol>/<YYYY-MM-DD>_<SIDE>_m1.bi5 so re-runs only fetch what is
missing. Weekends are skipped. The feed throttles hard (HTTP 503, dropped connections), so
requests run on a few threads with jittered backoff; failures are retried on the next run.
"""
import argparse
import datetime as dt
import lzma
import os
import random
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")


def path(sym, day, side):
    return os.path.join(RAW, sym, f"{day.isoformat()}_{side}_m1.bi5")


def url(sym, day, side):
    return (f"https://datafeed.dukascopy.com/datafeed/{sym}/{day.year}/{day.month - 1:02d}/{day.day:02d}/"
            f"{side}_candles_min_1.bi5")


def fetch(job):
    sym, day, side = job
    fn = path(sym, day, side)
    if os.path.exists(fn) and os.path.getsize(fn) > 0:
        return "cached"
    os.makedirs(os.path.dirname(fn), exist_ok=True)
    err = ""
    for attempt in range(20):
        try:
            req = urllib.request.Request(url(sym, day, side), headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            if data:
                lzma.decompress(data)  # validate before saving
            with open(fn, "wb") as f:
                f.write(data if data else b"EMPTY")
            return "ok"
        except urllib.error.HTTPError as ex:
            if ex.code == 404:
                with open(fn, "wb") as f:
                    f.write(b"MISSING")
                return "missing"
            err = f"HTTP {ex.code}"
        except Exception as ex:
            err = repr(ex)[:80]
        time.sleep(min(60, 2 + 1.5 * attempt) + random.uniform(0, 4))
    return "FAILED " + err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--start", default="2024-09-02")
    ap.add_argument("--end", default="2026-09-30")
    ap.add_argument("--sides", nargs="+", default=["BID"])
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--reverse", action="store_true")
    args = ap.parse_args()
    d, end, days = dt.date.fromisoformat(args.start), dt.date.fromisoformat(args.end), []
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += dt.timedelta(days=1)
    jobs = [(s, day, side) for s in args.symbols for side in args.sides for day in days]
    if args.reverse:
        jobs = jobs[::-1]
    todo = [j for j in jobs if not (os.path.exists(path(*j)) and os.path.getsize(path(*j)) > 0)]
    print(f"{len(jobs)} files, {len(todo)} to fetch", flush=True)
    counts, t0 = {}, time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        for i, res in enumerate(ex.map(fetch, todo), 1):
            k = res.split()[0]
            counts[k] = counts.get(k, 0) + 1
            if i % 50 == 0 or i == len(todo):
                print(f"{i}/{len(todo)} {counts} {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
