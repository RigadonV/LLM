"""Step 6: charts of representative trades (entry, exit, stop, fib leg, EMAs, RSI)."""
import argparse
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

from common import ET, ROOT, ema, load_prices, resample, rsi  # noqa: E402

# reference palette (light mode)
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
UP, DOWN = "#2a78d6", "#e34948"            # diverging poles
EMA_COL = {20: "#eb6834", 50: "#1baf7a", 200: "#6250d6"}  # categorical slots 2, 3, 7
GOOD, CRITICAL = "#0ca30c", "#d03b3b"     # status: target / stop (always labelled)
LONDON_BAND = "#f0efec"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": AXIS, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
})


def candles(ax, bars, width):
    for t, r in bars.iterrows():
        col = UP if r["close"] >= r["open"] else DOWN
        x = mdates.date2num(t.tz_localize(None))
        ax.vlines(x, r["low"], r["high"], color=col, linewidth=0.8, zorder=2)
        lo, hi = sorted((r["open"], r["close"]))
        ax.add_patch(plt.Rectangle((x - width / 2, lo), width, max(hi - lo, 0.5), facecolor=col, edgecolor=col,
                                   linewidth=0.5, zorder=3))


def tag(v):
    return "None" if pd.isna(v) else v


def naive(ts):
    return pd.Timestamp(ts).tz_localize(None) if pd.Timestamp(ts).tzinfo else pd.Timestamp(ts)


def chart_trade(tr, m1, path, title_prefix=""):
    entry_t = pd.Timestamp(tr.entry_et).tz_localize(ET)
    exit_t = pd.Timestamp(tr.exit_et).tz_localize(ET)
    anchor_t = pd.Timestamp(tr.fib_anchor_time).tz_localize(ET) if pd.notna(tr.fib_anchor_time) else entry_t - pd.Timedelta(hours=3)
    start = max(anchor_t - pd.Timedelta(minutes=45), entry_t - pd.Timedelta(hours=10))
    end = exit_t + pd.Timedelta(minutes=max(60, 0.4 * tr.minutes))
    span_h = (end - start).total_seconds() / 3600
    rule, width = ("5min", 5 / 1440 * 0.7) if span_h <= 7 else ("15min", 15 / 1440 * 0.7)
    bars = resample(m1.loc[start - pd.Timedelta(minutes=15): end], rule).loc[start:end]
    m15 = resample(m1.loc[start - pd.Timedelta(days=5): end], "15min")

    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(11, 7.0), sharex=True, gridspec_kw={"height_ratios": [4, 1.1], "hspace": 0.06})
    # London kill-zone shading
    for day in pd.date_range(start.normalize(), end.normalize(), freq="D"):
        a, b = max(day + pd.Timedelta(hours=2), start), min(day + pd.Timedelta(hours=5), end)
        if a < b:
            ax.axvspan(naive(a), naive(b), color=LONDON_BAND, zorder=0, linewidth=0)
    candles(ax, bars, width)
    emas = {}
    for n, col in EMA_COL.items():
        e = ema(m15["close"], n).loc[start:end]
        emas[n] = e
        ax.plot([naive(t) for t in e.index], e.values, color=col, linewidth=1.4, zorder=4, label=f"EMA {n} (15m)")

    s = 1 if tr.direction == "long" else -1
    x0, x1 = naive(anchor_t), naive(exit_t + pd.Timedelta(minutes=20))
    if pd.notna(tr.fib_anchor_price):
        a, x = tr.fib_anchor_price, tr.fib_extreme_price
        for lvl, style in ((1.0, "-"), (0.79, "--"), (0.705, "--"), (0.5, ":"), (0.0, "-")):
            px = x - lvl * (x - a)
            emph = abs(lvl - tr.fib_level) < 1e-6
            ax.hlines(px, x0, x1, colors=INK if emph else MUTED, linestyles=style, linewidth=1.3 if emph else 0.8, zorder=5)
            ax.text(x1, px, f" {lvl:g}", va="center", ha="left", fontsize=8, color=INK if emph else INK2)
        ax.plot([naive(anchor_t), naive(pd.Timestamp(tr.fib_extreme_time).tz_localize(ET))], [a, x], color=MUTED,
                linewidth=0.8, linestyle=(0, (2, 2)), zorder=5)
        ax.scatter([naive(anchor_t)], [a], s=36, facecolor=SURFACE, edgecolor=INK, zorder=7, linewidth=1.2)
        ax.scatter([naive(pd.Timestamp(tr.fib_extreme_time).tz_localize(ET))], [x], s=36, facecolor=SURFACE, edgecolor=INK, zorder=7, linewidth=1.2)
    xe0, xe1 = naive(entry_t), naive(exit_t)
    ax.hlines(tr.stop_price_est, xe0, xe1, colors=CRITICAL, linewidth=1.6, zorder=6)
    ax.text(xe0, tr.stop_price_est, "Stop ", va="center", ha="right", fontsize=8, color=INK2)
    if tr.result != "Loss":
        ax.hlines(tr.exit_price_est, xe0, xe1, colors=GOOD, linewidth=1.6, zorder=6)
        ax.text(xe0, tr.exit_price_est, "Exit ", va="center", ha="right", fontsize=8, color=INK2)
    ax.scatter([xe0], [tr.entry_price_est], marker="^" if s == 1 else "v", s=110, color=INK, edgecolor=SURFACE,
               linewidth=1.5, zorder=8)
    ax.scatter([xe1], [tr.exit_price_est], marker="X", s=90, color=INK, edgecolor=SURFACE, linewidth=1.5, zorder=8)
    ax.annotate(f"{tr.direction.upper()} @ {tr.fib_level:g}", (xe0, tr.entry_price_est), xytext=(-8, -16 * s),
                textcoords="offset points", ha="right", fontsize=8.5, color=INK, fontweight="bold")

    r = rsi(m15["close"]).loc[start:end]
    ax2.plot([naive(t) for t in r.index], r.values, color=INK2, linewidth=1.2)
    for lvl in (30, 50, 70):
        ax2.axhline(lvl, color=AXIS if lvl != 50 else GRID, linewidth=0.8)
    ax2.axvline(xe0, color=MUTED, linewidth=0.8, linestyle=":")
    ax2.set_ylim(10, 90)
    # fit the price axis to the candles and trade levels; far-away EMAs simply clip
    lv = [bars["low"].min(), bars["high"].max(), tr.stop_price_est, tr.exit_price_est]
    if pd.notna(tr.fib_anchor_price):
        lv += [tr.fib_anchor_price, tr.fib_extreme_price]
    lo, hi = np.nanmin(lv), np.nanmax(lv)
    pad = 0.06 * (hi - lo)
    ax.set_ylim(lo - pad, hi + pad)
    ax2.set_ylabel("RSI 14 (15m)")
    ax.set_ylabel("Nasdaq-100 (Dukascopy CFD)")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    ax.set_xlim(naive(start), naive(end) + pd.Timedelta(minutes=20 if span_h <= 7 else 50))

    res = {"Win": f"Win +{tr.rr:.2f}R", "Loss": "Loss -1R",
           "BE": f"closed +{tr.rr:.2f}R (journal 'BE': peak {tr.mfe_r:.2f}R < 3R)"}[tr.result]
    fig.suptitle(f"{title_prefix}Trade #{tr.trade_id} - {tr.date} {tr.entry_et[-5:]} ET - {tr.direction} at {tr.fib_level:g} - {res}",
                 x=0.07, ha="left", fontsize=11.5, color=INK, fontweight="bold", y=0.985)
    sub = (f"Leg {tr.fib_anchor_time[-5:]} -> {tr.fib_extreme_time[-5:]} ({tr.leg_size_pts:.0f} pts), entry ratio {tr.fib_ratio_at_entry:.3f}; "
           f"stop {tr.stop_pts_est:.1f} pts ({tr.stop_leg_frac:.2f} of leg); held {tr.minutes:.0f} min. "
           f"Journal: OB {tag(tr.ob_tf)}, FVG {tag(tr.fvg_tf)}, trend aligned {tr.trend_aligned}") if pd.notna(tr.fib_anchor_price) else ""
    fig.text(0.07, 0.945, sub, ha="left", fontsize=8.5, color=INK2)
    def ema_label(n):
        e = emas[n]
        if e.max() < lo - pad:
            return f"EMA {n} (15m, below chart)"
        if e.min() > hi + pad:
            return f"EMA {n} (15m, above chart)"
        return f"EMA {n} (15m)"
    handles = [Line2D([], [], color=EMA_COL[n], linewidth=1.4, label=ema_label(n)) for n in EMA_COL]
    handles += [Line2D([], [], color=INK, linestyle="--", linewidth=1.3, label="fib level traded"),
                Line2D([], [], color=CRITICAL, linewidth=1.6, label="stop"),
                Line2D([], [], marker="^", color=INK, linestyle="", label="entry"),
                Line2D([], [], marker="X", color=INK, linestyle="", label="exit"),
                plt.Rectangle((0, 0), 1, 1, color=LONDON_BAND, label="02:00-05:00 ET")]
    if tr.result != "Loss":
        handles.insert(5, Line2D([], [], color=GOOD, linewidth=1.6, label="exit level (RR achieved)"))
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.065, 0.925), fontsize=7.5, frameon=False,
               ncol=len(handles), labelcolor=INK2, handlelength=1.6, columnspacing=1.2)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ctx", default=os.path.join(ROOT, "trade_context.csv"))
    ap.add_argument("--ids", required=True, help="comma-separated trade ids, in the form id:label")
    ap.add_argument("--outdir", default=os.path.join(ROOT, "charts"))
    args = ap.parse_args()
    ctx = pd.read_csv(args.ctx).set_index("trade_id", drop=False)
    m1 = load_prices("m1")
    os.makedirs(args.outdir, exist_ok=True)
    for item in args.ids.split(","):
        tid, label = (item.split(":", 1) + [""])[:2]
        tr = ctx.loc[int(tid)]
        fn = os.path.join(args.outdir, f"trade_{int(tid):03d}{'_' + label if label else ''}.png")
        chart_trade(tr, m1, fn, "Does not fit the rules: " if "not_fit" in label else "")
        print("wrote", fn)


if __name__ == "__main__":
    main()
