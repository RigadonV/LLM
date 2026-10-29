"""Shared helpers: journal loading, Dukascopy price data, resampling and indicators."""
import datetime as dt
import glob
import lzma
import os
import re

import numpy as np
import openpyxl
import pandas as pd

ET = "America/New_York"
PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PIPELINE_DIR)
DATA_DIR = os.path.join(ROOT, "data")        # price caches (git-ignored, rebuilt by fetch_data.py)
RESULTS_DIR = os.path.join(ROOT, "results")  # analysis outputs

# Leg definition selected by pipeline/leg_definition.py (see results/leg_definition_test.csv)
LEG_PIVOT_N = 2        # 15M fractal: 2 bars each side
LEG_MIN_ATR = 1.5      # ignore legs smaller than 1.5 x ATR(14) on 15M
M1_CACHE = os.path.join(DATA_DIR, "USATECHIDXUSD_m1.csv.gz")
H1_CACHE = os.path.join(DATA_DIR, "USATECHIDXUSD_h1.csv.gz")
PRICE_SCALE = 1000.0  # Dukascopy stores USATECHIDXUSD prices as integers x1000

JOURNAL_COLUMNS = [
    "date", "instrument", "fib_level", "result", "rr", "mae_pts", "mfe_r", "minutes", "entry_time",
    "fib15_drawn", "trend_aligned", "pa_type", "fvg_tf", "ob_tf", "key_open", "dow", "week_of_month",
    "news", "rating", "notes",
]
URL_RE = re.compile(r"https?://\S+")


# --------------------------------------------------------------------------- journal
def load_journal(path):
    """Read the 'Trade Log' sheet into one row per trade with tz-aware ET entry/exit times."""
    wb = openpyxl.load_workbook(path, data_only=True)
    rows = list(wb["Trade Log"].iter_rows(values_only=True))
    recs = []
    for sheet_row, r in enumerate(rows[1:], start=2):
        if r[1] is None:  # legend block / blank rows have no instrument
            continue
        rec = dict(zip(JOURNAL_COLUMNS, r[:20]))
        rec["trade_id"] = sheet_row
        text = " ".join(str(v) for v in r[19:] if v not in (None, ""))
        urls = URL_RE.findall(text)
        rec["chart_url"] = urls[0] if urls else ""
        rec["notes"] = URL_RE.sub("", text).strip()
        recs.append(rec)
    df = pd.DataFrame(recs)
    df["date"] = pd.to_datetime(df["date"])
    entry = [pd.Timestamp.combine(d.date(), t) for d, t in zip(df["date"], df["entry_time"])]
    df["entry_et"] = pd.DatetimeIndex(entry).tz_localize(ET)
    df["exit_et"] = df["entry_et"] + pd.to_timedelta(df["minutes"], unit="m")
    df["key_open"] = df["key_open"].map(lambda v: v.strftime("%H:%M") if isinstance(v, dt.time) else v)
    df["dow"] = df["date"].dt.strftime("%a")
    df["week_of_month"] = np.ceil(df["date"].dt.day / 7).astype(int)
    df["entry_time"] = df["entry_time"].map(lambda t: t.strftime("%H:%M"))
    cols = ["trade_id", "date", "entry_et", "exit_et"] + [c for c in JOURNAL_COLUMNS if c not in ("date",)] + ["chart_url"]
    return df[cols].sort_values(["entry_et", "trade_id"]).reset_index(drop=True)


# --------------------------------------------------------------------------- price data
def decode_bi5(path, start_utc):
    """Decode a Dukascopy candle .bi5 file (records: sec offset, open, close, low, high, volume)."""
    raw = open(path, "rb").read()
    if raw in (b"", b"EMPTY"):
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    buf = lzma.decompress(raw)
    n = len(buf) // 24
    arr = np.frombuffer(buf[: n * 24], dtype=np.dtype([("t", ">i4"), ("o", ">i4"), ("c", ">i4"), ("l", ">i4"), ("h", ">i4"), ("v", ">f4")]))
    idx = pd.Timestamp(start_utc, tz="UTC") + pd.to_timedelta(arr["t"].astype(np.int64), unit="s")
    df = pd.DataFrame({
        "open": arr["o"] / PRICE_SCALE, "high": arr["h"] / PRICE_SCALE, "low": arr["l"] / PRICE_SCALE,
        "close": arr["c"] / PRICE_SCALE, "volume": arr["v"].astype(float),
    }, index=idx)
    # Dukascopy pads closed-market minutes with flat zero-volume candles; drop them
    flat = (df["volume"] == 0) & (df["high"] == df["low"])
    return df[~flat]


def build_cache(raw_dir, kind="m1"):
    """Concatenate downloaded .bi5 files into a single gzip CSV (UTC timestamps)."""
    frames = []
    for fn in sorted(glob.glob(os.path.join(raw_dir, "*.bi5"))):
        stem = os.path.basename(fn).split("_")[0]
        start = stem if kind == "m1" else stem + "-01"
        frames.append(decode_bi5(fn, start))
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated()]
    os.makedirs(DATA_DIR, exist_ok=True)
    out = M1_CACHE if kind == "m1" else H1_CACHE
    df.to_csv(out, index_label="time_utc", float_format="%.3f", compression="gzip")
    return out, len(df)


def load_prices(kind="m1"):
    """Load cached candles indexed by tz-aware New York time."""
    path = M1_CACHE if kind == "m1" else H1_CACHE
    df = pd.read_csv(path, parse_dates=["time_utc"], index_col="time_utc")
    df.index = df.index.tz_convert(ET)
    return df


def resample(df, rule, origin=None):
    """OHLC resample on New York clock. 4H and daily bars are anchored to the 18:00 futures session open."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    if rule in ("4h", "1D"):
        # shift so that 18:00 ET becomes midnight, bucket, then shift labels back
        shifted = df.copy()
        shifted.index = shifted.index.tz_localize(None) + pd.Timedelta(hours=6)
        out = shifted.resample("4h" if rule == "4h" else "1D").agg(agg).dropna(subset=["open"])
        out.index = (out.index - pd.Timedelta(hours=6)).tz_localize(ET, ambiguous="NaT", nonexistent="shift_forward")
        return out[out.index.notna()]
    return df.resample(rule, origin=origin or "start_day").agg(agg).dropna(subset=["open"])


# --------------------------------------------------------------------------- indicators
def ema(s, n):
    return s.ewm(span=n, adjust=False).mean()


def rsi(close, n=14):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def macd(close, fast=12, slow=26, signal=9):
    line = ema(close, fast) - ema(close, slow)
    sig = ema(line, signal)
    return line, sig, line - sig


def stochastic(df, k=14, smooth_k=3, d=3):
    lo = df["low"].rolling(k).min()
    hi = df["high"].rolling(k).max()
    fast_k = 100 * (df["close"] - lo) / (hi - lo)
    slow_k = fast_k.rolling(smooth_k).mean()
    return slow_k, slow_k.rolling(d).mean()


def atr(df, n=14):
    prev = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def bollinger_pctb(close, n=20, k=2.0):
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return (close - (mid - k * sd)) / (2 * k * sd)


def add_indicators(df):
    """Standard indicator set used throughout the analysis (computed on completed bars)."""
    out = df.copy()
    for n in (20, 50, 200):
        out[f"ema{n}"] = ema(out["close"], n)
    out["rsi14"] = rsi(out["close"])
    out["macd"], out["macd_signal"], out["macd_hist"] = macd(out["close"])
    out["stoch_k"], out["stoch_d"] = stochastic(out)
    out["atr14"] = atr(out)
    out["bb_pctb"] = bollinger_pctb(out["close"])
    return out


def pivots(df, left=2, right=2):
    """Fractal swing highs/lows. A pivot is only *known* `right` bars after it forms."""
    hi, lo = df["high"].values, df["low"].values
    n = len(df)
    ph = np.zeros(n, bool)
    pl = np.zeros(n, bool)
    for i in range(left, n - right):
        win_h = hi[i - left: i + right + 1]
        win_l = lo[i - left: i + right + 1]
        ph[i] = hi[i] == win_h.max() and (win_h == hi[i]).sum() == 1
        pl[i] = lo[i] == win_l.min() and (win_l == lo[i]).sum() == 1
    return pd.Series(ph, df.index), pd.Series(pl, df.index)


def session_of(ts):
    """Session label for a New York timestamp (ICT-style kill-zone boundaries)."""
    h = ts.hour + ts.minute / 60
    if h >= 20 or h < 0:
        return "Asian"
    if 0 <= h < 2:
        return "Pre-London"
    if 2 <= h < 5:
        return "London"
    if 5 <= h < 7:
        return "London (late)"
    if 7 <= h < 9.5:
        return "NY pre-open"
    if 9.5 <= h < 16:
        return "NY"
    return "Post-NY"


def load_h1_extended(m1):
    """Hourly history from the monthly files, topped up with 1m-derived bars where the files end."""
    h1 = load_prices("h1")
    tail = resample(m1.loc[h1.index.max() + pd.Timedelta(hours=1):], "1h")
    return pd.concat([h1, tail]).sort_index()
