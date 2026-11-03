"""Exploratory: which conditions known at entry went with better ORB + London-filter trades on the Nasdaq-100.

  python pipeline/orb15_explore.py

Not a test. It splits the trades orb15_manage.py already ran (fixed stop, 2R target, London filter, both stops,
both years) by conditions known when the trade is entered, to choose which ideas deserve a proper test. Each
condition is split at its median over both years, so both years use the same threshold. A condition is only a
lead if it points the same way in both years.
"""
import os

import numpy as np
import pandas as pd

import orb15
from orb15 import RESULTS, TZ, load_m1

PLAN = "fixed stop, target 2R, London filter"
FILES = {"Nov 2024 - Oct 2025": "orb15_management_trades_prior.csv", "Nov 2025 - Oct 2026": "orb15_management_trades.csv"}


def sessions(m):
    s = m[(m.index.time >= pd.Timestamp("09:30").time()) & (m.index.time < pd.Timestamp("16:00").time())]
    d = s.groupby(s.index.date).agg(open=("open", "first"), high=("high", "max"), low=("low", "min"),
                                    close=("close", "last"))
    d["range"] = d["high"] - d["low"]
    d["atr14"] = d["range"].rolling(14).mean().shift(1)  # average session range of the 14 sessions before
    d["prev_close"] = d["close"].shift(1)
    prev = d["range"].shift(1)
    d["nr7"] = prev == prev.rolling(7).min()  # yesterday's range was the narrowest of the last 7 (Crabel)
    return d


def main():
    m = load_m1("USATECHIDXUSD")
    m = m[m.index >= pd.Timestamp("2024-09-01", tz="UTC")].tz_convert(TZ)
    days = sessions(m)
    at3 = m["open"][(m.index.hour == 3) & (m.index.minute == 0)]
    at3.index = at3.index.date
    b = orb15.candles(m, "09:30")
    t = pd.concat([pd.read_csv(os.path.join(RESULTS, f)).assign(year=y) for y, f in FILES.items()], ignore_index=True)
    t = t[(t["market"] == "Nasdaq-100") & (t["plan"] == PLAN)].copy()
    t["day"] = pd.to_datetime(t["day"]).dt.date
    bc = pd.to_datetime(t["breakout_candle"], utc=True).dt.tz_convert(TZ)
    atr = t["day"].map(days["atr14"])
    candle = b.reindex(bc.to_numpy())
    feats = {
        "opening range width / ATR": (t["range_high"] - t["range_low"]) / atr,
        "London move size / ATR": (t["day"].map(days["open"]) - t["day"].map(at3)).abs() / atr,
        "overnight gap / ATR": (t["day"].map(days["open"]) - t["day"].map(days["prev_close"])).abs() / atr,
        "breakout candle body / range width": (candle["close"].to_numpy() - candle["open"].to_numpy()).__abs__()
                                             / (t["range_high"] - t["range_low"]).to_numpy(),
        "entry distance beyond 50 EMA / ATR": t["dir"] * (candle["close"].to_numpy() - candle["ema50"].to_numpy()) / atr,
        "minutes after the open": (bc - bc.dt.normalize() - pd.Timedelta(hours=9, minutes=30)).dt.total_seconds() / 60,
    }
    feats = {f: pd.Series(np.asarray(s, dtype=float), index=t.index) for f, s in feats.items()}
    t["win"], t["nr7"] = t["r"] > 0.05, t["day"].map(days["nr7"]).astype(bool)
    rows = []
    for stop, g in t.groupby("stop_rule"):
        splits = {f: (s.loc[g.index] <= s.median()).to_numpy() for f, s in feats.items()}
        splits["yesterday was an NR7 day"] = g["nr7"].to_numpy()  # the "low" side here means NR7 yes
        for f, low in splits.items():
            low = np.asarray(low, dtype=bool)
            out = dict(stop_rule=stop, condition=f)
            for y in FILES:
                yy = (g["year"] == y).to_numpy()
                for side, mask in (("low", low & yy), ("high", ~low & yy)):
                    x = g[mask]
                    out[f"{y[-4:]} {side}: n"] = len(x)
                    out[f"{y[-4:]} {side}: win%"] = 100 * x["win"].mean()
                    out[f"{y[-4:]} {side}: avgR"] = x["r"].mean()
            d1 = out["2025 low: avgR"] - out["2025 high: avgR"]
            d2 = out["2026 low: avgR"] - out["2026 high: avgR"]
            out["same way both years"] = bool(np.sign(d1) == np.sign(d2))
            rows.append(out)
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, "orb15_explore.csv"), index=False, float_format="%.4f")
    medians = {f: round(float(s.median()), 3) for f, s in feats.items()}
    print("pooled medians (the split points):", medians)
    with pd.option_context("display.width", 300, "display.max_columns", 40, "display.max_colwidth", 38):
        print(res.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
