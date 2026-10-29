"""Step 3: record the market context of every trade at entry (and exit) -> trade_context.csv.

All indicator values come from the last *completed* bar before the entry minute (no look-ahead),
except fields prefixed `entrybar_`, which describe the 15M candle that contains the entry and are
only known after it closes.
"""
import argparse
import os

import numpy as np
import pandas as pd

from common import LEG_MIN_ATR, LEG_PIVOT_N, ROOT, RESULTS_DIR, add_indicators, load_h1_extended, load_journal, load_prices, resample, session_of
from structure import Structure, candle_pattern, fvgs, order_blocks, session_levels, zone_hit

TF_BAR = {"15m": pd.Timedelta(minutes=15), "30m": pd.Timedelta(minutes=30), "1h": pd.Timedelta(hours=1),
          "4h": pd.Timedelta(hours=4), "1D": pd.Timedelta(days=1)}


def last_closed(frame, t, tf):
    """Row of the last bar that closed at or before t (frames are labelled by bar start)."""
    sub = frame.loc[: t - TF_BAR[tf]]
    return sub.iloc[-1] if len(sub) else None


def trend_label(row, price_col="close"):
    if row is None or np.isnan(row["ema50_slope"]):
        return "n/a"
    above = row[price_col] > row["ema50"]
    if above and row["ema50_slope"] > 0:
        return "up"
    if not above and row["ema50_slope"] < 0:
        return "down"
    return "mixed"


def prep(frame, slope_bars=4):
    f = add_indicators(frame)
    for n in (20, 50, 200):
        f[f"ema{n}_slope"] = (f[f"ema{n}"] - f[f"ema{n}"].shift(slope_bars)) / f["atr14"]
    return f


def fib_coord(price, leg):
    """Fib coordinate of a price on a leg: 1 = anchor (swing point), 0 = extreme, <0 = extension."""
    return (leg["ext"] - price) / (leg["ext"] - leg["anchor"])


def nearest_level(price, levels, r_pts):
    best = min(((abs(price - v), k) for k, v in levels.items() if not np.isnan(v)), default=(np.nan, ""))
    return best[1], best[0] / r_pts if r_pts else np.nan


def build(journal, inf, m1, h1):
    st = Structure(m1, LEG_PIVOT_N, LEG_MIN_ATR)
    frames = {
        "15m": prep(st.m15),
        "30m": prep(resample(m1, "30min")),
        "1h": prep(h1),
        "4h": prep(resample(h1, "4h")),
        "1D": prep(resample(h1, "1D"), slope_bars=3),
    }
    m5 = resample(m1, "5min")
    inf = inf.set_index("trade_id")
    rows = []
    for tr in journal.itertuples():
        row = {k: getattr(tr, k) for k in ("trade_id", "date", "entry_et", "exit_et", "instrument", "fib_level", "result",
                                           "rr", "mae_pts", "mfe_r", "minutes", "trend_aligned", "pa_type", "fvg_tf",
                                           "ob_tf", "key_open", "news", "rating", "notes", "chart_url")}
        row["date"] = tr.date.date()
        t0 = tr.entry_et
        row["hour"] = t0.hour
        row["dow"] = t0.strftime("%a")
        row["session"] = session_of(t0)
        row["mins_after_0200"] = (t0 - t0.normalize() - pd.Timedelta(hours=2)).total_seconds() / 60
        row["news_day"] = tr.news not in (None, "None", "")
        d = inf.at[tr.trade_id, "direction"] if tr.trade_id in inf.index else None
        row["direction"] = d if isinstance(d, str) else ""
        row["direction_confidence"] = inf.at[tr.trade_id, "direction_confidence"] if tr.trade_id in inf.index else "none"
        if not isinstance(d, str) or len(m1.loc[t0 - pd.Timedelta(minutes=5): t0 + pd.Timedelta(minutes=5)]) == 0:
            rows.append(row)
            continue
        s = 1 if d == "long" else -1
        e = inf.at[tr.trade_id, "entry_price_est"]
        row["entry_price_est"] = round(e, 2)

        # ---- fib leg (most recent valid 15M swing anchor)
        recent, best = st.leg_for_entry(t0, d, e, tr.fib_level)
        if recent:
            row.update({
                "fib_anchor_time": recent["anchor_t"], "fib_anchor_price": round(recent["anchor"], 2),
                "fib_extreme_time": recent["ext_t"], "fib_extreme_price": round(recent["ext"], 2),
                "leg_size_pts": round(recent["size"], 1), "fib_ratio_at_entry": round(recent["ratio"], 3),
                "fib_match": abs(recent["ratio"] - tr.fib_level) <= 0.05,
                "leg_minutes": (recent["ext_t"] - recent["anchor_t"]).total_seconds() / 60,
                "mins_since_extreme": (t0 - recent["ext_t"]).total_seconds() / 60,
                "best_leg_ratio": round(best["ratio"], 3), "best_leg_is_recent": best is recent,
            })
            leg = recent
        else:
            leg = None

        # ---- stop / target reconstruction
        win = m1.loc[t0: tr.exit_et]
        fav = s * ((win["high"].max() if s == 1 else win["low"].min()) - e) if len(win) else np.nan
        if tr.result == "Loss":
            r_pts = tr.mae_pts
        else:
            # Win and "BE" both stood at RR x R at the logged time (see infer_direction.py)
            r_pts = fav / tr.rr if tr.rr > 0 else np.nan
        stop = e - s * r_pts
        exit_t = tr.exit_et
        if tr.result == "Loss":
            exit_px = stop
        elif tr.result == "Win":
            exit_px = e + s * tr.rr * r_pts
        else:
            # "BE": the stop was moved to entry at +2R (trader's checklist) and then hit. The logged time is
            # when the trade peaked, so the exit is the first return to the entry after it (before 12:00).
            exit_px = e
            after = m1.loc[tr.exit_et: t0.normalize() + pd.Timedelta(hours=12)]
            back = after.index[(after["low"] <= e) if s == 1 else (after["high"] >= e)]
            exit_t = back[0] if len(back) else pd.NaT
        row["exit_time_est"] = exit_t
        row.update({"stop_pts_est": round(r_pts, 2), "stop_price_est": round(stop, 2), "exit_price_est": round(exit_px, 2)})
        a15 = last_closed(frames["15m"], t0, "15m")
        row["stop_atr15"] = round(r_pts / a15["atr14"], 2)
        if leg:
            row["stop_leg_frac"] = round(r_pts / leg["size"], 3)
            row["stop_fib_coord"] = round(fib_coord(stop, leg), 3)
            row["stop_beyond_anchor_pts"] = round(s * (leg["anchor"] - stop), 1)
            row["exit_fib_coord"] = round(fib_coord(exit_px, leg), 3)

        # ---- indicators on completed bars
        for tf in ("15m", "1h", "4h", "1D"):
            b = last_closed(frames[tf], t0, tf)
            if b is None:
                continue
            for n in (20, 50, 200):
                row[f"{tf}_px_vs_ema{n}"] = round((e - b[f"ema{n}"]) / b["atr14"], 2)  # +above / -below, in ATRs
                row[f"{tf}_ema{n}_slope"] = round(b[f"ema{n}_slope"], 3)
            row[f"{tf}_trend"] = trend_label(b)
            row[f"{tf}_rsi14"] = round(b["rsi14"], 1)
            if tf in ("15m", "1h"):
                row[f"{tf}_macd_hist"] = round(b["macd_hist"], 2)
                row[f"{tf}_stoch_k"] = round(b["stoch_k"], 1)
                row[f"{tf}_stoch_d"] = round(b["stoch_d"], 1)
                row[f"{tf}_atr14"] = round(b["atr14"], 1)
                row[f"{tf}_bb_pctb"] = round(b["bb_pctb"], 2)
        for tf in ("15m", "1h", "4h", "1D"):
            if f"{tf}_trend" in row:
                row[f"{tf}_trend_with_trade"] = row[f"{tf}_trend"] == ("up" if s == 1 else "down")

        # ---- structure & key levels
        lv = session_levels(m1, frames["1D"], t0)
        row.update({k: round(v, 2) for k, v in lv.items()})
        row["vs_0000_open"] = "below" if e < lv["open_0000"] else "above"
        row["vs_1800_open"] = "below" if e < lv["open_1800"] else "above"
        # ICT premium/discount: longs below the 00:00 open, shorts above it
        row["entry_favourable_vs_0000"] = (e < lv["open_0000"]) if s == 1 else (e > lv["open_0000"])
        rng = lv["overnight_high"] - lv["overnight_low"]
        row["pos_in_overnight_range"] = round((e - lv["overnight_low"]) / rng, 2) if rng > 0 else np.nan
        row["asia_high_swept"] = lv["london_high_so_far"] > lv["asia_high"]
        row["asia_low_swept"] = lv["london_low_so_far"] < lv["asia_low"]
        if leg:
            anchor = leg["anchor"]
            row["leg_anchor_swept_asia"] = (anchor < lv["asia_low"]) if s == 1 else (anchor > lv["asia_high"])
            row["leg_anchor_swept_pd"] = (anchor < lv["pdl"]) if s == 1 else (anchor > lv["pdh"])
            # did the leg break the last opposite swing before the anchor (break of structure)?
            prior = st.piv_hi_t if s == 1 else st.piv_lo_t
            prior = prior[(prior < leg["anchor_t"]) & (prior >= leg["anchor_t"] - pd.Timedelta(hours=24))]
            if len(prior):
                lvl = st.m15.at[prior[-1], "high" if s == 1 else "low"]
                row["leg_broke_structure"] = (leg["ext"] > lvl) if s == 1 else (leg["ext"] < lvl)
            # confluence zones formed inside the leg, containing the entry price
            for tf, bars in (("15m", st.m15), ("30m", frames["30m"]), ("1h", frames["1h"])):
                z_start, z_end = leg["anchor_t"] - TF_BAR[tf], t0 - TF_BAR[tf]
                row[f"fvg_{tf}_at_entry"] = zone_hit(fvgs(bars, d, z_start, z_end), e, tol=2.0)
                row[f"ob_{tf}_at_entry"] = zone_hit(order_blocks(bars, d, z_start, z_end), e, tol=2.0)
            # target vs liquidity levels on the opposite side
            if tr.result == "Win" and r_pts > 0:
                levels = {"fib0_extreme": leg["ext"], "asia_high": lv["asia_high"], "asia_low": lv["asia_low"],
                          "london_high": lv["london_high_so_far"], "london_low": lv["london_low_so_far"],
                          "pdh": lv["pdh"], "pdl": lv["pdl"], "open_0000": lv["open_0000"], "open_1800": lv["open_1800"],
                          "fib_-0.27": leg["ext"] + 0.27 * (leg["ext"] - leg["anchor"]),
                          "fib_-0.5": leg["ext"] + 0.5 * (leg["ext"] - leg["anchor"])}
                levels = {k: v for k, v in levels.items() if not np.isnan(v) and s * (v - e) > 0}
                name, dist_r = nearest_level(exit_px, levels, r_pts)
                row["target_nearest_level"] = name
                row["target_dist_to_level_R"] = round(dist_r, 2)

        # ---- candles: last completed 15M bar, the 15M bar containing the entry, and the 5m entry bar
        b15 = st.m15.loc[: t0 - pd.Timedelta(minutes=15)]
        if len(b15) >= 2:
            row["prev15_pattern"] = candle_pattern(b15.iloc[-2], b15.iloc[-1])
        cur15_start = t0.floor("15min")
        if cur15_start in st.m15.index:
            i = st.m15.index.get_loc(cur15_start)
            cur, prev = st.m15.iloc[i], st.m15.iloc[i - 1]
            row["entrybar15_pattern"] = candle_pattern(prev, cur)
            rng15 = cur["high"] - cur["low"]
            wick = (min(cur["open"], cur["close"]) - cur["low"]) if s == 1 else (cur["high"] - max(cur["open"], cur["close"]))
            row["entrybar15_rejection_wick_frac"] = round(wick / rng15, 2) if rng15 > 0 else np.nan
            row["entrybar15_closed_in_favour"] = (cur["close"] > e) if s == 1 else (cur["close"] < e)
        cur5 = t0.floor("5min")
        if cur5 in m5.index:
            i5 = m5.index.get_loc(cur5)
            row["entrybar5_pattern"] = candle_pattern(m5.iloc[i5 - 1], m5.iloc[i5])

        # ---- exit context
        bx = last_closed(frames["15m"], (exit_t if pd.notna(exit_t) else tr.exit_et) + pd.Timedelta(minutes=15), "15m")
        if bx is not None:
            row["exit_15m_rsi14"] = round(bx["rsi14"], 1)
            row["exit_15m_px_vs_ema20"] = round((exit_px - bx["ema20"]) / bx["atr14"], 2)
            row["exit_session"] = session_of(exit_t if pd.notna(exit_t) else tr.exit_et)
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("journal")
    ap.add_argument("--out", default=os.path.join(ROOT, "trade_context.csv"))
    args = ap.parse_args()
    journal = load_journal(args.journal)
    inf = pd.read_csv(os.path.join(RESULTS_DIR, "direction_inference.csv"))
    m1 = load_prices("m1")
    h1 = load_h1_extended(m1)
    ctx = build(journal, inf, m1, h1)
    for c in ("entry_et", "exit_et", "exit_time_est", "fib_anchor_time", "fib_extreme_time"):
        if c in ctx:
            ctx[c] = pd.to_datetime(ctx[c]).dt.strftime("%Y-%m-%d %H:%M")
    ctx.to_csv(args.out, index=False)
    print(f"wrote {args.out}: {ctx.shape[0]} trades x {ctx.shape[1]} columns")


if __name__ == "__main__":
    main()
