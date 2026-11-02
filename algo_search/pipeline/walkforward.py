"""Round 5: walk-forward test of the whole process of rounds 2-4, one out-of-sample year at a time.

  python pipeline/walkforward.py

At the start of each test year the process runs on the data before it only: for each family and asset class the
variant with the best Sharpe ratio so far is picked (at least 20 trades), streams with a positive Sharpe so far are
admitted, and their risk per trade is set to maximise growth over the data so far (Kelly, at most 5% per trade).
The year that follows is out of sample. Test years run November to October; the last one is the window,
Nov 2025 - Oct 2026. Training always starts in January 2018. Each stream's weekly returns come from its own
account at 1% risk per trade (20:1 cap), scaled linearly to the chosen risk, and the streams are rebalanced weekly.
Every test year starts flat, with only the trades entered in that year, as a new account would.

The window portfolio is then rerun trade by trade at its Kelly risks: without a leverage limit, with all open
positions held under 20:1, and with overnight financing removed or doubled.
"""
import os

import numpy as np
import pandas as pd

from data import RESULTS, TEST_END, TEST_START
from evaluate import account, prepare, run, weekly_stats
from portfolio import kelly, stats
from search import grid_trades

START, MAX_RISK, CAP = pd.Timestamp("2018-01-01"), 5.0, 20
TESTS = [(pd.Timestamp(f"{y}-11-01"), pd.Timestamp(f"{y + 1}-10-31")) for y in range(2020, 2025)] + [
    (TEST_START, TEST_END)]


def choose(R, n_trades, before):
    """Streams the process would hold from `before`, and their full-Kelly risk per trade (in % of the account)."""
    tr = R[R.index < pd.Period(before, "W-FRI")]
    sharpe = np.sqrt(52) * tr.mean() / tr.std()
    ok = [c for c in R.columns if n_trades[c](before) >= 20 and np.isfinite(sharpe[c])]
    best = pd.Series({c: sharpe[c] for c in ok}).groupby(lambda c: (c.split()[0], c[c.rfind("(") + 1:-1])).idxmax()
    keep = [c for c in best if sharpe[c] > 0]
    return keep, kelly(tr[keep].mean().to_numpy(), tr[keep].cov().to_numpy(), MAX_RISK)


def main():
    g = prepare(grid_trades())
    g = g[g["entry_time"] >= START]
    g["stream"] = g["strategy"] + " (" + g["cls"] + ")"
    R = pd.DataFrame({s: run(t, START, TEST_END)[1] for s, t in g.groupby("stream")}).fillna(0.0)
    entries = {s: np.sort(t["entry_time"].to_numpy()) for s, t in g.groupby("stream")}
    n_trades = {s: (lambda e: lambda when: int(np.searchsorted(e, np.datetime64(when))))(e) for s, e in entries.items()}
    rows = []
    for a, b in TESTS:
        keep, full = choose(R, n_trades, a)
        sub = g[g["stream"].isin(keep) & (g["entry_time"] >= a) & (g["entry_time"] < b + pd.Timedelta(days=1))]
        te = pd.DataFrame({s: run(t, a, b)[1] for s, t in sub.groupby("stream")})  # a fresh start each year
        te = te.reindex(columns=keep).fillna(0.0).to_numpy()
        for plan, m in (("1% each", np.ones(len(keep))), ("half Kelly", full / 2), ("full Kelly", full)):
            rows.append(dict(test_year=f"{a:%b %Y} - {b:%b %Y}", streams=len(keep), plan=plan,
                             avg_risk_pct=m.mean(), **stats(te @ m)))
    wf = pd.DataFrame(rows)
    wf.to_csv(os.path.join(RESULTS, "walkforward.csv"), index=False, float_format="%.4f")
    with pd.option_context("display.width", 250):
        print(wf.round(2).to_string(index=False))
        for plan, p in wf.groupby("plan", sort=False):
            print("%-10s over the %d test years: median compound week %+.2f%%, worst year %+.2f%%/week, "
                  "years at 2%%+ a week: %d" % (plan, len(p), p["compound_week_pct"].median(),
                                                 p["compound_week_pct"].min(), (p["compound_week_pct"] >= 2).sum()))

    keep, full = choose(R, n_trades, TEST_START)
    w = g[g["stream"].isin(keep) & (g["entry_time"] >= TEST_START)].copy()
    risk = w["stream"].map(dict(zip(keep, full)))
    rows = []
    for plan, m in (("half Kelly", risk / 2), ("full Kelly", risk)):
        for fin in (0.0, 1.0, 2.0):
            for cap in (None, CAP):
                t = w.assign(r=m * (w["r_gross"] - fin * w["fin_r"]), leverage_at_1pct=m * w["leverage_at_1pct"])
                s, wk = weekly_stats(account(t, max_leverage=cap), TEST_START, TEST_END)
                rows.append(dict(plan=plan, financing=f"x{fin:g}", leverage_cap="none" if cap is None else f"{cap}:1",
                                 avg_week_pct=s["avg_week_pct"], compound_week_pct=s["compound_week_pct"],
                                 positive_weeks_pct=s["positive_weeks_pct"], worst_week_pct=s["worst_week_pct"],
                                 max_drawdown_pct=s["max_drawdown_pct"], final_balance=s["final_balance"]))
    ex = pd.DataFrame(rows)
    ex.to_csv(os.path.join(RESULTS, "window_exact.csv"), index=False, float_format="%.4f")
    print("\nWindow portfolio rerun trade by trade (%d streams, %d trades):" % (len(keep), len(w)))
    print(pd.DataFrame(dict(stream=keep, risk_pct_full=full)).round(2).to_string(index=False))
    print(ex.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
