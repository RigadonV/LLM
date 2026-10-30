"""The rules of STRATEGY.md as code: trend, swing points, key levels, signal bars and orders.

Everything a rule uses on day t is known at the close of day t: a swing point at bar i is only
used from bar i + 5 on, when the 5 bars to its right exist.
"""
import math

import numpy as np

from common import atr

TREND_DAYS = 252     # rule 1: 12 months
PIVOT_N = 5          # rule 2: highest/lowest of the 5 bars on either side
LOOKBACK = 250       # rule 2: swings of the last 250 trading days
ZONE_ATR = 0.25      # rule 3: zone = level +/- 1/4 ATR
MIN_TOUCHES = 2      # rule 3
APPROACH_BARS = 3    # rule 4: one of the 3 previous closes on the far side of the zone
PIN_WICK = 0.5       # rule 6: wick at least half of the bar's range
STOP_ATR = 0.1       # rule 9
TARGET_R = 2.0       # rule 10
MAX_BARS = 20        # rule 10

VARIANTS = {
    # trend gate, minimum touches for a level (None = no level), signal bar, entry type, room rule
    "V0": dict(name="Trend only", trend=True, touches=None, signal="any", entry="stop", room=False),
    "V1": dict(name="S/R only", trend=False, touches=2, signal=None, entry="limit", room=True),
    "V2": dict(name="S/R + trend", trend=True, touches=2, signal=None, entry="limit", room=True),
    "V3": dict(name="PA only", trend=True, touches=None, signal="pattern", entry="stop", room=False),
    "V4": dict(name="Hybrid", trend=True, touches=2, signal="pattern", entry="stop", room=True),
    "V4a": dict(name="Hybrid without trend", trend=False, touches=2, signal="pattern", entry="stop", room=True),
    "V4b": dict(name="Hybrid without room rule", trend=True, touches=2, signal="pattern", entry="stop", room=False),
    "V4c": dict(name="Hybrid, 1-touch levels", trend=True, touches=1, signal="pattern", entry="stop", room=True),
    "V4d": dict(name="Hybrid, next-open entry", trend=True, touches=2, signal="pattern", entry="open", room=True),
}


def swing_points(high, low, n=PIVOT_N):
    """(bar index, price, is_high) of every swing point; ties go to the earliest bar."""
    out = []
    for i in range(n, len(high) - n):
        wh, wl = high[i - n: i + n + 1], low[i - n: i + n + 1]
        if np.argmax(wh) == n:
            out.append((i, high[i], True))
        if np.argmin(wl) == n:
            out.append((i, low[i], False))
    return out


def round_step(price, asset_class):
    """Forex: the big figure (100 pips). Other markets: half of the second significant digit."""
    if asset_class == "FX":
        return 1.0 if price > 20 else 0.01
    return 0.5 * 10 ** (math.floor(math.log10(price)) - 1)


class Market:
    """Daily arrays and per-day key levels of one instrument."""

    def __init__(self, d, tick, asset_class):
        self.d, self.tick, self.asset_class = d, tick, asset_class
        self.o, self.h, self.l, self.c = (d[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.atr = atr(d).to_numpy()
        self.n = len(d)
        trend = np.zeros(self.n)
        trend[TREND_DAYS:] = np.sign(self.c[TREND_DAYS:] - self.c[:-TREND_DAYS])
        self.trend = trend
        rng = self.h - self.l
        body_lo, body_hi = np.minimum(self.o, self.c), np.maximum(self.o, self.c)
        with np.errstate(invalid="ignore", divide="ignore"):
            self.bull_pin = (rng > 0) & (body_lo - self.l >= PIN_WICK * rng)
            self.bear_pin = (rng > 0) & (self.h - body_hi >= PIN_WICK * rng)
        po, pc = np.r_[np.nan, self.o[:-1]], np.r_[np.nan, self.c[:-1]]
        self.bull_eng = (pc < po) & (self.c > self.o) & (self.o <= pc) & (self.c >= po)
        self.bear_eng = (pc > po) & (self.c < self.o) & (self.o >= pc) & (self.c <= po)
        sw = swing_points(self.h, self.l)
        self.sw_idx = np.array([s[0] for s in sw], dtype=int)
        self.sw_px = np.array([s[1] for s in sw], dtype=float)
        self.sw_high = np.array([s[2] for s in sw], dtype=bool)
        self._levels = {}

    def levels(self, t, min_touches):
        """Key levels known at the close of day t: (price, touches, flipped)."""
        key = (t, min_touches)
        if key not in self._levels:
            a = np.searchsorted(self.sw_idx, t - LOOKBACK, "left")
            b = np.searchsorted(self.sw_idx, t - PIVOT_N, "right")
            px, is_high = self.sw_px[a:b], self.sw_high[a:b]
            w = ZONE_ATR * self.atr[t]
            near = np.abs(px[:, None] - px[None, :]) <= w
            touches = near.sum(axis=1)
            flipped = (near & is_high[None, :]).any(axis=1) & (near & ~is_high[None, :]).any(axis=1)
            keep = touches >= min_touches
            self._levels[key] = (px[keep], touches[keep], flipped[keep])
        return self._levels[key]

    def on_round_number(self, level):
        """Within 10% of the round-number step (10 pips in forex) of a round number."""
        step = round_step(level, self.asset_class)
        return abs(level - step * round(level / step)) <= 0.1 * step


def make_order(m, t, v):
    """The order (for day t + 1) that variant v places at the close of day t, or None."""
    if t < TREND_DAYS or not np.isfinite(m.atr[t]) or m.atr[t] <= 0:
        return None
    directions = [int(m.trend[t])] if v["trend"] else [1, -1]
    orders = [o for o in (_order(m, t, v, s) for s in directions if s != 0) if o is not None]
    if not orders:
        return None
    # without a trend gate a day can set up both ways: take the one closest to the market
    return min(orders, key=lambda o: abs(o["price"] - m.c[t]) if o["price"] is not None else 0)


def _order(m, t, v, s):
    a, w = m.atr[t], ZONE_ATR * m.atr[t]
    hi, lo, cl = m.h[t], m.l[t], m.c[t]
    meta = {}
    if v["touches"] is not None:
        px, touches, flipped = m.levels(t, v["touches"])
        if not len(px):
            return None
    if v["signal"] is None:
        # V1/V2: limit order at the edge of the nearest key level on the far side of the market
        side = (px + w < cl) if s > 0 else (px - w > cl)
        if not side.any():
            return None
        k = np.flatnonzero(side)[np.argmax(px[side])] if s > 0 else np.flatnonzero(side)[np.argmin(px[side])]
        level = px[k]
        price = level + s * w
        stop = level - s * (w + STOP_ATR * a)
        meta = dict(level=level, touches=int(touches[k]), flipped=bool(flipped[k]))
    else:
        if v["signal"] == "pattern":
            ok = (m.bull_pin[t] or m.bull_eng[t]) if s > 0 else (m.bear_pin[t] or m.bear_eng[t])
            if not ok:
                return None
        extreme = lo if s > 0 else hi
        if v["touches"] is None:
            stop = extreme - s * STOP_ATR * a
        else:
            prev = m.c[max(0, t - APPROACH_BARS): t]
            if s > 0:
                cand = (lo <= px + w) & (cl > px) & (prev.max() > px + w)
            else:
                cand = (hi >= px - w) & (cl < px) & (prev.min() < px - w)
            if not cand.any():
                return None
            k = np.flatnonzero(cand)[np.argmin(px[cand])] if s > 0 else np.flatnonzero(cand)[np.argmax(px[cand])]
            level = px[k]
            stop = min(lo, level - w) - STOP_ATR * a if s > 0 else max(hi, level + w) + STOP_ATR * a
            meta = dict(level=level, touches=int(touches[k]), flipped=bool(flipped[k]))
        price = (hi + m.tick) if s > 0 else (lo - m.tick)
        if v["entry"] == "open":
            price = None  # filled at the next open; the room rule below uses today's close
    ref = cl if price is None else price
    risk = s * (ref - stop)
    if risk <= 0:
        return None
    target = ref + s * TARGET_R * risk
    if v["room"]:
        if s > 0:
            blocked = ((px > ref) & (px < target + w)).any()
        else:
            blocked = ((px < ref) & (px > target - w)).any()
        if blocked:
            return None
    if "level" in meta:
        meta["round_number"] = bool(m.on_round_number(meta["level"]))
    kind = {"stop": "stop", "limit": "limit", "open": "open"}[v["entry"]]
    return dict(kind=kind, dir=s, price=price, stop=stop, target=target, risk=risk, signal_t=t, atr=a, **meta)
