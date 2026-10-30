"""Ways to raise R per trade: chart-pattern filters on the entry, and trade-management changes.

Starting point: the best configuration so far (London 07:00-13:00 UK, the trader's risk rules,
15M trend filter). Every change is run inside the backtest on the common basis of compare_results.py
(every weekday, 1.5-pt costs, 1% risk compounding), so a skipped trade frees the slot for the next one.

Pattern filters (thresholds are round numbers near the Mar-Aug terciles in trade_features.py):
  no_spike_leg        skip legs that moved faster than 2.5 x ATR(15M) per hour (news-type spikes)
  no_slow_pullback    skip pullbacks that have already taken >= 0.8x as long as the leg
  wicky_pullback      only take pullbacks whose 5m candles are wick-heavy (bodies < 50% of range)
  no_counter_fvgs     skip pullbacks that left 2+ counter-direction 5m FVGs (strong counter move)
The same patterns are also checked on the trader's own journal trades, whose outcomes do not come from
this backtest at all.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import ROOT, RESULTS_DIR, load_journal, load_prices, resample  # noqa: E402
from compare_results import PERIOD, RISK_RULES, rules, score  # noqa: E402
from replicate_strategy import Market, Rules, backtest, in_window  # noqa: E402

BEST = rules(**RISK_RULES, trend_filter="15m")


class Patterns:
    """Entry-time chart features from closed candles only."""

    def __init__(self, mk, m1):
        self.mk = mk
        m5 = resample(m1, "5min")
        self.t5 = m5.index
        self.o5, self.h5, self.l5, self.c5 = (m5[k].values for k in ("open", "high", "low", "close"))

    def features(self, d, i, s0, a, ext, j_ext, px):
        mk, s = self.mk, (1 if d == "long" else -1)
        atr = mk.atr15[i]
        leg_min = max((mk.t[j_ext] - mk.t[s0]).total_seconds() / 60, 1)
        pb_min = max((mk.t[i] - mk.t[j_ext]).total_seconds() / 60, 1)
        a5 = self.t5.searchsorted(mk.t[j_ext].floor("5min"))
        b5 = self.t5.searchsorted(mk.t[i] - pd.Timedelta(minutes=5), side="right")  # 5m candles closed by entry
        o, h, lo, c = self.o5[a5:b5], self.h5[a5:b5], self.l5[a5:b5], self.c5[a5:b5]
        rng = (h - lo).sum()
        body_ratio = np.abs(c - o).sum() / rng if len(o) and rng > 0 else np.nan
        counter_fvgs = sum((lo[j] > h[j - 2]) if s == -1 else (h[j] < lo[j - 2]) for j in range(2, len(o)))
        return {"leg_speed": (abs(ext - a) / atr) / (leg_min / 60), "pb_vs_leg_time": pb_min / leg_min,
                "body_ratio": body_ratio, "counter_fvgs": counter_fvgs}

    def make_filter(self, max_leg_speed=None, max_pb_time=None, max_body_ratio=None, max_counter_fvgs=None):
        def accept(mk, d, i, k, a, ext, j_ext, px):
            f = self.features(d, i, mk.piv[d]["start"][k], a, ext, j_ext, px)
            if max_leg_speed is not None and f["leg_speed"] >= max_leg_speed:
                return False
            if max_pb_time is not None and f["pb_vs_leg_time"] >= max_pb_time:
                return False
            if max_body_ratio is not None and not (f["body_ratio"] < max_body_ratio):
                return False
            if max_counter_fvgs is not None and f["counter_fvgs"] > max_counter_fvgs:
                return False
            return True
        return accept


FILTERS = {
    "no_spike_leg": dict(max_leg_speed=2.5),
    "no_slow_pullback": dict(max_pb_time=0.8),
    "wicky_pullback": dict(max_body_ratio=0.5),
    "no_counter_fvgs": dict(max_counter_fvgs=1),
}


def journal_check(mk, pat, journal_path):
    """Do the same patterns separate the trader's own winners and losers? (London trades, score 3R/0/-1R)"""
    j = load_journal(journal_path)
    j = j[in_window(j.entry_et, BEST)]
    ctx = pd.read_csv(os.path.join(ROOT, "trade_context.csv")).set_index("trade_id")
    rows = []
    for tr in j.itertuples():
        c = ctx.loc[tr.trade_id]
        if not isinstance(c.direction, str) or pd.isna(c.fib_anchor_time) or c.fib_match is not True and c.fib_match != "True":
            continue
        loc = lambda t: mk.t.searchsorted(pd.Timestamp(t).tz_localize("America/New_York"))
        f = pat.features(c.direction, loc(c.entry_et), loc(c.fib_anchor_time), c.fib_anchor_price,
                         c.fib_extreme_price, loc(c.fib_extreme_time), c.entry_price_est)
        rows.append({**f, "R": {"Win": 3.0, "BE": 0.0, "Loss": -1.0}[tr.result], "result": tr.result})
    df = pd.DataFrame(rows)
    tests = {"no_spike_leg": df.leg_speed < 2.5, "no_slow_pullback": df.pb_vs_leg_time < 0.8,
             "wicky_pullback": df.body_ratio < 0.5, "no_counter_fvgs": df.counter_fvgs <= 1}
    out = []
    for name, keep in tests.items():
        out.append({"pattern": name, "journal_trades_kept": int(keep.sum()), "R_kept": round(df.R[keep].mean(), 2),
                    "loss_rate_kept": round((df.result[keep] == "Loss").mean(), 3),
                    "journal_trades_skipped": int((~keep).sum()), "R_skipped": round(df.R[~keep].mean(), 2),
                    "loss_rate_skipped": round((df.result[~keep] == "Loss").mean(), 3)})
    return pd.DataFrame(out), len(df)


def main(journal_path):
    m1 = load_prices("m1")
    mk = Market(m1, 2)
    pat = Patterns(mk, m1)
    pd.set_option("display.width", 260)
    pd.set_option("display.max_columns", 20)

    def run(name, r):
        row = score(name, backtest(mk, r, *PERIOD))
        print(f"{name:55s} trades {row['trades']:4d}  R/trade {row['net_R_per_trade']:+.3f}  return {row['total_return_pct']:+6.1f}%  "
              f"DD {row['max_drawdown_pct']:5.1f}%  Mar-Aug {row['Mar-Aug_return_pct']:+6.1f}%  Sep-Oct {row['Sep-Oct_return_pct']:+5.1f}%", flush=True)
        return row

    rows = [{"group": "baseline", **run("best config (baseline)", BEST)}]

    # 1. chart-pattern filters, alone and combined
    combos = {**{k: [k] for k in FILTERS},
              "no_spike_leg + no_slow_pullback": ["no_spike_leg", "no_slow_pullback"],
              "no_spike_leg + no_slow_pullback + no_counter_fvgs": ["no_spike_leg", "no_slow_pullback", "no_counter_fvgs"],
              "no_spike_leg + wicky_pullback": ["no_spike_leg", "wicky_pullback"],
              "all four": list(FILTERS)}
    for name, keys in combos.items():
        kw = {}
        for key in keys:
            kw.update(FILTERS[key])
        rows.append({"group": "entry filter", **run(name, Rules(**{**BEST.__dict__, "entry_filter": pat.make_filter(**kw)}))})

    # 2. trade management on the baseline entries
    for tp in (2.0, 2.5, 3.0, 4.0, 5.0):
        for be in (1.0, 1.5, 2.0, None):
            if be is not None and be >= tp:
                continue
            rows.append({"group": "take profit x break-even",
                         **run(f"TP {tp}R, BE at {be}R" if be else f"TP {tp}R, no BE",
                               Rules(**{**BEST.__dict__, "target_r": tp, "be_at_r": be}))})
    for name, kw in {"TP 4R, at +2R lock +1R": dict(target_r=4.0, be_at_r=2.0, be_lock_r=1.0),
                     "TP 5R, at +2R lock +1R": dict(target_r=5.0, be_at_r=2.0, be_lock_r=1.0),
                     "half off at 2R, rest to 4R (BE)": dict(target_r=4.0, be_at_r=None, partial_at_r=2.0),
                     "half off at 2R, rest to 5R (BE)": dict(target_r=5.0, be_at_r=None, partial_at_r=2.0),
                     "half off at 3R, rest to 5R (BE)": dict(target_r=5.0, be_at_r=None, partial_at_r=3.0)}.items():
        rows.append({"group": "lock / partial", **run(name, Rules(**{**BEST.__dict__, **kw}))})
    for frac in (0.12, 0.17, 0.20):
        rows.append({"group": "stop size", **run(f"stop {frac:.2f} x leg (baseline 0.14)", Rules(**{**BEST.__dict__, "stop_leg_frac": frac}))})
    rows.append({"group": "entry level", **run("0.79 level only (deeper entry)", Rules(**{**BEST.__dict__, "fib_levels": (0.79,)}))})

    # 3. is each threshold a plateau or a knife-edge?
    for spd in (2.0, 3.0):
        rows.append({"group": "threshold check", **run(f"no_spike_leg at {spd} ATR/h (chosen 2.5)",
                     Rules(**{**BEST.__dict__, "entry_filter": pat.make_filter(max_leg_speed=spd)}))})
    for frac in (0.16, 0.18):
        rows.append({"group": "threshold check", **run(f"stop {frac:.2f} x leg", Rules(**{**BEST.__dict__, "stop_leg_frac": frac}))})

    # 4. the robust changes combined
    spike = pat.make_filter(max_leg_speed=2.5)
    spike_wicky = pat.make_filter(max_leg_speed=2.5, max_body_ratio=0.5)
    for name, kw in {
            "A no_spike_leg + B TP 4R/BE 2R": dict(entry_filter=spike, target_r=4.0),
            "A no_spike_leg + C stop 0.17": dict(entry_filter=spike, stop_leg_frac=0.17),
            "B TP 4R/BE 2R + C stop 0.17": dict(target_r=4.0, stop_leg_frac=0.17),
            "A + B + C": dict(entry_filter=spike, target_r=4.0, stop_leg_frac=0.17),
            "A + B + C + wicky pullback": dict(entry_filter=spike_wicky, target_r=4.0, stop_leg_frac=0.17)}.items():
        rows.append({"group": "combined", **run(name, Rules(**{**BEST.__dict__, **kw}))})

    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS_DIR, "rr_improvements.csv"), index=False)

    jc, n = journal_check(mk, pat, journal_path)
    jc.to_csv(os.path.join(RESULTS_DIR, "rr_patterns_in_journal.csv"), index=False)
    print(f"\nSame patterns in the journal ({n} London trades with a reconstructed leg, scored 3R/0/-1R):")
    print(jc.to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
