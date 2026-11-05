"""A 15-minute opening range breakout on the Nasdaq-100 (US Tech 100), targets 1R and 2R, last 12 months.

  python pipeline/orb15_15min.py

Opening range: the first 15-minute candle, 09:30-09:45 New York. The rest follows orb15.py:
- entry on a full-body 15-minute candle closing beyond the range: a bullish candle above the high, or a bearish one
  below the low, in either direction (no trend, London or volume filter);
- entry at the next candle's open, one trade a day, entries until 12:30, anything open closed at 16:00;
- stop beyond the breakout candle, or at the other side of the range; target 1R or 2R.
Also run with the two filters of the best 30-minute version: the range at most 0.45 x the average session range
of the previous 14 sessions, and the breakout candle closing by 10:30. A 15-minute range is narrower than a
30-minute one, so that filter skips fewer days here.
Window: 3 Nov 2025 - 30 Oct 2026. $10,000, 1% risk per trade, compounding, positions under 20:1.
"""
import os

import pandas as pd

import orb15
from orb15 import BASE, END, RESULTS, START, TZ, account, load_m1, spread_by_hour, summarize

VERSIONS = {}
for f_name, f in (("plain", {}), ("narrow range + breakout by 10:30", dict(max_or_atr=0.45, cutoff_h=1.0))):
    for stop, s_name in (("candle", "stop beyond breakout candle"), ("range", "stop at other side of range")):
        for tp in (1.0, 2.0):
            VERSIONS[f"{f_name} | {s_name} | target {tp:g}R"] = dict(or_min=15, trend=None, london=False, stop=stop,
                                                                     target=tp, **f)


def monthly(t):
    """Month-by-month % change of a fresh $10,000 account."""
    curve = account(t, max_leverage=20)
    months = pd.period_range(START.strftime("%Y-%m"), END.strftime("%Y-%m"), freq="M")
    end = curve.groupby(curve.index.to_period("M")).last().reindex(months).ffill().fillna(10_000.0)
    return 100 * (end / end.shift(1).fillna(10_000.0) - 1)


def main():
    m = load_m1("USATECHIDXUSD")
    m = m[(m.index >= pd.Timestamp("2025-10-01", tz="UTC")) & (m.index < (END + pd.Timedelta(days=1)).tz_localize("UTC"))]
    sp = spread_by_hour("USATECHIDXUSD").to_numpy()[m.index.hour]
    m = m.tz_convert(TZ)
    rows, months, keep = [], {}, []
    for name, change in VERSIONS.items():
        t = orb15.simulate(m, sp, {**BASE, "manage": "fixed", **change}, ("09:30", "16:00"))
        s = summarize("Nasdaq-100", name, t)
        s["total_return_pct"] = 100 * (s["final_balance"] / 10_000 - 1)
        rows.append(s)
        months[name] = monthly(t)
        keep.append(t.assign(version=name))
    res = pd.DataFrame(rows)
    mon = pd.DataFrame(months)
    mon.index.name = "month"
    res.to_csv(os.path.join(RESULTS, "orb15_15min_results.csv"), index=False, float_format="%.4f")
    mon.to_csv(os.path.join(RESULTS, "orb15_15min_monthly.csv"), float_format="%.4f")
    pd.concat(keep).to_csv(os.path.join(RESULTS, "orb15_15min_trades.csv"), index=False, float_format="%.6g")
    with pd.option_context("display.width", 260, "display.max_columns", 30, "display.max_colwidth", 70):
        print(res[["version", "trades", "win_rate_pct", "target_pct", "stop_pct", "close_pct", "avg_r", "total_r",
                   "avg_risk_pts", "positive_weeks_pct", "max_drawdown_pct", "total_return_pct", "final_balance"]]
              .round(2).to_string(index=False))
        print(mon.round(2).T.to_string())


if __name__ == "__main__":
    main()
