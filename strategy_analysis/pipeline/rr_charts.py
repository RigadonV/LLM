"""Charts for RR_IMPROVEMENTS.md: a pattern scorecard and two example trades (spiky leg vs calm leg)."""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import ROOT, RESULTS_DIR, load_prices, resample  # noqa: E402
from compare_results import PERIOD  # noqa: E402
from improve_rr import BEST  # noqa: E402
from make_charts import chart_trade  # noqa: E402
from replicate_strategy import Market, backtest  # noqa: E402
from trade_features import describe, leg_of  # noqa: E402

INK, INK2, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"
KEPT, SKIPPED = "#2a78d6", "#eb6834"
PATTERNS = [  # label, column, rule that keeps the trade
    ("Skip spiky legs\n(< 2.5 ATR/h kept)", "leg_speed_atr_per_h", lambda x: x < 2.5),
    ("Skip slow pullbacks\n(< 0.8x leg time kept)", "pullback_vs_leg_time", lambda x: x < 0.8),
    ("Wick-heavy pullbacks\n(bodies < 50% kept)", "pullback_body_ratio", lambda x: x < 0.5),
    ("Skip counter-FVGs\n(0-1 kept)", "pullback_counter_fvgs_5m", lambda x: x <= 1),
]


def scorecard(feat, journal):
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": AXIS, "xtick.color": INK2,
                         "ytick.color": INK2, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.6))
    x = np.arange(len(PATTERNS))
    w = 0.36
    bt_k = [feat.r_net[keep(feat[col])].mean() for _, col, keep in PATTERNS]
    bt_s = [feat.r_net[~keep(feat[col])].mean() for _, col, keep in PATTERNS]
    bt_nk = [int(keep(feat[col]).sum()) for _, col, keep in PATTERNS]
    bt_ns = [int((~keep(feat[col])).sum()) for _, col, keep in PATTERNS]
    jk, js = journal.R_kept.values, journal.R_skipped.values
    for ax, k, sk, nk, ns, title in (
            (a1, bt_k, bt_s, bt_nk, bt_ns, "Backtest (best config), net R per trade"),
            (a2, jk, js, journal.journal_trades_kept.values, journal.journal_trades_skipped.values,
             "Your journal, R per trade (3R / 0 / -1R)")):
        ax.bar(x - w / 2, k, w, color=KEPT, label="trades the rule keeps", zorder=3)
        ax.bar(x + w / 2, sk, w, color=SKIPPED, label="trades the rule skips", zorder=3)
        for xi, (v1, v2, n1, n2) in enumerate(zip(k, sk, nk, ns)):
            for dx, v, n in ((-w / 2, v1, n1), (w / 2, v2, n2)):
                ax.annotate(f"{v:+.2f}\nn={n}", (xi + dx, v), xytext=(0, 3 if v >= 0 else -24), textcoords="offset points",
                            ha="center", fontsize=7.5, color=INK2)
        ax.axhline(0, color=AXIS, linewidth=1)
        ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
        ax.set_xticks(x, [p[0] for p in PATTERNS], fontsize=8)
        ax.set_title(title, loc="left", fontsize=10, color=INK, fontweight="bold", pad=10)
        lo, hi = min(0, min(k), min(sk)), max(k + sk if isinstance(k, list) else list(k) + list(sk))
        ax.set_ylim(lo - 0.25 * (hi - lo), hi + 0.25 * (hi - lo))
    a1.legend(loc="upper right", frameon=False, fontsize=8, labelcolor=INK2)
    fig.suptitle("Chart patterns at entry: trades kept vs skipped", x=0.01, ha="left", fontsize=11.5, color=INK,
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "charts", "rr_patterns.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)


def example(mk, m1, tr, feat_row, path, prefix):
    i = mk.t.searchsorted(tr.entry_et)
    k, a, ext, j_ext = leg_of(mk, tr, i)
    s0 = mk.piv[tr.direction]["start"][k]
    ny = lambda t: pd.Timestamp(t).tz_convert("America/New_York").strftime("%Y-%m-%d %H:%M")
    exit_t = mk.t[min(mk.t.searchsorted(tr.exit_et), len(mk.t) - 1)]
    result = {"Win": "Win", "Loss": "Loss"}.get(tr.outcome, "BE")
    row = pd.Series({
        "trade_id": "backtest", "date": ny(tr.entry_et)[:10], "entry_et": ny(tr.entry_et), "exit_et": ny(exit_t),
        "exit_time_est": ny(exit_t), "fib_anchor_time": ny(mk.t[s0]), "fib_anchor_price": a,
        "fib_extreme_time": ny(mk.t[j_ext]), "fib_extreme_price": ext, "direction": tr.direction,
        "fib_level": tr.fib_level, "entry_price_est": tr.entry, "stop_price_est": tr.stop, "exit_price_est": tr.exit,
        "result": result, "rr": max(tr.r, 0), "mfe_r": max(tr.r, 0), "minutes": tr.minutes, "leg_size_pts": tr.leg_size,
        "fib_ratio_at_entry": tr.fib_level, "stop_pts_est": abs(tr.entry - tr.stop),
        "stop_leg_frac": abs(tr.entry - tr.stop) / tr.leg_size, "ob_tf": "", "fvg_tf": "", "trend_aligned": "",
    })
    sub = (f"Leg {abs(ext - a):.0f} pts in {feat_row.leg_minutes:.0f} min = {feat_row.leg_speed_atr_per_h:.1f} ATR/hour; "
           f"pullback {feat_row.pullback_minutes:.0f} min ({feat_row.pullback_vs_leg_time:.2f}x the leg's time), "
           f"pullback candle bodies {feat_row.pullback_body_ratio:.0%} of range, {feat_row.pullback_counter_fvgs_5m} counter-FVGs (5m)")
    chart_trade(row, m1, path, prefix, subtitle=sub)


def main():
    m1 = load_prices("m1")
    mk = Market(m1, 2)
    bt = backtest(mk, BEST, *PERIOD).reset_index(drop=True)
    feat = describe(mk, resample(m1, "5min"), resample(m1, "1D"), bt)
    journal = pd.read_csv(os.path.join(RESULTS_DIR, "rr_patterns_in_journal.csv"))
    scorecard(feat, journal)

    # typical examples: the median-speed spiky loser and the median-speed calm, wick-heavy winner
    spiky = feat[(feat.leg_speed_atr_per_h >= 2.5) & (feat.outcome == "Loss")]
    calm = feat[(feat.leg_speed_atr_per_h < 2.5) & (feat.pullback_body_ratio < 0.5) & (feat.outcome == "Win")]
    for sel, path, prefix in ((spiky, "rr_example_spiky_leg_loss.png", "Pattern to avoid - spiky leg: "),
                              (calm, "rr_example_calm_leg_win.png", "Pattern to keep - calm leg, wick-heavy pullback: ")):
        pick = sel.iloc[(sel.leg_speed_atr_per_h - sel.leg_speed_atr_per_h.median()).abs().argsort().iloc[0]]
        tr = bt[bt.entry_et == pick.entry_et].iloc[0]
        example(mk, m1, tr, pick, os.path.join(ROOT, "charts", path), prefix)
        print("wrote", path, pick.entry_et)


if __name__ == "__main__":
    main()
