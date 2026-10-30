"""Shared helpers: instrument list, Dukascopy bid/ask candles, daily bars, ATR."""
import lzma
import os

import numpy as np
import pandas as pd

PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(PIPELINE_DIR)
DATA_DIR = os.path.join(ROOT, "data")        # raw downloads + caches (git-ignored, rebuilt by fetch_data.py)
RESULTS_DIR = os.path.join(ROOT, "results")
CHARTS_DIR = os.path.join(ROOT, "charts")

# Dukascopy symbol -> label, asset class, integer price scale, pip, first year requested.
# Scales were checked against known prices (EURUSD 1.4579 and XAUUSD 833 on 1 Jan 2008,
# USA500 1426 in Jan 2013). Index and oil CFDs start later on Dukascopy; earlier files are 404.
INSTRUMENTS = {
    "EURUSD": ("EUR/USD", "FX", 1e5, 0.0001, 2007),
    "GBPUSD": ("GBP/USD", "FX", 1e5, 0.0001, 2007),
    "USDJPY": ("USD/JPY", "FX", 1e3, 0.01, 2007),
    "AUDUSD": ("AUD/USD", "FX", 1e5, 0.0001, 2007),
    "USDCAD": ("USD/CAD", "FX", 1e5, 0.0001, 2007),
    "USDCHF": ("USD/CHF", "FX", 1e5, 0.0001, 2007),
    "NZDUSD": ("NZD/USD", "FX", 1e5, 0.0001, 2007),
    "XAUUSD": ("Gold", "Commodity", 1e3, 0.1, 2007),
    "USA500IDXUSD": ("S&P 500", "Index", 1e3, 0.1, 2012),
    "USATECHIDXUSD": ("Nasdaq-100", "Index", 1e3, 0.1, 2012),
    "DEUIDXEUR": ("DAX 40", "Index", 1e3, 0.1, 2015),
    "GBRIDXGBP": ("FTSE 100", "Index", 1e3, 0.1, 2012),
    "JPNIDXJPY": ("Nikkei 225", "Index", 1e3, 1.0, 2012),
    "BRENTCMDUSD": ("Brent crude", "Commodity", 1e3, 0.01, 2010),
    "XAGUSD": ("Silver", "Commodity", 1e3, 0.001, 2007),
}
LAST_FULL_YEAR = 2025   # yearly daily files exist up to here
RECENT_MONTHS = pd.period_range("2026-01", "2026-09", freq="M")  # 2026 comes from monthly hourly files
COLS = ["open", "high", "low", "close"]
MAX_GAP_DAYS = 7  # longer gaps in a daily series are feed holes, not market holidays
# Test window: the last 24 months of data. Earlier history is only used to warm up the 12-month
# trend, the 250-day swing levels and the ATR, so the first trade can enter on TEST_START.
TEST_START, TEST_END = pd.Timestamp("2024-10-01"), pd.Timestamp("2026-09-30")


def raw_path(symbol, kind, side, year, month=None):
    """kind 'd1': yearly file of daily candles; kind 'h1': monthly file of hourly candles."""
    stem = f"{year}" if kind == "d1" else f"{year}-{month:02d}"
    return os.path.join(DATA_DIR, "raw", symbol, f"{stem}_{side}_{kind}.bi5")


def raw_url(symbol, kind, side, year, month=None):
    base = f"https://datafeed.dukascopy.com/datafeed/{symbol}/{year}"
    if kind == "d1":
        return f"{base}/{side}_candles_day_1.bi5"
    return f"{base}/{month - 1:02d}/{side}_candles_hour_1.bi5"


# --------------------------------------------------------------------------- raw files
def decode_bi5(path, start, scale):
    """Decode a Dukascopy candle .bi5 file (records: sec offset, open, close, low, high, volume)."""
    raw = open(path, "rb").read() if os.path.exists(path) else b"MISSING"
    if raw in (b"", b"EMPTY", b"MISSING"):
        return pd.DataFrame(columns=COLS + ["volume"], dtype=float)
    buf = lzma.decompress(raw)
    n = len(buf) // 24
    arr = np.frombuffer(buf[: n * 24], dtype=np.dtype([("t", ">i4"), ("o", ">i4"), ("c", ">i4"),
                                                      ("l", ">i4"), ("h", ">i4"), ("v", ">f4")]))
    idx = pd.Timestamp(start, tz="UTC") + pd.to_timedelta(arr["t"].astype(np.int64), unit="s")
    df = pd.DataFrame({"open": arr["o"] / scale, "high": arr["h"] / scale, "low": arr["l"] / scale,
                       "close": arr["c"] / scale, "volume": arr["v"].astype(float)}, index=idx)
    return df[df["volume"] > 0]  # closed-market periods are padded with zero-volume candles


def join_sides(bid, ask):
    """One frame with bid_* and ask_* columns; drop the odd crossed quote in the raw feed."""
    out = bid.add_prefix("bid_").rename(columns={"bid_volume": "volume"}).join(
        ask[COLS].add_prefix("ask_"), how="inner")
    return out[(out["ask_close"] >= out["bid_close"]) & (out["ask_high"] >= out["bid_high"])]


def hourly_month(symbol, year, month):
    """Hourly bid/ask candles of one month (used to settle which level a trade touched first)."""
    scale = INSTRUMENTS[symbol][2]
    start = f"{year}-{month:02d}-01"
    return join_sides(decode_bi5(raw_path(symbol, "h1", "BID", year, month), start, scale),
                      decode_bi5(raw_path(symbol, "h1", "ASK", year, month), start, scale))


def trading_day(index):
    """UTC date, with Sunday-evening quotes moved to Monday and stray Saturday quotes to Friday."""
    day = index.tz_convert("UTC").tz_localize(None).normalize()
    wd = day.dayofweek
    return day + pd.to_timedelta(np.where(wd == 6, 1, np.where(wd == 5, -1, 0)), unit="D")


def to_trading_days(df):
    """UTC-midnight daily bars, with the short Sunday-evening session folded into Monday (5 bars a week)."""
    df = df.sort_index()
    day = trading_day(df.index)
    agg = {}
    for side in ("bid", "ask"):
        agg.update({f"{side}_open": "first", f"{side}_high": "max", f"{side}_low": "min", f"{side}_close": "last"})
    agg["volume"] = "sum"
    out = df.groupby(day).agg(agg)
    out.index.name = "day"
    return out


def build_daily(symbol):
    """Daily bid/ask bars from the yearly files, extended through Sep 2026 with hourly files."""
    _, _, scale, _, first = INSTRUMENTS[symbol]
    parts = []
    for y in range(first, LAST_FULL_YEAR + 1):
        bid = decode_bi5(raw_path(symbol, "d1", "BID", y), f"{y}-01-01", scale)
        ask = decode_bi5(raw_path(symbol, "d1", "ASK", y), f"{y}-01-01", scale)
        if len(bid) and len(ask):
            parts.append(join_sides(bid, ask))
    recent = [hourly_month(symbol, p.year, p.month) for p in RECENT_MONTHS]
    recent = [r for r in recent if len(r)]
    if recent:
        parts.append(pd.concat(recent))
    d = to_trading_days(pd.concat(parts))
    path = os.path.join(DATA_DIR, f"{symbol}_d1.csv.gz")
    d.to_csv(path, float_format="%.6f", compression="gzip")
    return path, len(d), str(d.index.min().date()), str(d.index.max().date())


def load_daily(symbol):
    """Daily bars from the first bar after the last gap of more than MAX_GAP_DAYS.

    The index and oil CFD feeds have holes of up to 94 days before late May 2013 (and about one bar
    a week for FTSE and Nikkei in 2012); market holidays never close a market for more than 7 days.
    """
    d = pd.read_csv(os.path.join(DATA_DIR, f"{symbol}_d1.csv.gz"), parse_dates=["day"], index_col="day")
    gaps = d.index.to_series().diff().dt.days
    holes = gaps[gaps > MAX_GAP_DAYS]
    if len(holes):
        d = d.loc[holes.index[-1]:]
    for c in COLS:  # signals are read off bid prices, the way a chart is drawn
        d[c] = d[f"bid_{c}"]
    return d


def atr(df, n=14):
    prev = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()
