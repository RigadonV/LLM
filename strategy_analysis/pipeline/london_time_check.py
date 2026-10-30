"""Are the journal's times New York clock time or London clock time? And what does London-only trading look like?

Part 1 re-reads the logged times in several time zones (proper DST handling) and repeats the whole
chain for each reading: price-path direction fit, fib-leg match (against a chance baseline) and how
many journal trades the final backtest rules reproduce.

Part 2 (New York reading) splits the journal and the backtest by session window, shown in both
New York and UK clock time.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import infer_direction as inf  # noqa: E402
from common import ET, LEG_MIN_ATR, LEG_PIVOT_N, RESULTS_DIR, load_journal, load_prices  # noqa: E402
from replicate_strategy import FINAL, Market, Rules, backtest, match  # noqa: E402
from structure import Structure  # noqa: E402

ZONES = {
    "New York": "America/New_York",
    "London (UK)": "Europe/London",
    "UTC": "UTC",
    "Central Europe": "Europe/Berlin",
    "South Africa": "Africa/Johannesburg",
}
CLASS_R = {"Win": 3.0, "BE": 0.0, "Loss": -1.0}  # the checklist's own scoring


def reinterpret(journal, zone):
    """Treat the logged wall-clock times as `zone` time and express them in New York time."""
    j = journal.copy()
    naive = j["entry_et"].dt.tz_localize(None)
    j["entry_et"] = naive.dt.tz_localize(zone, ambiguous="NaT", nonexistent="shift_forward").dt.tz_convert(ET)
    j["exit_et"] = j["entry_et"] + pd.to_timedelta(j["minutes"], unit="m")
    return j


def trading_day(ts):
    """CME convention: the session that opens at 18:00 ET belongs to the next calendar day."""
    return (ts + pd.Timedelta(hours=6)).dt.normalize()


def clock(hours):
    """Hours after midnight of the trading day as HH:MM, flagging times on the previous evening."""
    mins = int(round(hours * 60))
    return f"{(mins // 60) % 24:02d}:{mins % 60:02d}" + (" prev. day" if mins < 0 else "")


def fib_match_rate(st, trades, rng, shuffle=False):
    hits = 0
    for tr in trades.itertuples():
        t0, entry = tr.entry_et, tr.entry
        if shuffle:  # chance baseline: a random minute within 3 hours, priced at that minute's close
            t0 = t0 + pd.Timedelta(minutes=int(rng.integers(-180, 181)))
            bar = st.m1.loc[t0: t0 + pd.Timedelta(minutes=2)]
            if not len(bar):
                continue
            t0, entry = bar.index[0], bar["close"].iloc[0]
        recent, _ = st.leg_for_entry(t0, tr.direction, entry)
        hits += bool(recent) and abs(recent["ratio"] - tr.fib_level) <= 0.05
    return hits / len(trades) if len(trades) else np.nan


def part1(journal, m1, mk, st):
    rng = np.random.default_rng(11)
    rows = []
    for name, zone in ZONES.items():
        j = reinterpret(journal, zone)
        stage1 = inf.run(j, m1, 0)
        fits = stage1["fit"].isin(["long", "short", "long*", "short*", "ambiguous"])
        has_data = stage1["fit"] != "no_data"
        res = inf.fib_stage(m1, j, stage1)
        known = res[res.direction.isin(["long", "short"])].merge(j[["trade_id", "entry_et", "fib_level"]], on="trade_id")
        known = known.assign(entry=known.entry_price_path)
        clear = known[known.direction_confidence == "high"]
        # backtest window that covers this reading's entry times (hours after midnight of the trading day)
        h = (j.entry_et - trading_day(j.entry_et)).dt.total_seconds() / 3600
        window = (np.floor(h.min() * 2) / 2, np.ceil(h.max() * 2) / 2)
        rules = Rules(**{**FINAL.__dict__, "window": window, "window_tz": "", "exit_by": window[1] + 2.5})
        bt = backtest(mk, rules, journal.date.min() - pd.Timedelta(days=1), journal.date.max())
        jt, bt = match(j, bt, res[["trade_id", "direction"]])
        days = set(trading_day(j.entry_et))
        on_days = bt[trading_day(bt.entry_et).isin(days)]
        uk = j.entry_et.dt.tz_convert("Europe/London")
        uk_h = uk.dt.hour + uk.dt.minute / 60
        rows.append({
            "reading": name,
            "entries_NY_clock": f"{clock(h.min())}-{clock(h.max())}",
            "entries_UK_clock": f"{uk.dt.strftime('%H:%M').min()}-{uk.dt.strftime('%H:%M').max()}",
            "in_London_session_08-16:30_UK": round(((uk_h >= 8) & (uk_h < 16.5)).mean(), 3),
            "price_path_fit": round(fits[has_data].mean(), 3),
            "direction_found": int(len(known)),
            "fib_match_clear_dir": round(fib_match_rate(st, clear, rng), 3),
            "fib_match_chance": round(fib_match_rate(st, clear, rng, shuffle=True), 3),
            "backtest_recall": round(jt.matched.mean(), 3),
            "backtest_precision": round(on_days.matched_trade_id.notna().mean(), 3),
        })
        print(rows[-1], flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RESULTS_DIR, "timezone_reading_check.csv"), index=False)
    return out


# (label, start, end, clock). New York windows match how the journal was logged; UK = NY + 5h
# (+4h from 8 to 28 March 2026). The last row is the go-forward London-only rule on the UK clock.
WINDOWS = [
    ("02:00-05:00 NY = 07:00-10:00 UK (London kill zone)", 2.0, 5.0, ""),
    ("05:00-08:00 NY = 10:00-13:00 UK (rest of London morning)", 5.0, 8.0, ""),
    ("08:00-09:30 NY = 13:00-14:30 UK (NY pre-open, 08:30 news)", 8.0, 9.5, ""),
    ("As journaled: 02:00-09:30 NY", 2.0, 9.5, ""),
    ("London only: 07:00-13:00 UK clock", 7.0, 13.0, "Europe/London"),
]


def part2(journal, mk):
    inferred = pd.read_csv(os.path.join(RESULTS_DIR, "direction_inference.csv"))
    rows = []
    for label, a, b, tz in WINDOWS:
        local = journal.entry_et.dt.tz_convert(tz) if tz else journal.entry_et
        h = local.dt.hour + local.dt.minute / 60
        sub = journal[(h >= a) & (h < b)]
        rules = FINAL if tz else Rules(**{**FINAL.__dict__, "window": (a, b), "window_tz": "", "exit_by": 12.0})
        bt = backtest(mk, rules, journal.date.min(), journal.date.max())
        jt, bt = match(sub, bt, inferred)
        logged = set(journal.entry_et.dt.normalize())
        on_days = bt[bt.entry_et.dt.normalize().isin(logged)]
        rows.append({
            "window": label,
            "journal_trades": len(sub),
            "journal_loss_rate": round((sub.result == "Loss").mean(), 3),
            "journal_R_per_trade (3R/0/-1)": round(sub.result.map(CLASS_R).mean(), 2),
            "backtest_trades": len(on_days),
            "backtest_recall": round(jt.matched.mean(), 3),
            "backtest_precision": round(on_days.matched_trade_id.notna().mean(), 3),
            "backtest_loss_rate": round((on_days.outcome == "Loss").mean(), 3),
            "backtest_R_per_trade": round(on_days.r.mean(), 3),
        })
        print(rows[-1], flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RESULTS_DIR, "london_session_windows.csv"), index=False)
    return out


def main(journal_path):
    journal = load_journal(journal_path)
    m1 = load_prices("m1")
    mk = Market(m1, FINAL.pivot_n)
    st = Structure(m1, LEG_PIVOT_N, LEG_MIN_ATR)
    pd.set_option("display.width", 250)
    print(part1(journal, m1, mk, st).to_string(index=False))
    print(part2(journal, mk).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
