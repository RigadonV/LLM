"""Shared intraday tools: 1-minute data, real time-of-day spreads, and the $10k / 1%-risk account.

Prices are Dukascopy bid candles. Buys pay the spread: a long fills at bid + spread and its stop and
target are read off bid prices; a short fills at the bid and its stop and target are read off
bid + spread. The spread for each instrument and UTC hour is the median ask - bid of Dukascopy's
own hourly bid and ask candles over the test window.
"""
import glob
import lzma
import os
import pickle
import random
import time
import urllib.error
import urllib.request

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")
HYBRID_RAW = os.path.join(os.path.dirname(ROOT), "pa_sr_hybrid", "data", "raw")  # hourly bid/ask from the last study
TEST_START, TEST_END = pd.Timestamp("2024-10-01"), pd.Timestamp("2026-09-30")
SPLIT = pd.Timestamp("2025-10-01")  # year 1 = tuning, year 2 = validation
SCALE = {"USATECHIDXUSD": 1e3, "USA500IDXUSD": 1e3, "USA30IDXUSD": 1e3, "DEUIDXEUR": 1e3, "XAUUSD": 1e3,
         "GBPUSD": 1e5, "EURUSD": 1e5}
LABEL = {"USATECHIDXUSD": "Nasdaq-100", "USA500IDXUSD": "S&P 500", "USA30IDXUSD": "Dow 30", "DEUIDXEUR": "DAX 40",
         "XAUUSD": "Gold", "GBPUSD": "GBP/USD", "EURUSD": "EUR/USD"}
START_BALANCE, RISK = 10_000.0, 0.01


def decode(path, start, scale):
    raw = open(path, "rb").read()
    if raw in (b"", b"EMPTY", b"MISSING"):
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"], dtype=float)
    buf = lzma.decompress(raw)
    n = len(buf) // 24
    a = np.frombuffer(buf[: n * 24], dtype=np.dtype([("t", ">i4"), ("o", ">i4"), ("c", ">i4"), ("l", ">i4"),
                                                    ("h", ">i4"), ("v", ">f4")]))
    idx = pd.Timestamp(start, tz="UTC") + pd.to_timedelta(a["t"].astype(np.int64), unit="s")
    df = pd.DataFrame({"open": a["o"] / scale, "high": a["h"] / scale, "low": a["l"] / scale,
                       "close": a["c"] / scale, "volume": a["v"].astype(float)}, index=idx)
    return df[df["volume"] > 0]


def load_m1(sym):
    """All downloaded 1-minute bid bars of one instrument (UTC index), cached as a pickle."""
    cache = os.path.join(DATA, f"{sym}_m1.pkl")
    files = sorted(glob.glob(os.path.join(DATA, "raw", sym, "*_BID_m1.bi5")))
    if os.path.exists(cache) and os.path.getmtime(cache) > max(os.path.getmtime(f) for f in files):
        return pickle.load(open(cache, "rb"))
    df = pd.concat([decode(f, os.path.basename(f)[:10], SCALE[sym]) for f in files]).sort_index()
    df = df[~df.index.duplicated()]
    pickle.dump(df, open(cache, "wb"))
    return df


def fetch_hourly(sym, months):
    """Hourly bid/ask months for spreads, if the last study did not already download them."""
    for p in months:
        for side in ("BID", "ASK"):
            fn = os.path.join(HYBRID_RAW, sym, f"{p.year}-{p.month:02d}_{side}_h1.bi5")
            if os.path.exists(fn) and os.path.getsize(fn) > 0:
                continue
            os.makedirs(os.path.dirname(fn), exist_ok=True)
            url = f"https://datafeed.dukascopy.com/datafeed/{sym}/{p.year}/{p.month - 1:02d}/{side}_candles_hour_1.bi5"
            for attempt in range(20):
                try:
                    data = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}),
                                                  timeout=60).read()
                    lzma.decompress(data)
                    open(fn, "wb").write(data)
                    break
                except Exception:
                    time.sleep(min(60, 2 + 1.5 * attempt) + random.uniform(0, 4))


def spread_by_hour(sym):
    """Median ask - bid per UTC hour over the test window, from Dukascopy hourly bid and ask candles."""
    months = pd.period_range(TEST_START.strftime("%Y-%m"), TEST_END.strftime("%Y-%m"), freq="M")
    fetch_hourly(sym, months)
    rows = []
    for p in months:
        start = f"{p.year}-{p.month:02d}-01"
        b = decode(os.path.join(HYBRID_RAW, sym, f"{p.year}-{p.month:02d}_BID_h1.bi5"), start, SCALE[sym])
        a = decode(os.path.join(HYBRID_RAW, sym, f"{p.year}-{p.month:02d}_ASK_h1.bi5"), start, SCALE[sym])
        j = b.join(a, lsuffix="_b", rsuffix="_a", how="inner")
        rows.append(pd.DataFrame({"hour": j.index.hour, "spread": (j["open_a"] - j["open_b"]).clip(lower=0)}))
    s = pd.concat(rows).groupby("hour")["spread"].median()
    return s.reindex(range(24)).ffill().bfill()


# --------------------------------------------------------------------------- account
def account(trades, risk=RISK, start_balance=START_BALANCE, max_leverage=None):
    """Compound 1% of the current balance per trade, booked at exit in time order.

    trades needs columns entry_time, exit_time, r (net R) and optionally leverage_at_1pct (notional / balance
    if 1% were risked). With max_leverage, a trade that would need more is sized down to the cap.
    """
    t = trades.sort_values("entry_time").reset_index(drop=True)
    ev = [(row.entry_time, 0, i) for i, row in t.iterrows()] + [(row.exit_time, 1, i) for i, row in t.iterrows()]
    ev.sort(key=lambda e: (e[0], e[1]))
    bal, stake, curve = start_balance, {}, []
    for when, kind, i in ev:
        if kind == 0:
            f = risk
            if max_leverage is not None and "leverage_at_1pct" in t and t.at[i, "leverage_at_1pct"] > max_leverage:
                f = risk * max_leverage / t.at[i, "leverage_at_1pct"]
            stake[i] = f * bal
        else:
            bal += stake.pop(i) * t.at[i, "r"]
            curve.append((when, bal))
    return pd.Series([b for _, b in curve], index=pd.DatetimeIndex([w for w, _ in curve]))


def weekly_stats(curve, start=TEST_START, end=TEST_END, start_balance=START_BALANCE):
    """Week-by-week % change of the balance (weeks ending Friday), including weeks with no trades."""
    idx = curve.index.tz_convert("UTC").tz_localize(None) if curve.index.tz is not None else curve.index
    s = pd.Series(curve.values, index=idx)
    weeks = pd.date_range(start, end + pd.Timedelta(days=7), freq="W-FRI")
    bal = s.groupby(s.index.to_period("W-FRI")).last().reindex(weeks.to_period("W-FRI")).ffill().fillna(start_balance)
    prev = bal.shift(1).fillna(start_balance)
    wk = (bal / prev - 1).loc[: pd.Period(end, "W-FRI")]
    final = bal.iloc[-1]
    peak = np.maximum.accumulate(np.r_[start_balance, bal.values])
    dd = (1 - np.r_[start_balance, bal.values] / peak).max()
    years = (end - start).days / 365.25
    return dict(weeks=len(wk), avg_week_pct=100 * wk.mean(), median_week_pct=100 * wk.median(),
                compound_week_pct=100 * ((final / start_balance) ** (1 / len(wk)) - 1),
                positive_weeks_pct=100 * (wk > 0).mean(), weeks_at_4pct_pct=100 * (wk >= 0.04).mean(),
                worst_week_pct=100 * wk.min(), best_week_pct=100 * wk.max(), final_balance=final,
                total_return_pct=100 * (final / start_balance - 1), cagr_pct=100 * ((final / start_balance) ** (1 / years) - 1),
                max_drawdown_pct=100 * dd), wk


def r_stats(r):
    r = np.asarray(r)
    if not len(r):
        return dict(trades=0)
    win, loss = r[r > 0].sum(), -r[r < 0].sum()
    return dict(trades=len(r), win_rate_pct=100 * (r > 0).mean(), avg_r=r.mean(),
                profit_factor=win / loss if loss else np.nan, total_r=r.sum(), r_per_week=r.sum() / 104.4)
