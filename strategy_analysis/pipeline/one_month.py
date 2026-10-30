"""One-month backtest of the strategy under forex-style trading rules.

  - a fixed session window of a few hours, chosen on the months *before* the test month only
  - fixed-fractional risk: 1% of the current balance per trade, sized from the stop (as with a CFD /
    forex broker, where position size is not restricted to whole contracts), compounding
  - trading costs: 1.5 index points per round trip (NAS100 spread + commission during London)
  - the trader's risk rules: 2 losses = done for the day, SL < 50 pts, BE at +2R, TP at 3R
  - flat by 14:30 UK (the New York open)

Test month: September 2026, the latest full calendar month in the data.
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
from common import ROOT, RESULTS_DIR, load_journal, load_prices  # noqa: E402
from replicate_strategy import FINAL, Market, Rules, backtest  # noqa: E402

START_BALANCE = 10_000.0
RISK = 0.01
COST_PTS = 1.5
TEST = (pd.Timestamp("2026-09-01"), pd.Timestamp("2026-09-30"))
SELECT = (pd.Timestamp("2026-03-10"), pd.Timestamp("2026-08-31"))
CANDIDATE_WINDOWS = [(7.0, 10.0), (8.0, 11.0), (9.0, 12.0), (10.0, 13.0)]  # 3-hour windows inside London
RULES = Rules(**{**FINAL.__dict__, "name": "forex_rules", "max_losses_day": 2, "max_stop_pts": 50.0, "exit_by": 14.5})
CLASS_R = {"Win": 3.0, "BE": 0.0, "Loss": -1.0}
UK = "Europe/London"


def window_rules(window, **extra):
    return Rules(**{**RULES.__dict__, "window": window, **extra})


def net_r(bt):
    """R after costs: the round-trip cost in points as a fraction of the stop distance."""
    return bt.r - COST_PTS / (bt.entry - bt.stop).abs()


def account(r_net):
    """Compound 1% risk per trade. Returns the balance after each trade."""
    return START_BALANCE * np.cumprod(1 + RISK * np.asarray(r_net, dtype=float))


def summary(label, r_gross, r_net):
    bal = account(r_net)
    peak = np.maximum.accumulate(np.concatenate([[START_BALANCE], bal]))[1:]
    wins, losses = (r_net[r_net > 0]).sum(), -(r_net[r_net < 0]).sum()
    return {
        "run": label, "trades": len(r_net),
        "win_rate": round(float((r_gross >= 2.9).mean()), 3) if len(r_net) else np.nan,
        "loss_rate": round(float((r_gross <= -0.99).mean()), 3) if len(r_net) else np.nan,
        "gross_R": round(float(r_gross.sum()), 1), "net_R": round(float(r_net.sum()), 1),
        "return_pct": round(100 * (bal[-1] / START_BALANCE - 1), 1) if len(bal) else 0.0,
        "max_drawdown_pct": round(100 * float(((peak - bal) / peak).max()), 1) if len(bal) else 0.0,
        "profit_factor": round(wins / losses, 2) if losses else np.nan,
        "end_balance": round(float(bal[-1]), 0) if len(bal) else START_BALANCE,
    }


def journal_month(journal, window):
    """The trader's own trades in the test month and window, scored 3R / 0 / -1R with the same costs."""
    uk = journal.entry_et.dt.tz_convert(UK)
    h = uk.dt.hour + uk.dt.minute / 60
    j = journal[(journal.date >= TEST[0]) & (journal.date <= TEST[1]) & (h >= window[0]) & (h < window[1])]
    stops = pd.read_csv(os.path.join(ROOT, "trade_context.csv")).set_index("trade_id").stop_pts_est
    stop = j.trade_id.map(stops).fillna(stops.median()).clip(lower=5)
    gross = j.result.map(CLASS_R).values
    return j, gross, gross - COST_PTS / stop.values


def main(journal_path):
    journal = load_journal(journal_path)
    mk = Market(load_prices("m1"), RULES.pivot_n)

    # 1. pick the 3-hour window on March-August only
    sel = []
    for w in CANDIDATE_WINDOWS:
        b = backtest(mk, window_rules(w), *SELECT)
        rn = net_r(b)
        sel.append({"window_UK": f"{int(w[0]):02d}:00-{int(w[1]):02d}:00", "trades": len(b),
                    "net_R_per_trade": round(rn.mean(), 3), "net_R": round(rn.sum(), 1)})
    sel = pd.DataFrame(sel)
    best = CANDIDATE_WINDOWS[int(sel.net_R_per_trade.idxmax())]
    print("Window selection on 10 Mar - 31 Aug (net of costs):\n" + sel.to_string(index=False))
    label = f"{int(best[0]):02d}:00-{int(best[1]):02d}:00 UK"
    print(f"chosen: {label}\n")

    # 2. the test month
    bt = backtest(mk, window_rules(best), *TEST).sort_values("entry_et").reset_index(drop=True)
    bt["r_net"] = net_r(bt)
    bt["balance"] = account(bt.r_net)
    bt["entry_uk"] = bt.entry_et.dt.tz_convert(UK).dt.strftime("%a %d %b %H:%M")
    bt["stop_pts"] = (bt.entry - bt.stop).abs().round(1)
    bt["pnl"] = np.diff(np.concatenate([[START_BALANCE], bt.balance])).round(0)
    cols = ["entry_uk", "direction", "fib_level", "stop_pts", "outcome", "r", "r_net", "pnl", "balance"]
    out = bt[cols].round({"r_net": 2, "balance": 0})
    out.to_csv(os.path.join(RESULTS_DIR, "one_month_trades.csv"), index=False)
    print(out.to_string(index=False))

    rows = [summary(f"Backtest {label}, Sep 2026", bt.r.values, bt.r_net.values)]
    full = backtest(mk, window_rules((7.0, 13.0)), *TEST)
    rows.append(summary("Backtest 07:00-13:00 UK, Sep 2026", full.r.values, net_r(full).values))
    j, g, n = journal_month(journal, best)
    rows.append(summary(f"Your journal {label}, Sep 2026", g, n))
    j2, g2, n2 = journal_month(journal, (7.0, 13.0))
    rows.append(summary("Your journal 07:00-13:00 UK, Sep 2026", g2, n2))
    res = pd.DataFrame(rows)
    print("\n" + res.to_string(index=False))

    # 3. the same rules in every month, for context
    months = []
    for start in pd.date_range("2026-03-01", "2026-10-01", freq="MS"):
        a, z = max(start, pd.Timestamp("2026-03-10")), min(start + pd.offsets.MonthEnd(0), pd.Timestamp("2026-10-16"))
        b = backtest(mk, window_rules(best), a, z)
        s = summary(start.strftime("%b %Y") + ("" if z.day > 20 else " (part)"), b.r.values, net_r(b).values)
        months.append(s)
    months = pd.DataFrame(months)
    print("\nSame rules, every month:\n" + months.to_string(index=False))

    pd.concat([sel.assign(table="window selection, Mar-Aug"), res.assign(table="September 2026"),
               months.assign(table="every month")]).to_csv(os.path.join(RESULTS_DIR, "one_month_summary.csv"), index=False)
    chart(bt, j, n, label)


def chart(bt, j, j_net, label):
    ink, ink2, grid, axis, surface = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7", "#fcfcfb"
    blue, orange = "#2a78d6", "#eb6834"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": axis, "xtick.color": ink2,
                         "ytick.color": ink2, "axes.facecolor": surface, "figure.facecolor": surface,
                         "axes.spines.top": False, "axes.spines.right": False})
    fig, ax = plt.subplots(figsize=(10, 4.6))
    series = [("Mechanical rules", bt.entry_et, bt.balance.values, blue),
              ("Your journal (3R / 0 / -1R)", j.entry_et, account(j_net), orange)]
    for name, t, bal, col in series:
        x = [pd.Timestamp("2026-09-01", tz=t.dt.tz)] + list(t)
        y = [START_BALANCE] + list(bal)
        ax.step([pd.Timestamp(v).tz_convert(UK).tz_localize(None) for v in x], y, where="post", color=col, linewidth=2, label=name)
        ax.annotate(f"{name}: {y[-1] / START_BALANCE - 1:+.1%}", (pd.Timestamp(x[-1]).tz_convert(UK).tz_localize(None), y[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center", fontsize=8.5, color=ink)
    ax.axhline(START_BALANCE, color=axis, linewidth=1)
    ax.grid(axis="y", color=grid, linewidth=0.6)
    ax.set_ylabel("account balance ($), 1% risk per trade", color=ink2)
    ax.set_xlim(pd.Timestamp("2026-09-01"), pd.Timestamp("2026-10-07"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=ink2)
    ax.set_title(f"September 2026, {label} entries, after 1.5-pt costs", loc="left", fontsize=11, color=ink,
                 fontweight="bold")
    fig.tight_layout()
    fig.savefig(os.path.join(ROOT, "charts", "one_month_equity.png"), dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main(sys.argv[1])
