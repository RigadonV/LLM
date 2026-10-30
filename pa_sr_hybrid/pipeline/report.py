"""Step 3: summary tables from results/trades.csv.gz.

  python pipeline/report.py

Writes results/data_summary.csv, results/summary_variants.csv, results/hybrid_breakdown.csv, results/hybrid_by_market.csv, results/equity_daily.csv and
results/report_tables.md (the tables used in BACKTEST.md).
R is profit or loss divided by the risk planned at entry, after spread and commission.
"""
import os

import numpy as np
import pandas as pd

from common import INSTRUMENTS, RESULTS_DIR, atr, load_daily
from strategy import TREND_DAYS, VARIANTS

START, END = pd.Timestamp("2008-01-01"), pd.Timestamp("2026-09-30")
YEARS = (END - START).days / 365.25
SPLIT = pd.Timestamp("2017-01-01")
RISK = 0.01
rng = np.random.default_rng(7)


def max_drawdown_r(r):
    cum = np.cumsum(r)
    return float((np.maximum.accumulate(np.r_[0, cum]) - np.r_[0, cum]).max())


def block_bootstrap(df, n=10000):
    """Average R resampled by calendar month of entry, so trades taken together (often in correlated
    markets) stay together. Returns the 95% interval and the share of resamples at or below zero."""
    g = df.groupby(df["entry_day"].dt.to_period("M"))["r"].agg(["sum", "count"])
    if len(g) < 2:
        return np.nan, np.nan, np.nan
    idx = rng.integers(0, len(g), size=(n, len(g)))
    means = g["sum"].to_numpy()[idx].sum(axis=1) / g["count"].to_numpy()[idx].sum(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return lo, hi, (means <= 0).mean()


def stats(df):
    df = df.sort_values(["exit_day", "entry_day"])
    r = df["r"].to_numpy()
    n = len(r)
    if n == 0:
        return dict(trades=0)
    lo, hi, p = block_bootstrap(df)
    win, loss = r[r > 0].sum(), -r[r < 0].sum()
    return dict(trades=n, per_year=n / YEARS, win_rate=(r > 0).mean(), avg_r=r.mean(), ci_lo=lo, ci_hi=hi,
                p_le_zero=p, profit_factor=win / loss if loss > 0 else np.nan, total_r=r.sum(),
                max_dd_r=max_drawdown_r(r), avg_bars=df["bars_held"].mean(),
                settled_by_rule=(df["settled"] == "rule").mean())


def equity(df):
    """1% of current equity risked per trade, all markets in one account, booked at exit."""
    ev = []
    for i, tr in enumerate(df.itertuples()):
        ev.append((pd.Timestamp(tr.entry_day), 0, i, tr.r))
        ev.append((pd.Timestamp(tr.exit_day), 1, i, tr.r))
    ev.sort()
    eq, stake, curve = 1.0, {}, []
    for day, kind, i, r in ev:
        if kind == 0:
            stake[i] = RISK * eq
        else:
            eq += stake.pop(i) * r
            curve.append((day, eq))
    s = pd.Series([e for _, e in curve], index=[d for d, _ in curve]).groupby(level=0).last()
    return s


def equity_stats(s):
    if s.empty:
        return dict(cagr=np.nan, max_dd=np.nan, final=np.nan)
    peak = np.maximum.accumulate(np.r_[1.0, s.to_numpy()])
    dd = 1 - np.r_[1.0, s.to_numpy()] / peak
    return dict(final=s.iloc[-1], cagr=s.iloc[-1] ** (1 / YEARS) - 1, max_dd=dd.max())


def data_summary():
    """What went in: the bars of each market and its typical spread (at the 00:00 UTC daily close)."""
    rows = []
    for sym, (label, cls, _, pip, _) in INSTRUMENTS.items():
        d = load_daily(sym)
        spread = d["ask_close"] - d["bid_close"]
        a = atr(d)
        rows.append(dict(market=label, symbol=sym, asset_class=cls, first_day=d.index[0].date(),
                         trading_from=d.index[TREND_DAYS].date(), last_day=d.index[-1].date(), bars=len(d),
                         median_spread=spread.median(), pip=pip, median_spread_pips=spread.median() / pip,
                         median_spread_pct_atr=100 * (spread / a).median()))
    return pd.DataFrame(rows)


def fmt_table(df, cols, fmts):
    head = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
    rows = []
    for _, r in df.iterrows():
        rows.append("| " + " | ".join(f(r) for f in fmts) + " |")
    return head + "\n".join(rows) + "\n"


def main():
    data = data_summary()
    data.to_csv(os.path.join(RESULTS_DIR, "data_summary.csv"), index=False, float_format="%.6g")
    t = pd.read_csv(os.path.join(RESULTS_DIR, "trades.csv.gz"), parse_dates=["signal_day", "entry_day", "exit_day"])
    t = t[(t["entry_day"] >= START) & (t["entry_day"] <= END)]
    daily, hourly = t[~t["hourly"]], t[t["hourly"]]

    def pick(df, vk, rule, costs=True):
        return df[(df["variant"] == vk) & (df["rule"] == rule) & (df["costs"] == costs)]

    # every variant with same-day cases replayed on hourly bars where downloaded; leftovers counted
    # the worse way. The daily-bars-only runs give the bounds when no hourly data is used at all.
    main_runs = hourly[(hourly["rule"] == "cons") & hourly["costs"]]
    rows = []
    for vk, v in VARIANTS.items():
        g = main_runs[main_runs["variant"] == vk]
        s = stats(g)
        s.update(equity_stats(equity(g)))
        s.update(variant=vk, name=v["name"], avg_r_hourly_opt=pick(hourly, vk, "opt")["r"].mean(),
                 avg_r_daily_cons=pick(daily, vk, "cons")["r"].mean(),
                 avg_r_daily_opt=pick(daily, vk, "opt")["r"].mean(),
                 avg_r_no_costs=pick(hourly, vk, "cons", False)["r"].mean())
        s["cost_per_trade"] = s["avg_r_no_costs"] - s["avg_r"]
        rows.append(s)
    summ = pd.DataFrame(rows)
    summ.to_csv(os.path.join(RESULTS_DIR, "summary_variants.csv"), index=False, float_format="%.4f")

    hyb = hourly[(hourly["variant"] == "V4") & (hourly["rule"] == "cons") & hourly["costs"]].copy()
    hyb["period"] = np.where(hyb["entry_day"] < SPLIT, "2008–2016", "2017–2026")
    hyb["side"] = np.where(hyb["dir"] > 0, "long", "short")
    hyb["touch_group"] = np.where(hyb["touches"] >= 3, "3+ touches", "2 touches")
    hyb["flip_group"] = np.where(hyb["flipped"].astype(bool), "flipped level", "same-side level")
    hyb["round_group"] = np.where(hyb["round_number"].astype(bool), "round number", "not round")
    parts = []
    for col in ("period", "asset_class", "side", "touch_group", "flip_group", "round_group", "reason"):
        for key, g in hyb.groupby(col):
            parts.append(dict(split=col, group=key, **stats(g)))
    brk = pd.DataFrame(parts)
    brk.to_csv(os.path.join(RESULTS_DIR, "hybrid_breakdown.csv"), index=False, float_format="%.4f")
    by_mkt = pd.DataFrame([dict(market=k, **stats(g)) for k, g in hyb.groupby("market")]).sort_values("avg_r")
    by_mkt.to_csv(os.path.join(RESULTS_DIR, "hybrid_by_market.csv"), index=False, float_format="%.4f")

    curves = {vk: equity(main_runs[main_runs["variant"] == vk]) for vk in VARIANTS}
    eq = pd.DataFrame(curves).sort_index().ffill().fillna(1.0)
    eq.index.name = "day"
    eq.to_csv(os.path.join(RESULTS_DIR, "equity_daily.csv"), float_format="%.6f")

    pct = lambda c: (lambda r: f"{100 * r[c]:.0f}%")
    num = lambda c, d=2: (lambda r: f"{r[c]:+.{d}f}" if pd.notna(r[c]) else "–")
    out = ["## Data\n",
           fmt_table(data, ["Market", "Dukascopy symbol", "Bars", "From", "Trading from", "To",
                            "Median spread (pips/points)", "Median spread (% of ATR)"],
                     [lambda r: r["market"], lambda r: r["symbol"], lambda r: f"{r['bars']:,}",
                      lambda r: str(r["first_day"]), lambda r: str(r["trading_from"]), lambda r: str(r["last_day"]),
                      lambda r: f"{r['median_spread_pips']:.1f}", lambda r: f"{r['median_spread_pct_atr']:.2f}%"]),
           "\n## Variants (same-day cases replayed on hourly bars; any left over counted the worse way)\n",
           fmt_table(summ, ["Variant", "Trades", "Per year", "Win rate", "Avg R", "95% CI", "p(avg ≤ 0)",
                            "Profit factor", "Max DD (R)", "CAGR at 1%", "Max DD at 1%", "Settled by rule"],
                     [lambda r: f"{r['variant']} {r['name']}", lambda r: f"{r['trades']:.0f}",
                      lambda r: f"{r['per_year']:.1f}", pct("win_rate"), num("avg_r", 3),
                      lambda r: f"{r['ci_lo']:+.2f} to {r['ci_hi']:+.2f}", lambda r: f"{r['p_le_zero']:.3f}",
                      lambda r: f"{r['profit_factor']:.2f}", lambda r: f"{r['max_dd_r']:.1f}",
                      lambda r: f"{100 * r['cagr']:+.1f}%", lambda r: f"{100 * r['max_dd']:.1f}%",
                      pct("settled_by_rule")]),
           "\n## Average R under each way of settling same-day cases, and the cost of trading\n",
           fmt_table(summ, ["Variant", "Daily bars, worse way", "Daily bars, better way", "Hourly, worse way",
                            "Hourly, better way", "Hourly, before costs", "Spread + commission per trade"],
                     [lambda r: f"{r['variant']} {r['name']}", num("avg_r_daily_cons", 3), num("avg_r_daily_opt", 3),
                      num("avg_r", 3), num("avg_r_hourly_opt", 3), num("avg_r_no_costs", 3),
                      lambda r: f"{r['cost_per_trade']:.3f}R"]),
           "\n## Hybrid (V4) breakdown (hourly-settled, cons)\n",
           fmt_table(brk, ["Split", "Group", "Trades", "Win rate", "Avg R", "95% CI", "Profit factor"],
                     [lambda r: r["split"], lambda r: str(r["group"]), lambda r: f"{r['trades']:.0f}", pct("win_rate"),
                      num("avg_r", 3), lambda r: f"{r['ci_lo']:+.2f} to {r['ci_hi']:+.2f}",
                      lambda r: f"{r['profit_factor']:.2f}" if pd.notna(r["profit_factor"]) else "–"]),
           "\n## Hybrid (V4) by market\n",
           fmt_table(by_mkt, ["Market", "Trades", "Win rate", "Avg R", "Total R"],
                     [lambda r: r["market"], lambda r: f"{r['trades']:.0f}", pct("win_rate"), num("avg_r", 3),
                      num("total_r", 1)])]
    open(os.path.join(RESULTS_DIR, "report_tables.md"), "w").write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
