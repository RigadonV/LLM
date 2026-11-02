"""Targets of 1R / 2R / 3R, breakeven at 1R, a trailing stop from 1R, and the London session's bias, for the ORB.

  python pipeline/orb15_manage.py [--period last|prior]

Same strategy, data and window as orb15.py (--period prior: the 12 months before it, as a robustness check only):
50/200 EMA trend, 30-minute opening range, full-body breakout candle,
no volume condition, one trade a day. Both stops the PDF allows: the other side of the opening range, or beyond
the breakout candle. Trade management:
- fixed: the stop stays put; target 1R, 2R or 3R.
- breakeven at 1R: once price has gone 1R in the trade's favour, the stop moves to the entry price.
- trailing from 1R: once price has gone 1R, the stop moves to the entry and then follows the best price at 1R
  behind it; target 2R, 3R or none (held to the session close).
Stop moves are made at the end of the minute that reached 1R, so they count from the next minute.
London bias: bullish if price at the session open (09:30 Nasdaq-100, 08:20 gold) is above its price at 03:00 New
York, the London open; bearish if below. It is known before the opening range forms. Trades are split into those
with London's move and those against it, and "London filter" runs only take breakouts with it.
"""
import argparse
import os

import numpy as np
import pandas as pd

import orb15
from orb15 import BASE, MARKETS, RESULTS, TZ, intraday, load_m1, spread_by_hour, summarize

STOPS = {"range": "stop at other side of range", "candle": "stop beyond breakout candle"}
PLANS = [("fixed", 1.0), ("fixed", 2.0), ("fixed", 3.0), ("be", 2.0), ("be", 3.0), ("trail", 2.0), ("trail", 3.0),
         ("trail", None)]
NAME = {"fixed": "fixed stop", "be": "breakeven at 1R", "trail": "trailing from 1R"}


def plan_name(manage, target, london=False):
    return f"{NAME[manage]}, target {'none' if target is None else f'{target:g}R'}" + (", London filter" if london else "")


def bias_split(market, stop, plan, t):
    """Trades with London's move against those against it, with a Welch t-statistic for the difference in mean R."""
    out = dict(market=market, stop_rule=stop, plan=plan)
    for name, g in (("with", t[t["dir"] == t["london_bias"]]), ("against", t[t["dir"] == -t["london_bias"]])):
        out.update({f"{name}_trades": len(g), f"{name}_win_pct": 100 * (g["r"] > 0.05).mean(),
                    f"{name}_avg_r": g["r"].mean(), f"{name}_total_r": g["r"].sum()})
    a, b = t.loc[t["dir"] == t["london_bias"], "r"], t.loc[t["dir"] == -t["london_bias"], "r"]
    se = np.sqrt(a.var() / len(a) + b.var() / len(b)) if len(a) > 1 and len(b) > 1 else np.nan
    out["t_stat"] = (a.mean() - b.mean()) / se if se and se > 0 else np.nan
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="last", choices=["last", "prior"],
                    help="last: 3 Nov 2025 - 30 Oct 2026; prior: 4 Nov 2024 - 31 Oct 2025, a robustness check only")
    period = ap.parse_args().period
    if period == "prior":
        orb15.START, orb15.END = pd.Timestamp("2024-11-04"), pd.Timestamp("2025-10-31")
        intraday.TEST_START, intraday.TEST_END = pd.Timestamp("2024-11-01"), orb15.END
    suffix = "" if period == "last" else "_prior"
    rows, splits, keep = [], [], []
    for sym, info in MARKETS.items():
        m = load_m1(sym)
        m = m[(m.index >= (orb15.START - pd.Timedelta(days=33)).tz_localize("UTC")) &
              (m.index < (orb15.END + pd.Timedelta(days=1)).tz_localize("UTC"))]
        sp = spread_by_hour(sym).to_numpy()[m.index.hour]
        m = m.tz_convert(TZ)
        for stop, stop_name in STOPS.items():
            runs = [(mg, tg, False) for mg, tg in PLANS] + [("fixed", tg, True) for tg in (1.0, 2.0, 3.0)]
            for manage, target, london in runs:
                v = {**BASE, "stop": stop, "manage": manage, "target": target, "london": london}
                t = orb15.simulate(m, sp, v, info["session"])
                name = plan_name(manage, target, london)
                s = summarize(info["label"], name, t)
                hit1 = t["reached_1r"]
                s.update(stop_rule=stop_name, reached_1r=int(hit1.sum()),
                         after_1r_target=int((hit1 & (t["reason"] == "target")).sum()),
                         after_1r_breakeven=int((t["reason"] == "breakeven").sum()),
                         after_1r_trailing=int((t["reason"] == "trailing stop").sum()),
                         after_1r_trailing_avg_r=t.loc[t["reason"] == "trailing stop", "r"].mean(),
                         after_1r_close=int((hit1 & (t["reason"] == "session close")).sum()),
                         after_1r_stop=int((hit1 & (t["reason"] == "stop")).sum()))
                rows.append(s)
                keep.append(t.assign(market=info["label"], stop_rule=stop_name, plan=name))
                if not london:
                    splits.append(bias_split(info["label"], stop_name, name, t))
    res, spl = pd.DataFrame(rows), pd.DataFrame(splits)
    res.to_csv(os.path.join(RESULTS, f"orb15_management{suffix}.csv"), index=False, float_format="%.4f")
    spl.to_csv(os.path.join(RESULTS, f"orb15_london_bias{suffix}.csv"), index=False, float_format="%.4f")
    pd.concat(keep).to_csv(os.path.join(RESULTS, f"orb15_management_trades{suffix}.csv"), index=False,
                           float_format="%.6g")
    with pd.option_context("display.width", 260, "display.max_columns", 40, "display.max_colwidth", 45):
        print(res[["market", "stop_rule", "version", "trades", "win_rate_pct", "target_pct", "stop_pct", "close_pct",
                   "avg_r", "total_r", "max_drawdown_pct", "final_balance"]].round(2).to_string(index=False))
        print(res[["market", "stop_rule", "version", "trades", "reached_1r", "after_1r_target", "after_1r_breakeven",
                   "after_1r_trailing", "after_1r_trailing_avg_r", "after_1r_close", "after_1r_stop"]]
              .round(2).to_string(index=False))
        print(spl.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
