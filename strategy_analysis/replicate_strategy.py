"""Validation backtest for the reconstructed "Model 2 - London" NQ strategy (see STRATEGY.md).

Rules (all times New York):
  1. Structure: 15-minute candles; swing points are 2-left/2-right fractals, usable once confirmed.
  2. Leg: for longs, the most recent confirmed 15M swing LOW that price has not traded below, and the
     highest high made since it (shorts: mirror image). Fib 1.0 = swing point, 0.0 = extreme.
  3. Filters (refinements): leg >= 2 x ATR(14, 15M) and the fib level still untouched since the
     leg extreme. (Break-of-structure and an FVG-based level choice were tested and dropped.)
  4. Entry: limit orders at the 0.705 and 0.79 retracements of that leg, live 02:00-09:30; the first
     untouched level price trades into (from the correct side) is filled, the other is cancelled.
  5. Stop: 14% of the leg beyond the entry (=~fib 0.845 for 0.705 entries, ~0.93 for 0.79 entries).
  6. Exit: take profit at a fixed R multiple (or the leg extreme), stop moved to break-even once
     price reaches +BE_AT R; flat by EXIT_BY.
  7. One position at a time, each leg traded once, max trades per day.
  Optional, from the trader's own checklist: 2 losses = done for the day, SL < 50 pts, trend filter
  (15M or 1H EMA50 trend), and a 15M/30M/1H OB or FVG required at the entry.

Data: Dukascopy USATECHIDXUSD (Nasdaq-100 CFD) 1-minute bid candles as a proxy for NQ futures.
Run `python pipeline/fetch_data.py` first if data/ is empty.

Usage:
  python replicate_strategy.py JOURNAL.xlsx                       # all rounds -> results/validation_variants.csv
  python replicate_strategy.py JOURNAL.xlsx --variant refine2_both_levels
  python replicate_strategy.py JOURNAL.xlsx --variant london_only          # 07:00-13:00 UK clock only
"""
import argparse
import os
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline"))
from common import RESULTS_DIR, atr, ema, load_journal, load_prices, pivots, resample  # noqa: E402


@dataclass(frozen=True)
class Rules:
    name: str = "baseline"
    pivot_n: int = 2               # fractal strength for 15M swing points
    lookback_h: float = 30         # how far back a swing anchor may be
    fib_levels: tuple = (0.79,)    # retracement level(s) that get a limit order
    window: tuple = (2.0, 9.5)     # hours during which orders are live (clock of window_tz)
    window_tz: str = ""            # "" = New York clock; e.g. "Europe/London" for a UK-clock session
    stop_leg_frac: float = 0.14    # stop distance as a fraction of the leg
    target_r: float = 3.0          # take profit in R
    be_at_r: float = 2.0           # move stop to entry after this much open profit (None = never)
    min_leg_atr: float = 1.5       # minimum leg size in 15M ATRs
    require_bos: bool = False      # leg must break the last opposite 15M swing before the anchor
    fresh_level: bool = False      # the level must not have been touched since the leg extreme
    level_choice: str = "fixed"    # "fixed": use fib_levels; "fvg": 0.705 if a 15M FVG covers it, else 0.79
    target_mode: str = "r"         # "r": target_r x R; "fib0": the leg extreme, but at least min_target_r
    min_target_r: float = 2.0
    max_trades_day: int = 5
    exit_by: float = 12.0          # flat by this hour (window_tz clock) if neither stop nor target is hit
    # options mirroring the trader's own Model 2 checklist (0 / "none" / False = off)
    max_losses_day: int = 0        # "2 losses = done for the day"
    max_stop_pts: float = 0.0      # "SL < 50pts": skip legs whose stop would be wider
    trend_filter: str = "none"     # "15m" / "1h": EMA50 trend of the last closed bar must agree
    require_zone: bool = False     # "Either a HTF OB/FVG": a 15m/30m/1h OB or FVG formed in the leg covers the entry


BASE = Rules()
# round 1: skip small legs and levels price has already traded through since the leg extreme
REFINE1 = Rules(name="refine1_fresh_level_bigger_legs", fresh_level=True, min_leg_atr=2.0)
# round 2: rest orders at both OTE levels; the first untouched level price reaches gets filled
REFINE2 = Rules(name="refine2_both_levels", fresh_level=True, min_leg_atr=2.0, fib_levels=(0.705, 0.79))
FINAL = REFINE2
VARIANTS = {r.name: r for r in (BASE, REFINE1, REFINE2)}
# exit alternatives evaluated on the final entry rules
EXIT_VARIANTS = {r.name: r for r in (
    Rules(**{**FINAL.__dict__, "name": "exit_2R_noBE", "target_r": 2.0, "be_at_r": None}),
    Rules(**{**FINAL.__dict__, "name": "exit_3R_BE_at_2R"}),
    Rules(**{**FINAL.__dict__, "name": "exit_3R_noBE", "be_at_r": None}),
    Rules(**{**FINAL.__dict__, "name": "exit_fib0_min2R", "target_mode": "fib0", "be_at_r": None}),
)}
# London session only, defined on the UK clock: 07:00-13:00 UK (= 02:00-08:00 New York, except in the
# weeks when only one of the two countries is on summer time)
LONDON_ONLY = Rules(**{**FINAL.__dict__, "name": "london_only", "window": (7.0, 13.0),
                       "window_tz": "Europe/London", "exit_by": 17.0})
# the trader's stated checklist (TP 3R and BE at 2R are already the final rules' exits)
CHECKLIST_RISK = Rules(**{**FINAL.__dict__, "name": "checklist_risk", "max_losses_day": 2, "max_stop_pts": 50.0})
CHECKLIST_VARIANTS = {r.name: r for r in (
    CHECKLIST_RISK,
    Rules(**{**CHECKLIST_RISK.__dict__, "name": "checklist_risk_trend15m", "trend_filter": "15m"}),
    Rules(**{**CHECKLIST_RISK.__dict__, "name": "checklist_risk_trend1h", "trend_filter": "1h"}),
    Rules(**{**CHECKLIST_RISK.__dict__, "name": "checklist_risk_zone", "require_zone": True}),
    Rules(**{**CHECKLIST_RISK.__dict__, "name": "checklist_risk_trend15m_zone", "trend_filter": "15m", "require_zone": True}),
)}


class Market:
    """1m arrays + 15M pivots for fast minute-by-minute leg queries."""

    def __init__(self, m1, pivot_n):
        self.m1 = m1
        self.t = m1.index
        self.o, self.h, self.l, self.c = (m1[k].values for k in ("open", "high", "low", "close"))
        m15 = resample(m1, "15min")
        self.m15 = m15
        # ATR of the last completed 15M bar, aligned to every minute
        self.atr15 = atr(m15).shift(1).reindex(m1.index, method="ffill").values
        ph, pl = pivots(m15, pivot_n, pivot_n)
        delay = pd.Timedelta(minutes=15 * (pivot_n + 1))
        pos = lambda ts: self.t.searchsorted(ts)
        self.piv = {}
        for d, mask, col in (("long", pl, "low"), ("short", ph, "high")):
            times = m15.index[mask.values]
            self.piv[d] = {
                "start": np.array([pos(x) for x in times]),                  # 1m index of pivot bar start
                "conf": np.array([pos(x + delay) for x in times]),            # 1m index when it is known
                "price": m15.loc[times, col].values,
                "time": times,
            }
        # the swing on the other side, used for the break-of-structure check
        self.opp = {"long": self.piv["short"], "short": self.piv["long"]}
        # 15M fair value gaps: (1m index when the 3rd candle closes, zone low, zone high)
        hi15, lo15 = m15["high"].values, m15["low"].values
        self.fvg = {"long": [], "short": []}
        for b in range(2, len(m15)):
            formed = pos(m15.index[b] + pd.Timedelta(minutes=15))
            if lo15[b] > hi15[b - 2]:
                self.fvg["long"].append((formed, hi15[b - 2], lo15[b]))
            if hi15[b] < lo15[b - 2]:
                self.fvg["short"].append((formed, hi15[b], lo15[b - 2]))
        self.fvg = {d: np.array(v) for d, v in self.fvg.items()}
        # EMA50 trend of the last closed 15M / 1H bar, per minute: +1 up, -1 down, 0 mixed
        self.trend = {}
        for tf, bars in (("15m", m15), ("1h", resample(m1, "1h"))):
            e = ema(bars["close"], 50)
            slope = e - e.shift(4)
            tr = np.where((bars["close"] > e) & (slope > 0), 1, np.where((bars["close"] < e) & (slope < 0), -1, 0))
            self.trend[tf] = pd.Series(tr, index=bars.index).shift(1).reindex(m1.index, method="ffill").fillna(0).values
        # 15m/30m/1h FVGs and order blocks: (1m index when known, zone low, zone high)
        zones = {"long": [], "short": []}
        for rule in ("15min", "30min", "1h"):
            bars = m15 if rule == "15min" else resample(m1, rule)
            o_, h_, l_, c_ = (bars[k].values for k in ("open", "high", "low", "close"))
            step = pd.Timedelta(rule)
            for b in range(1, len(bars)):
                known = pos(bars.index[b] + step)
                if b >= 2 and l_[b] > h_[b - 2]:
                    zones["long"].append((known, h_[b - 2], l_[b]))
                if b >= 2 and h_[b] < l_[b - 2]:
                    zones["short"].append((known, h_[b], l_[b - 2]))
                if c_[b - 1] < o_[b - 1] and c_[b] > h_[b - 1]:
                    zones["long"].append((known, l_[b - 1], h_[b - 1]))
                if c_[b - 1] > o_[b - 1] and c_[b] < l_[b - 1]:
                    zones["short"].append((known, l_[b - 1], h_[b - 1]))
        self.zones = {d: np.array(v) for d, v in zones.items()}

    def zone_covers(self, d, start_i, i, price, tol=2.0):
        """Is there a 15m/30m/1h OB or FVG in direction d, known by i and formed since start_i, containing price?"""
        z = self.zones[d]
        m = (z[:, 0] >= start_i) & (z[:, 0] <= i) & (z[:, 1] - tol <= price) & (z[:, 2] + tol >= price)
        return bool(m.any())

    def fvg_covers(self, d, start_i, i, price, tol=2.0):
        """Is there a 15M FVG in direction d, formed inside [start_i, i), whose zone contains price?"""
        f = self.fvg[d]
        m = (f[:, 0] >= start_i) & (f[:, 0] <= i) & (f[:, 1] - tol <= price) & (f[:, 2] + tol >= price)
        return bool(m.any())

    def leg(self, i, d, lookback_bars):
        """Most recent valid leg known at 1m index i (using bars < i)."""
        p = self.piv[d]
        k = np.searchsorted(p["conf"], i, side="right") - 1
        # pivots are sorted by time; conf is monotonic in time as well
        while k >= 0 and p["start"][k] >= i - lookback_bars:
            a, s0 = p["price"][k], p["start"][k]
            if s0 < i:
                if d == "long":
                    seg_l = self.l[s0:i]
                    if seg_l.min() >= a:
                        j = s0 + int(np.argmax(self.h[s0:i]))
                        return k, a, self.h[j], j
                else:
                    seg_h = self.h[s0:i]
                    if seg_h.max() <= a:
                        j = s0 + int(np.argmin(self.l[s0:i]))
                        return k, a, self.l[j], j
            k -= 1
        return None

    def broke_structure(self, d, k, ext):
        p, o = self.piv[d], self.opp[d]
        prior = np.where((o["start"] < p["start"][k]) & (o["start"] >= p["start"][k] - 24 * 60))[0]
        if len(prior) == 0:
            return False
        lvl = o["price"][prior[-1]]
        return ext > lvl if d == "long" else ext < lvl


def simulate_exit(mk, i_fill, d, entry, stop, rules, day_end_i, leg_extreme):
    """Walk 1m bars after the fill. Returns (exit_index, exit_price, R multiple, outcome)."""
    s = 1 if d == "long" else -1
    r = abs(entry - stop)
    tgt = entry + s * rules.target_r * r
    if rules.target_mode == "fib0":
        tgt = leg_extreme if s * (leg_extreme - entry) >= rules.min_target_r * r else entry + s * rules.min_target_r * r
    cur_stop = stop
    be_done = False
    # fill bar: only count the stop if the bar *closes* beyond it (intrabar order unknown)
    if s * (mk.c[i_fill] - stop) < 0:
        return i_fill, stop, -1.0, "Loss"
    for i in range(i_fill + 1, day_end_i):
        hit_stop = mk.l[i] <= cur_stop if s == 1 else mk.h[i] >= cur_stop
        hit_tgt = mk.h[i] >= tgt if s == 1 else mk.l[i] <= tgt
        if hit_stop:  # conservative: stop before target when both are inside one bar
            res = 0.0 if be_done else -1.0
            return i, cur_stop, res, "BE" if be_done else "Loss"
        if hit_tgt:
            return i, tgt, round(s * (tgt - entry) / r, 2), "Win"
        if rules.be_at_r is not None and not be_done:
            fav = (mk.h[i] - entry) if s == 1 else (entry - mk.l[i])
            if fav >= rules.be_at_r * r:
                cur_stop, be_done = entry, True
    last = day_end_i - 1
    return last, mk.c[last], s * (mk.c[last] - entry) / r, "Time"


def backtest(mk, rules, start, end):
    days = pd.date_range(start, end, freq="D", tz=mk.t.tz)
    lookback_bars = int(rules.lookback_h * 60)
    trades = []
    for day in days:
        if day.weekday() >= 5:
            continue
        base = pd.Timestamp(day.date()).tz_localize(rules.window_tz) if rules.window_tz else day
        i0 = mk.t.searchsorted(base + pd.Timedelta(hours=rules.window[0]))
        i1 = mk.t.searchsorted(base + pd.Timedelta(hours=rules.window[1]))
        iend = mk.t.searchsorted(base + pd.Timedelta(hours=rules.exit_by))
        if i1 - i0 < 60:
            continue
        used_legs, n_day, losses, i = set(), 0, 0, i0
        while i < i1 and n_day < rules.max_trades_day and not (rules.max_losses_day and losses >= rules.max_losses_day):
            fill = None
            for d in ("long", "short"):
                lg = mk.leg(i, d, lookback_bars)
                if lg is None:
                    continue
                k, a, ext, j_ext = lg
                key = (d, k)
                if key in used_legs or ext == a:
                    continue
                size = abs(ext - a)
                atr15 = mk.atr15[i]
                if rules.min_leg_atr and (np.isnan(atr15) or size < rules.min_leg_atr * atr15):
                    continue
                if rules.require_bos and not mk.broke_structure(d, k, ext):
                    continue
                if rules.max_stop_pts and rules.stop_leg_frac * size > rules.max_stop_pts:
                    continue
                if rules.trend_filter != "none" and mk.trend[rules.trend_filter][i] != (1 if d == "long" else -1):
                    continue
                levels = sorted(rules.fib_levels)
                if rules.level_choice == "fvg":
                    p705 = ext - 0.705 * (ext - a)
                    levels = [0.705] if mk.fvg_covers(d, mk.piv[d]["start"][k], i, p705) else [0.79]
                for f in levels:
                    px = ext - f * (ext - a)
                    prev_close = mk.c[i - 1]
                    if rules.fresh_level and j_ext + 1 < i:
                        seg = slice(j_ext + 1, i)
                        if (mk.l[seg] <= px).any() if d == "long" else (mk.h[seg] >= px).any():
                            continue
                    if rules.require_zone and not mk.zone_covers(d, mk.piv[d]["start"][k], i, px):
                        continue
                    if d == "long" and prev_close > px and mk.l[i] <= px:
                        fill = (d, f, px, k, a, ext, size, j_ext)
                    elif d == "short" and prev_close < px and mk.h[i] >= px:
                        fill = (d, f, px, k, a, ext, size, j_ext)
                    if fill:
                        break
                if fill:
                    break
            if not fill:
                i += 1
                continue
            d, f, px, k, a, ext, size, j_ext = fill
            s = 1 if d == "long" else -1
            stop = px - s * rules.stop_leg_frac * size
            xi, xpx, r_mult, outcome = simulate_exit(mk, i, d, px, stop, rules, iend, ext)
            seg = slice(j_ext + 1, i)
            touched = (mk.l[seg] <= px).any() if d == "long" else (mk.h[seg] >= px).any()
            trades.append({
                "entry_et": mk.t[i], "exit_et": mk.t[xi], "direction": d, "fib_level": f, "entry": round(px, 2),
                "stop": round(stop, 2), "exit": round(xpx, 2), "r": round(r_mult, 2), "outcome": outcome,
                "leg_anchor_time": mk.piv[d]["time"][k], "leg_anchor": round(a, 2), "leg_extreme": round(ext, 2),
                "leg_size": round(size, 1), "minutes": (mk.t[xi] - mk.t[i]).total_seconds() / 60,
                # descriptive features, used to study which generated trades the trader skipped
                "hour": mk.t[i].hour, "leg_atr": round(size / mk.atr15[i], 2),
                "leg_minutes": (mk.t[j_ext] - mk.piv[d]["time"][k]).total_seconds() / 60,
                "mins_since_extreme": (mk.t[i] - mk.t[j_ext]).total_seconds() / 60,
                "bos": mk.broke_structure(d, k, ext), "nth_today": n_day + 1, "level_touched_before": bool(touched),
            })
            used_legs.add((d, k))
            n_day += 1
            losses += outcome == "Loss"
            i = xi + 1  # one position at a time
    return pd.DataFrame(trades)


def match(journal, bt, inferred, tol_min=15):
    """Pair journal trades with generated trades: same day, same direction (when known), entry within tol."""
    jt = journal.merge(inferred[["trade_id", "direction"]], on="trade_id", how="left")
    bt = bt.copy()
    bt["matched_trade_id"] = np.nan
    jt["matched"] = False
    jt["match_dt_min"] = np.nan
    jt["bt_outcome"] = None
    for idx, tr in jt.sort_values("entry_et").iterrows():
        cand = bt[(bt.matched_trade_id.isna()) & ((bt.entry_et - tr.entry_et).abs() <= pd.Timedelta(minutes=tol_min))]
        if isinstance(tr.direction, str):
            cand = cand[cand.direction == tr.direction]
        if len(cand):
            b = (cand.entry_et - tr.entry_et).abs().idxmin()
            bt.at[b, "matched_trade_id"] = tr.trade_id
            jt.at[idx, "matched"] = True
            jt.at[idx, "match_dt_min"] = (bt.at[b, "entry_et"] - tr.entry_et).total_seconds() / 60
            jt.at[idx, "bt_outcome"] = bt.at[b, "outcome"]
    return jt, bt


def report(name, jt, bt, covered):
    j = jt[covered]
    n_j, n_m = len(j), int(j.matched.sum())
    # the trader logged nothing on some weekdays (holidays, a late-August gap); judge precision on logged days
    logged_days = set(jt.entry_et.dt.normalize())
    on_logged = bt.entry_et.dt.normalize().isin(logged_days)
    extra_elsewhere = int((~on_logged).sum())
    bt = bt[on_logged]
    n_bt = len(bt)
    extra = int(bt.matched_trade_id.isna().sum())
    agree = j[j.matched]
    same_class = ((agree.result == "Loss") == (agree.bt_outcome == "Loss")).mean() if len(agree) else np.nan
    exp = bt.r.mean() if n_bt else np.nan
    return {
        "variant": name, "journal_trades": n_j, "generated": n_bt, "matched": n_m,
        "recall": round(n_m / n_j, 3) if n_j else np.nan,
        "precision": round((n_bt - extra) / n_bt, 3) if n_bt else np.nan,
        "missed": n_j - n_m, "extra": extra, "extra_on_unlogged_days": extra_elsewhere,
        "loss_vs_nonloss_agreement": round(same_class, 3),
        "bt_win_rate": round((bt.outcome == "Win").mean(), 3) if n_bt else np.nan,
        "bt_loss_rate": round((bt.outcome == "Loss").mean(), 3) if n_bt else np.nan,
        "bt_avg_R": round(exp, 3),
        "median_abs_dt_min": round(agree.match_dt_min.abs().median(), 1) if len(agree) else np.nan,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("journal")
    ap.add_argument("--variant", default=None, help="run a single named variant (entry or exit variant)")
    ap.add_argument("--tol", type=int, default=15, help="entry-time tolerance in minutes for a match")
    ap.add_argument("--outdir", default=RESULTS_DIR)
    args = ap.parse_args()

    journal = load_journal(args.journal)
    inferred = pd.read_csv(os.path.join(RESULTS_DIR, "direction_inference.csv"))
    m1 = load_prices("m1")
    start, end = journal.date.min(), journal.date.max()
    covered = journal.entry_et.between(m1.index.min() + pd.Timedelta(days=2), m1.index.max())
    all_variants = {**VARIANTS, **EXIT_VARIANTS, **CHECKLIST_VARIANTS, LONDON_ONLY.name: LONDON_ONLY}
    groups = {"single": {args.variant: all_variants[args.variant]}} if args.variant else \
        {"entry rules (refinement rounds)": VARIANTS, "exit alternatives on the final entry rules": EXIT_VARIANTS,
         "the trader's own checklist added to the final rules": CHECKLIST_VARIANTS}

    cache, table = {}, []
    for title, variants in groups.items():
        rows = []
        for name, rules in variants.items():
            if rules.pivot_n not in cache:
                cache[rules.pivot_n] = Market(m1, rules.pivot_n)
            bt = backtest(cache[rules.pivot_n], rules, start, end)
            jt, bt = match(journal, bt, inferred, args.tol)
            row = report(name, jt, bt, covered)
            m = bt[bt.matched_trade_id.notna()].merge(journal[["trade_id", "rr", "result"]], left_on="matched_trade_id", right_on="trade_id")
            row["bt_avg_R_on_matched"] = round(m.r.mean(), 3) if len(m) else np.nan
            # journal outcome scored with its own TP 3R / BE / -1R classes (the logged "RR Achieved" overstates BE trades)
            row["journal_avg_R_on_matched"] = round(m.result.map({"Win": 3.0, "BE": 0.0, "Loss": -1.0}).mean(), 3) if len(m) else np.nan
            rows.append(row)
            if name == FINAL.name or args.variant:
                bt.to_csv(os.path.join(args.outdir, f"bt_trades_{name}.csv"), index=False)
                jt.to_csv(os.path.join(args.outdir, f"bt_journal_match_{name}.csv"), index=False)
        print(f"\n== {title} ==")
        print(pd.DataFrame(rows).to_string(index=False))
        table += [{"group": title, **r} for r in rows]
    if not args.variant:
        pd.DataFrame(table).to_csv(os.path.join(args.outdir, "validation_variants.csv"), index=False)


if __name__ == "__main__":
    main()
