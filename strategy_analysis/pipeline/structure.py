"""Market-structure helpers: 15M fib legs, FVGs, order blocks, session levels."""
import numpy as np
import pandas as pd

from common import atr, pivots, resample

BAR = pd.Timedelta(minutes=15)


class Structure:
    """Pre-computes 15M bars + fractal pivots so legs can be queried at any minute without look-ahead."""

    def __init__(self, m1, pivot_n=2, min_leg_atr=0.0):
        self.m1 = m1
        self.m15 = resample(m1, "15min")
        self.pivot_n = pivot_n
        self.min_leg_atr = min_leg_atr
        ph, pl = pivots(self.m15, pivot_n, pivot_n)
        self.piv_hi_t = self.m15.index[ph.values]
        self.piv_lo_t = self.m15.index[pl.values]
        # a pivot at bar i is only known once bar i+n has closed
        self.confirm_delay = BAR * (pivot_n + 1)
        self.atr15 = atr(self.m15).shift(1)  # ATR of the last completed bar, labelled by the current bar

    def legs(self, t0, direction, lookback_h=30):
        """All valid fib legs at minute t0, most recent anchor last.

        long : anchor = confirmed 15M pivot low not broken since, extreme = highest high since anchor
        short: anchor = confirmed 15M pivot high not broken since, extreme = lowest low since anchor
        Legs smaller than min_leg_atr x ATR(14, 15M) are ignored.
        """
        min_size = self.min_leg_atr * self.atr15.asof(t0) if self.min_leg_atr else 0.0
        start = t0 - pd.Timedelta(hours=lookback_h)
        cands = self.piv_lo_t if direction == "long" else self.piv_hi_t
        cands = cands[(cands >= start) & (cands + self.confirm_delay <= t0)]
        seg_all = self.m1.loc[start: t0 - pd.Timedelta(minutes=1)]
        out = []
        for tb in cands:
            seg = seg_all.loc[tb:]
            if len(seg) == 0:
                continue
            if direction == "long":
                anchor = self.m15.at[tb, "low"]
                if seg["low"].min() < anchor - 1e-9:
                    continue  # anchor already traded through: leg invalid
                ext, t_ext = seg["high"].max(), seg["high"].idxmax()
            else:
                anchor = self.m15.at[tb, "high"]
                if seg["high"].max() > anchor + 1e-9:
                    continue
                ext, t_ext = seg["low"].min(), seg["low"].idxmin()
            if abs(ext - anchor) < min_size:
                continue
            out.append({"anchor_t": tb, "anchor": anchor, "ext_t": t_ext, "ext": ext, "size": abs(ext - anchor)})
        return out

    def leg_for_entry(self, t0, direction, entry, fib=None, lookback_h=30):
        """Most recent valid leg at t0 and the retracement ratio of `entry` on it (+ best-matching leg if fib given)."""
        legs = self.legs(t0, direction, lookback_h)
        if not legs:
            return None, None
        for lg in legs:
            lg["ratio"] = (lg["ext"] - entry) / (lg["ext"] - lg["anchor"]) if lg["size"] > 0 else np.nan
        recent = legs[-1]
        best = min(legs, key=lambda lg: abs(lg["ratio"] - fib)) if fib is not None else None
        return recent, best


def fvgs(bars, direction, start, end):
    """Three-candle fair value gaps formed between start and end. Returns list of (time, low, high)."""
    b = bars.loc[start:end]
    out = []
    for i in range(2, len(b)):
        if direction == "long" and b["low"].iloc[i] > b["high"].iloc[i - 2]:
            out.append((b.index[i - 1], b["high"].iloc[i - 2], b["low"].iloc[i]))
        if direction == "short" and b["high"].iloc[i] < b["low"].iloc[i - 2]:
            out.append((b.index[i - 1], b["high"].iloc[i], b["low"].iloc[i - 2]))
    return out


def order_blocks(bars, direction, start, end):
    """Last opposite-colour candle before a candle that closes beyond its high (long) / low (short)."""
    b = bars.loc[start:end]
    out = []
    for i in range(1, len(b)):
        prev, cur = b.iloc[i - 1], b.iloc[i]
        if direction == "long" and prev["close"] < prev["open"] and cur["close"] > prev["high"]:
            out.append((b.index[i - 1], prev["low"], prev["high"]))
        if direction == "short" and prev["close"] > prev["open"] and cur["close"] < prev["low"]:
            out.append((b.index[i - 1], prev["low"], prev["high"]))
    return out


def zone_hit(zones, price, tol=0.0):
    return any(lo - tol <= price <= hi + tol for _, lo, hi in zones)


def session_levels(m1, daily, t0):
    """Key opens and ranges relevant at minute t0 (New York time). `daily` = 18:00-anchored session bars."""
    day = t0.normalize()
    prev_globex_open = day - pd.Timedelta(hours=6)  # 18:00 previous evening
    asia = m1.loc[day - pd.Timedelta(hours=4): day - pd.Timedelta(minutes=1)]  # 20:00-00:00
    london = m1.loc[day + pd.Timedelta(hours=2): t0 - pd.Timedelta(minutes=1)]
    overnight = m1.loc[prev_globex_open: t0 - pd.Timedelta(minutes=1)]
    prev_sessions = daily[daily.index < prev_globex_open - pd.Timedelta(hours=1)]
    prev_day = prev_sessions.iloc[-1] if len(prev_sessions) else None

    def first_open(ts):
        w = m1.loc[ts: ts + pd.Timedelta(minutes=5)]
        return w["open"].iloc[0] if len(w) else np.nan

    return {
        "open_1800": first_open(prev_globex_open),
        "open_0000": first_open(day),
        "asia_high": asia["high"].max() if len(asia) else np.nan,
        "asia_low": asia["low"].min() if len(asia) else np.nan,
        "london_high_so_far": london["high"].max() if len(london) else np.nan,
        "london_low_so_far": london["low"].min() if len(london) else np.nan,
        "overnight_high": overnight["high"].max() if len(overnight) else np.nan,
        "overnight_low": overnight["low"].min() if len(overnight) else np.nan,
        "pdh": prev_day["high"] if prev_day is not None else np.nan,
        "pdl": prev_day["low"] if prev_day is not None else np.nan,
    }


def candle_pattern(prev, cur):
    """Simple candle pattern label for `cur` given the previous candle."""
    rng = cur["high"] - cur["low"]
    if rng <= 0:
        return "none"
    body = abs(cur["close"] - cur["open"])
    upper = cur["high"] - max(cur["open"], cur["close"])
    lower = min(cur["open"], cur["close"]) - cur["low"]
    if cur["close"] > cur["open"] and prev["close"] < prev["open"] and cur["close"] >= prev["open"] and cur["open"] <= prev["close"]:
        return "bullish_engulfing"
    if cur["close"] < cur["open"] and prev["close"] > prev["open"] and cur["close"] <= prev["open"] and cur["open"] >= prev["close"]:
        return "bearish_engulfing"
    if lower >= 2 * body and lower >= 0.6 * rng:
        return "bullish_pin"
    if upper >= 2 * body and upper >= 0.6 * rng:
        return "bearish_pin"
    if cur["high"] <= prev["high"] and cur["low"] >= prev["low"]:
        return "inside_bar"
    if body <= 0.1 * rng:
        return "doji"
    return "bull_candle" if cur["close"] > cur["open"] else "bear_candle"
