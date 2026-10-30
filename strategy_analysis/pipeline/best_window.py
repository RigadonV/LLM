"""Which time window inside the London session (07:00-13:00 UK) returns the most?

Two independent views of every window (each hour, and every block of 2-6 consecutive hours):
  - the journal: the trader's own trades, scored the way the checklist implies (Win +3R, BE 0R, Loss -1R)
  - the backtest: the final rules traded mechanically, bucketed by entry time
With 21 windows compared, the best one is flattered by the selection itself, so each window also gets
a bootstrap 95% range and a split-half check (first vs second half of the sample).
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import ROOT, RESULTS_DIR, load_journal, load_prices  # noqa: E402
from replicate_strategy import FINAL, Market, Rules, backtest, in_window  # noqa: E402

UK = "Europe/London"
CLASS_R = {"Win": 3.0, "BE": 0.0, "Loss": -1.0}
rng = np.random.default_rng(5)


def uk_hour(ts):
    local = ts.dt.tz_convert(UK)
    return local.dt.hour + local.dt.minute / 60


def ci(x, n_boot=4000):
    if len(x) < 5:
        return np.nan, np.nan
    means = rng.choice(x, (n_boot, len(x))).mean(axis=1)
    return np.percentile(means, 2.5), np.percentile(means, 97.5)


def max_drawdown(r):
    eq = np.cumsum(r)
    return float((np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max()) if len(r) else np.nan


def windows():
    for length in range(1, 7):
        for a in range(7, 14 - length):
            yield f"{a:02d}:00-{a + length:02d}:00", a, a + length


def main(journal_path):
    journal = load_journal(journal_path)
    logged = set(journal.entry_et.dt.normalize())  # every day the trader journaled, as elsewhere
    journal = journal[in_window(journal.entry_et, FINAL)].copy()
    journal["R"] = journal.result.map(CLASS_R)
    journal["h"] = uk_hour(journal.entry_et)

    mk = Market(load_prices("m1"), FINAL.pivot_n)
    bt = backtest(mk, FINAL, journal.date.min(), journal.date.max())
    bt = bt[bt.entry_et.dt.normalize().isin(logged)].sort_values("entry_et").copy()  # same days as the journal
    bt["h"] = uk_hour(bt.entry_et)

    split = journal.entry_et.sort_values().iloc[len(journal) // 2]  # first vs second half of the journal
    months = (journal.date.max() - journal.date.min()).days / 30.4

    rows = []
    for label, a, b in windows():
        jw = journal[(journal.h >= a) & (journal.h < b)]
        bw = bt[(bt.h >= a) & (bt.h < b)]
        lo, hi = ci(bw.r.values)
        rows.append({
            "window_UK": label, "hours": b - a,
            "journal_trades": len(jw), "journal_loss_rate": round((jw.result == "Loss").mean(), 3),
            "journal_R_per_trade": round(jw.R.mean(), 2), "journal_R_total": round(jw.R.sum(), 1),
            "journal_R_1st_half": round(jw[jw.entry_et < split].R.mean(), 2),
            "journal_R_2nd_half": round(jw[jw.entry_et >= split].R.mean(), 2),
            "bt_trades": len(bw), "bt_loss_rate": round((bw.outcome == "Loss").mean(), 3),
            "bt_R_per_trade": round(bw.r.mean(), 3), "bt_R_ci_low": round(lo, 2), "bt_R_ci_high": round(hi, 2),
            "bt_R_total": round(bw.r.sum(), 1), "bt_R_per_month": round(bw.r.sum() / months, 1),
            "bt_R_1st_half": round(bw[bw.entry_et < split].r.mean(), 2),
            "bt_R_2nd_half": round(bw[bw.entry_et >= split].r.mean(), 2),
            "bt_max_drawdown_R": round(max_drawdown(bw.r.values), 1),
        })
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS_DIR, "london_window_returns.csv"), index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 30)
    print(f"journal London trades: {len(journal)}, backtest trades on the same days: {len(bt)}, split at {split:%Y-%m-%d}")
    print(res.to_string(index=False))
    chart(res[res.hours == 1])
    exit_check(mk, journal, logged, bt)


def exit_check(mk, journal, logged, bt):
    """Does the late-London edge depend on holding into the New York open (14:30 UK)?"""
    late = bt[bt.h >= 12]
    print(f"\n12:00-13:00 entries still open at 14:30 UK: {(uk_hour(late.exit_et) >= 14.5).mean():.0%}; "
          f"exits after 13:00 UK: {(uk_hour(late.exit_et) >= 13).mean():.0%}")
    rows = []
    for flat in (13.0, 14.5, 17.0):
        rules = Rules(**{**FINAL.__dict__, "exit_by": flat})
        b = backtest(mk, rules, journal.date.min(), journal.date.max())
        b = b[b.entry_et.dt.normalize().isin(logged)].copy()
        b["h"] = uk_hour(b.entry_et)
        for label, a, z in (("07:00-10:00", 7, 10), ("10:00-13:00", 10, 13), ("12:00-13:00", 12, 13), ("07:00-13:00", 7, 13)):
            x = b[(b.h >= a) & (b.h < z)].r.values
            lo, hi = ci(x)
            rows.append({"flat_by_UK": f"{int(flat):02d}:{int(flat % 1 * 60):02d}", "window_UK": label, "trades": len(x),
                         "R_per_trade": round(x.mean(), 3), "ci_low": round(lo, 2), "ci_high": round(hi, 2),
                         "R_total": round(x.sum(), 1), "P(mean<=0)": round(float((rng.choice(x, (4000, len(x))).mean(axis=1) <= 0).mean()), 3)})
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS_DIR, "london_window_exit_check.csv"), index=False)
    print(res.to_string(index=False))


def chart(hourly):
    """Two panels (different scales -> never one shared axis): journal and backtest R per trade by hour."""
    ink, ink2, grid, axis, surface = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"
    blue, orange = "#2a78d6", "#eb6834"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": axis,
                         "xtick.color": ink2, "ytick.color": ink2, "axes.facecolor": surface,
                         "figure.facecolor": surface, "axes.spines.top": False, "axes.spines.right": False})
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    x = np.arange(len(hourly))
    labels = [w[:5] for w in hourly.window_UK]
    for ax, col, ycol, title, color in (
            (a1, "journal_trades", "journal_R_per_trade", "Your journal (Win +3R, BE 0, Loss -1R)", blue),
            (a2, "bt_trades", "bt_R_per_trade", "Mechanical backtest, with 95% range", orange)):
        y = hourly[ycol].values
        ax.bar(x, y, width=0.6, color=color, zorder=3)
        if ax is a2:
            ax.errorbar(x, y, yerr=[y - hourly.bt_R_ci_low.values, hourly.bt_R_ci_high.values - y],
                        fmt="none", ecolor=ink2, elinewidth=1, capsize=3, zorder=4)
        ax.axhline(0, color=axis, linewidth=1, zorder=2)
        ax.grid(axis="y", color=grid, linewidth=0.6, zorder=0)
        ax.set_xticks(x, [f"{lab}\nn={n}" for lab, n in zip(labels, hourly[col].values)])
        ax.set_xlabel("entry hour (UK), number of trades", color=ink2)
        ax.set_ylabel("R per trade", color=ink2)
        ax.set_title(title, loc="left", fontsize=10, color=ink, fontweight="bold", pad=12)
        top = max(y.max(), hourly.bt_R_ci_high.max() if ax is a2 else 0)
        bottom = min(0, y.min(), hourly.bt_R_ci_low.min() if ax is a2 else 0)
        ax.set_ylim(bottom - 0.08 * (top - bottom), top + 0.12 * (top - bottom))
        for xi, yi in enumerate(y):
            # value beside the bar top, clear of the error bar
            ax.annotate(f"{yi:+.2f}", (xi + 0.3, yi), xytext=(3, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=8, color=ink)
    fig.suptitle("R per trade by entry hour, London session (07:00-13:00 UK)", x=0.01, ha="left", fontsize=11.5,
                 color=ink, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "charts", "london_hours.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1])
