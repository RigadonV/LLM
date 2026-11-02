"""The intraday strategies of strategy_search/ rerun through October 2026 -> results/intraday_trades.csv.gz.

  python pipeline/intraday_window.py

Same code and rules as strategy_search/pipeline/orb.py and noise_momentum.py, on the same Dukascopy 1-minute data;
only the end of the data moves from 30 Sep to 30 Oct 2026. orb_wf are the ORB variants that
strategy_search/pipeline/orb_search.py chose per market on Oct 2024 - Sep 2025, before this window starts.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                "strategy_search", "pipeline"))
import intraday  # noqa: E402
import noise_momentum  # noqa: E402
import orb  # noqa: E402
from data import RESULTS  # noqa: E402

END = pd.Timestamp("2026-10-30")
for module in (intraday, orb, noise_momentum):
    module.TEST_END = END
WF = {"USATECHIDXUSD": (15, None, "candle"), "USA500IDXUSD": (15, 10.0, "candle"),
      "USA30IDXUSD": (5, 5.0, "break"), "DEUIDXEUR": (5, None, "break")}


def main():
    parts = []
    for sym in orb.SESSIONS:
        parts.append(orb.orb_trades(sym).assign(strategy="orb"))
        parts.append(orb.orb_trades(sym, *WF[sym]).assign(strategy="orb_wf"))
        for exits in ("resting", "check"):
            parts.append(noise_momentum.noise_trades(sym, exits).assign(strategy=f"noise_{exits}"))
    t = pd.concat(parts, ignore_index=True)
    t["cls"] = "Index"
    t.to_csv(os.path.join(RESULTS, "intraday_trades.csv.gz"), index=False, float_format="%.6g")
    print(t.groupby("strategy").agg(trades=("r", "size"), avg_r=("r", "mean"), last=("day", "max")).round(3))


if __name__ == "__main__":
    main()
