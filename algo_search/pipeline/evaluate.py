"""Every strategy on the $10k account at 1% risk per trade: the history before the window, and the last 12 months.

  python pipeline/evaluate.py

Window: trades entered 1 Nov 2025 - 30 Oct 2026 (52 weeks ending Friday). History: trades entered from 1 Jan 2018
(daily strategies; the daily data starts in 2017) or 1 Oct 2024 (intraday: the 1-minute data starts in Sep 2024)
to 31 Oct 2025. Every account keeps all open positions under 20:1 leverage, the EU/UK retail limit on major
indices. The Turtle rule of at most 12 positions open in one direction is applied to the breakout systems.
The target is compounded: 2% a week for 52 weeks turns $10,000 into $28,003. A plain average of weekly returns can
show 2% while the account shrinks, when the weeks swing widely.
"chosen on history" keeps each strategy-market pair whose own account had a positive Sharpe ratio before the
window, over at least 30 trades. The choice uses nothing from the window, so the window is a fair test of it.
Risk scaling reruns the same trades at more than 1% per trade, to show what reaching the target would have taken
and what the same risk did before the window.
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
COLS = ["strategy", "markets", "hist_trades", "hist_avg_r", "hist_years_positive", "hist_compound_week_pct",
        "hist_sharpe", "hist_max_dd_pct", "trades_per_week", "avg_r", "compound_week_pct", "sharpe",
        "positive_weeks_pct", "worst_week_pct", "max_drawdown_pct", "final_balance"]


def load():
    parts = []
    for name, kind in (("daily_trades.csv.gz", "daily"), ("intraday_trades.csv.gz", "intraday")):
        if os.path.exists(os.path.join(RESULTS, name)):
            parts.append(pd.read_csv(os.path.join(RESULTS, name)).assign(kind=kind))
    t = pd.concat(parts, ignore_index=True)
    for col in ("entry_time", "exit_time"):
        t[col] = pd.to_datetime(t[col], utc=True, format="mixed").dt.tz_localize(None)  # daily naive, intraday UTC
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
    parts = [limit_direction(g) if s.startswith(("turtle", "breakout")) else g for s, g in t.groupby("strategy")]
    return pd.concat(parts).sort_values("entry_time")


def window(t):
    return t[(t["entry_time"] >= TEST_START) & (t["entry_time"] < WIN_END)]


def history(t):
    return t[(t["entry_time"] >= t["kind"].map(HIST_FROM)) & (t["entry_time"] < TEST_START)]


def run(t, start, end, risk=0.01):
    """Weekly statistics of the capped account, with the annualised Sharpe ratio of its weekly returns."""
    w, wk = weekly_stats(account(t, risk=risk, max_leverage=CAP), start, end)
    w["sharpe"] = float(np.sqrt(52) * wk.mean() / wk.std()) if wk.std() > 0 else 0.0
    return w, wk


def hist_run(h, risk=0.01):
    return run(h, h["kind"].map(HIST_FROM).min(), HIST_END, risk)


def summarize(name, t):
    h, w = history(t), window(t)
    out = dict(strategy=name, markets=t["symbol"].nunique(), hist_trades=len(h), hist_avg_r=h["r"].mean())
    if len(h):
        yr = h.groupby(h["entry_time"].dt.year)["r"].sum()
        hw, _ = hist_run(h)
        out.update(hist_years_positive=f"{(yr > 0).sum()}/{len(yr)}", hist_compound_week_pct=hw["compound_week_pct"],
                   hist_sharpe=hw["sharpe"], hist_max_dd_pct=hw["max_drawdown_pct"])
    if len(w):
        ww, wk = run(w, TEST_START, TEST_END)
        out.update(trades=len(w), trades_per_week=len(w) / ww["weeks"], avg_r=w["r"].mean(),
                   avg_week_pct=ww["avg_week_pct"], compound_week_pct=ww["compound_week_pct"], sharpe=ww["sharpe"],
                   positive_weeks_pct=ww["positive_weeks_pct"], weeks_at_2pct_pct=100 * (wk >= 0.02).mean(),
                   worst_week_pct=ww["worst_week_pct"], max_drawdown_pct=ww["max_drawdown_pct"],
                   final_balance=ww["final_balance"])
    return out


def risk_for_target(name, g):
    """Smallest risk per trade (0.5% steps, up to 10%) whose account compounds TARGET% a week in the window, and
    what the same risk did before the window."""
    w, h = window(g), history(g)
    rows = []
    for risk in np.round(np.arange(0.005, 0.1001, 0.005), 3):
        ww, _ = run(w, TEST_START, TEST_END, risk)
        rows.append(dict(strategy=name, risk_pct=100 * risk, compound_week_pct=ww["compound_week_pct"],
                         max_drawdown_pct=ww["max_drawdown_pct"], worst_week_pct=ww["worst_week_pct"],
                         final_balance=ww["final_balance"]))
        if ww["compound_week_pct"] >= TARGET:
            break
    if len(h):
        hw, _ = hist_run(h, risk)
        rows[-1].update(hist_compound_week_pct=hw["compound_week_pct"], hist_max_drawdown_pct=hw["max_drawdown_pct"],
                        hist_final_balance=hw["final_balance"])
    return rows


def pair_table(t, keys):
    """History Sharpe (accounts with at least 30 trades before the window) and window result of every group."""
    rows = []
    for k, g in t.groupby(keys):
        h, w = history(g), window(g)
        row = dict(zip(keys, k), market=g["market"].iloc[0], hist_trades=len(h), hist_avg_r=h["r"].mean(),
                   trades=len(w), avg_r=w["r"].mean(), total_r=w["r"].sum())
        if len(h) >= 30:
            row["hist_sharpe"] = hist_run(h)[0]["sharpe"]
        if len(w):
            row["sharpe"] = run(w, TEST_START, TEST_END)[0]["sharpe"]
        rows.append(row)
    return pd.DataFrame(rows)


def report(groups, tag):
    res = pd.DataFrame([summarize(n, g) for n, g in groups])
    res.to_csv(os.path.join(RESULTS, f"{tag}_strategies.csv"), index=False, float_format="%.4f")
    scale = pd.DataFrame([row for n, g in groups if len(window(g)) for row in risk_for_target(n, g)])
    scale.to_csv(os.path.join(RESULTS, f"{tag}_risk_scaling.csv"), index=False, float_format="%.4f")
    with pd.option_context("display.width", 250, "display.max_columns", 30, "display.max_colwidth", 48):
        print(res[[c for c in COLS if c in res]].round(3).to_string(index=False))
        print("\nRisk per trade needed to compound %.0f%% a week in the window (or the most tried):" % TARGET)
        print(scale.groupby("strategy", sort=False).tail(1).round(2).to_string(index=False))
    return res, scale


def main():
    t = prepare(load())
    pairs = pair_table(t, ["strategy", "symbol"])
    pairs.to_csv(os.path.join(RESULTS, "eval_pairs.csv"), index=False, float_format="%.4f")
    good = pairs[pairs["hist_sharpe"] > 0]
    chosen = t.merge(good[["strategy", "symbol"]], on=["strategy", "symbol"])
    groups = [(s, g) for s, g in t.groupby("strategy")]
    groups += [(f"chosen on history: {len(good)} pairs", chosen), ("everything together", t)]
    report(groups, "eval")
    ok = pairs.dropna(subset=["hist_sharpe", "sharpe"])
    print("\nPairs: correlation of Sharpe before the window with Sharpe in the window: %.2f (%d pairs)" % (
        ok["hist_sharpe"].corr(ok["sharpe"]), len(ok)))


if __name__ == "__main__":
    main()
