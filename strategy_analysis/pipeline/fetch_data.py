"""Step 2a: download Dukascopy USATECHIDXUSD (Nasdaq-100 CFD) candles and build the local caches.

  python pipeline/fetch_data.py --start 2026-02-15 --end 2026-10-17

Downloads 1-minute bid candles (one file per UTC day) for the trade period plus warm-up, and
1-hour bid candles (one file per month) from --hourly-start for higher-timeframe trend context.
Files are cached under data/raw/ so re-runs only fetch what is missing. The Dukascopy feed
rate-limits and drops connections, so requests are spread over a few threads with backoff.
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

from common import DATA_DIR, build_cache

BASE = "https://datafeed.dukascopy.com/datafeed/USATECHIDXUSD"


def jobs_for(kind, start, end, outdir):
    jobs, d = [], start
    if kind == "m1":
        while d <= end:
            if d.weekday() != 5:  # no index data on Saturdays (UTC)
                jobs.append((f"{BASE}/{d.year}/{d.month - 1:02d}/{d.day:02d}/BID_candles_min_1.bi5",
                             os.path.join(outdir, f"{d.isoformat()}_BID_m1.bi5")))
            d += dt.timedelta(days=1)
    else:
        d = d.replace(day=1)
        while d <= end:
            jobs.append((f"{BASE}/{d.year}/{d.month - 1:02d}/BID_candles_hour_1.bi5",
                         os.path.join(outdir, f"{d.year}-{d.month:02d}_BID_h1.bi5")))
            d = (d + dt.timedelta(days=32)).replace(day=1)
    return jobs


def fetch(job):
    url, fn = job
    if os.path.exists(fn) and os.path.getsize(fn) > 0:
        return fn, "cached"
    err = ""
    for attempt in range(10):
        try:
            time.sleep(random.uniform(0, 1.5))
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
            if data:
                lzma.decompress(data)  # validate before saving
            with open(fn, "wb") as f:
                f.write(data if data else b"EMPTY")
            return fn, len(data)
        except urllib.error.HTTPError as ex:
            if ex.code == 404:  # e.g. the monthly hourly file of the current month is not published yet
                return fn, "missing"
            err = repr(ex)[:60]
            time.sleep(min(60, 2 * 2 ** attempt) + random.uniform(0, 2))
        except Exception as ex:  # rate limits / dropped tunnels: back off and retry
            err = repr(ex)[:60]
            time.sleep(min(60, 2 * 2 ** attempt) + random.uniform(0, 2))
    return fn, "FAILED " + err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-02-15")
    ap.add_argument("--end", default="2026-10-17")
    ap.add_argument("--hourly-start", default="2025-01-01")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    for kind, start in (("h1", args.hourly_start), ("m1", args.start)):
        outdir = os.path.join(DATA_DIR, "raw", kind)
        os.makedirs(outdir, exist_ok=True)
        jobs = jobs_for(kind, dt.date.fromisoformat(start), dt.date.fromisoformat(args.end), outdir)
        with ThreadPoolExecutor(args.workers) as ex:
            results = [res for _, res in ex.map(fetch, jobs)]
        failed = sum(str(r).startswith("FAILED") for r in results)
        missing = sum(r == "missing" for r in results)
        print(f"{kind}: {len(jobs)} files, {failed} failed, {missing} not published")
        print(build_cache(outdir, kind))


if __name__ == "__main__":
    main()
