"""Step 4: find the conditions that are consistently present at entries, compare longs/shorts and
winners/losers, work out the exit logic and rank candidate rules by how many trades they explain."""
import argparse
import os

import numpy as np
import pandas as pd

from common import ROOT, RESULTS_DIR


def pct(x):
    return f"{100 * x:.0f}%" if pd.notna(x) else "n/a"


def bool_table(ctx, features):
    """Share of trades where each condition holds: all / longs / shorts / winners(Win+BE) / losers."""
    rows = []
    for name, f in features.items():
        v = pd.Series(f(ctx), index=ctx.index).astype(object)
        ok = v.notna()
        v = v.where(ok, np.nan)
        rows.append({
            "condition": name,
            "n": int(ok.sum()),
            "all": v[ok].mean(),
            "longs": v[ok & (ctx.direction == "long")].mean(),
            "shorts": v[ok & (ctx.direction == "short")].mean(),
            "non-losers": v[ok & (ctx.result != "Loss")].mean(),
            "losers": v[ok & (ctx.result == "Loss")].mean(),
            "loss rate if true": (ctx.result[ok & (v == True)] == "Loss").mean(),
            "loss rate if false": (ctx.result[ok & (v == False)] == "Loss").mean(),
        })
    t = pd.DataFrame(rows).sort_values("all", ascending=False)
    return t


def logged(series):
    """Journal confluence columns use the text 'None' for absent, which pandas reads as NaN."""
    return series.notna() & (series.astype(str) != "None")


def as_bool(series):
    return series.map(lambda x: np.nan if pd.isna(x) else bool(x) if not isinstance(x, str) else x == "True")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", default=os.path.join(ROOT, "trade_context.csv"))
    args = ap.parse_args()
    ctx = pd.read_csv(args.ctx)
    out = []

    def p(s=""):
        out.append(str(s))
        print(s)

    all_n = len(ctx)
    ctx = ctx[ctx.direction.isin(["long", "short"])].copy()
    s = np.where(ctx.direction == "long", 1, -1)
    p(f"Trades with inferred direction: {len(ctx)} of {all_n}")
    p(ctx.groupby("direction").agg(n=("trade_id", "size"), loss_rate=("result", lambda r: (r == "Loss").mean()),
                                   avg_rr=("rr", "mean"), fib_0705=("fib_level", lambda f: (f == 0.705).mean())).round(3).to_string())
    p()

    entry_t = pd.to_datetime(ctx.entry_et)
    hhmm = entry_t.dt.hour + entry_t.dt.minute / 60
    sign = pd.Series(s, index=ctx.index)
    feats = {
        "entry 02:00-09:30 ET": lambda c: (hhmm >= 2) & (hhmm < 9.5),
        "entry at logged fib of most recent unbroken 15M swing leg (+/-0.05)": lambda c: as_bool(c.fib_match),
        "leg broke prior 15M swing (BOS) before retrace": lambda c: as_bool(c.leg_broke_structure),
        "leg anchor swept Asian high/low": lambda c: as_bool(c.leg_anchor_swept_asia),
        "leg anchor swept previous-day high/low": lambda c: as_bool(c.leg_anchor_swept_pd),
        "entry on premium/discount side of 00:00 open": lambda c: as_bool(c.entry_favourable_vs_0000),
        "entry on premium/discount side of 18:00 open": lambda c: (c.vs_1800_open == np.where(c.direction == "long", "below", "above")).where(c.vs_1800_open.notna()),
        "15m trend with trade (close vs EMA50 + slope)": lambda c: as_bool(c["15m_trend_with_trade"]),
        "1h trend with trade": lambda c: as_bool(c["1h_trend_with_trade"]),
        "4h trend with trade": lambda c: as_bool(c["4h_trend_with_trade"]),
        "daily trend with trade": lambda c: as_bool(c["1D_trend_with_trade"]),
        "entry on trade side of 15m EMA200": lambda c: (sign * c["15m_px_vs_ema200"] > 0).where(c["15m_px_vs_ema200"].notna()),
        "entry on trade side of 1h EMA50": lambda c: (sign * c["1h_px_vs_ema50"] > 0).where(c["1h_px_vs_ema50"].notna()),
        "entry on trade side of 1h EMA200": lambda c: (sign * c["1h_px_vs_ema200"] > 0).where(c["1h_px_vs_ema200"].notna()),
        "15m EMA50 sloping with trade": lambda c: (sign * c["15m_ema50_slope"] > 0).where(c["15m_ema50_slope"].notna()),
        "1h EMA50 sloping with trade": lambda c: (sign * c["1h_ema50_slope"] > 0).where(c["1h_ema50_slope"].notna()),
        "15m RSI on pullback side of 50 (long<50 / short>50)": lambda c: (sign * (50 - c["15m_rsi14"]) > 0).where(c["15m_rsi14"].notna()),
        "15m stoch in pullback extreme (long<30 / short>70)": lambda c: pd.Series(np.where(c.direction == "long", c["15m_stoch_k"] < 30, c["15m_stoch_k"] > 70), index=c.index).where(c["15m_stoch_k"].notna()),
        "15m MACD hist against trade (pullback)": lambda c: (sign * c["15m_macd_hist"] < 0).where(c["15m_macd_hist"].notna()),
        "15m BB %b on pullback side (long<0.5 / short>0.5)": lambda c: (sign * (0.5 - c["15m_bb_pctb"]) > 0).where(c["15m_bb_pctb"].notna()),
        "15m FVG (in trade direction) at entry price": lambda c: as_bool(c.fvg_15m_at_entry),
        "30m FVG at entry price": lambda c: as_bool(c.fvg_30m_at_entry),
        "1h FVG at entry price": lambda c: as_bool(c.fvg_1h_at_entry),
        "15m order block at entry price": lambda c: as_bool(c.ob_15m_at_entry),
        "30m order block at entry price": lambda c: as_bool(c.ob_30m_at_entry),
        "1h order block at entry price": lambda c: as_bool(c.ob_1h_at_entry),
        "any FVG or OB (15m/30m/1h) at entry": lambda c: (as_bool(c.fvg_15m_at_entry) | as_bool(c.fvg_30m_at_entry) | as_bool(c.fvg_1h_at_entry)
                                                         | as_bool(c.ob_15m_at_entry) | as_bool(c.ob_30m_at_entry) | as_bool(c.ob_1h_at_entry)),
        "entry 15m candle closes back in trade direction": lambda c: as_bool(c.entrybar15_closed_in_favour),
        "entry 15m candle has rejection wick >= 30% of range": lambda c: (c.entrybar15_rejection_wick_frac >= 0.3).where(c.entrybar15_rejection_wick_frac.notna()),
        "journal: aligned with trend = Y": lambda c: c.trend_aligned == "Y",
        "journal: OB confluence logged": lambda c: logged(c.ob_tf),
        "journal: FVG confluence logged": lambda c: logged(c.fvg_tf),
        "journal: key open confluence logged": lambda c: logged(c.key_open),
        "journal: OB or FVG confluence logged": lambda c: logged(c.ob_tf) | logged(c.fvg_tf),
    }
    tab = bool_table(ctx, feats)
    p("== Condition prevalence (share of trades where it holds) ==")
    show = tab.copy()
    for col in ("all", "longs", "shorts", "non-losers", "losers", "loss rate if true", "loss rate if false"):
        show[col] = show[col].map(pct)
    p(show.to_string(index=False))
    tab.to_csv(os.path.join(RESULTS_DIR, "condition_prevalence.csv"), index=False)
    p()

    p("== Fib leg geometry ==")
    m = ctx[as_bool(ctx.fib_match) == True]
    p(m[["leg_size_pts", "leg_minutes", "mins_since_extreme", "fib_ratio_at_entry"]].describe().round(2).to_string())
    p("leg size in 15m ATRs: " + (m.leg_size_pts / m["15m_atr14"]).describe().round(2).to_string().replace("\n", " | "))
    p()

    p("== Stop placement ==")
    ok = ctx.stop_pts_est.notna() & np.isfinite(ctx.stop_pts_est)
    for res in ("Loss", "Win", "BE"):
        sub = ctx[ok & (ctx.result == res)]
        p(f"{res:5s} n={len(sub):3d}  stop pts median {sub.stop_pts_est.median():.1f}  "
          f"stop/leg {sub.stop_leg_frac.median():.3f} (IQR {sub.stop_leg_frac.quantile(.25):.3f}-{sub.stop_leg_frac.quantile(.75):.3f})  "
          f"stop/ATR15 {sub.stop_atr15.median():.2f} (IQR {sub.stop_atr15.quantile(.25):.2f}-{sub.stop_atr15.quantile(.75):.2f})  "
          f"stop fib coord {sub.stop_fib_coord.median():.3f}")
    for f in (0.705, 0.79):
        sub = ctx[ok & (ctx.fib_level == f) & as_bool(ctx.fib_match).fillna(False)]
        p(f"fib {f}: stop fib coord median {sub.stop_fib_coord.median():.3f} (IQR {sub.stop_fib_coord.quantile(.25):.3f}-{sub.stop_fib_coord.quantile(.75):.3f}), "
          f"stop/leg {sub.stop_leg_frac.median():.3f}, stop beyond anchor pts {sub.stop_beyond_anchor_pts.median():.1f}")
    cv = lambda x: x.std() / x.mean()
    sub = ctx[ok & as_bool(ctx.fib_match).fillna(False)]
    p(f"Coefficient of variation (lower = more rule-like): stop pts {cv(sub.stop_pts_est):.2f}, stop/leg {cv(sub.stop_leg_frac):.2f}, stop/ATR15 {cv(sub.stop_atr15):.2f}")
    p()

    p("== Exit logic ==")
    j = ctx
    p("RR achieved (wins): " + j[j.result == "Win"].rr.describe().round(2).to_string().replace("\n", " | "))
    p("MFE of BE trades: " + j[j.result == "BE"].mfe_r.describe().round(2).to_string().replace("\n", " | "))
    p("MFE of losing trades: " + j[j.result == "Loss"].mfe_r.describe().round(2).to_string().replace("\n", " | "))
    w = j[(j.result == "Win") & j.exit_fib_coord.notna()]
    p("Win exit fib coordinate (0 = leg extreme, <0 extension): " + w.exit_fib_coord.describe().round(2).to_string().replace("\n", " | "))
    p("Nearest liquidity level to the winning exit:")
    p(w.target_nearest_level.value_counts().to_string())
    p("distance of exit to that level (R): " + w.target_dist_to_level_R.describe().round(2).to_string().replace("\n", " | "))
    p("Holding minutes by result: " + j.groupby("result").minutes.median().to_string().replace("\n", " | "))
    p()

    p("== Time ==")
    p("entries by hour: " + entry_t.dt.hour.value_counts().sort_index().to_string().replace("\n", " | "))
    p("loss rate by hour: " + ctx.assign(h=entry_t.dt.hour).groupby("h").result.apply(lambda r: round((r == "Loss").mean(), 2)).to_string().replace("\n", " | "))
    p("loss rate by weekday: " + ctx.groupby("dow").result.apply(lambda r: round((r == "Loss").mean(), 2)).to_string().replace("\n", " | "))
    p("loss rate news day vs not: " + ctx.groupby("news_day").result.apply(lambda r: round((r == "Loss").mean(), 2)).to_string().replace("\n", " | "))
    p()

    p("== Winners vs losers: numeric medians ==")
    num = ["fib_ratio_at_entry", "leg_size_pts", "leg_minutes", "mins_since_extreme", "stop_pts_est", "stop_atr15",
           "15m_rsi14", "15m_stoch_k", "15m_bb_pctb", "1h_rsi14", "15m_atr14", "pos_in_overnight_range", "rating"]
    g = ctx.assign(outcome=np.where(ctx.result == "Loss", "loss", "non-loss"))
    for c in ("15m_rsi14", "15m_stoch_k", "15m_bb_pctb", "pos_in_overnight_range"):
        g[c + "_dirnorm"] = np.where(g.direction == "long", g[c], (100 if "rsi" in c or "stoch" in c else 1) - g[c])
    num += [c + "_dirnorm" for c in ("15m_rsi14", "15m_stoch_k", "15m_bb_pctb", "pos_in_overnight_range")]
    p(g.groupby("outcome")[num].median().T.round(2).to_string())
    p()

    p("== Candle patterns ==")
    p("entry 15m bar: " + ctx.entrybar15_pattern.value_counts().to_string().replace("\n", " | "))
    p("prev 15m bar: " + ctx.prev15_pattern.value_counts().to_string().replace("\n", " | "))

    with open(os.path.join(RESULTS_DIR, "patterns_report.txt"), "w") as fh:
        fh.write("\n".join(out))


if __name__ == "__main__":
    main()
