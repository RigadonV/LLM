"""Backtest of the OTE (optimal trade entry) strategy in OTE_Trading_Strategy.pdf: London session, last 12 months.

  python pipeline/ote.py

Market: Nasdaq-100, Dukascopy USATECHIDXUSD CFD, 1-minute bid candles; the PDF's 50-point stop fits this market.
Window: 3 Nov 2025 - 30 Oct 2026. Session: entries 02:00-09:30 New York time, as in the PDF.

The PDF's rules, made mechanical (its discretionary parts are marked *):
- 15-minute swing range. A swing high is a 15-minute candle whose high is above the K candles on each side; it is
  confirmed K candles later. A bullish range runs from the lowest low since the last swing low to a new swing
  high; a bearish range from the highest high since the last swing high to a new swing low.
- *Trend alignment / market condition: the range must break structure in its direction (a bullish range's high
  is above the swing high before the range started; mirror for bearish), so only trending legs are traded.
  Variant: also on the right side of the 1-hour 50 EMA.
- OTE zone: 0.705-0.79 retracement of the range.
- Order block / fair value gap: a 15M, 30M or 1H OB or FVG formed in the range must overlap the OTE zone. An FVG
  is a three-candle gap in the range's direction. An OB is an opposite-colour candle that price later closed
  beyond in the range's direction.
- *Key opening levels: variant only. Longs below, shorts above the New York midnight open.
- Entry: a limit order at the 0.705 level, placed when the swing is confirmed. If price is already inside the
  zone it fills at once; if it is past 0.79 the range is skipped. The order stays until filled, until price takes
  out the start of the range, until a newer range replaces it, or until 09:30.
- Stop 50 points from the fill; stop to breakeven once price reaches 2R; target 4R (variant 3R). At most 2 losses
  a day, one trade at a time. Anything still open at 16:00 New York is closed (variant: at 09:30).
Costs and fills: Dukascopy's own ask - bid by hour. Buys fill at the ask, and shorts are stopped and take profit
on the ask. Within one minute the stop counts before the target; on the entry minute only the stop is checked;
breakeven applies from the minute after 2R is reached.
Account: $10,000, 1% risk per trade, compounding (strategy_search/pipeline/intraday.py).
"""
import bisect
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "strategy_search", "pipeline"))
import intraday  # noqa: E402
from intraday import account, load_m1, spread_by_hour, weekly_stats  # noqa: E402

SYM, TZ = "USATECHIDXUSD", "America/New_York"
START, END = pd.Timestamp("2025-11-03"), pd.Timestamp("2026-10-30")
WARMUP = pd.Timestamp("2025-10-01")
SESSION, FLAT_AT = ("02:00", "09:30"), "16:00"
STOP_PTS, BE_AT_R = 50.0, 2.0
intraday.TEST_START, intraday.TEST_END = pd.Timestamp("2025-11-01"), END  # spreads measured over the window

BASE = dict(k=2, target_r=4.0, confluence=True, htf=False, midnight=False, close_at="16:00")
VARIANTS = {
    "base (as written, target 4R)": {},
    "target 3R": dict(target_r=3.0),
    "+ 1-hour 50 EMA trend filter": dict(htf=True),
    "+ midnight-open filter": dict(midnight=True),
    "swings of 1 candle each side": dict(k=1),
    "swings of 3 candles each side": dict(k=3),
    "no OB/FVG needed": dict(confluence=False),
    "close at 09:30": dict(close_at="09:30"),
}
PDF_STATS = dict(win_rate_pct=84.4, avg_mfe_r=8.4, avg_minutes=32.9, reach_3r_pct=82.1, reach_4r_pct=66.1,
                 reach_5r_pct=57.1, avg_mae_pts=11.7)


def resample(m, rule):
    return m.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def ob_fvg(b, d):
    """(low, high) of every fair value gap and order block of direction d in bars b."""
    o, h, l, c = (b[x].to_numpy() for x in ("open", "high", "low", "close"))
    out = []
    for i in range(len(b) - 2):
        if d > 0 and l[i + 2] > h[i]:
            out.append((h[i], l[i + 2]))
        elif d < 0 and h[i + 2] < l[i]:
            out.append((h[i + 2], l[i]))
    for i in range(len(b) - 1):
        if (d > 0 and c[i] < o[i] and (c[i + 1:] > h[i]).any()) or (d < 0 and c[i] > o[i] and (c[i + 1:] < l[i]).any()):
            out.append((l[i], h[i]))
    return out


def find_setups(m, k):
    """Every bullish and bearish OTE range on 15-minute candles, with its confluence and filter flags."""
    b15, b30, b60 = resample(m, "15min"), resample(m, "30min"), resample(m, "1h")
    ema = b60["close"].ewm(span=50, adjust=False).mean()
    mid_open = m["open"][(m.index.hour == 0) & (m.index.minute == 0)]
    mid_open.index = mid_open.index.date
    t, h, l, c = b15.index, b15["high"].to_numpy(), b15["low"].to_numpy(), b15["close"].to_numpy()
    n = len(t)
    is_hi = np.array([k <= i < n - k and h[i] > max(np.r_[h[i - k:i], h[i + 1:i + k + 1]]) for i in range(n)])
    is_lo = np.array([k <= i < n - k and l[i] < min(np.r_[l[i - k:i], l[i + 1:i + k + 1]]) for i in range(n)])
    highs, lows, out = [], [], []
    for j in range(2 * k, n):
        i, act = j - k, t[j] + pd.Timedelta(minutes=15)  # swing i is confirmed when candle j closes
        for d, flag in ((1, is_hi[i]), (-1, is_lo[i])):
            if not flag:
                continue
            same, other = (highs, lows) if d > 0 else (lows, highs)
            p = bisect.bisect_left(other, i)
            if p:
                s0 = other[p - 1]  # the last opposite swing before this one starts the range
                seg = l[s0:i + 1] if d > 0 else h[s0:i + 1]
                si = s0 + int(np.argmin(seg) if d > 0 else np.argmax(seg))
                start, end = (l[si], h[i]) if d > 0 else (h[si], l[i])
                q = bisect.bisect_left(same, s0)
                bos = q > 0 and (end > h[same[q - 1]] if d > 0 else end < l[same[q - 1]])
                rng = abs(end - start)
                entry, far = end - d * 0.705 * rng, end - d * 0.79 * rng
                if bos and rng > 0 and (c[j] - far) * d > 0:
                    zlo, zhi = min(entry, far), max(entry, far)
                    zones = ob_fvg(b15.iloc[si:i + 1], d)
                    for bb, step in ((b30, "30min"), (b60, "1h")):
                        done = bb[(bb.index >= t[si].floor(step)) & (bb.index + pd.Timedelta(step) <= act)]
                        zones += ob_fvg(done, d)
                    hours = b60.index[b60.index + pd.Timedelta(hours=1) <= act]
                    trend = (c[j] - ema[hours[-1]]) * d > 0 if len(hours) else False
                    mo = mid_open.get(act.date(), np.nan)
                    out.append(dict(dir=d, act=act, entry=entry, far=far, start=start, end=end,
                                    confluence=any(a <= zhi and bhi >= zlo for a, bhi in zones),
                                    htf=bool(trend), midnight=bool((mo - entry) * d > 0)))
            same.append(i)
    return out


def simulate(m, sp, setups, v):
    """Trades of one variant: the newest range's limit order, managed minute by minute."""
    t, o, h, l, c = m.index, *(m[x].to_numpy() for x in ("open", "high", "low", "close"))
    acts = [s["act"] for s in setups]
    trades = []
    for day in pd.bdate_range(START, END):
        a = t.searchsorted(pd.Timestamp(f"{day.date()} {SESSION[0]}", tz=TZ))
        z = t.searchsorted(pd.Timestamp(f"{day.date()} {v['close_at'] if v['close_at'] < FLAT_AT else FLAT_AT}", tz=TZ))
        stop_entries = pd.Timestamp(f"{day.date()} {SESSION[1]}", tz=TZ)
        if z - a < 60:
            continue  # holiday or missing data
        lo_s = bisect.bisect_left(acts, pd.Timestamp(f"{day.date()} 00:00", tz=TZ))
        nxt, active, pos, losses = lo_s, None, None, 0
        for x in range(a, z):
            while nxt < len(setups) and setups[nxt]["act"] <= t[x]:
                s = setups[nxt]
                nxt += 1
                ok = (not v["confluence"] or s["confluence"]) and (not v["htf"] or s["htf"]) and \
                     (not v["midnight"] or s["midnight"])
                active = s if ok else None
            if pos is not None and x > pos["i"]:
                d, fill = pos["dir"], pos["fill"]
                lo_x, hi_x = (l[x], h[x]) if d > 0 else (l[x] + sp[x], h[x] + sp[x])
                op = o[x] if d > 0 else o[x] + sp[x]
                if (lo_x <= pos["sl"]) if d > 0 else (hi_x >= pos["sl"]):
                    px = min(pos["sl"], op) if d > 0 else max(pos["sl"], op)
                    pos.update(x=x, exit=px, reason="breakeven" if pos["be"] else "stop")
                elif (hi_x >= pos["tp"]) if d > 0 else (lo_x <= pos["tp"]):
                    px = max(pos["tp"], op) if d > 0 else min(pos["tp"], op)
                    pos.update(x=x, exit=px, reason="target")
                elif not pos["be"] and ((hi_x >= fill + BE_AT_R * STOP_PTS) if d > 0 else (lo_x <= fill - BE_AT_R * STOP_PTS)):
                    pos.update(be=True, sl=fill)
            if pos is not None and "x" in pos:
                trades.append(pos)
                losses += pos["exit"] * pos["dir"] < pos["fill"] * pos["dir"] - 0.05 * STOP_PTS
                pos = None
            if active is None:
                continue
            d = active["dir"]
            if (l[x] < active["start"]) if d > 0 else (h[x] > active["start"]):
                active = None  # the start of the range is taken out (read off the chart, like the swings)
                continue
            touched = (l[x] + sp[x] <= active["entry"]) if d > 0 else (h[x] >= active["entry"])
            if not touched:
                continue
            if pos is None and t[x] < stop_entries and losses < 2:
                fill = min(active["entry"], o[x] + sp[x]) if d > 0 else max(active["entry"], o[x])
                sl = fill - d * STOP_PTS
                pos = dict(dir=d, i=x, fill=fill, sl=sl, tp=fill + d * v["target_r"] * STOP_PTS, be=False, s=active)
                if (l[x] <= sl) if d > 0 else (h[x] + sp[x] >= sl):  # entry minute: only the stop is checked
                    pos.update(x=x, exit=sl, reason="stop")
                    trades.append(pos)
                    losses += 1
                    pos = None
            active = None  # the order is used, or was touched while it could not be taken
        if pos is not None:
            px = c[z - 1] + (sp[z - 1] if pos["dir"] < 0 else 0.0)
            pos.update(x=z - 1, exit=px, reason=f"closed {v['close_at']}")
            trades.append(pos)
    rows = []
    for p in trades:
        d, i, x = p["dir"], p["i"], p["x"]
        eod = t.searchsorted(pd.Timestamp(f"{t[i].date()} {FLAT_AT}", tz=TZ))
        fav = (h[i:eod] - p["fill"]) if d > 0 else (p["fill"] - (l[i:eod] + sp[i:eod]))
        adv = (p["fill"] - l[i:eod]) if d > 0 else ((h[i:eod] + sp[i:eod]) - p["fill"])
        hit = np.flatnonzero(adv >= STOP_PTS)
        upto = hit[0] if len(hit) else len(fav)  # favourable move before the original stop would be hit
        s = p["s"]
        rows.append(dict(day=t[i].date(), dir=d, range_confirmed=s["act"], range_start=s["start"], range_end=s["end"],
                         ote_0705=s["entry"], ote_079=s["far"], entry_time=t[i].tz_convert("UTC"),
                         exit_time=t[x].tz_convert("UTC"), entry=p["fill"], exit=p["exit"],
                         r=d * (p["exit"] - p["fill"]) / STOP_PTS,
                         reason=p["reason"], minutes=(t[x] - t[i]).total_seconds() / 60 + 1,
                         mfe_r=max(0.0, fav[:upto].max() if upto else 0.0) / STOP_PTS,
                         mae_pts=max(0.0, adv[:x - i + 1].max()), leverage_at_1pct=0.01 * p["fill"] / STOP_PTS))
    return pd.DataFrame(rows)


def summarize(name, t):
    w, wk = weekly_stats(account(t, max_leverage=20), START, END)
    win, loss = t["r"] > 0.05, t["r"] < -0.05
    return dict(variant=name, trades=len(t), trades_per_week=len(t) / w["weeks"],
                win_rate_pct=100 * win.mean(), loss_pct=100 * loss.mean(), breakeven_pct=100 * (~win & ~loss).mean(),
                win_rate_ex_be_pct=100 * win.sum() / max(1, (win | loss).sum()), avg_r=t["r"].mean(),
                total_r=t["r"].sum(), reach_3r_pct=100 * (t["mfe_r"] >= 3).mean(), reach_4r_pct=100 * (t["mfe_r"] >= 4).mean(),
                reach_5r_pct=100 * (t["mfe_r"] >= 5).mean(), avg_mfe_r=t["mfe_r"].mean(), avg_mae_pts=t["mae_pts"].mean(),
                avg_minutes=t["minutes"].mean(), avg_week_pct=w["avg_week_pct"], compound_week_pct=w["compound_week_pct"],
                positive_weeks_pct=w["positive_weeks_pct"], worst_week_pct=w["worst_week_pct"],
                max_drawdown_pct=w["max_drawdown_pct"], final_balance=w["final_balance"])


def main():
    os.makedirs(RESULTS, exist_ok=True)
    m = load_m1(SYM)
    m = m[(m.index >= WARMUP.tz_localize("UTC")) & (m.index < (END + pd.Timedelta(days=1)).tz_localize("UTC"))]
    sp = spread_by_hour(SYM).to_numpy()[m.index.hour]
    m = m.tz_convert(TZ)
    print("spread by New York hour, 02:00-09:00:", {hr: round(float(np.median(sp[m.index.hour == hr])), 2)
                                                    for hr in range(2, 10)})
    cache, rows = {}, []
    for name, change in VARIANTS.items():
        v = {**BASE, **change}
        if v["k"] not in cache:
            cache[v["k"]] = find_setups(m, v["k"])
        t = simulate(m, sp, cache[v["k"]], v)
        if name.startswith("base"):
            t.to_csv(os.path.join(RESULTS, "ote_base_trades.csv"), index=False, float_format="%.6g")
            by_month = t.groupby(pd.to_datetime(t["day"]).dt.to_period("M"))["r"].agg(["size", "sum", "mean"])
            by_month.to_csv(os.path.join(RESULTS, "ote_base_by_month.csv"), float_format="%.4f")
            print(by_month.round(2).T.to_string())
            print(t["reason"].value_counts().to_dict())
        rows.append(summarize(name, t))
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, "ote_variants.csv"), index=False, float_format="%.4f")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(pd.DataFrame([dict(variant="PDF's own statistics", **PDF_STATS)]).to_string(index=False))
        print(res.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
