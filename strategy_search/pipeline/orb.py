"""5-minute opening range breakout, as published by Zarattini & Aziz (2023, SSRN 4416622).

  python pipeline/orb.py [--symbols ...]

Rules, unchanged from the paper: the first 5-minute candle of the cash session sets the direction
(up candle: long; down candle: short; open = close: no trade). Enter at the open of the second
5-minute candle, stop at the other end of the first candle, target 10 x the risk, otherwise exit at
the close. Risk 1% of the account per trade. US indices: 09:30-16:00 New York; DAX: 09:00-17:30
Frankfurt. Writes results/orb_trades.csv and prints R and account statistics.
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
OR_MIN, TARGET_R = 5, 10.0


def orb_trades(sym, or_min=OR_MIN, target_r=TARGET_R):
    tz, t_open, t_close = SESSIONS[sym]
    m1 = load_m1(sym)
    spread = spread_by_hour(sym)
    local = m1.tz_convert(tz)
    rows = []
    for day, d in local.groupby(local.index.date):
        day = pd.Timestamp(day)
        if not (TEST_START <= day <= TEST_END):
            continue
        open_ts = pd.Timestamp(f"{day.date()} {t_open}", tz=tz)
        close_ts = pd.Timestamp(f"{day.date()} {t_close}", tz=tz)
        orng = d[(d.index >= open_ts) & (d.index < open_ts + pd.Timedelta(minutes=or_min))]
        rest = d[(d.index >= open_ts + pd.Timedelta(minutes=or_min)) & (d.index < close_ts)]
        if len(orng) < or_min - 1 or len(rest) < 30 or orng.index[0] != open_ts:
            continue  # holiday / half day / missing data
        o, c = orng["open"].iloc[0], orng["close"].iloc[-1]
        if c == o:
            continue
        s = 1 if c > o else -1
        hi, lo = orng["high"].max(), orng["low"].min()
        first = rest.iloc[0]
        sp = lambda ts: spread[ts.tz_convert("UTC").hour]
        entry = first["open"] + (sp(rest.index[0]) if s > 0 else 0.0)
        stop = lo if s > 0 else hi
        risk = s * (entry - stop) if s > 0 else stop - first["open"]
        if risk <= 0:
            continue
        target = entry + s * target_r * risk
        exit_px, reason, exit_ts = None, "close", rest.index[-1]
        for ts, bar in rest.iterrows():
            spr = 0.0 if s > 0 else sp(ts)  # shorts are stopped / taken on the ask
            lo_b, hi_b, op_b = bar["low"] + spr, bar["high"] + spr, bar["open"] + spr
            if s > 0:
                if lo_b <= stop:
                    exit_px, reason, exit_ts = min(stop, op_b), "stop", ts
                    break
                if hi_b >= target:
                    exit_px, reason, exit_ts = max(target, op_b), "target", ts
                    break
            else:
                if hi_b >= stop:
                    exit_px, reason, exit_ts = max(stop, op_b), "stop", ts
                    break
                if lo_b <= target:
                    exit_px, reason, exit_ts = min(target, op_b), "target", ts
                    break
        if exit_px is None:
            last = rest.iloc[-1]
            exit_px = last["close"] + (0.0 if s > 0 else sp(rest.index[-1]))
        entry_px = entry if s > 0 else first["open"]
        r = s * (exit_px - entry_px) / risk
        rows.append(dict(symbol=sym, market=LABEL[sym], day=day.date(), dir=s, entry_time=rest.index[0].tz_convert("UTC"),
                         exit_time=exit_ts.tz_convert("UTC"), entry=entry_px, stop=stop, target=target, exit=exit_px,
                         risk_pts=risk, r=r, reason=reason, leverage_at_1pct=0.01 * entry_px / risk))
    return pd.DataFrame(rows)


def summarize(name, t):
    out = dict(strategy=name, **r_stats(t["r"]))
    for label, part in (("year1", t[pd.to_datetime(t["day"]) < SPLIT]), ("year2", t[pd.to_datetime(t["day"]) >= SPLIT])):
        out[f"{label}_avg_r"] = part["r"].mean()
    w, _ = weekly_stats(account(t))
    out.update(w)
    wc, _ = weekly_stats(account(t, max_leverage=20))
    out["avg_week_pct_lev20"], out["final_balance_lev20"] = wc["avg_week_pct"], wc["final_balance"]
    out["trades_over_20x"] = int((t["leverage_at_1pct"] > 20).sum())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=list(SESSIONS))
    args = ap.parse_args()
    all_t = []
    for sym in args.symbols:
        t = orb_trades(sym)
        all_t.append(t)
    trades = pd.concat(all_t, ignore_index=True)
    trades.to_csv(os.path.join(RESULTS, "orb_trades.csv"), index=False, float_format="%.6g")
    rows = [summarize(f"ORB {LABEL[s]}", trades[trades.symbol == s]) for s in args.symbols]
    rows.append(summarize("ORB all markets", trades))
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, "orb_summary.csv"), index=False, float_format="%.4f")
    cols = ["strategy", "trades", "win_rate_pct", "avg_r", "year1_avg_r", "year2_avg_r", "r_per_week", "avg_week_pct",
            "positive_weeks_pct", "worst_week_pct", "max_drawdown_pct", "final_balance", "avg_week_pct_lev20",
            "trades_over_20x"]
    print(res[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
