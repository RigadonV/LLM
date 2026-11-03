"""Month-by-month returns of the best version found, Jan 2025 - Oct 2026, on a fresh $10,000 account at 1% risk.

  python pipeline/orb15_monthly.py [--variant "candle base | 1 + 2, no London or trend filter"]

Default (best version): the highest average R and ending balance of the versions in orb15_history.py, over
Jan 2019 - Oct 2026. Its rules:
- Nasdaq-100, with the London filter;
- the opening range at most 0.45 x the average session range of the previous 14 sessions;
- the breakout candle closing by 10:30;
- stop beyond the breakout candle, target 2R.
Its trades are read from results/orb15_history_trades.csv. Profit and loss is booked in the month a trade closes;
all trades open and close on the same day.
"""
import argparse
import os

import pandas as pd

from orb15 import RESULTS, account

VARIANT = "candle base | 1 + 2"
START, LAST = pd.Timestamp("2025-01-01", tz="UTC"), pd.Period("2026-10", "M")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=VARIANT, help="a variant name from results/orb15_history_trades.csv")
    variant = ap.parse_args().variant
    t = pd.read_csv(os.path.join(RESULTS, "orb15_history_trades.csv"))
    t = t[t["variant"] == variant].copy()
    for col in ("entry_time", "exit_time"):
        t[col] = pd.to_datetime(t[col], utc=True)
    t = t[t["entry_time"] >= START]
    curve = account(t, max_leverage=20)  # $10,000, 1% of the current balance per trade, booked at exit
    months = pd.period_range("2025-01", LAST, freq="M")
    end = curve.groupby(curve.index.to_period("M")).last().reindex(months).ffill().fillna(10_000.0)
    t["month"] = t["exit_time"].dt.tz_localize(None).dt.to_period("M")
    per = t.groupby("month").agg(trades=("r", "size"), wins=("r", lambda r: int((r > 0.05).sum())),
                                 losses=("r", lambda r: int((r < -0.05).sum())), total_r=("r", "sum"))
    out = pd.DataFrame({"start_balance": end.shift(1).fillna(10_000.0), "end_balance": end}).join(per)
    out = out.fillna({"trades": 0, "wins": 0, "losses": 0, "total_r": 0.0})
    out["breakeven"] = out["trades"] - out["wins"] - out["losses"]
    out["return_pct"] = 100 * (out["end_balance"] / out["start_balance"] - 1)
    out.index.name = "month"
    name = "orb15_best_monthly.csv" if variant == VARIANT else (
        "orb15_monthly_" + variant.split("| ")[-1].replace(" ", "_").replace(",", "").replace("+", "plus") + ".csv")
    out.to_csv(os.path.join(RESULTS, name), float_format="%.4f")
    peak, dd = 10_000.0, 0.0
    for b in curve.to_numpy():
        peak, dd = max(peak, b), max(dd, 1 - b / peak)
    y25 = out.loc[out.index.year == 2025]
    y26 = out.loc[out.index.year == 2026]
    print(out[["trades", "wins", "losses", "breakeven", "total_r", "return_pct", "end_balance"]].round(2).to_string())
    print("2025: %+.2f%% (%d trades), 2026 Jan-Oct: %+.2f%% (%d trades), max drawdown %.1f%%, positive months %d/%d, "
          "average month %+.2f%%" % (100 * (y25["end_balance"].iloc[-1] / 10_000 - 1), y25["trades"].sum(),
                                     100 * (y26["end_balance"].iloc[-1] / y25["end_balance"].iloc[-1] - 1),
                                     y26["trades"].sum(), 100 * dd, (out["return_pct"] > 0).sum(), len(out),
                                     out["return_pct"].mean()))


if __name__ == "__main__":
    main()
