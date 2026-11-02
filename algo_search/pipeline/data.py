"""Data for the 12-month search: Dukascopy daily and hourly bid/ask candles for a multi-asset universe.

  python pipeline/data.py fetch [--symbols ...]   # download what is missing (shared cache: pa_sr_hybrid/data/raw)
  python pipeline/data.py build [--symbols ...]   # daily bars and spreads -> data/

Daily bars are bid prices, from Dukascopy's yearly files of daily candles (2017-2025) and, for 2026, from its
monthly files of hourly candles. Sunday-evening quotes are folded into Monday. The spread of each instrument is the
median ask - bid of its hourly bid and ask candles in four months spread across the test window (SPREAD_MONTHS).
Symbols the feed does not have come back 404 and are dropped.
"""
import argparse
import lzma
import os
import pickle
import random
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")
RAW = os.path.join(os.path.dirname(ROOT), "pa_sr_hybrid", "data", "raw")  # shared with the earlier studies

TEST_START, TEST_END = pd.Timestamp("2025-11-01"), pd.Timestamp("2026-10-30")  # the last 12 months (52 weeks)
FIRST_YEAR, LAST_FULL_YEAR = 2017, 2025
RECENT = pd.period_range("2026-01", "2026-10", freq="M")  # 2026 daily bars come from monthly hourly files
SPREAD_MONTHS = [pd.Period(m, "M") for m in ("2025-11", "2026-02", "2026-06", "2026-10")]
COLS = ["open", "high", "low", "close"]
MAX_GAP_DAYS = 7

# symbol -> (label, asset class, price scale). The scale only changes how prices print: returns, R and leverage
# are ratios and do not depend on it.
UNIVERSE = {
    **{s: (f"{s[:3]}/{s[3:]}", "FX", 1e3 if "JPY" in s else 1e5) for s in [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD",
        "EURJPY", "GBPJPY", "EURGBP", "EURCHF", "AUDJPY", "EURAUD", "GBPCHF", "AUDNZD", "CADJPY", "EURCAD"]},
    "XAUUSD": ("Gold", "Metal", 1e3), "XAGUSD": ("Silver", "Metal", 1e3), "COPPERCMDUSD": ("Copper", "Metal", 1e3),
    "XPTCMDUSD": ("Platinum", "Metal", 1e3), "XPDCMDUSD": ("Palladium", "Metal", 1e3),
    "BRENTCMDUSD": ("Brent crude", "Energy", 1e3), "LIGHTCMDUSD": ("WTI crude", "Energy", 1e3),
    "GASCMDUSD": ("Natural gas", "Energy", 1e3), "DIESELCMDUSD": ("Gasoil", "Energy", 1e3),
    "COCOACMDUSD": ("Cocoa", "Agri", 1e3), "COFFEECMDUSX": ("Coffee", "Agri", 1e3),
    "COTTONCMDUSX": ("Cotton", "Agri", 1e3), "ORANGEJUICECMDUSX": ("Orange juice", "Agri", 1e3),
    "SOYBEANCMDUSX": ("Soybeans", "Agri", 1e3), "SUGARCMDUSD": ("Sugar", "Agri", 1e3),
    "USA500IDXUSD": ("S&P 500", "Index", 1e3), "USATECHIDXUSD": ("Nasdaq-100", "Index", 1e3),
    "USA30IDXUSD": ("Dow 30", "Index", 1e3), "USSC2000IDXUSD": ("Russell 2000", "Index", 1e3),
    "DEUIDXEUR": ("DAX 40", "Index", 1e3), "FRAIDXEUR": ("CAC 40", "Index", 1e3),
    "GBRIDXGBP": ("FTSE 100", "Index", 1e3), "EUSIDXEUR": ("Euro Stoxx 50", "Index", 1e3),
    "ESPIDXEUR": ("IBEX 35", "Index", 1e3), "CHEIDXCHF": ("SMI", "Index", 1e3), "NLDIDXEUR": ("AEX", "Index", 1e3),
    "JPNIDXJPY": ("Nikkei 225", "Index", 1e3), "AUSIDXAUD": ("ASX 200", "Index", 1e3),
    "HKGIDXHKD": ("Hang Seng", "Index", 1e3), "CHIIDXUSD": ("China A50", "Index", 1e3),
    "BUNDTREUR": ("Euro Bund", "Bond", 1e3), "USTBONDTRUSD": ("US T-Bond", "Bond", 1e3),
    "UKGILTTRGBP": ("UK Gilt", "Bond", 1e3),
    "BTCUSD": ("Bitcoin", "Crypto", 1e1), "ETHUSD": ("Ether", "Crypto", 1e1),
}


# --------------------------------------------------------------------------- download
def raw_path(sym, kind, side, year, month=None):
    stem = f"{year}" if kind == "d1" else f"{year}-{month:02d}"
    return os.path.join(RAW, sym, f"{stem}_{side}_{kind}.bi5")


def raw_url(sym, kind, side, year, month=None):
    base = f"https://datafeed.dukascopy.com/datafeed/{sym}/{year}"
    return f"{base}/{side}_candles_day_1.bi5" if kind == "d1" else f"{base}/{month - 1:02d}/{side}_candles_hour_1.bi5"


def jobs_for(sym):
    jobs = [("d1", sym, "BID", y, None) for y in range(FIRST_YEAR, LAST_FULL_YEAR + 1)]
    jobs += [("h1", sym, "BID", p.year, p.month) for p in RECENT]
    return jobs + [("h1", sym, side, p.year, p.month) for p in SPREAD_MONTHS for side in ("BID", "ASK")
                   if not (side == "BID" and p in RECENT)]


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
            data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                          timeout=60).read()
            if data:
                lzma.decompress(data)  # validate before saving
            open(fn, "wb").write(data if data else b"EMPTY")
            return "ok"
        except urllib.error.HTTPError as ex:
            if ex.code == 404:  # before the instrument's history starts, or not on the feed
                open(fn, "wb").write(b"MISSING")
                return "missing"
            err = f"HTTP {ex.code}"
        except Exception as ex:  # resets, timeouts, truncated files
            err = repr(ex)[:80]
        time.sleep(min(60, 2 + 1.5 * attempt) + random.uniform(0, 4))
    return "FAILED " + err


def download(symbols, workers=6):
    todo = [j for s in symbols for j in jobs_for(s) if not have(j)]
    print(f"{len(todo)} files to fetch", flush=True)
    counts, t0 = {}, time.time()
    with ThreadPoolExecutor(workers) as ex:
        for i, res in enumerate(ex.map(fetch, todo), 1):
            counts[res.split()[0]] = counts.get(res.split()[0], 0) + 1
            if i % 50 == 0 or i == len(todo):
                print(f"{i}/{len(todo)} {counts} {time.time() - t0:.0f}s", flush=True)


# --------------------------------------------------------------------------- daily bars and spreads
def decode(path, start, scale):
    raw = open(path, "rb").read() if os.path.exists(path) else b"MISSING"
    if raw in (b"", b"EMPTY", b"MISSING"):
        return pd.DataFrame(columns=COLS + ["volume"], dtype=float)
    buf = lzma.decompress(raw)
    n = len(buf) // 24
    a = np.frombuffer(buf[: n * 24], dtype=np.dtype([("t", ">i4"), ("o", ">i4"), ("c", ">i4"), ("l", ">i4"),
                                                    ("h", ">i4"), ("v", ">f4")]))
    idx = pd.Timestamp(start, tz="UTC") + pd.to_timedelta(a["t"].astype(np.int64), unit="s")
    df = pd.DataFrame({"open": a["o"] / scale, "high": a["h"] / scale, "low": a["l"] / scale,
                       "close": a["c"] / scale, "volume": a["v"].astype(float)}, index=idx)
    return df[df["volume"] > 0]  # closed-market periods are padded with zero-volume candles


def candles(sym, kind, side, year, month=None):
    start = f"{year}-01-01" if kind == "d1" else f"{year}-{month:02d}-01"
    return decode(raw_path(sym, kind, side, year, month), start, UNIVERSE[sym][2])


def build(sym):
    """Daily bid bars (Sunday folded into Monday) and the median hourly spread over the window."""
    parts = [candles(sym, "d1", "BID", y) for y in range(FIRST_YEAR, LAST_FULL_YEAR + 1)]
    parts += [candles(sym, "h1", "BID", p.year, p.month) for p in RECENT]
    df = pd.concat([p for p in parts if len(p)]).sort_index() if any(len(p) for p in parts) else pd.DataFrame()
    q = [candles(sym, "h1", "BID", p.year, p.month).join(candles(sym, "h1", "ASK", p.year, p.month)[["open"]],
                                                         rsuffix="_ask", how="inner") for p in SPREAD_MONTHS]
    q = pd.concat(q)
    if df.empty or q.empty:
        return None
    day = df.index.tz_convert("UTC").tz_localize(None).normalize()
    wd = day.dayofweek
    day = day + pd.to_timedelta(np.where(wd == 6, 1, np.where(wd == 5, -1, 0)), unit="D")
    d = df.groupby(day).agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    gaps = d.index.to_series().diff().dt.days
    if (gaps > MAX_GAP_DAYS).any():
        d = d.loc[gaps[gaps > MAX_GAP_DAYS].index[-1]:]  # start after the last feed hole
    spread = float((q["open_ask"] - q["open"]).clip(lower=0).median())
    return d, spread


def load(sym):
    return pickle.load(open(os.path.join(DATA, f"{sym}_d1.pkl"), "rb"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["fetch", "build"])
    ap.add_argument("--symbols", nargs="*", default=list(UNIVERSE))
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    if args.step == "fetch":
        download(args.symbols, args.workers)
        return
    os.makedirs(DATA, exist_ok=True)
    rows = []
    for sym in args.symbols:
        res = build(sym)
        if res is None:
            rows.append(dict(symbol=sym, label=UNIVERSE[sym][0], bars=0))
            continue
        d, spread = res
        pickle.dump((d, spread), open(os.path.join(DATA, f"{sym}_d1.pkl"), "wb"))
        rows.append(dict(symbol=sym, label=UNIVERSE[sym][0], cls=UNIVERSE[sym][1], bars=len(d),
                         first=d.index[0].date(), last=d.index[-1].date(), last_close=d["close"].iloc[-1],
                         spread=spread, spread_pct=100 * spread / d["close"].iloc[-1]))
    inv = pd.DataFrame(rows)
    os.makedirs(RESULTS, exist_ok=True)
    inv.to_csv(os.path.join(RESULTS, "universe.csv"), index=False)
    with pd.option_context("display.width", 200):
        print(inv.to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
