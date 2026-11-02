"""Backtest of howtotrade.com's "Opening Range Breakout (ORB) Trading Strategy" PDF on 15-minute candles.

  python pipeline/orb15.py

Markets: Nasdaq-100 (Dukascopy USATECHIDXUSD CFD) and gold (XAUUSD). 15-minute candles are built from Dukascopy's
1-minute bid candles. Window: the last 12 months, 3 Nov 2025 - 30 Oct 2026.

The PDF's four steps, made mechanical (its open choices are marked *):
1. Trend: the 50 and 200 EMA, here on the 15-minute chart. 50 above 200 is an uptrend (longs only), below is a
   downtrend (shorts only). Variant: price above both EMAs for longs, below both for shorts.
2. Opening range: the high and low of the first 30 minutes of the session (*the PDF's example; variant: 15).
   Sessions: Nasdaq-100 09:30-16:00 New York. *Gold trades almost 24 hours; the base uses the COMEX day session,
   08:20-13:30 New York, and the London session, 03:00-11:30 New York, is a variant.
3. Entry: a 15-minute candle closes beyond the range in the trend's direction, and its body breaks out with it - a
   bullish candle closing above the high, or a bearish one below the low. The PDF waits for "a full-body candle
   break" instead of a touch. Entry is at the next candle's open.
   *The PDF also wants a spike in volume, which this data cannot show. Dukascopy's volume is its own liquidity
   providers', not exchange volume. Its level rose about 10x during the year on the Nasdaq-100, and its US-session
   share fell. So the base has no volume condition. Two readings are variants: volume above 1.5x the previous 20
   candles, or above 1.5x the same 15-minute slot's average over the previous 20 days.
   *One trade a day, from a breakout candle that closes within 3 hours of the open.
4. Stop beyond the breakout candle, or at the other side of the opening range; target 2R or 3R. *Anything still
   open at the session close is closed.
Costs: Dukascopy's ask - bid by hour. Longs fill at the ask, and shorts are stopped and take profit on the ask.
Stops and targets are checked on the 1-minute prices inside each 15-minute candle, so when one candle touches both,
the one touched first counts (within a single minute, the stop).
Account: $10,000, 1% risk per trade, compounding, positions under 20:1 (strategy_search/pipeline/intraday.py).
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
sys.path.insert(0, os.path.join(os.path.dirname(ROOT), "strategy_search", "pipeline"))
import intraday  # noqa: E402
from intraday import account, load_m1, spread_by_hour, weekly_stats  # noqa: E402

TZ = "America/New_York"
START, END = pd.Timestamp("2025-11-03"), pd.Timestamp("2026-10-30")
intraday.TEST_START, intraday.TEST_END = pd.Timestamp("2025-11-01"), END  # spreads measured over the window
MARKETS = {"USATECHIDXUSD": dict(label="Nasdaq-100", session=("09:30", "16:00")),
           "XAUUSD": dict(label="Gold", session=("08:20", "13:30"))}
BASE = dict(or_min=30, trend="ema", volume=None, body=None, stop="range", target=2.0, cutoff_h=3, session=None)
VERSIONS = {  # the four combinations the PDF allows
    "stop at other side of range, 2R": {},
    "stop at other side of range, 3R": dict(target=3.0),
    "stop beyond breakout candle, 2R": dict(stop="candle"),
    "stop beyond breakout candle, 3R": dict(stop="candle", target=3.0),
}
VARIANTS = {  # each on the first version
    "opening range of 15 minutes": dict(or_min=15),
    "trend: price above/below both EMAs": dict(trend="price"),
    "+ volume spike vs the previous 20 candles": dict(volume=("prev20", 1.5)),
    "+ volume spike vs the same time of day": dict(volume=("slot20", 1.5)),
    "stricter full body (70% of the candle)": dict(body=0.7),
    "no trend filter": dict(trend=None),
}
GOLD_LONDON = {"London session, 03:00-11:30 New York": dict(session=("03:00", "11:30"))}


def candles(m, start_hhmm):
    """15-minute candles aligned to the session open (gold's 08:20 open puts them at :05, :20, :35, :50)."""
    offset = f"{int(start_hhmm[3:]) % 15}min"
    b = m.resample("15min", offset=offset, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
    b["ema50"] = b["close"].ewm(span=50, adjust=False).mean()
    b["ema200"] = b["close"].ewm(span=200, adjust=False).mean()
    b["vol_prev20"] = b["volume"].rolling(20).mean().shift(1)
    slot = b.index.strftime("%H:%M")
    b["vol_slot20"] = b.groupby(slot)["volume"].transform(lambda s: s.rolling(20, min_periods=10).mean().shift(1))
    return b


def simulate(m, sp, v, session):
    t, o, h, l, c = m.index, *(m[x].to_numpy() for x in ("open", "high", "low", "close"))
    b = candles(m, session[0])
    bt = b.index
    rows = []
    for day in pd.bdate_range(START, END):
        op = pd.Timestamp(f"{day.date()} {session[0]}", tz=TZ)
        cl = pd.Timestamp(f"{day.date()} {session[1]}", tz=TZ)
        a, z = t.searchsorted(op), t.searchsorted(cl)
        if z - a < 0.9 * (cl - op).total_seconds() / 60:
            continue  # holiday, early close or missing data
        rng = b[(bt >= op) & (bt < op + pd.Timedelta(minutes=v["or_min"]))]
        if len(rng) != v["or_min"] // 15 or rng.index[0] != op:
            continue
        hi, lo = rng["high"].max(), rng["low"].min()
        last = op + pd.Timedelta(hours=v["cutoff_h"])
        for k in np.flatnonzero((bt >= op + pd.Timedelta(minutes=v["or_min"])) & (bt + pd.Timedelta(minutes=15) <= last)):
            r = b.iloc[k]
            if v["trend"] == "ema":
                allowed = 1 if r.ema50 > r.ema200 else -1
            elif v["trend"] == "price":
                allowed = 1 if r.close > max(r.ema50, r.ema200) else -1 if r.close < min(r.ema50, r.ema200) else 0
            else:
                allowed = None
            body = r.close - r.open
            d = 1 if (r.close > hi and body > 0) else -1 if (r.close < lo and body < 0) else 0
            if d == 0 or (allowed is not None and d != allowed):
                continue
            if v["body"] and abs(body) < v["body"] * (r.high - r.low):
                continue
            if v["volume"] and not (r.volume > v["volume"][1] * r[f"vol_{v['volume'][0]}"]):
                continue
            x = t.searchsorted(bt[k] + pd.Timedelta(minutes=15))  # the next candle's first minute
            if x >= z:
                break
            fill = o[x] + sp[x] if d > 0 else o[x]
            stop = (lo if d > 0 else hi) if v["stop"] == "range" else (r.low if d > 0 else r.high)
            risk = d * (fill - stop)
            if risk <= 0:
                break  # the next open is already beyond the stop
            tp = fill + d * v["target"] * risk
            exit_px, reason, y = None, None, None
            for y in range(x, z):
                lo_y, hi_y, op_y = (l[y], h[y], o[y]) if d > 0 else (l[y] + sp[y], h[y] + sp[y], o[y] + sp[y])
                if (lo_y <= stop) if d > 0 else (hi_y >= stop):
                    exit_px, reason = (min(stop, op_y) if d > 0 else max(stop, op_y)), "stop"
                    break
                if (hi_y >= tp) if d > 0 else (lo_y <= tp):
                    exit_px, reason = (max(tp, op_y) if d > 0 else min(tp, op_y)), "target"
                    break
            if exit_px is None:
                y = z - 1
                exit_px, reason = c[y] + (sp[y] if d < 0 else 0.0), "session close"
            rows.append(dict(day=day.date(), dir=d, range_high=hi, range_low=lo, breakout_candle=bt[k],
                             entry_time=t[x].tz_convert("UTC"), exit_time=t[y].tz_convert("UTC"), entry=fill,
                             stop=stop, target=tp, exit=exit_px, risk_pts=risk, r=d * (exit_px - fill) / risk,
                             reason=reason, leverage_at_1pct=0.01 * fill / risk))
            break  # one trade a day
    return pd.DataFrame(rows)


def summarize(market, name, t):
    if t.empty:
        return dict(market=market, version=name, trades=0)
    w, _ = weekly_stats(account(t, max_leverage=20), START, END)
    win, loss = t["r"] > 0.05, t["r"] < -0.05
    return dict(market=market, version=name, trades=len(t), trades_per_week=len(t) / w["weeks"],
                long_pct=100 * (t["dir"] > 0).mean(), win_rate_pct=100 * win.mean(), loss_pct=100 * loss.mean(),
                target_pct=100 * (t["reason"] == "target").mean(), stop_pct=100 * (t["reason"] == "stop").mean(),
                close_pct=100 * (t["reason"] == "session close").mean(), avg_r=t["r"].mean(), total_r=t["r"].sum(),
                avg_risk_pts=t["risk_pts"].mean(), avg_week_pct=w["avg_week_pct"],
                compound_week_pct=w["compound_week_pct"], positive_weeks_pct=w["positive_weeks_pct"],
                worst_week_pct=w["worst_week_pct"], max_drawdown_pct=w["max_drawdown_pct"],
                final_balance=w["final_balance"])


def main():
    os.makedirs(RESULTS, exist_ok=True)
    rows, keep = [], []
    for sym, info in MARKETS.items():
        m = load_m1(sym)
        m = m[(m.index >= pd.Timestamp("2025-10-01", tz="UTC")) & (m.index < (END + pd.Timedelta(days=1)).tz_localize("UTC"))]
        sp = spread_by_hour(sym).to_numpy()[m.index.hour]
        m = m.tz_convert(TZ)
        print(info["label"], "minutes:", len(m), " median spread in session:",
              round(float(np.median(sp[(m.index.hour >= 3) & (m.index.hour < 16)])), 3), flush=True)
        versions = {**VERSIONS, **{k: {**VERSIONS[next(iter(VERSIONS))], **x} for k, x in VARIANTS.items()}}
        if sym == "XAUUSD":
            versions.update(GOLD_LONDON)
        for name, change in versions.items():
            v = {**BASE, **change}
            t = simulate(m, sp, v, v["session"] or info["session"])
            keep.append(t.assign(market=info["label"], version=name))
            rows.append(summarize(info["label"], name, t))
            if name == next(iter(VERSIONS)):
                bm = t.groupby(pd.to_datetime(t["day"]).dt.to_period("M"))["r"].agg(["size", "sum"])
                bm.to_csv(os.path.join(RESULTS, f"{sym}_by_month.csv"), float_format="%.4f")
                print(bm.round(2).T.to_string())
    pd.concat(keep).to_csv(os.path.join(RESULTS, "orb15_trades.csv"), index=False, float_format="%.6g")
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, "orb15_results.csv"), index=False, float_format="%.4f")
    with pd.option_context("display.width", 260, "display.max_columns", 30):
        print(res.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
