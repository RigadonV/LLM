"""Out-of-sample test of the repo's optimised "Model 2 London" Nasdaq-100 strategy.

  python pipeline/model2_oos.py

strategy_analysis/OPTIMISED_BACKTEST.md chose its rules (London 07:00-13:00 UK, 15M trend filter,
skip spiky legs, 2 losses a day, stop under 50 points) on 2 March - 16 October 2026. October 2024 -
February 2026 was never used for any of those choices, so it is a true out-of-sample test. Same
code, same Dukascopy 1-minute Nasdaq-100 bid data, same 1.5-point cost per trade.
"""
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SA = os.path.join(os.path.dirname(os.path.dirname(HERE)), "strategy_analysis")
sys.path[:0] = [SA, os.path.join(SA, "pipeline")]
from common import build_cache, load_prices  # noqa: E402  (strategy_analysis/pipeline/common.py)
from compare_results import RISK_RULES, rules  # noqa: E402
from improve_rr import Patterns  # noqa: E402
from one_month import COST_PTS  # noqa: E402
from replicate_strategy import Market, Rules, backtest  # noqa: E402

sys.path.insert(0, HERE)
from intraday import DATA, RESULTS, account, r_stats, weekly_stats  # noqa: E402

PERIODS = {"out-of-sample Oct 2024 - Feb 2026": ("2024-10-01", "2026-02-28"),
           "in-sample Mar - Sep 2026": ("2026-03-02", "2026-09-30")}
EXITS = {"TP 2R": dict(target_r=2.0, be_at_r=None), "TP 4R, BE at 2R": dict(target_r=4.0, be_at_r=2.0)}


def main():
    build_cache(os.path.join(DATA, "raw", "USATECHIDXUSD"), "m1")  # -> strategy_analysis/data/USATECHIDXUSD_m1.csv.gz
    m1 = load_prices("m1")
    mk = Market(m1, 2)
    spike = Patterns(mk, m1).make_filter(max_leg_speed=2.5)
    base = rules(**RISK_RULES, trend_filter="15m", entry_filter=spike)
    rows, keep = [], []
    for pname, (a, b) in PERIODS.items():
        weeks_start, weeks_end = pd.Timestamp(a), pd.Timestamp(b)
        for ename, kw in EXITS.items():
            bt = backtest(mk, Rules(**{**base.__dict__, **kw}), pd.Timestamp(a), pd.Timestamp(b) + pd.Timedelta(days=1))
            r = (bt.r - COST_PTS / (bt.entry - bt.stop).abs()).values
            t = pd.DataFrame({"entry_time": bt.entry_et.dt.tz_convert("UTC"),
                              "exit_time": (bt.exit_et if "exit_et" in bt else bt.entry_et).dt.tz_convert("UTC"),
                              "r": r})
            w, _ = weekly_stats(account(t), weeks_start, weeks_end)
            rows.append(dict(period=pname, exit=ename, **r_stats(r), **{k: w[k] for k in (
                "weeks", "avg_week_pct", "compound_week_pct", "positive_weeks_pct", "worst_week_pct",
                "max_drawdown_pct", "total_return_pct")}))
            rows[-1]["r_per_week"] = r.sum() / w["weeks"]
            keep.append(t.assign(period=pname, exit=ename))
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, "model2_oos_summary.csv"), index=False, float_format="%.4f")
    pd.concat(keep).to_csv(os.path.join(RESULTS, "model2_oos_trades.csv"), index=False, float_format="%.6g")
    print(res.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
