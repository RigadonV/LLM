"""Opening range breakout. Default rules are as published by Zarattini & Aziz (2023, SSRN 4416622).

  python pipeline/orb.py [--symbols ...]          # published rules, every market
  (orb_search.py runs the variants)

Published rules: the first 5-minute candle of the cash session sets the direction (up candle: long;
down candle: short; open = close: no trade). Enter at the open of the second 5-minute candle, stop at
the other end of the first candle, target 10 x the risk, otherwise exit at the close. Risk 1% of the
account per trade.
Variant knobs: or_min (opening-range length), target_r (None = hold to the close), and entry
"break" (stop orders at the range high and low; the first one hit is the trade, stop at the other end).
Sessions: US indices 09:30-16:00 New York; DAX 09:00-17:30 Frankfurt.
"""
import argparse
import os

import numpy as np
import pandas as pd

from intraday import (LABEL, RESULTS, SPLIT, TEST_END, TEST_START, account, load_m1, r_stats, spread_by_hour,
                      weekly_stats)

SESSIONS = {"USATECHIDXUSD": ("America/New_York", "09:30", "16:00"),
            "USA500IDXUSD": ("America/New_York", "09:30", "16:00"),
            "USA30IDXUSD": ("America/New_York", "09:30", "16:00"),
            "DEUIDXEUR": ("Europe/Berlin", "09:00", "17:30")}
_days = {}


def session_days(sym):
    """Per trading day: minute times (UTC), bid open/high/low/close arrays and the spread of each minute."""
    if sym in _days:
        return _days[sym]
    tz, t_open, t_close = SESSIONS[sym]
    m1 = load_m1(sym)
    spread = spread_by_hour(sym).values
    local = m1.tz_convert(tz)
    out = []
    for day, d in local.groupby(local.index.date):
        day = pd.Timestamp(day)
        if not (TEST_START <= day <= TEST_END):
            continue
        open_ts = pd.Timestamp(f"{day.date()} {t_open}", tz=tz)
        close_ts = pd.Timestamp(f"{day.date()} {t_close}", tz=tz)
        s = d[(d.index >= open_ts) & (d.index < close_ts)]
        if len(s) < 120 or s.index[0] != open_ts:
            continue  # holiday, half day or missing data
        mins = ((s.index - open_ts).total_seconds() // 60).astype(int).values
        out.append(dict(day=day.date(), t=s.index.tz_convert("UTC"), mins=mins, o=s["open"].values,
                        h=s["high"].values, l=s["low"].values, c=s["close"].values,
                        sp=spread[s.index.tz_convert("UTC").hour]))
    _days[sym] = out
    return out


def first_hit(cond):
    i = np.flatnonzero(cond)
    return i[0] if len(i) else None


def orb_trades(sym, or_min=5, target_r=10.0, entry="candle"):
    rows = []
    for D in session_days(sym):
        k = np.searchsorted(D["mins"], or_min)  # first bar after the opening range
        if k < or_min - 1 or k >= len(D["mins"]) - 5:
            continue
        hi, lo = D["h"][:k].max(), D["l"][:k].min()
        o, h, l, c, sp = D["o"][k:], D["h"][k:], D["l"][k:], D["c"][k:], D["sp"][k:]
        if entry == "candle":
            first_o, last_c = D["o"][0], D["c"][k - 1]
            if last_c == first_o:
                continue
            s, j = (1 if last_c > first_o else -1), 0
            fill = o[0] + (sp[0] if s > 0 else 0.0)
        else:  # "break": buy stop at the range high (on the ask), sell stop at the range low
            up, dn = first_hit(h + sp >= hi), first_hit(l <= lo)
            if up is None and dn is None:
                continue
            if dn is None or (up is not None and up < dn):
                s, j = 1, up
                fill = max(hi, o[j] + sp[j])
            elif up is None or dn < up:
                s, j = -1, dn
                fill = min(lo, o[j])
            else:
                continue  # both in the same minute: order unknown, skip
        stop = lo if s > 0 else hi
        risk = (fill - stop) if s > 0 else (stop - fill)
        if risk <= 0:
            continue
        target = fill + s * target_r * risk if target_r else None
        # walk forward from the entry minute; shorts are stopped and taken on the ask
        adj = 0.0 if s > 0 else 1.0
        hh, ll, oo = h[j:] + adj * sp[j:], l[j:] + adj * sp[j:], o[j:] + adj * sp[j:]
        if entry == "break":  # the entry minute itself: only the part after the fill is known, so skip its open
            oo = oo.copy()
            oo[0] = fill
        st = first_hit(ll <= stop) if s > 0 else first_hit(hh >= stop)
        tg = None
        if target is not None:
            tg = first_hit(hh >= target) if s > 0 else first_hit(ll <= target)
        if st is not None and (tg is None or st <= tg):
            x = st
            exit_px = min(stop, oo[x]) if s > 0 else max(stop, oo[x])
            reason = "stop"
        elif tg is not None:
            x = tg
            exit_px = max(target, oo[x]) if s > 0 else min(target, oo[x])
            reason = "target"
        else:
            x = len(hh) - 1
            exit_px = c[-1] + adj * sp[-1]
            reason = "close"
        r = s * (exit_px - fill) / risk
        rows.append(dict(symbol=sym, market=LABEL[sym], day=D["day"], dir=s, entry_time=D["t"][k + j],
                         exit_time=D["t"][k + j + x], entry=fill, stop=stop, exit=exit_px, risk_pts=risk, r=r,
                         reason=reason, leverage_at_1pct=0.01 * fill / risk))
    return pd.DataFrame(rows)


def summarize(name, t, start=TEST_START, end=TEST_END):
    out = dict(strategy=name, **r_stats(t["r"]))
    days = pd.to_datetime(t["day"])
    out["year1_avg_r"], out["year2_avg_r"] = t["r"][days < SPLIT].mean(), t["r"][days >= SPLIT].mean()
    w, _ = weekly_stats(account(t), start, end)
    out.update(w)
    out["r_per_week"] = t["r"].sum() / w["weeks"]
    out["trades_over_20x"] = int((t["leverage_at_1pct"] > 20).sum())
    return out


COLS = ["strategy", "trades", "win_rate_pct", "avg_r", "year1_avg_r", "year2_avg_r", "r_per_week", "avg_week_pct",
        "positive_weeks_pct", "worst_week_pct", "max_drawdown_pct", "final_balance", "trades_over_20x"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=list(SESSIONS))
    args = ap.parse_args()
    trades = pd.concat([orb_trades(s) for s in args.symbols], ignore_index=True)
    trades.to_csv(os.path.join(RESULTS, "orb_published_trades.csv"), index=False, float_format="%.6g")
    rows = [summarize(f"ORB {LABEL[s]}", trades[trades.symbol == s]) for s in args.symbols]
    rows.append(summarize("ORB, all these markets in one account", trades))
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, "orb_published_summary.csv"), index=False, float_format="%.4f")
    print(res[COLS].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
