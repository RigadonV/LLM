"""Walk-forward search over opening-range-breakout variants.

  python pipeline/orb_search.py

For every market, every combination of opening-range length (5/15/30 min), target (2/3/5/10R or
hold to the close) and entry (first-candle direction as published, or a break of the range) is
run over the whole window. The variant with the best average R in year 1 (Oct 2024 - Sep 2025,
at least 100 trades) is chosen per market; year 2 (Oct 2025 - Sep 2026) was not used for the
choice and shows how the choice holds up. The chosen variants then trade together in one $10k
account at 1% risk per trade, and its year-2 weeks are reported.
"""
import itertools
import os

import numpy as np
import pandas as pd

from intraday import LABEL, RESULTS, SPLIT, TEST_END, account, weekly_stats
from orb import SESSIONS, orb_trades

GRID = list(itertools.product([5, 15, 30], [2.0, 3.0, 5.0, 10.0, None], ["candle", "break"]))


def main():
    rows, chosen = [], []
    for sym in SESSIONS:
        best, best_t = None, None
        for or_min, target_r, entry in GRID:
            t = orb_trades(sym, or_min, target_r, entry)
            if t.empty:
                continue
            y1 = t[pd.to_datetime(t["day"]) < SPLIT]
            y2 = t[pd.to_datetime(t["day"]) >= SPLIT]
            row = dict(market=LABEL[sym], or_min=or_min, target=("close" if target_r is None else f"{target_r:g}R"),
                       entry=entry, y1_trades=len(y1), y1_avg_r=y1["r"].mean(), y1_r_per_week=y1["r"].sum() / 52.1,
                       y2_trades=len(y2), y2_avg_r=y2["r"].mean(), y2_r_per_week=y2["r"].sum() / 52.1)
            rows.append(row)
            if len(y1) >= 100 and (best is None or row["y1_avg_r"] > best["y1_avg_r"]):
                best, best_t = row, t
        best["chosen"] = True
        chosen.append(best_t[pd.to_datetime(best_t["day"]) >= SPLIT])
        print(f"{LABEL[sym]:11s} chosen on year 1: OR {best['or_min']}m, target {best['target']}, {best['entry']}: "
              f"year 1 {best['y1_avg_r']:+.3f}R ({best['y1_r_per_week']:+.2f}R/week) -> "
              f"year 2 {best['y2_avg_r']:+.3f}R ({best['y2_r_per_week']:+.2f}R/week)", flush=True)
    grid = pd.DataFrame(rows)
    grid["chosen"] = grid.get("chosen", False)
    grid.to_csv(os.path.join(RESULTS, "orb_search_grid.csv"), index=False, float_format="%.4f")
    port = pd.concat(chosen, ignore_index=True)
    w, wk = weekly_stats(account(port), SPLIT, TEST_END)
    print("\nAll variants, year 2 average R: median %+.3f, best %+.3f, share positive %.0f%%" % (
        grid["y2_avg_r"].median(), grid["y2_avg_r"].max(), 100 * (grid["y2_avg_r"] > 0).mean()))
    print("Chosen variants together, year 2 only ($10k, 1%% risk/trade): trades %d, avg week %+.2f%%, compound week "
          "%+.2f%%, positive weeks %.0f%%, weeks >= 4%% %.0f%%, worst week %+.1f%%, max DD %.1f%%, $10k -> $%.0f" % (
              len(port), w["avg_week_pct"], w["compound_week_pct"], w["positive_weeks_pct"], w["weeks_at_4pct_pct"],
              w["worst_week_pct"], w["max_drawdown_pct"], w["final_balance"]))
    pd.DataFrame([dict(scope="chosen ORB variants, year 2", trades=len(port), **w)]).to_csv(
        os.path.join(RESULTS, "orb_search_portfolio_year2.csv"), index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
