"""Ideas 1-4 for the ORB + London filter on the Nasdaq-100, year by year over Jan 2019 - Oct 2026.

  python pipeline/orb15_history.py

Base: the PDF strategy as in orb15.py, with the London filter. The rules: 50/200 EMA trend on 15 minutes,
30-minute opening range from 09:30 New York, a full-body breakout close, entry at the next open, one trade a day,
entries until 12:30, anything open closed at 16:00. The London filter keeps only breakouts in the direction price
moved from 03:00 to 09:30. Stop at the other side of the range, or beyond the breakout candle; target 2R.
Each change was fixed before this history was run:
  1. early breakouts only: the breakout candle closes by 10:30;
  2. narrow opening range only: width at most 0.45 x the average session range of the previous 14 sessions;
  3. stop at the opening range's midpoint;
  4. target at a real level - (a) the previous session's high (longs) or low (shorts), (b) the London session's
     (03:00-09:30) high or low - or 2R if that level is less than 0.5R beyond the entry;
plus two combinations, also fixed in advance: 1 + 2, and 1 + 2 + 3.
A change counts only if it beats its base in most years on both average R and win rate.
Spreads: Dukascopy's own ask - bid by hour, measured separately for each year. Account: $10,000, 1% risk per
trade, compounding, positions under 20:1, over the whole period.
"""
import os

import numpy as np
import pandas as pd

import orb15
from orb15 import BASE, RESULTS, TZ, intraday, load_m1, summarize

SYM, SESSION = "USATECHIDXUSD", ("09:30", "16:00")
START, END = pd.Timestamp("2019-01-02"), pd.Timestamp("2026-10-30")
FILTERED = {**BASE, "london": True, "manage": "fixed", "target": 2.0}
CHANGES = {
    "base, London filter": {},
    "1. early breakouts (by 10:30)": dict(cutoff_h=1.0),
    "2. narrow opening range (<= 0.45 x ATR)": dict(max_or_atr=0.45),
    "3. stop at range midpoint": dict(stop="mid"),
    "4a. target previous session high/low": dict(target=("level", "prev_day")),
    "4b. target London high/low": dict(target=("level", "london")),
    "1 + 2": dict(cutoff_h=1.0, max_or_atr=0.45),
    "1 + 2 + 3": dict(cutoff_h=1.0, max_or_atr=0.45, stop="mid"),
    "no London filter (reference)": dict(london=False),
    "1 + 2, no London filter": dict(cutoff_h=1.0, max_or_atr=0.45, london=False),
    "1 + 2, no trend filter": dict(cutoff_h=1.0, max_or_atr=0.45, trend=None),
    "1 + 2, no London or trend filter": dict(cutoff_h=1.0, max_or_atr=0.45, london=False, trend=None),
}


def spreads_by_year(years):
    """Median ask - bid by UTC hour for each year, from Dukascopy's hourly bid and ask candles."""
    out = {}
    for y in years:
        parts = []
        for p in pd.period_range(f"{y}-01", f"{y}-12", freq="M"):
            fb, fa = (os.path.join(intraday.HYBRID_RAW, SYM, f"{p.year}-{p.month:02d}_{s}_h1.bi5") for s in ("BID", "ASK"))
            if os.path.exists(fb) and os.path.exists(fa):
                start = f"{p.year}-{p.month:02d}-01"
                j = intraday.decode(fb, start, intraday.SCALE[SYM]).join(
                    intraday.decode(fa, start, intraday.SCALE[SYM]), lsuffix="_b", rsuffix="_a", how="inner")
                parts.append(pd.DataFrame({"hour": j.index.hour, "spread": (j["open_a"] - j["open_b"]).clip(lower=0)}))
        out[y] = pd.concat(parts).groupby("hour")["spread"].median().reindex(range(24)).ffill().bfill().to_numpy()
    return out


def yearly(t):
    y = pd.to_datetime(t["day"]).dt.year
    return t.groupby(y).agg(trades=("r", "size"), win_pct=("r", lambda r: 100 * (r > 0.05).mean()),
                            avg_r=("r", "mean"), total_r=("r", "sum"))


def main():
    orb15.START, orb15.END = START, END
    m = load_m1(SYM)
    m = m[(m.index >= pd.Timestamp("2018-12-01", tz="UTC")) & (m.index < (END + pd.Timedelta(days=1)).tz_localize("UTC"))]
    spy = spreads_by_year(range(2018, 2027))
    years, hours = m.index.year.to_numpy(), m.index.hour.to_numpy()
    sp = np.empty(len(m))
    for y in np.unique(years):
        k = years == y
        sp[k] = spy[y][hours[k]]
    print("median spread 09:00-16:00 New York by year:",
          {int(y): round(float(np.median(spy[y][13:21])), 2) for y in spy}, flush=True)
    m = m.tz_convert(TZ)
    print("minutes by year:", m.groupby(m.index.year).size().to_dict(), flush=True)
    summ, per_year, keep = [], [], []
    for stop in ("range", "candle"):
        for name, change in CHANGES.items():
            v = {**FILTERED, "stop": stop, **change}
            if stop == "candle" and v["stop"] == "mid":
                continue  # the midpoint stop replaces either base stop; it is run once, with the range base
            label = f"{'range' if stop == 'range' else 'candle'} base | {name}"
            t = orb15.simulate(m, sp, v, SESSION)
            keep.append(t.assign(variant=label))
            s = summarize("Nasdaq-100", label, t)
            yr = yearly(t)
            per_year.append(yr.assign(variant=label).reset_index().rename(columns={"day": "year"}))
            summ.append(s)
            print(f"{label}: {len(t)} trades, avg R {t['r'].mean():+.3f}, win {100 * (t['r'] > 0.05).mean():.1f}%",
                  flush=True)
    years_tab = pd.concat(per_year, ignore_index=True)
    res = pd.DataFrame(summ)
    for label in res["version"]:  # years beating the base (the midpoint stop is compared with both bases)
        base = "range base | base, London filter" if label.startswith("range") else "candle base | base, London filter"
        a = years_tab[years_tab["variant"] == label].set_index("year")
        for bname, col in ((base, ""), ("candle base | base, London filter", " vs candle base")):
            if col and "midpoint" not in label and "1 + 2 + 3" not in label:
                continue
            b = years_tab[years_tab["variant"] == bname].set_index("year")
            j = a.join(b, rsuffix="_base", how="inner")
            res.loc[res["version"] == label, f"years better avg R{col}"] = f"{(j['avg_r'] > j['avg_r_base']).sum()}/{len(j)}"
            res.loc[res["version"] == label, f"years better win%{col}"] = f"{(j['win_pct'] > j['win_pct_base']).sum()}/{len(j)}"
    res.to_csv(os.path.join(RESULTS, "orb15_history_summary.csv"), index=False, float_format="%.4f")
    years_tab.to_csv(os.path.join(RESULTS, "orb15_history_years.csv"), index=False, float_format="%.4f")
    pd.concat(keep).to_csv(os.path.join(RESULTS, "orb15_history_trades.csv"), index=False, float_format="%.6g")
    with pd.option_context("display.width", 300, "display.max_columns", 40, "display.max_colwidth", 60):
        cols = ["version", "trades", "win_rate_pct", "avg_r", "total_r", "max_drawdown_pct", "final_balance"]
        print(res[cols + [c for c in res.columns if c.startswith("years better")]].round(3).to_string(index=False))
        wide = years_tab.pivot(index="variant", columns="year", values="avg_r").round(3)
        print(wide.to_string())
        print(years_tab.pivot(index="variant", columns="year", values="win_pct").round(1).to_string())
        print(years_tab.pivot(index="variant", columns="year", values="trades").to_string())


if __name__ == "__main__":
    main()
