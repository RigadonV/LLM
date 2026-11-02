"""Round 3: size the streams of round 2 as one portfolio, with the weights set before the window.

  python pipeline/portfolio.py

Uses the daily streams that search.py chose and that had a positive Sharpe ratio before the window. The intraday
streams are left out: their 13 months of history are too short to estimate how they move with the others. Each
stream's weekly returns at 1% risk per trade are measured before the window (Jan 2018 - Oct 2025). The risk per
trade of each stream is then set to maximise the growth of the combined account over that history - the Kelly
criterion for correlated returns, maximising mean - variance / 2 of the weekly portfolio return - with at most
MAX_RISK % per trade. Half of that risk (half Kelly) is the usual safer choice. Both are judged on
Nov 2025 - Oct 2026. Returns are scaled linearly from the 1% accounts and the streams are rebalanced weekly.
The 20:1 leverage limit is not applied here; the table shows the highest leverage the positions would have needed.
"""
import argparse
import os

import numpy as np
import pandas as pd

from data import RESULTS, TEST_END, TEST_START
from evaluate import HIST_END, HIST_FROM, history, run, window

MAX_RISK = 5.0


def load_streams(source):
    t = pd.read_csv(os.path.join(RESULTS, f"{source}_chosen_trades.csv.gz"))
    for col in ("entry_time", "exit_time"):
        t[col] = pd.to_datetime(t[col], utc=True, format="mixed").dt.tz_localize(None)
    return t[t["kind"] == "daily"]


def kelly(mu, cov, wmax, steps=50000):
    """Risk multipliers in [0, wmax] that maximise mu.w - w'.cov.w / 2 (projected gradient ascent)."""
    w = np.zeros(len(mu))
    eta = 1 / np.linalg.eigvalsh(cov).max()
    for _ in range(steps):
        w = np.clip(w + eta * (mu - cov @ w), 0, wmax)
    return w


def stats(r):
    bal = 10_000 * np.cumprod(1 + r)
    curve = np.r_[10_000, bal]
    return dict(compound_week_pct=100 * ((bal[-1] / 1e4) ** (1 / len(r)) - 1), avg_week_pct=100 * r.mean(),
                sharpe=np.sqrt(52) * r.mean() / r.std(), positive_weeks_pct=100 * (r > 0).mean(),
                worst_week_pct=100 * r.min(), max_drawdown_pct=100 * (1 - curve / np.maximum.accumulate(curve)).max(),
                final_balance=bal[-1])


def peak_leverage(t, mult):
    """Highest total notional / balance of the positions open at one time, each stream at its multiple of 1%."""
    ev = []
    for s, g in t.groupby("stream"):
        lev = g["leverage_at_1pct"].to_numpy() * mult.get(s, 0.0)
        ev += [(a, 0, x) for a, x in zip(g["entry_time"], lev)] + [(b, 1, -x) for b, x in zip(g["exit_time"], lev)]
    ev.sort(key=lambda e: (e[0], e[1]))
    return float(np.max(np.cumsum([x for _, _, x in ev]))) if ev else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="search", help="search (rounds 2+4) or search_round3 (no market-neutral)")
    source = ap.parse_args().source
    out = "portfolio" if source == "search" else "portfolio_round3"
    t = load_streams(source)
    hist_sharpe = {s: run(history(g), HIST_FROM["daily"], HIST_END)[0]["sharpe"] for s, g in t.groupby("stream")}
    names = [s for s, v in hist_sharpe.items() if v > 0]
    t = t[t["stream"].isin(names)]
    H = pd.DataFrame({s: run(history(g), HIST_FROM["daily"], HIST_END)[1] for s, g in t.groupby("stream")})
    W = pd.DataFrame({s: run(window(g), TEST_START, TEST_END)[1] for s, g in t.groupby("stream")}).fillna(0.0)
    W = W[H.columns]
    full = kelly(H.mean().to_numpy(), H.cov().to_numpy(), MAX_RISK)
    plans = {"1% risk per trade on every stream": np.ones(len(full)), "half Kelly (set on history)": full / 2,
             "full Kelly (set on history)": full}
    rows = []
    for plan, m in plans.items():
        mult = dict(zip(H.columns, m))
        rows.append(dict(plan=plan, period="before the window (fit here)", **stats(H.to_numpy() @ m),
                         peak_leverage=peak_leverage(history(t), mult)))
        rows.append(dict(plan=plan, period="last 12 months", **stats(W.to_numpy() @ m),
                         peak_leverage=peak_leverage(window(t), mult)))
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, f"{out}_plans.csv"), index=False, float_format="%.4f")
    weights = pd.DataFrame(dict(stream=H.columns, hist_sharpe=[hist_sharpe[s] for s in H.columns],
                                window_sharpe=[np.sqrt(52) * W[s].mean() / W[s].std() for s in H.columns],
                                risk_pct_full=full, risk_pct_half=full / 2))
    weights.to_csv(os.path.join(RESULTS, f"{out}_weights.csv"), index=False, float_format="%.4f")
    print("Average correlation between streams' weekly returns before the window: %.2f" % (
        (H.corr().to_numpy().sum() - len(H.columns)) / (len(H.columns) ** 2 - len(H.columns))))
    with pd.option_context("display.width", 250, "display.max_colwidth", 50):
        print(weights.round(2).to_string(index=False))
        print(res.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
