"""What would a TradingAgents-style daily bias add to the strategy?

TradingAgents (github.com/TauricResearch/TradingAgents) makes one Buy/Overweight/Hold/Underweight/Sell
call per ticker per day from daily prices, news, filings, macro data and social sentiment, scored over
5 trading days. It cannot time intraday fib entries, so the only way to plug it into this strategy is as
a daily bias set before London opens: longs only on Buy/Overweight days, shorts only on
Sell/Underweight days, no trades on Hold days.

Running it needs an LLM API key, news/price feeds and ~20-30 model calls per day, and an LLM that has
read about the backtest period afterwards would leak the answer, so its real accuracy cannot be
measured here. Instead the bias is simulated at a given daily accuracy (how often the call matches the
direction of that day's NQ session, 18:00-17:00 New York), from a coin flip up to a perfect call, and the
backtest is re-run with the filter applied inside it (a skipped trade frees the slot and the daily loss
count, exactly as it would live).
"""
import os
import sys
from multiprocessing import Pool

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import RESULTS_DIR, load_prices, resample  # noqa: E402
from one_month import COST_PTS, RISK, START_BALANCE, TEST, window_rules  # noqa: E402
from replicate_strategy import Market, Rules, backtest  # noqa: E402

WINDOW = (10.0, 13.0)            # the window chosen out-of-sample in one_month.py
FULL = (pd.Timestamp("2026-03-10"), pd.Timestamp("2026-10-16"))
ACCURACIES = [0.50, 0.55, 0.60, 0.70]
SIMS = {"Sep 2026": 400, "Mar-Oct 2026": 120}

m1 = load_prices("m1")
MK = Market(m1, 2)
BASE = window_rules(WINDOW)


def day_direction():
    """+1 / -1 for each trading day: close vs open of the 18:00-17:00 New York session."""
    d = resample(m1, "1D")
    dates = (d.index + pd.Timedelta(hours=6)).date
    return dict(zip(dates, np.sign(d["close"].values - d["open"].values).astype(int)))


TRUTH = day_direction()


def run(period, bias):
    b = backtest(MK, Rules(**{**BASE.__dict__, "bias": bias}), *period)
    r_net = (b.r - COST_PTS / (b.entry - b.stop).abs()).values if len(b) else np.array([])
    months = max((period[1] - period[0]).days / 30.4, 1.0)
    growth = np.prod(1 + RISK * r_net) if len(r_net) else 1.0
    return {"trades": len(r_net), "net_R": float(r_net.sum()),
            "return_pct_per_month": 100 * (growth ** (1 / months) - 1), "total_return_pct": 100 * (growth - 1)}


def simulate(args):
    period, accuracy, hold, seed = args
    rng = np.random.default_rng(seed)
    bias = {}
    for day, truth in TRUTH.items():
        if hold and rng.random() < hold:
            bias[day] = 0
        else:
            bias[day] = truth if rng.random() < accuracy else -truth
    return run(period, bias)


def describe(label, period_name, sims):
    df = pd.DataFrame(sims)
    return {"period": period_name, "scenario": label, "trades": round(df.trades.mean(), 1),
            "net_R": round(df.net_R.mean(), 1),
            "return_pct_per_month": round(df.return_pct_per_month.mean(), 1),
            "total_return_pct": round(df.total_return_pct.mean(), 1),
            "total_return_p5": round(df.total_return_pct.quantile(0.05), 1),
            "total_return_p95": round(df.total_return_pct.quantile(0.95), 1),
            "chance_of_loss": round((df.total_return_pct < 0).mean(), 2) if len(df) > 1 else np.nan}


def main():
    periods = {"Sep 2026": TEST, "Mar-Oct 2026": FULL}
    rows = []
    with Pool(4) as pool:
        for name, period in periods.items():
            rows.append(describe("no filter (strategy alone)", name, [run(period, None)]))
            rows.append(describe("perfect daily bias (upper bound)", name, [run(period, TRUTH)]))
            rows.append(describe("always wrong (lower bound)", name, [run(period, {k: -v for k, v in TRUTH.items()})]))
            n = SIMS[name]
            scenarios = [(f"bias {int(a * 100)}% accurate", a, 0.0) for a in ACCURACIES]
            scenarios.append(("bias 55% accurate, 25% Hold days", 0.55, 0.25))
            for label, acc, hold in scenarios:
                sims = pool.map(simulate, [(period, acc, hold, 1000 * i + 7) for i in range(n)])
                rows.append(describe(label, name, sims))
                print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS_DIR, "agent_overlay_scenarios.csv"), index=False)
    pd.set_option("display.width", 220)
    print(res.to_string(index=False))

    # how much does the day's direction matter to this strategy?
    b = backtest(MK, BASE, *FULL)
    b["r_net"] = b.r - COST_PTS / (b.entry - b.stop).abs()
    b["with_day"] = [TRUTH.get(t.date()) == (1 if d == "long" else -1) for t, d in zip(b.entry_et, b.direction)]
    print("\nStrategy trades with vs against the day's direction (Mar-Oct, net R per trade):")
    print(b.groupby("with_day").r_net.agg(["size", "mean"]).round(3).to_string())
    print(f"days up: {np.mean([v > 0 for v in TRUTH.values()]):.0%}; start balance {START_BALANCE:,.0f}")


if __name__ == "__main__":
    main()
