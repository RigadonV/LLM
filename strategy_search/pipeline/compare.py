"""One table for every strategy tested in this search, on the same $10k account at 1% risk per trade.

  python pipeline/compare.py

Reads the trade files written by orb.py, orb_search.py and noise_momentum.py. Each account is shown without a
leverage limit and with all open positions together capped at 20:1, the EU/UK retail limit on major indices, which
is the most a regulated broker would let a $10k account hold.
"""
import os

import pandas as pd

from intraday import RESULTS, SPLIT, TEST_END, TEST_START, account, weekly_stats

CAP = 20
KEYS = ["avg_week_pct", "compound_week_pct", "positive_weeks_pct", "weeks_at_4pct_pct", "worst_week_pct",
        "max_drawdown_pct", "final_balance"]


def load(name):
    t = pd.read_csv(os.path.join(RESULTS, name))
    for col in ("entry_time", "exit_time"):
        t[col] = pd.to_datetime(t[col], utc=True)
    return t


def row(name, t, start, end):
    out = dict(strategy=name, period=f"{start:%b %Y} - {end:%b %Y}", trades=len(t), avg_r=t["r"].mean())
    for cap in (None, CAP):
        w, _ = weekly_stats(account(t, max_leverage=cap), start, end)
        out.update({(k if cap is None else f"{k}_cap{cap}"): w[k] for k in KEYS})
    out["trades_per_week"] = len(t) / w["weeks"]
    out["r_per_week"] = t["r"].sum() / w["weeks"]
    return out


def main():
    orb, noise = load("orb_published_trades.csv"), load("noise_momentum_trades.csv")
    groups = [(f"ORB published, {m}", t, TEST_START, TEST_END) for m, t in orb.groupby("market", sort=False)]
    groups.append(("ORB published, 4 markets in one account", orb, TEST_START, TEST_END))
    for ex in ("resting", "check"):
        n = noise[noise["exits"] == ex]
        groups += [(f"Noise momentum ({ex}), {m}", t, TEST_START, TEST_END) for m, t in n.groupby("market", sort=False)]
        groups.append((f"Noise momentum ({ex}), 4 markets in one account", n, TEST_START, TEST_END))
    groups.append(("ORB + noise momentum (resting), 8 strategies in one account",
                   pd.concat([orb, noise[noise["exits"] == "resting"]], ignore_index=True), TEST_START, TEST_END))
    if os.path.exists(os.path.join(RESULTS, "orb_search_chosen_trades_year2.csv")):
        groups.append(("ORB variants chosen on year 1, 4 markets, year 2 only",
                       load("orb_search_chosen_trades_year2.csv"), SPLIT, TEST_END))
    res = pd.DataFrame([row(*g) for g in groups])
    res.to_csv(os.path.join(RESULTS, "comparison.csv"), index=False, float_format="%.4f")
    cols = ["strategy", "trades_per_week", "avg_r", "r_per_week", "avg_week_pct", f"avg_week_pct_cap{CAP}",
            f"positive_weeks_pct_cap{CAP}", f"weeks_at_4pct_pct_cap{CAP}", f"worst_week_pct_cap{CAP}",
            f"max_drawdown_pct_cap{CAP}", f"final_balance_cap{CAP}"]
    with pd.option_context("display.width", 250, "display.max_colwidth", 60):
        print(res[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
