"""Chart patterns at the moment of entry, and which of them separate good trades from bad ones.

Every backtest trade (London 07:00-13:00 UK, the trader's risk rules; with and without the 15M trend
filter) is described by what the chart showed when the order filled, using only candles that had
closed by then:

  the impulse leg   size, speed, biggest candle (displacement), FVGs left behind, break of
                    structure, whether its swing point swept the prior lows/highs (liquidity grab),
                    whether its extreme was a new session high/low
  the pullback      how long and how fast it was, its biggest counter-candle, counter-direction FVGs,
                    how "clean" (body-heavy) or "choppy" (wick-heavy) its candles were
  the context       hour, volatility regime, how much of the day's usual range is already used,
                    1H trend, OB/FVG at the level, premium/discount vs the 00:00 open, stop size,
                    trade number of the day

Patterns are found on Mar-Aug and checked on Sep-Oct, which was not used to find them.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import RESULTS_DIR, load_prices, resample  # noqa: E402
from compare_results import PERIOD, RISK_RULES, rules  # noqa: E402
from one_month import COST_PTS  # noqa: E402
from replicate_strategy import Market, backtest  # noqa: E402

ET = "America/New_York"
SPLIT = pd.Timestamp("2026-09-01", tz=ET)


def leg_of(mk, tr, i):
    d = tr.direction
    lg = mk.leg(i, d, 30 * 60)
    if lg is None:
        return None
    k, a, ext, j_ext = lg
    if abs(a - tr.leg_anchor) > 0.01:  # the leg the trade was taken on
        return None
    return k, a, ext, j_ext


def describe(mk, m5, daily, bt):
    rows = []
    adr = (daily["high"] - daily["low"]).rolling(10).mean().shift(1)
    for tr in bt.itertuples():
        i = mk.t.searchsorted(tr.entry_et)
        lg = leg_of(mk, tr, i)
        if lg is None:
            continue
        k, a, ext, j_ext = lg
        d, s = tr.direction, (1 if tr.direction == "long" else -1)
        s0 = mk.piv[d]["start"][k]
        atr = mk.atr15[i]
        t0, ta, te = mk.t[i], mk.t[s0], mk.t[j_ext]
        stop_pts = abs(tr.entry - tr.stop)
        leg_min = max((te - ta).total_seconds() / 60, 1)
        pb_min = max((t0 - te).total_seconds() / 60, 1)

        legbars = mk.m15.loc[ta: te.floor("15min")]
        displacement = (s * (legbars["close"] - legbars["open"])).max() / atr
        f = mk.fvg[d]
        leg_fvgs = int(((f[:, 0] >= s0) & (f[:, 0] <= j_ext + 15)).sum()) if len(f) else 0
        prior = slice(max(s0 - 360, 0), s0)  # 6 hours before the swing point
        sweep = (a < mk.l[prior].min()) if s == 1 else (a > mk.h[prior].max())
        sess = mk.t.searchsorted((t0 + pd.Timedelta(hours=6)).normalize() - pd.Timedelta(hours=6))
        new_extreme = (ext >= mk.h[sess:i].max()) if s == 1 else (ext <= mk.l[sess:i].min())

        pb5 = m5.loc[te.floor("5min"): t0 - pd.Timedelta(minutes=5)]  # 5m candles of the pullback, closed
        if len(pb5):
            counter = -s * (pb5["close"] - pb5["open"])
            counter_body = counter.max() / atr
            rng = (pb5["high"] - pb5["low"]).sum()
            body_ratio = (pb5["close"] - pb5["open"]).abs().sum() / rng if rng > 0 else np.nan
            hi, lo = pb5["high"].values, pb5["low"].values
            counter_fvgs = int(sum((lo[j] > hi[j - 2]) if s == -1 else (hi[j] < lo[j - 2]) for j in range(2, len(pb5))))
        else:
            counter_body, body_ratio, counter_fvgs = 0.0, np.nan, 0
        pb_depth = s * (ext - tr.entry) / atr

        day_lo, day_hi = mk.l[sess:i].min(), mk.h[sess:i].max()
        adr_now = adr.asof(t0)
        open00 = mk.o[mk.t.searchsorted(t0.normalize())]
        uk = t0.tz_convert("Europe/London")
        r_net = tr.r - COST_PTS / stop_pts
        rows.append({
            "entry_et": tr.entry_et, "direction": d, "fib_level": tr.fib_level, "outcome": tr.outcome, "r": tr.r,
            "r_net": r_net, "holdout": tr.entry_et >= SPLIT,
            # impulse leg
            "leg_atr": tr.leg_size / atr, "leg_minutes": leg_min, "leg_speed_atr_per_h": (tr.leg_size / atr) / (leg_min / 60),
            "displacement_atr": displacement, "leg_fvgs_15m": leg_fvgs, "leg_broke_structure": mk.broke_structure(d, k, ext),
            "swing_swept_6h_liquidity": bool(sweep), "extreme_is_session_extreme": bool(new_extreme),
            # pullback
            "pullback_minutes": pb_min, "pullback_vs_leg_time": pb_min / leg_min,
            "pullback_speed_atr_per_h": pb_depth / (pb_min / 60), "pullback_biggest_counter_candle_atr": counter_body,
            "pullback_counter_fvgs_5m": counter_fvgs, "pullback_body_ratio": body_ratio,
            # context
            "hour_uk": uk.hour, "atr15": atr, "atr_vs_5day": atr / np.nanmedian(mk.atr15[max(i - 5 * 1380, 0): i]),
            "day_range_used": (day_hi - day_lo) / adr_now if adr_now else np.nan,
            "trend_1h_with_trade": mk.trend["1h"][i] == s, "ob_fvg_at_level": mk.zone_covers(d, s0, i, tr.entry),
            "discount_vs_0000_open": (tr.entry < open00) if s == 1 else (tr.entry > open00),
            "stop_pts": stop_pts, "nth_trade_today": tr.nth_today,
        })
    return pd.DataFrame(rows)


def bucket_table(df, name):
    """Net R per trade by feature bucket: terciles (cut on Mar-Aug) for numbers, True/False for flags."""
    disc, hold = df[~df.holdout], df[df.holdout]
    out = []
    skip = {"entry_et", "direction", "outcome", "r", "r_net", "holdout"}
    for col in [c for c in df.columns if c not in skip]:
        x = df[col]
        if x.dtype == bool or x.nunique() <= 3:
            buckets = {str(v): x == v for v in sorted(x.dropna().unique())}
        else:
            q1, q2 = disc[col].quantile([1 / 3, 2 / 3])
            buckets = {f"low (<{q1:.2f})": x < q1, "mid": (x >= q1) & (x < q2), f"high (>={q2:.2f})": x >= q2}
        for label, mask in buckets.items():
            dm, hm = mask[~df.holdout], mask[df.holdout]
            out.append({"set": name, "feature": col, "bucket": label,
                        "n_mar_aug": int(dm.sum()), "R_mar_aug": round(disc.r_net[dm].mean(), 3) if dm.sum() else np.nan,
                        "n_sep_oct": int(hm.sum()), "R_sep_oct": round(hold.r_net[hm].mean(), 3) if hm.sum() else np.nan,
                        "win_rate_all": round((df.outcome[mask] == "Win").mean(), 3) if mask.sum() else np.nan})
    return pd.DataFrame(out)


def main():
    m1 = load_prices("m1")
    mk = Market(m1, 2)
    m5 = resample(m1, "5min")
    daily = resample(m1, "1D")
    tables, feats = [], {}
    for name, r in (("risk rules, no trend filter", rules(**RISK_RULES)),
                    ("best config (with 15M trend)", rules(**RISK_RULES, trend_filter="15m"))):
        bt = backtest(mk, r, *PERIOD)
        f = describe(mk, m5, daily, bt)
        feats[name] = f
        print(f"{name}: {len(bt)} trades, {len(f)} described, net R/trade {f.r_net.mean():+.3f} "
              f"(Mar-Aug {f[~f.holdout].r_net.mean():+.3f}, Sep-Oct {f[f.holdout].r_net.mean():+.3f})")
        tables.append(bucket_table(f, name))
    res = pd.concat(tables)
    res.to_csv(os.path.join(RESULTS_DIR, "pattern_buckets.csv"), index=False)
    feats["risk rules, no trend filter"].to_csv(os.path.join(RESULTS_DIR, "trade_features.csv"), index=False)
    pd.set_option("display.width", 220)
    pd.set_option("display.max_rows", 400)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
