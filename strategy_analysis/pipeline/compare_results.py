"""Every configuration tested so far, re-run on one common basis so their returns can be compared.

Basis: 10 Mar - 16 Oct 2026, every weekday, 1.5-pt round-trip costs, 1% of the balance risked per
trade (compounding from $10,000), flat by 14:30 UK. Mar-Aug is where the 10:00-13:00 window was
picked; Sep-Oct was never used to choose anything.
"""
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import ROOT, RESULTS_DIR, load_prices  # noqa: E402
from one_month import COST_PTS, RISK, START_BALANCE  # noqa: E402
from replicate_strategy import AS_JOURNALED, FINAL, Market, Rules, backtest  # noqa: E402

PERIOD = (pd.Timestamp("2026-03-10"), pd.Timestamp("2026-10-16"))
SPLIT = pd.Timestamp("2026-09-01", tz="America/New_York")
rng = np.random.default_rng(9)


def rules(**kw):
    return Rules(**{**FINAL.__dict__, "exit_by": 14.5, **kw})


RISK_RULES = {"max_losses_day": 2, "max_stop_pts": 50.0}
CANDIDATES = [
    ("Journal's own window 07:00-14:30 UK, final rules", AS_JOURNALED),
    ("London 07:00-13:00 UK, final rules", rules()),
    ("London 07:00-13:00 + your risk rules", rules(**RISK_RULES)),
    ("London 07:00-13:00 + risk rules + 15M trend", rules(**RISK_RULES, trend_filter="15m")),
    ("London 07:00-13:00 + risk rules + 1H trend", rules(**RISK_RULES, trend_filter="1h")),
    ("London 07:00-13:00 + risk rules + OB/FVG", rules(**RISK_RULES, require_zone=True)),
    ("London 07:00-13:00 + risk rules + 15M trend + OB/FVG", rules(**RISK_RULES, trend_filter="15m", require_zone=True)),
    ("10:00-13:00 UK + risk rules (one-month test setup)", rules(**RISK_RULES, window=(10.0, 13.0))),
    ("12:00-13:00 UK + risk rules (best single hour)", rules(**RISK_RULES, window=(12.0, 13.0))),
    ("NEW combination: 10:00-13:00 UK + risk rules + 15M trend", rules(**RISK_RULES, window=(10.0, 13.0), trend_filter="15m")),
]


def growth(r):
    return float(np.prod(1 + RISK * np.asarray(r))) if len(r) else 1.0


def score(name, bt):
    r = (bt.r - COST_PTS / (bt.entry - bt.stop).abs()).values
    bal = START_BALANCE * np.cumprod(1 + RISK * r)
    peak = np.maximum.accumulate(np.concatenate([[START_BALANCE], bal]))[1:]
    months = bt.entry_et.dt.strftime("%Y-%m")
    monthly = pd.Series(r).groupby(months.values).apply(lambda x: growth(x) - 1)
    boots = rng.choice(r, (4000, len(r))).mean(axis=1)
    early, late = r[(bt.entry_et < SPLIT).values], r[(bt.entry_et >= SPLIT).values]
    total = growth(r) - 1
    dd = float(((peak - bal) / peak).max())
    return {
        "configuration": name, "trades": len(r), "win_rate": round(float((bt.r >= 2.9).mean()), 3),
        "net_R": round(r.sum(), 1), "net_R_per_trade": round(r.mean(), 3),
        "R_per_trade_ci": f"{np.percentile(boots, 2.5):+.2f} to {np.percentile(boots, 97.5):+.2f}",
        "total_return_pct": round(100 * total, 1),
        "per_month_pct": round(100 * ((1 + total) ** (1 / 7.2) - 1), 1),
        "max_drawdown_pct": round(100 * dd, 1),
        "return_to_drawdown": round(total / dd, 2) if dd else np.nan,
        "losing_months": f"{int((monthly < 0).sum())} of {len(monthly)}",
        "Mar-Aug_return_pct": round(100 * (growth(early) - 1), 1),
        "Sep-Oct_return_pct": round(100 * (growth(late) - 1), 1),
    }


def net(bt):
    return (bt.r - COST_PTS / (bt.entry - bt.stop).abs()).values


def main():
    mk = Market(load_prices("m1"), FINAL.pivot_n)
    rows, trades = [], {}
    for name, r in CANDIDATES:
        bt = backtest(mk, r, *PERIOD)
        trades[name] = bt
        rows.append(score(name, bt))
        print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    top = res.sort_values("total_return_pct", ascending=False).configuration.head(3).tolist()
    show = top + ["London 07:00-13:00 UK, final rules"]
    monthly = pd.DataFrame({name: pd.Series(net(trades[name])).groupby(trades[name].entry_et.dt.strftime("%b").values,
                                                                         sort=False).apply(lambda x: round(100 * (growth(x) - 1), 1))
                            for name in show})
    monthly.to_csv(os.path.join(RESULTS_DIR, "best_return_monthly.csv"))
    print(monthly.T.to_string())
    chart({name: trades[name] for name in show})
    res.to_csv(os.path.join(RESULTS_DIR, "best_return_comparison.csv"), index=False)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 20)
    print(res.sort_values("total_return_pct", ascending=False).to_string(index=False))


def chart(series):
    ink, ink2, grid, axis, surface = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"
    colors = ["#2a78d6", "#eb6834", "#1baf7a", "#898781"]  # categorical slots 1-3, last series muted
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": axis, "xtick.color": ink2,
                         "ytick.color": ink2, "axes.facecolor": surface, "figure.facecolor": surface,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(11, 5))
    ends = []
    for (name, bt), col in zip(series.items(), colors):
        bal = START_BALANCE * np.cumprod(1 + RISK * net(bt))
        x = [PERIOD[0]] + [t.tz_localize(None) for t in bt.entry_et.dt.tz_convert("Europe/London")]
        y = [START_BALANCE] + list(bal)
        ax.step(x, y, where="post", color=col, linewidth=2, label=name)
        ends.append((y[-1], x[-1]))
    # end labels, nudged apart so close finishes stay readable
    placed = []
    for y_end, x_end in sorted(ends, reverse=True):
        y_lab = min([y_end] + [p - 350 for p in placed if abs(p - y_end) < 350])
        placed.append(y_lab)
        ax.annotate(f"{y_end / START_BALANCE - 1:+.0%}", (x_end, y_end), xytext=(PERIOD[1] + pd.Timedelta(days=2), y_lab),
                    textcoords="data", va="center", fontsize=9, color=ink, fontweight="bold")
    ax.set_xlim(PERIOD[0] - pd.Timedelta(days=3), PERIOD[1] + pd.Timedelta(days=12))
    ax.axhline(START_BALANCE, color=axis, linewidth=1)
    ax.grid(axis="y", color=grid, linewidth=0.6)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_ylabel("account balance ($), 1% risk per trade, after costs", color=ink2)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=ink2)
    ax.set_title("Best configurations so far, 10 Mar - 16 Oct 2026, every weekday", loc="left", fontsize=11,
                 color=ink, fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "charts", "best_return_equity.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
