"""Round 2: choose strategy variants per asset class on the history before the window, then test them on the window.

  python pipeline/search.py

Two families of daily-bar rules, on all 51 markets:
- breakout (trend following, the Turtle mechanics of daily.py): entry and exit channels of 20/10, 55/20, 100/50
  or 200/100 days, stop 2N or 4N.
- reversion (the RSI(2) mechanics of daily.py: longs above the 200-day average, shorts below): RSI(2) thresholds
  5/95, 10/90 or 25/75, exit at the first close beyond the 5- or 10-day average, stop 2N, 4N or none (sized as 2N).
Round 4 adds the two market-neutral families of neutral.py: pairs (lookback 20, 60 or 120 days x entry at 1.5, 2
or 2.5 standard deviations) and cross-sectional momentum (past 1, 3, 6 or 12-1 months x stop 3N or none).
For each family and asset class, the variant with the best Sharpe ratio before the window (Jan 2018 - Oct 2025, on
its own $10k account at 1% risk per trade) is chosen. Every stream with a positive Sharpe before the window - the
chosen variants, the turn of the month and the intraday strategies of round 1 - then trades in one account, which
is judged on Nov 2025 - Oct 2026. The window plays no part in any choice.
"""
import argparse
import os

import pandas as pd

import daily
import neutral
from data import DATA, RESULTS, UNIVERSE
from data import load as load_bars
from evaluate import hist_run, history, load, pair_table, prepare, report

BREAKOUT = [dict(n_in=a, n_out=b, k=k) for a, b in [(20, 10), (55, 20), (100, 50), (200, 100)] for k in (2.0, 4.0)]
REVERSION = [dict(lo=lo, hi=100 - lo, exit_ma=m, stops=k is not None, k=k or 2.0)
             for lo in (5, 10, 25) for m in (5, 10) for k in (2.0, 4.0, None)]


def name(family, p):
    if family == "breakout":
        return f"breakout {p['n_in']}/{p['n_out']}, stop {p['k']:g}N"
    return f"reversion {p['lo']}/{p['hi']}, exit ma{p['exit_ma']}, " + (f"stop {p['k']:g}N" if p["stops"] else "no stop")


def grid_trades(market_neutral=True):
    rows, bars = [], {}
    for sym in UNIVERSE:
        if not os.path.exists(os.path.join(DATA, f"{sym}_d1.pkl")):
            continue
        d, sp = load_bars(sym)
        if len(d) < 300:
            continue
        bars[sym] = (d, sp)
        for p in BREAKOUT:
            rows += daily.turtle(sym, d, sp, p["n_in"], p["n_out"], name("breakout", p), p["k"])
        for p in REVERSION:
            rows += daily.rsi2(sym, d, sp, p["stops"], name("reversion", p), p["lo"], p["hi"], p["exit_ma"], p["k"])
    if not market_neutral:
        return pd.DataFrame(rows).assign(kind="daily")
    for a, b, cls in neutral.PAIRS:  # round 4
        if a in bars and b in bars:
            rows += [r for L in (20, 60, 120) for Z in (1.5, 2.0, 2.5) for r in neutral.pairs(bars, a, b, cls, L, Z)]
    for cls in sorted({UNIVERSE[s][1] for s in bars}):
        rows += [r for look in (1, 3, 6, "12-1") for stop in (True, False) for r in neutral.xsmom(bars, cls, look, stop)]
    return pd.DataFrame(rows).assign(kind="daily")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--without-neutral", action="store_true", help="round 3: no pairs or cross-sectional momentum")
    args = ap.parse_args()
    tag = "search_round3" if args.without_neutral else "search"
    grid = prepare(grid_trades(market_neutral=not args.without_neutral))
    streams = pair_table(grid, ["strategy", "cls"]).rename(columns={"market": "example_market"})
    streams["family"] = streams["strategy"].str.split().str[0]
    streams.to_csv(os.path.join(RESULTS, f"{tag}_streams.csv"), index=False, float_format="%.4f")
    ok = streams.dropna(subset=["hist_sharpe", "sharpe"])
    print("%d variant x asset-class streams; correlation of Sharpe before the window with Sharpe in it: %.2f" % (
        len(ok), ok["hist_sharpe"].corr(ok["sharpe"])))
    best = streams.dropna(subset=["hist_sharpe"]).sort_values("hist_sharpe", ascending=False)
    best = best.groupby(["family", "cls"]).head(1)
    print(best[["family", "cls", "strategy", "hist_trades", "hist_sharpe", "trades", "sharpe"]].round(2)
          .to_string(index=False))

    r1 = prepare(load())
    r1 = r1[~r1["strategy"].str.startswith(("turtle", "rsi2"))]  # those rules are part of the grid above
    extra = []
    for (s, cls), g in r1.groupby(["strategy", "cls"]):
        h = history(g)
        if len(h) >= 30:
            extra.append(dict(strategy=s, cls=cls, hist_sharpe=hist_run(h)[0]["sharpe"]))
    extra = pd.DataFrame(extra)
    print(extra.round(2).to_string(index=False))

    pick = [(f"{r.strategy} ({r.cls})", grid[(grid["strategy"] == r.strategy) & (grid["cls"] == r.cls)])
            for r in best.itertuples()]
    pick += [(f"{r.strategy} ({r.cls})", r1[(r1["strategy"] == r.strategy) & (r1["cls"] == r.cls)])
             for r in extra.itertuples()]
    pd.concat([g.assign(stream=n) for n, g in pick], ignore_index=True).to_csv(
        os.path.join(RESULTS, f"{tag}_chosen_trades.csv.gz"), index=False, float_format="%.6g")
    keep = set(f"{r.strategy} ({r.cls})" for r in best.itertuples() if r.hist_sharpe > 0)
    keep |= set(f"{r.strategy} ({r.cls})" for r in extra.itertuples() if r.hist_sharpe > 0)
    port = pd.concat([g for n, g in pick if n in keep], ignore_index=True)
    groups = pick + [(f"portfolio: {len(keep)} streams positive before the window", port)]
    report(groups, tag)


if __name__ == "__main__":
    main()
