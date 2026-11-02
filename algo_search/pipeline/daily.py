"""Daily-bar strategies on the multi-asset universe, with Dukascopy bid/ask prices.

  python pipeline/daily.py          # every strategy on every instrument it applies to -> results/daily_trades.csv.gz

Every rule was published long before the test window, and none is tuned here:
- turtle_s1 / turtle_s2: the Turtle systems (Faith, "Way of the Turtle", 2007). Buy stop at the 20-day (S1) or
  55-day (S2) high, sell stop at the 20/55-day low. Stop 2N from the fill, N = 20-day average true range,
  (19 x N + TR) / 20. Exit at the 10-day (S1) or 20-day (S2) low for longs, high for shorts. One unit per market,
  sized so the 2N stop is 1% of the account: no pyramiding and no S1 last-trade filter. The rule of at most 12
  positions in one direction is applied in evaluate.py.
- rsi2: Connors & Alvarez (2008), equity indices. Above the 200-day average, buy at the close when RSI(2) < 5 and
  sell at the first close above the 5-day average; below it, short when RSI(2) > 95 and cover at the first close
  below the 5-day average. The book uses no stop. For 1% risk the stop here is 2N; rsi2_nostop keeps the book's
  no-stop rule and is sized as if the stop were 2N, so a loss can be bigger than 1%.
- tom: turn of the month (Lakonishok & Smidt 1988; McConnell & Xu 2008), equity indices, long only. Hold from the
  close two trading days before month end to the close of the third trading day of the new month; stop 2N.
Costs: buys fill at bid + the instrument's median hourly spread, sells at the bid, so shorts are stopped and closed
at the ask. A stop that gaps fills at the open. On the day of a stop entry, an exit level inside the day's range
counts as hit. Overnight financing is charged per calendar night on the position's value at FINANCING a year; that
is an assumption (broker rates are not in the price data), about a typical CFD markup over the benchmark rate.
"""
import os

import numpy as np
import pandas as pd

from data import DATA, RESULTS, UNIVERSE, load

FINANCING = {"FX": 0.01, "Metal": 0.03, "Energy": 0.03, "Agri": 0.03, "Index": 0.03, "Bond": 0.03, "Crypto": 0.10}


def prep(d):
    o, h, l, c = (d[k].values for k in ("open", "high", "low", "close"))
    prev = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.c_[h - l, np.abs(h - prev), np.abs(l - prev)], axis=1)
    return o, h, l, c, pd.Series(tr).ewm(alpha=1 / 20, adjust=False).mean().values


def prior(x, n, how):
    """Highest / lowest of the previous n days, known before today's open."""
    r = pd.Series(x).rolling(n)
    return (r.max() if how == "max" else r.min()).shift(1).values


def make_rec(name, sym, days):
    label, cls, _ = UNIVERSE[sym]

    def rec(s, i0, i1, fill, px, risk, reason, h_in, h_out):
        nights = (days[i1] - days[i0]).days
        fin = FINANCING[cls] * nights / 365 * fill / risk
        r_gross = s * (px - fill) / risk
        return dict(strategy=name, symbol=sym, market=label, cls=cls, dir=s, entry_day=days[i0], exit_day=days[i1],
                    entry_time=days[i0] + pd.Timedelta(hours=h_in), exit_time=days[i1] + pd.Timedelta(hours=h_out),
                    entry=fill, exit=px, risk_pts=risk, nights=nights, r_gross=r_gross, fin_r=fin, r=r_gross - fin,
                    reason=reason, leverage_at_1pct=0.01 * fill / risk)
    return rec


def turtle(sym, d, sp, n_in, n_out, name):
    o, h, l, c, N = prep(d)
    rec = make_rec(name, sym, d.index)
    hi_in, lo_in, hi_out, lo_out = prior(h, n_in, "max"), prior(l, n_in, "min"), prior(h, n_out, "max"), prior(l, n_out, "min")
    rows, pos = [], None
    for t in range(n_in + 21, len(c)):
        if pos is None:
            up, dn = h[t] + sp >= hi_in[t], l[t] <= lo_in[t]
            if up == dn:  # no breakout, or both in one day (order unknown)
                continue
            s = 1 if up else -1
            fill = max(hi_in[t], o[t] + sp) if s > 0 else min(lo_in[t], o[t])
            risk = 2 * N[t - 1]
            pos = [s, t, fill, fill - s * risk, risk]
            level = max(pos[3], lo_out[t]) if s > 0 else min(pos[3], hi_out[t])
            if (s > 0 and l[t] <= level) or (s < 0 and h[t] + sp >= level):
                rows.append(rec(s, t, t, fill, level, risk, "stop, entry day", 12, 13))
                pos = None
            continue
        s, t0, fill, stop, risk = pos
        level = max(stop, lo_out[t]) if s > 0 else min(stop, hi_out[t])
        if s > 0 and l[t] <= level:
            px = min(level, o[t])
        elif s < 0 and h[t] + sp >= level:
            px = max(level, o[t] + sp)
        else:
            continue
        rows.append(rec(s, t0, t, fill, px, risk, "stop" if level == stop else "exit channel", 12, 12))
        pos = None
    if pos is not None:
        s, t0, fill, _, risk = pos
        rows.append(rec(s, t0, len(c) - 1, fill, c[-1] + (sp if s < 0 else 0.0), risk, "end of data", 12, 21))
    return rows


def rsi(c, n=2):
    diff = np.diff(c, prepend=np.nan)
    up = pd.Series(np.where(diff > 0, diff, 0.0)).ewm(alpha=1 / n, adjust=False).mean()
    dn = pd.Series(np.where(diff < 0, -diff, 0.0)).ewm(alpha=1 / n, adjust=False).mean()
    return (100 - 100 / (1 + up / dn)).values


def rsi2(sym, d, sp, stops, name):
    o, h, l, c, N = prep(d)
    rec = make_rec(name, sym, d.index)
    r2, ma200, ma5 = rsi(c), pd.Series(c).rolling(200).mean().values, pd.Series(c).rolling(5).mean().values
    rows, pos = [], None
    for t in range(200, len(c)):
        if pos is None:
            if c[t] > ma200[t] and r2[t] < 5:
                s = 1
            elif c[t] < ma200[t] and r2[t] > 95:
                s = -1
            else:
                continue
            fill = c[t] + sp if s > 0 else c[t]
            pos = [s, t, fill, fill - s * 2 * N[t], 2 * N[t]]
            continue
        s, t0, fill, stop, risk = pos
        if stops and ((s > 0 and l[t] <= stop) or (s < 0 and h[t] + sp >= stop)):
            px, reason, h_out = (min(stop, o[t]) if s > 0 else max(stop, o[t] + sp)), "stop", 12
        elif (s > 0 and c[t] > ma5[t]) or (s < 0 and c[t] < ma5[t]):
            px, reason, h_out = (c[t] if s > 0 else c[t] + sp), "5-day average", 21
        else:
            continue
        rows.append(rec(s, t0, t, fill, px, risk, reason, 21, h_out))
        pos = None
    if pos is not None:
        s, t0, fill, _, risk = pos
        rows.append(rec(s, t0, len(c) - 1, fill, c[-1] + (sp if s < 0 else 0.0), risk, "end of data", 21, 21))
    return rows


def tom(sym, d, sp):
    o, h, l, c, N = prep(d)
    rec = make_rec("tom", sym, d.index)
    month = d.index.to_period("M")
    rows = []
    for i in np.flatnonzero(month[1:] != month[:-1]):  # i = last trading day of its month (day -1)
        t0, t1 = i - 1, i + 3
        if t0 < 21 or t1 >= len(c):
            continue
        fill, risk = c[t0] + sp, 2 * N[t0]
        stop = fill - risk
        hit = [t for t in range(t0 + 1, t1 + 1) if l[t] <= stop]
        if hit:
            rows.append(rec(1, t0, hit[0], fill, min(stop, o[hit[0]]), risk, "stop", 21, 12))
        else:
            rows.append(rec(1, t0, t1, fill, c[t1], risk, "day +3", 21, 21))
    return rows


def main():
    rows = []
    for sym in UNIVERSE:
        if not os.path.exists(os.path.join(DATA, f"{sym}_d1.pkl")):
            continue
        d, sp = load(sym)
        if len(d) < 300:
            continue
        rows += turtle(sym, d, sp, 20, 10, "turtle_s1") + turtle(sym, d, sp, 55, 20, "turtle_s2")
        if UNIVERSE[sym][1] == "Index":
            rows += rsi2(sym, d, sp, True, "rsi2") + rsi2(sym, d, sp, False, "rsi2_nostop") + tom(sym, d, sp)
    t = pd.DataFrame(rows)
    t.to_csv(os.path.join(RESULTS, "daily_trades.csv.gz"), index=False, float_format="%.6g")
    print(t.groupby("strategy").agg(markets=("symbol", "nunique"), trades=("r", "size"), avg_r=("r", "mean"),
                                    avg_r_gross=("r_gross", "mean")).round(3).to_string())


if __name__ == "__main__":
    main()
