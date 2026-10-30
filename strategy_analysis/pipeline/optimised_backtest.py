"""Backtest of the optimised strategy on Dukascopy data, 2 March 2026 to the latest complete session.

No journal input: every weekday is traded mechanically.
  - session: entries 07:00-13:00 UK, everything flat by 14:30 UK
  - setup: most recent unbroken 15M fractal leg >= 2 x ATR, limit orders at the untouched 0.705 / 0.79 level
  - risk rules: 2 losses = done for the day, SL < 50 pts, stop 14% of the leg beyond the entry
  - additions: 15M EMA50 trend filter, skip spiky legs (faster than 2.5 x ATR per hour)
  - account: 1% of the balance risked per trade, compounding from $10,000, 1.5-pt costs per round trip
Each addition is switched on in turn and run with TP 2R and TP 4R. Data after 16 October was never
used to choose anything, so those days are reported separately as unseen.
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
from compare_results import RISK_RULES, rules  # noqa: E402
from improve_rr import Patterns  # noqa: E402
from one_month import COST_PTS, RISK, START_BALANCE  # noqa: E402
from replicate_strategy import Market, Rules, backtest  # noqa: E402

START = pd.Timestamp("2026-03-02")
UNSEEN = pd.Timestamp("2026-10-17", tz="America/New_York")  # first day after the data used for every choice so far
EXITS = {
    "TP 2R": dict(target_r=2.0, be_at_r=None),
    "TP 2R, BE at 1R": dict(target_r=2.0, be_at_r=1.0),
    "TP 4R, BE at 2R": dict(target_r=4.0, be_at_r=2.0),
}


def net_r(bt):
    return (bt.r - COST_PTS / (bt.entry - bt.stop).abs()).values


def growth(r):
    return float(np.prod(1 + RISK * np.asarray(r))) if len(r) else 1.0


def stats(name, exit_name, bt, months):
    r = net_r(bt)
    bal = START_BALANCE * np.cumprod(1 + RISK * r)
    peak = np.maximum.accumulate(np.concatenate([[START_BALANCE], bal]))[1:]
    losses = (bt.outcome == "Loss").values
    streak = longest = 0
    for x in losses:
        streak = streak + 1 if x else 0
        longest = max(longest, streak)
    monthly = pd.Series(r).groupby(bt.entry_et.dt.strftime("%Y-%m").values).apply(lambda x: growth(x) - 1)
    unseen = r[(bt.entry_et >= UNSEEN).values]
    gains, pains = r[r > 0].sum(), -r[r < 0].sum()
    tgt = 2.0 if exit_name.startswith("TP 2R") else 4.0
    cost_r = np.mean(COST_PTS / (bt.entry - bt.stop).abs())
    return {
        "additions": name, "exit": exit_name, "trades": len(r), "trades_per_month": round(len(r) / months, 1),
        "win_rate": round(float((bt.outcome == "Win").mean()), 3),
        "breakeven_win_rate": round((1 + cost_r) / (1 + tgt), 3),  # ignoring scratches
        "be_rate": round(float(bt.outcome.isin(["BE", "Locked"]).mean()), 3), "loss_rate": round(float(losses.mean()), 3),
        "net_R_per_trade": round(r.mean(), 3), "profit_factor": round(gains / pains, 2) if pains else np.nan,
        "total_return_pct": round(100 * (growth(r) - 1), 1),
        "per_month_pct": round(100 * (growth(r) ** (1 / months) - 1), 1),
        "max_drawdown_pct": round(100 * float(((peak - bal) / peak).max()), 1),
        "longest_losing_streak": longest, "losing_months": f"{int((monthly < 0).sum())} of {len(monthly)}",
        "unseen_17-29_Oct_trades": len(unseen), "unseen_17-29_Oct_return_pct": round(100 * (growth(unseen) - 1), 1),
    }


def main():
    m1 = load_prices("m1")
    end = m1.index.max().tz_localize(None).normalize()
    months = (end - START).days / 30.44
    mk = Market(m1, 2)
    pat = Patterns(mk, m1)
    spike = pat.make_filter(max_leg_speed=2.5)
    spike_wicky = pat.make_filter(max_leg_speed=2.5, max_body_ratio=0.5)
    ladder = [
        ("1. London 07:00-13:00 + your risk rules", rules(**RISK_RULES)),
        ("2. + 15M trend filter", rules(**RISK_RULES, trend_filter="15m")),
        ("3. + skip spiky legs  (= optimised)", rules(**RISK_RULES, trend_filter="15m", entry_filter=spike)),
        ("4. optimised + stop 0.17 x leg", rules(**RISK_RULES, trend_filter="15m", entry_filter=spike, stop_leg_frac=0.17)),
        ("5. optimised + wick-heavy pullbacks only", rules(**RISK_RULES, trend_filter="15m", entry_filter=spike_wicky)),
    ]
    rows, keep = [], {}
    for name, base in ladder:
        for exit_name, kw in EXITS.items():
            bt = backtest(mk, Rules(**{**base.__dict__, **kw}), START, end)
            rows.append(stats(name, exit_name, bt, months))
            keep[(name, exit_name)] = bt
            s = rows[-1]
            print(f"{name:42s} {exit_name:16s} trades {s['trades']:4d} win {s['win_rate']:.0%} (need {s['breakeven_win_rate']:.0%}) "
                  f"R/trade {s['net_R_per_trade']:+.3f} return {s['total_return_pct']:+6.1f}% DD {s['max_drawdown_pct']:5.1f}% "
                  f"unseen {s['unseen_17-29_Oct_return_pct']:+5.1f}% ({s['unseen_17-29_Oct_trades']} tr)", flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS_DIR, "optimised_backtest.csv"), index=False)

    opt = "3. + skip spiky legs  (= optimised)"
    monthly = pd.DataFrame({ex: pd.Series(net_r(keep[(opt, ex)])).groupby(
        keep[(opt, ex)].entry_et.dt.strftime("%b").values, sort=False).apply(lambda x: round(100 * (growth(x) - 1), 1))
        for ex in EXITS})
    monthly.to_csv(os.path.join(RESULTS_DIR, "optimised_backtest_monthly.csv"))
    print("\nOptimised strategy, return by month (%):\n" + monthly.T.to_string())
    trades = keep[(opt, "TP 2R")].assign(r_net=lambda d: net_r(d))
    trades.to_csv(os.path.join(RESULTS_DIR, "optimised_trades_tp2r.csv"), index=False)
    keep[(opt, "TP 4R, BE at 2R")].assign(r_net=lambda d: net_r(d)).to_csv(
        os.path.join(RESULTS_DIR, "optimised_trades_tp4r.csv"), index=False)
    chart({"Optimised, TP 2R": keep[(opt, "TP 2R")], "Optimised, TP 4R (BE 2R)": keep[(opt, "TP 4R, BE at 2R")],
           "London + risk rules only, TP 2R": keep[(ladder[0][0], "TP 2R")]}, end)


def chart(series, end):
    ink, ink2, grid, axis, surface = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"
    colors = ["#2a78d6", "#eb6834", "#898781"]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": axis, "xtick.color": ink2,
                         "ytick.color": ink2, "axes.facecolor": surface, "figure.facecolor": surface,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.axvspan(UNSEEN.tz_localize(None), end + pd.Timedelta(days=1), color="#f0efec", zorder=0, linewidth=0)
    ax.text(UNSEEN.tz_localize(None) + pd.Timedelta(days=1), 0.98, "unseen\ndata", transform=ax.get_xaxis_transform(),
            va="top", fontsize=8, color=ink2)
    for (name, bt), col in zip(series.items(), colors):
        bal = START_BALANCE * np.cumprod(1 + RISK * net_r(bt))
        x = [START] + [t.tz_localize(None) for t in bt.entry_et.dt.tz_convert("Europe/London")]
        y = [START_BALANCE] + list(bal)
        ax.step(x, y, where="post", color=col, linewidth=2, label=f"{name}: {y[-1] / START_BALANCE - 1:+.0%}")
    ax.axhline(START_BALANCE, color=axis, linewidth=1)
    ax.grid(axis="y", color=grid, linewidth=0.6)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_ylabel("account balance ($), 1% risk per trade, after costs", color=ink2)
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=ink2)
    ax.set_title(f"Optimised strategy, every weekday, 2 Mar - {end:%d %b} 2026", loc="left", fontsize=11, color=ink,
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "charts", "optimised_equity.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
