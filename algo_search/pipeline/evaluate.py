"""Every strategy on the $10k account at 1% risk per trade: the history before the window, and the last 12 months.

  python pipeline/evaluate.py

Window: trades entered 1 Nov 2025 - 30 Oct 2026 (52 weeks ending Friday). History: trades entered from 1 Jan 2018
(daily strategies; the daily data starts in 2017) or 1 Oct 2024 (intraday: the 1-minute data starts in Sep 2024)
to 31 Oct 2025. Every account
keeps all open positions under 20:1 leverage, the EU/UK retail limit on major indices. The Turtle rule of at most
12 positions open in one direction is applied to the Turtle systems.
"chosen on history" keeps each strategy-market pair whose average R before the window was positive over at least
20 trades. The choice uses nothing from the window, so the window is a fair test of it.
Risk scaling reruns the same trades at more than 1% per trade, to show what reaching 2% a week would have taken.
"""
import os
import sys

import numpy as np
import pandas as pd

from data import RESULTS, TEST_END, TEST_START

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                "strategy_search", "pipeline"))
from intraday import account, weekly_stats  # noqa: E402

CAP, TARGET = 20, 2.0
HIST_FROM = {"daily": pd.Timestamp("2018-01-01"), "intraday": pd.Timestamp("2024-10-01")}
HIST_END = TEST_START - pd.Timedelta(days=1)
WIN_END = TEST_END + pd.Timedelta(days=1)


def load():
    parts = []
    for name, kind in (("daily_trades.csv.gz", "daily"), ("intraday_trades.csv.gz", "intraday")):
        if os.path.exists(os.path.join(RESULTS, name)):
            parts.append(pd.read_csv(os.path.join(RESULTS, name)).assign(kind=kind))
    t = pd.concat(parts, ignore_index=True)
    for col in ("entry_time", "exit_time"):
        t[col] = pd.to_datetime(t[col], utc=True).dt.tz_localize(None)
    return t


def limit_direction(t, max_open=12):
    """Turtle portfolio rule: with max_open positions open in one direction, further signals that way are skipped."""
    t = t.sort_values("entry_time")
    open_, keep = [], []
    for row in t.itertuples():
        open_ = [(x, s) for x, s in open_ if x > row.entry_time]
        ok = sum(s == row.dir for _, s in open_) < max_open
        if ok:
            open_.append((row.exit_time, row.dir))
        keep.append(ok)
    return t[np.array(keep, dtype=bool)]


def prepare(t):
    """Apply the Turtle direction limit to each Turtle system, leave the rest as they are."""
    parts = [limit_direction(g) if s.startswith("turtle") else g for s, g in t.groupby("strategy")]
    return pd.concat(parts).sort_values("entry_time")


def window(t):
    return t[(t["entry_time"] >= TEST_START) & (t["entry_time"] < WIN_END)]


def history(t):
    start = t["kind"].map(HIST_FROM)
    return t[(t["entry_time"] >= start) & (t["entry_time"] < TEST_START)]


def summarize(name, t):
    h, w = history(t), window(t)
    out = dict(strategy=name, markets=t["symbol"].nunique(), hist_trades=len(h), hist_avg_r=h["r"].mean())
    if len(h):
        yr = h.groupby(h["entry_time"].dt.year)["r"].sum()
        out["hist_years_positive"] = f"{(yr > 0).sum()}/{len(yr)}"
        hw, _ = weekly_stats(account(h, max_leverage=CAP), h["kind"].map(HIST_FROM).min(), HIST_END)
        out.update(hist_avg_week_pct=hw["avg_week_pct"], hist_max_dd_pct=hw["max_drawdown_pct"])
    if len(w):
        ww, wk = weekly_stats(account(w, max_leverage=CAP), TEST_START, TEST_END)
        out.update(trades=len(w), trades_per_week=len(w) / ww["weeks"], avg_r=w["r"].mean(),
                   r_per_week=w["r"].sum() / ww["weeks"], avg_week_pct=ww["avg_week_pct"],
                   compound_week_pct=ww["compound_week_pct"], positive_weeks_pct=ww["positive_weeks_pct"],
                   weeks_at_2pct_pct=100 * (wk >= 0.02).mean(), worst_week_pct=ww["worst_week_pct"],
                   max_drawdown_pct=ww["max_drawdown_pct"], final_balance=ww["final_balance"])
    return out


def risk_for_target(name, g):
    """Smallest risk per trade (0.5% steps, up to 10%) that averages TARGET% a week in the window, and what the
    same risk did before the window."""
    w, h = window(g), history(g)
    rows = []
    for risk in np.round(np.arange(0.005, 0.1001, 0.005), 3):
        ww, _ = weekly_stats(account(w, risk=risk, max_leverage=CAP), TEST_START, TEST_END)
        rows.append(dict(strategy=name, risk_pct=100 * risk, avg_week_pct=ww["avg_week_pct"],
                         max_drawdown_pct=ww["max_drawdown_pct"], worst_week_pct=ww["worst_week_pct"],
                         final_balance=ww["final_balance"]))
        if ww["avg_week_pct"] >= TARGET:
            break
    if len(h):
        hw, _ = weekly_stats(account(h, risk=risk, max_leverage=CAP), h["kind"].map(HIST_FROM).min(), HIST_END)
        rows[-1].update(hist_avg_week_pct=hw["avg_week_pct"], hist_max_drawdown_pct=hw["max_drawdown_pct"],
                        hist_final_balance=hw["final_balance"])
    return rows


def main():
    t = prepare(load())
    groups = [(s, g) for s, g in t.groupby("strategy")]
    pairs = []
    for (s, sym), g in t.groupby(["strategy", "symbol"]):
        h, w = history(g), window(g)
        pairs.append(dict(strategy=s, symbol=sym, market=g["market"].iloc[0], hist_trades=len(h),
                          hist_avg_r=h["r"].mean(), trades=len(w), avg_r=w["r"].mean(), total_r=w["r"].sum()))
    pairs = pd.DataFrame(pairs)
    pairs.to_csv(os.path.join(RESULTS, "eval_pairs.csv"), index=False, float_format="%.4f")
    good = pairs[(pairs["hist_trades"] >= 20) & (pairs["hist_avg_r"] > 0)]
    chosen = t.merge(good[["strategy", "symbol"]], on=["strategy", "symbol"])
    groups += [("chosen on history: %d pairs" % len(good), chosen), ("everything together", t)]
    res = pd.DataFrame([summarize(n, g) for n, g in groups])
    res.to_csv(os.path.join(RESULTS, "eval_strategies.csv"), index=False, float_format="%.4f")
    scale = [row for n, g in groups if len(window(g)) for row in risk_for_target(n, g)]
    pd.DataFrame(scale).to_csv(os.path.join(RESULTS, "eval_risk_scaling.csv"), index=False, float_format="%.4f")
    cols = ["strategy", "markets", "hist_trades", "hist_avg_r", "hist_years_positive", "hist_avg_week_pct",
            "hist_max_dd_pct", "trades_per_week", "avg_r", "r_per_week", "avg_week_pct", "positive_weeks_pct",
            "weeks_at_2pct_pct", "worst_week_pct", "max_drawdown_pct", "final_balance"]
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(res[cols].round(3).to_string(index=False))
        last = pd.DataFrame(scale).groupby("strategy").tail(1)
        print("\nRisk per trade needed for %.0f%% a week in the window (or the most tried):" % TARGET)
        print(last.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
