"""Step 4: charts for BACKTEST.md, each in a light and a dark version.

  python pipeline/charts.py

charts/avg_r_by_variant[-dark].png   average R per trade with 95% bootstrap interval, every variant
charts/equity[-dark].png             account growth at 1% risk per trade: hybrid vs its parts
charts/example_win[-dark].png        a hybrid winner and a loser, bar by bar, with level, entry, stop, target
charts/example_loss[-dark].png
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from common import CHARTS_DIR, RESULTS_DIR, load_daily  # noqa: E402
from strategy import PIVOT_N, LOOKBACK, VARIANTS, ZONE_ATR  # noqa: E402

THEMES = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9",
                  axis="#c3c2b7", series=["#2a78d6", "#eb6834", "#1baf7a", "#eda100"], up="#a9a8a2", down="#52514e"),
    "dark": dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a",
                 axis="#383835", series=["#3987e5", "#d95926", "#199e70", "#c98500"], up="#c3c2b7", down="#6e6d68"),
}


def style(ax, th, ygrid=True, xgrid=False):
    ax.set_facecolor(th["surface"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(th["axis"])
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=th["muted"], labelsize=9, length=0)
    ax.grid(False)
    if ygrid:
        ax.yaxis.grid(True, color=th["grid"], linewidth=0.8, linestyle="-")
    if xgrid:
        ax.xaxis.grid(True, color=th["grid"], linewidth=0.8, linestyle="-")
    ax.set_axisbelow(True)


def titles(fig, th, title, subtitle):
    fig.text(0.012, 0.975, title, ha="left", va="top", fontsize=12.5, fontweight="bold", color=th["ink"])
    fig.text(0.012, 0.925, subtitle, ha="left", va="top", fontsize=9.5, color=th["ink2"])


def save(fig, name, mode):
    path = os.path.join(CHARTS_DIR, f"{name}{'' if mode == 'light' else '-dark'}.png")
    fig.savefig(path, dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def avg_r_chart(summ, mode):
    th = THEMES[mode]
    s = summ.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=th["surface"])
    fig.subplots_adjust(left=0.31, right=0.97, top=0.83, bottom=0.12)
    style(ax, th, ygrid=False, xgrid=True)
    ax.axvline(0, color=th["axis"], linewidth=1.2, zorder=1)
    for i, r in s.iterrows():
        hyb = r["variant"] == "V4"
        col = th["series"][0] if hyb else th["muted"]
        ax.plot([r["ci_lo"], r["ci_hi"]], [i, i], color=col, linewidth=2, solid_capstyle="round", zorder=2)
        ax.scatter([r["avg_r"]], [i], s=60, color=col, edgecolor=th["surface"], linewidth=2, zorder=3)
        if hyb:
            ax.annotate(f"{r['avg_r']:+.2f}R".replace("-", "\u2212"), (r["avg_r"], i), xytext=(0, 10),
                        textcoords="offset points", ha="center", va="bottom", fontsize=9, color=th["ink"],
                        fontweight="bold")
    ax.set_yticks(range(len(s)))
    ax.set_yticklabels([f"{r['variant']}  {r['name']}  ({r['trades']:.0f})" for _, r in s.iterrows()],
                       color=th["ink2"], fontsize=9)
    ax.set_xlabel("Average R per trade, after spread and commission", color=th["muted"], fontsize=9)
    titles(fig, th, "Average result per trade, by variant",
           "Dot: average R; line: 95% interval (bootstrap by month of entry); (trades). After spread and commission.")
    return save(fig, "avg_r_by_variant", mode)


def equity_chart(eq, mode):
    th = THEMES[mode]
    show = [("V4", "Hybrid"), ("V3", "PA only"), ("V2", "S/R + trend"), ("V1", "S/R only")]
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=th["surface"])
    fig.subplots_adjust(left=0.08, right=0.8, top=0.78, bottom=0.1)
    style(ax, th)
    ends = []
    for k, (vk, name) in enumerate(show):
        s = eq[vk]
        ax.plot(s.index, 100 * (s - 1), color=th["series"][k], linewidth=1.8, solid_capstyle="round",
                solid_joinstyle="round", label=f"{vk} {name}", zorder=3 if vk == "V4" else 2)
        ends.append((100 * (s.iloc[-1] - 1), f"{vk} {name}  {100 * (s.iloc[-1] - 1):+.0f}%", s.index[-1]))
    ax.axhline(0, color=th["axis"], linewidth=1.2, zorder=1)
    # end labels: keep them at least 6% of the axis height apart, with a leader line when moved
    lo, hi = ax.get_ylim()
    gap = 0.06 * (hi - lo)
    ends.sort()
    placed = []
    for y, _, _ in ends:
        placed.append(max(y, placed[-1] + gap) if placed else y)
    for (y, text, x), yl in zip(ends, placed):
        ax.annotate(text, (x, y), xytext=(14, 0), textcoords="offset points", va="center", fontsize=8.5,
                    color=th["ink2"], annotation_clip=False)
        if abs(yl - y) > 1e-9:
            ax.texts[-1].remove()
            ax.annotate(text, (x, y), xytext=(x + 0.05 * (eq.index[-1] - eq.index[0]), yl), textcoords="data", va="center",
                        fontsize=8.5, color=th["ink2"], annotation_clip=False,
                        arrowprops=dict(arrowstyle="-", color=th["muted"], linewidth=0.7, shrinkA=0, shrinkB=2))
    ax.set_ylabel("Account return (%)", color=th["muted"], fontsize=9)
    leg = ax.legend(loc="lower left", frameon=False, fontsize=8.5, ncol=4, bbox_to_anchor=(0, 1.0),
                    handlelength=1.6, borderaxespad=0.2)
    for txt in leg.get_texts():
        txt.set_color(th["ink2"])
    titles(fig, th, "Account growth at 1% risk per trade, all markets in one account",
           "Compounded, after spread and commission, no swap.")
    return save(fig, "equity", mode)


def example_chart(tr, mode, name):
    th = THEMES[mode]
    d = load_daily(tr["symbol"])
    i_sig = d.index.get_loc(pd.Timestamp(tr["signal_day"]))
    i_exit = d.index.get_loc(pd.Timestamp(tr["exit_day"]))
    a, b = max(0, i_sig - 45), min(len(d), i_exit + 6)
    w = d.iloc[a:b]
    zone = ZONE_ATR * tr["atr"]
    fig, ax = plt.subplots(figsize=(8, 4.6), facecolor=th["surface"])
    fig.subplots_adjust(left=0.09, right=0.86, top=0.83, bottom=0.1)
    style(ax, th)
    x = np.arange(len(w))
    for k, (o, h, lo, c) in enumerate(zip(w["open"], w["high"], w["low"], w["close"])):
        col = th["up"] if c >= o else th["down"]
        ax.plot([k, k], [lo, h], color=col, linewidth=0.9, zorder=2)
        ax.add_patch(Rectangle((k - 0.32, min(o, c)), 0.64, max(abs(c - o), 1e-9), color=col, zorder=3, linewidth=0))
    ks, ke = i_sig - a, i_exit - a
    ax.axhspan(tr["level"] - zone, tr["level"] + zone, color=th["series"][0], alpha=0.12, linewidth=0, zorder=1)
    for y, lab, col in ((tr["entry"], "entry", th["series"][0]), (tr["target"], "target 2R", th["series"][2]),
                        (tr["stop"], "stop", th["series"][1])):
        ax.plot([ks + 1, ke + 0.4], [y, y], color=col, linewidth=1.8, solid_capstyle="round", zorder=4)
        ax.annotate(lab, (1.01, y), xycoords=("axes fraction", "data"), va="center", fontsize=8.5,
                    color=th["ink2"], annotation_clip=False)
        ax.plot([1.0], [y], marker="s", markersize=5, color=col, transform=ax.get_yaxis_transform(),
                clip_on=False, zorder=4)
    ax.annotate("key level zone", (0.5, tr["level"]), va="center", fontsize=8.5, color=th["ink2"])
    sig_y = w["low"].iloc[ks] if tr["dir"] > 0 else w["high"].iloc[ks]
    off = -1 if tr["dir"] > 0 else 1
    ax.annotate("signal bar", (ks, sig_y), xytext=(0, 18 * off), textcoords="offset points", ha="center",
                va="center", fontsize=8.5, color=th["ink"],
                arrowprops=dict(arrowstyle="-", color=th["ink2"], linewidth=0.8))
    ticks = list(range(0, len(w), 10))
    ax.set_xticks(ticks)
    ax.set_xticklabels([w.index[t].strftime("%d %b %y") for t in ticks], fontsize=8.5)
    ax.set_xlim(-1, len(w))
    side = "long" if tr["dir"] > 0 else "short"
    result = f"{tr['r']:+.2f}R, {tr['reason']}"
    titles(fig, th, f"{tr['market']}: hybrid {side}, signal {pd.Timestamp(tr['signal_day']):%d %b %Y} ({result})",
           f"Daily bid candles, lighter grey = up day. Key level: {tr['touches']:.0f} swing points "
           f"({PIVOT_N} bars either side) in {LOOKBACK} days; zone ±¼ ATR.")
    return save(fig, name, mode)


def main():
    os.makedirs(CHARTS_DIR, exist_ok=True)
    summ = pd.read_csv(os.path.join(RESULTS_DIR, "summary_variants.csv"))
    summ = summ.set_index("variant").loc[list(VARIANTS)].reset_index()
    eq = pd.read_csv(os.path.join(RESULTS_DIR, "equity_daily.csv"), parse_dates=["day"], index_col="day")
    t = pd.read_csv(os.path.join(RESULTS_DIR, "trades.csv.gz"))
    hyb = t[(t["variant"] == "V4") & (t["rule"] == "cons") & t["costs"] & t["hourly"] & (t["settled"] == "daily")]
    hyb = hyb.sort_values(["entry_day", "symbol"])
    # examples: the most recent clean target hit and the most recent clean stop-out
    win = hyb[hyb["reason"] == "target"].iloc[-1]
    loss = hyb[hyb["reason"] == "stop"].iloc[-1]
    for mode in THEMES:
        print(avg_r_chart(summ, mode))
        print(equity_chart(eq, mode))
        print(example_chart(win, mode, "example_win"))
        print(example_chart(loss, mode, "example_loss"))


if __name__ == "__main__":
    main()
