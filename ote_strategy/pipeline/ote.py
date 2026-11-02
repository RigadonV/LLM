"""Backtests of the OTE (optimal trade entry) strategy in OTE_Trading_Strategy.pdf, and of changes taken from ICT's
own OTE teaching, on the London session of the last 12 months.

  python pipeline/ote.py [--market USATECHIDXUSD|XAUUSD] [--suite pdf|ict] [--period last|prior]

Markets: Nasdaq-100 (Dukascopy USATECHIDXUSD CFD) and gold (XAUUSD), 1-minute bid candles.
Window: 3 Nov 2025 - 30 Oct 2026 (--period prior: 4 Nov 2024 - 31 Oct 2025, a robustness check only).
Entries in the London session, New York time.

Suite "pdf": the PDF's rules made mechanical (its discretionary parts are marked *):
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
  out the start of the range, until a newer range replaces it, or until the end of the entry session.
- Stop 50 points from the fill; stop to breakeven once price reaches 2R; target 4R (variant 3R). At most 2 losses
  a day, one trade at a time. Entries 02:00-09:30; anything still open at 16:00 is closed (variant: at 09:30).
- Gold: the PDF's "50 points" is read as 50 pips = $5.00. At the MT4/MT5 point of $0.01 it would be $0.50, less
  than gold's spread; at $1 a point it would be $50, more than most London sessions' whole range. Variant: $10.

Suite "ict": one change at a time from ICT's OTE as public sources describe it (ICT publishes no closed rules):
- OTE zone 62-79%, entry at 62%;
- stop beyond the swing that starts the range (the 100% level) by 5% of the range, instead of a fixed distance,
  and at least 3 spreads from the entry;
- target at the -0.27 or -0.62 Fibonacci extension of the range;
- entries only in ICT's London killzone, 02:00-05:00 New York;
- a Judas swing first: the range must start, after midnight, by sweeping the Asian range (20:00-00:00 New York)
  high or low;
- the combined ICT London model: sweep + structure shift + displacement (a fair value gap in the leg) + OB/FVG in
  the 62-79% zone, entry at 70.5%, stop beyond the swing, half off at -0.27 with the stop then at breakeven and the
  rest at -0.62, entries 02:00-05:00. Also the same with the whole position aimed at the other side of the Asian
  range.

Costs and fills: Dukascopy's own ask - bid by hour. Buys fill at the ask, and shorts are stopped and take profit
on the ask. Within one minute the stop counts before a target; on the entry minute only the stop is checked;
breakeven applies from the minute after it is triggered.
Account: $10,000, 1% risk per trade, compounding, all positions under 20:1 (strategy_search/pipeline/intraday.py).
"""
import argparse
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

TZ = "America/New_York"
PERIODS = {"last": ("2025-11-03", "2026-10-30"),  # the last 12 months, the test asked for
           "prior": ("2024-11-04", "2025-10-31")}  # the 12 months before it, as a robustness check only
START, END = (pd.Timestamp(x) for x in PERIODS["last"])
FLAT_AT, MIN_RISK_SPREADS = "16:00", 3
LABEL = {"USATECHIDXUSD": "Nasdaq-100", "XAUUSD": "Gold"}
PDF_STOP = {"USATECHIDXUSD": 50.0, "XAUUSD": 5.0}  # 50 points on the Nasdaq-100, 50 pips on gold
PREFIX = {("USATECHIDXUSD", "pdf"): "ote", ("XAUUSD", "pdf"): "ote_gold",
          ("USATECHIDXUSD", "ict"): "ote_ict_nq", ("XAUUSD", "ict"): "ote_ict_gold"}

BASE = dict(k=2, entry_level=0.705, zone="705", confluence=True, htf=False, midnight=False, sweep=False,
            displacement=False, session=("02:00", "09:30"), close_at="16:00", target=("r", 4.0), be_at_r=2.0,
            max_losses=2)
PDF = {
    "base (as written, target 4R)": {},
    "target 3R": dict(target=("r", 3.0)),
    "+ 1-hour 50 EMA trend filter": dict(htf=True),
    "+ midnight-open filter": dict(midnight=True),
    "swings of 1 candle each side": dict(k=1),
    "swings of 3 candles each side": dict(k=3),
    "no OB/FVG needed": dict(confluence=False),
    "close at 09:30": dict(close_at="09:30"),
}
ICT_MODEL = dict(sweep=True, displacement=True, zone="62", entry_level=0.705, stop=("swing", 0.05),
                 target=("partial", 0.27, 0.62), be_at_r=None, session=("02:00", "05:00"))
ICT = {
    "PDF base": {},
    "OTE zone 62-79%, entry at 62%": dict(zone="62", entry_level=0.62),
    "stop beyond the swing, target 4R": dict(stop=("swing", 0.05)),
    "stop beyond the swing, target -0.27": dict(stop=("swing", 0.05), target=("ext", 0.27), be_at_r=None),
    "stop beyond the swing, target -0.62": dict(stop=("swing", 0.05), target=("ext", 0.62), be_at_r=None),
    "London killzone only, 02:00-05:00": dict(session=("02:00", "05:00")),
    "Asian-range sweep first (Judas swing)": dict(sweep=True),
    "ICT London model, -0.27 / -0.62": ICT_MODEL,
    "ICT London model, other side of Asia": {**ICT_MODEL, "target": ("asia",)},
}
PDF_STATS = dict(win_rate_pct=84.4, avg_mfe_r=8.4, avg_minutes=32.9, reach_3r_pct=82.1, reach_4r_pct=66.1,
                 reach_5r_pct=57.1, avg_mae_pts=11.7)


def resample(m, rule):
    return m.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()


def ob_fvg(b, d):
    """(low, high, kind) of every fair value gap and order block of direction d in bars b."""
    o, h, l, c = (b[x].to_numpy() for x in ("open", "high", "low", "close"))
    out = []
    for i in range(len(b) - 2):
        if d > 0 and l[i + 2] > h[i]:
            out.append((h[i], l[i + 2], "fvg"))
        elif d < 0 and h[i + 2] < l[i]:
            out.append((h[i + 2], l[i], "fvg"))
    for i in range(len(b) - 1):
        if (d > 0 and c[i] < o[i] and (c[i + 1:] > h[i]).any()) or (d < 0 and c[i] > o[i] and (c[i + 1:] < l[i]).any()):
            out.append((l[i], h[i], "ob"))
    return out


def find_setups(m, k):
    """Every bullish and bearish OTE range on 15-minute candles, with its levels and filter flags."""
    b15, b30, b60 = resample(m, "15min"), resample(m, "30min"), resample(m, "1h")
    ema = b60["close"].ewm(span=50, adjust=False).mean()
    first = m["open"][(m.index.hour == 0) & (m.index.minute == 0)]
    mid_open = dict(zip(first.index.date, first.to_numpy()))
    eve = m[m.index.hour >= 20]  # the Asian range, 20:00-00:00 New York, belongs to the next day
    asia = {day: (g["high"].max(), g["low"].min()) for day, g in eve.groupby((eve.index + pd.Timedelta(hours=4)).date)}
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
                leg = abs(end - start)
                e705, e62, far = end - d * 0.705 * leg, end - d * 0.62 * leg, end - d * 0.79 * leg
                if bos and leg > 0 and (c[j] - far) * d > 0:
                    zones = ob_fvg(b15.iloc[si:i + 1], d)
                    disp = any(z[2] == "fvg" for z in zones)
                    for bb, step in ((b30, "30min"), (b60, "1h")):
                        done = bb[(bb.index >= t[si].floor(step)) & (bb.index + pd.Timedelta(step) <= act)]
                        zones += ob_fvg(done, d)

                    def overlaps(a, b):
                        lo, hi = min(a, b), max(a, b)
                        return any(z0 <= hi and z1 >= lo for z0, z1, _ in zones)

                    hours = b60.index[b60.index + pd.Timedelta(hours=1) <= act]
                    trend = (c[j] - ema[hours[-1]]) * d > 0 if len(hours) else False
                    ah, al = asia.get(act.date(), (np.nan, np.nan))
                    swept = t[si] >= act.normalize() and ((d > 0 and start < al) or (d < 0 and start > ah))
                    out.append(dict(dir=d, act=act, start=start, end=end, leg=leg, far=far, e705=e705, e62=e62,
                                    conf705=overlaps(e705, far), conf62=overlaps(e62, far), disp=disp,
                                    sweep=bool(swept), asia_target=ah if d > 0 else al, htf=bool(trend),
                                    midnight=bool((mid_open.get(act.date(), np.nan) - e705) * d > 0)))
            same.append(i)
    return out


def passes(s, v):
    return ((not v["confluence"] or s["conf705" if v["zone"] == "705" else "conf62"]) and (not v["htf"] or s["htf"])
            and (not v["midnight"] or s["midnight"]) and (not v["sweep"] or s["sweep"])
            and (not v["displacement"] or s["disp"]))


def simulate(m, sp, setups, v):
    """Trades of one variant: the newest range's limit order, managed minute by minute."""
    t, o, h, l, c = m.index, *(m[x].to_numpy() for x in ("open", "high", "low", "close"))
    acts = [s["act"] for s in setups]
    kind, stop_arg = v["stop"]
    at = lambda day, hhmm: pd.Timestamp(f"{day.date()} {hhmm}", tz=TZ)  # noqa: E731
    trades = []

    def open_position(s, x, E):
        d = s["dir"]
        fill = min(E, o[x] + sp[x]) if d > 0 else max(E, o[x])
        sl = fill - d * stop_arg if kind == "fixed" else s["start"] - d * stop_arg * s["leg"]
        risk = d * (fill - sl)
        if risk <= 0 or (kind == "swing" and risk < MIN_RISK_SPREADS * sp[x]):
            return None
        tg = v["target"]
        tps = ([(fill + d * tg[1] * risk, 1.0)] if tg[0] == "r" else
               [(s["end"] + d * tg[1] * s["leg"], 1.0)] if tg[0] == "ext" else
               [(s["end"] + d * tg[1] * s["leg"], 0.5), (s["end"] + d * tg[2] * s["leg"], 0.5)] if tg[0] == "partial"
               else [(s["asia_target"], 1.0)])
        if any(not np.isfinite(p) or d * (p - fill) <= 0 for p, _ in tps):
            return None
        return dict(dir=d, i=x, fill=fill, risk=risk, sl=sl, sl0=sl, tps=tps, w=1.0, r=0.0, be=False, hits=0,
                    partial=tg[0] == "partial", s=s)

    def close(pos, x, px, reason):
        pos["r"] += pos["w"] * pos["dir"] * (px - pos["fill"]) / pos["risk"]
        pos.update(w=0.0, x=x, exit=px, reason=reason)

    def step(pos, x):
        d, fill, risk = pos["dir"], pos["fill"], pos["risk"]
        lo_x, hi_x, op = (l[x], h[x], o[x]) if d > 0 else (l[x] + sp[x], h[x] + sp[x], o[x] + sp[x])
        if (lo_x <= pos["sl"]) if d > 0 else (hi_x >= pos["sl"]):
            px = min(pos["sl"], op) if d > 0 else max(pos["sl"], op)
            close(pos, x, px, "target 1, then breakeven" if pos["hits"] else "breakeven" if pos["be"] else "stop")
            return
        for p, w in list(pos["tps"]):
            if (hi_x >= p) if d > 0 else (lo_x <= p):
                px = max(p, op) if d > 0 else min(p, op)
                pos["r"] += w * d * (px - fill) / risk
                pos["w"] -= w
                pos["tps"].remove((p, w))
                pos["hits"] += 1
                if pos["w"] <= 1e-9:
                    pos.update(w=0.0, x=x, exit=px, reason="target")
                    return
                if pos["partial"]:
                    pos.update(sl=fill, be=True)
        if v["be_at_r"] and not pos["be"] and ((hi_x >= fill + v["be_at_r"] * risk) if d > 0 else
                                               (lo_x <= fill - v["be_at_r"] * risk)):
            pos.update(sl=fill, be=True)

    for day in pd.bdate_range(START, END):
        a = t.searchsorted(at(day, v["session"][0]))
        z = t.searchsorted(at(day, min(v["close_at"], FLAT_AT)))
        last_entry = at(day, v["session"][1])
        if z - a < 60:
            continue  # holiday or missing data
        nxt, active, pos, losses = bisect.bisect_left(acts, at(day, "00:00")), None, None, 0
        for x in range(a, z):
            while nxt < len(setups) and setups[nxt]["act"] <= t[x]:
                active = setups[nxt] if passes(setups[nxt], v) else None
                nxt += 1
            if pos is not None and x > pos["i"]:
                step(pos, x)
            if pos is not None and "x" in pos:
                trades.append(pos)
                losses += pos["r"] < -0.05
                pos = None
            if active is None:
                continue
            d = active["dir"]
            if (l[x] < active["start"]) if d > 0 else (h[x] > active["start"]):
                active = None  # the start of the range is taken out (read off the chart, like the swings)
                continue
            E = active["e705"] if v["entry_level"] == 0.705 else active["e62"]
            if not ((l[x] + sp[x] <= E) if d > 0 else (h[x] >= E)):
                continue
            if pos is None and t[x] < last_entry and losses < v["max_losses"]:
                pos = open_position(active, x, E)
                if pos is not None and ((l[x] <= pos["sl"]) if d > 0 else (h[x] + sp[x] >= pos["sl"])):
                    close(pos, x, pos["sl"], "stop")  # entry minute: only the stop is checked
                    trades.append(pos)
                    losses += 1
                    pos = None
            active = None  # the order is used, or was touched while it could not be taken
        if pos is not None:
            close(pos, z - 1, c[z - 1] + (sp[z - 1] if pos["dir"] < 0 else 0.0), f"closed {v['close_at']}")
            trades.append(pos)
    rows = []
    for p in trades:
        d, i, x, s, risk = p["dir"], p["i"], p["x"], p["s"], p["risk"]
        eod = t.searchsorted(pd.Timestamp(f"{t[i].date()} {FLAT_AT}", tz=TZ))
        fav = (h[i:eod] - p["fill"]) if d > 0 else (p["fill"] - (l[i:eod] + sp[i:eod]))
        adv = (p["fill"] - l[i:eod]) if d > 0 else ((h[i:eod] + sp[i:eod]) - p["fill"])
        hit = np.flatnonzero(adv >= risk)
        upto = hit[0] if len(hit) else len(fav)  # favourable move before the original stop would be hit
        rows.append(dict(day=t[i].date(), dir=d, range_confirmed=s["act"], range_start=s["start"], range_end=s["end"],
                         ote_entry=s["e705"] if v["entry_level"] == 0.705 else s["e62"],
                         ote_079=s["far"], entry_time=t[i].tz_convert("UTC"), exit_time=t[x].tz_convert("UTC"),
                         entry=p["fill"], stop=p["sl0"], risk_pts=risk, exit=p["exit"], r=p["r"], reason=p["reason"],
                         minutes=(t[x] - t[i]).total_seconds() / 60 + 1,
                         mfe_r=max(0.0, fav[:upto].max() if upto else 0.0) / risk,
                         mae_pts=max(0.0, adv[:x - i + 1].max()), leverage_at_1pct=0.01 * p["fill"] / risk))
    return pd.DataFrame(rows)


def summarize(name, t):
    if t.empty:
        return dict(variant=name, trades=0)
    w, _ = weekly_stats(account(t, max_leverage=20), START, END)
    win, loss = t["r"] > 0.05, t["r"] < -0.05
    return dict(variant=name, trades=len(t), trades_per_week=len(t) / w["weeks"],
                win_rate_pct=100 * win.mean(), loss_pct=100 * loss.mean(), breakeven_pct=100 * (~win & ~loss).mean(),
                win_rate_ex_be_pct=100 * win.sum() / max(1, (win | loss).sum()), avg_r=t["r"].mean(),
                total_r=t["r"].sum(), avg_risk_pts=t["risk_pts"].mean(), reach_3r_pct=100 * (t["mfe_r"] >= 3).mean(),
                reach_4r_pct=100 * (t["mfe_r"] >= 4).mean(), reach_5r_pct=100 * (t["mfe_r"] >= 5).mean(),
                avg_mfe_r=t["mfe_r"].mean(), avg_mae_pts=t["mae_pts"].mean(), avg_minutes=t["minutes"].mean(),
                avg_week_pct=w["avg_week_pct"], compound_week_pct=w["compound_week_pct"],
                positive_weeks_pct=w["positive_weeks_pct"], worst_week_pct=w["worst_week_pct"],
                max_drawdown_pct=w["max_drawdown_pct"], final_balance=w["final_balance"])


def main():
    global START, END
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="USATECHIDXUSD", choices=list(LABEL))
    ap.add_argument("--suite", default="pdf", choices=["pdf", "ict"])
    ap.add_argument("--period", default="last", choices=list(PERIODS))
    args = ap.parse_args()
    START, END = (pd.Timestamp(x) for x in PERIODS[args.period])
    intraday.TEST_START, intraday.TEST_END = START - pd.Timedelta(days=2), END  # spreads measured over the period
    sym = args.market
    prefix = PREFIX[(sym, args.suite)] + ("" if args.period == "last" else "_prior")
    os.makedirs(RESULTS, exist_ok=True)
    m = load_m1(sym)
    warmup = (START - pd.Timedelta(days=33)).tz_localize("UTC")
    m = m[(m.index >= warmup) & (m.index < (END + pd.Timedelta(days=1)).tz_localize("UTC"))]
    sp = spread_by_hour(sym).to_numpy()[m.index.hour]
    m = m.tz_convert(TZ)
    print(LABEL[sym], "spread by New York hour, 02:00-09:00:",
          {hr: round(float(np.median(sp[m.index.hour == hr])), 3) for hr in range(2, 10)})
    variants = dict(PDF) if args.suite == "pdf" else dict(ICT)
    if sym == "XAUUSD" and args.suite == "pdf":
        variants["stop $10 instead of $5"] = dict(stop=("fixed", 10.0))
    cache, rows, keep = {}, [], []
    for name, change in variants.items():
        v = {**BASE, "stop": ("fixed", PDF_STOP[sym]), **change}
        if v["k"] not in cache:
            cache[v["k"]] = find_setups(m, v["k"])
        t = simulate(m, sp, cache[v["k"]], v)
        keep.append(t.assign(variant=name))
        if not rows:
            t.to_csv(os.path.join(RESULTS, f"{prefix}_base_trades.csv"), index=False, float_format="%.6g")
            by_month = t.groupby(pd.to_datetime(t["day"]).dt.to_period("M"))["r"].agg(["size", "sum", "mean"])
            by_month.to_csv(os.path.join(RESULTS, f"{prefix}_base_by_month.csv"), float_format="%.4f")
            print(by_month.round(2).T.to_string())
        rows.append(summarize(name, t))
    pd.concat(keep).to_csv(os.path.join(RESULTS, f"{prefix}_trades.csv"), index=False, float_format="%.6g")
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, f"{prefix}_variants.csv"), index=False, float_format="%.4f")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        if args.suite == "pdf":
            print(pd.DataFrame([dict(variant="PDF's own statistics", **PDF_STATS)]).to_string(index=False))
        print(res.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
