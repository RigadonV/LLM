"""Step 2: backtest every variant of STRATEGY.md on daily bid/ask bars.

  python pipeline/backtest.py

Trades enter from TEST_START (common.py: the last 24 months); earlier bars only warm up the
indicators.

Buys fill at the ask and sells at the bid, plus commission. When a daily bar holds both the stop
and the target (or the entry and the stop) the order of events is unknown. Every variant is run
on daily bars alone with such cases settled the worse way ('cons') and the better way ('opt'),
so all variants are compared on the same footing with a lower and an upper bound. A second pass
('hourly' = True) settles them from hourly bars where those months have been downloaded.

Writes results/trades.csv.gz (every trade of every run) and results/hourly_needed.csv (the months
whose hourly files would settle the remaining cases: fetch_data.py --needed, then run this again).
"""
import argparse
import os

import numpy as np
import pandas as pd

from common import INSTRUMENTS, RESULTS_DIR, TEST_START, hourly_month, load_daily, raw_path, trading_day
from strategy import MAX_BARS, TARGET_R, VARIANTS, Market, make_order

COMMISSION = 0.000035  # per side, fraction of the price: IC Markets Raw Spread, $3.50 per lot per side
SETTLED_RANK = {"daily": 0, "hourly": 1, "rule": 2}


def run_bar(b, pend, pos, rule):
    """Advance one bar. Returns (position, exit price, exit reason, ambiguous).

    position is None if a pending order was not filled. rule None reports an ambiguity without
    settling it; 'cons' / 'opt' settle it the worse / better way for the trade.
    """
    bo, bh, bl, bc, ao, ah, al, ac = b
    kind = "held"
    if pend is not None:
        s, price = pend["dir"], pend["price"]
        fill = None
        if pend["kind"] == "open":
            fill = ao if s > 0 else bo
        elif pend["kind"] == "stop":
            if s > 0 and ah >= price:
                fill = max(price, ao)
            elif s < 0 and bl <= price:
                fill = min(price, bo)
        else:  # limit
            if s > 0 and al <= price:
                fill = min(price, ao)
            elif s < 0 and bh >= price:
                fill = max(price, bo)
        if fill is None:
            return None, None, None, False
        if pend["kind"] == "open":
            risk = s * (fill - pend["stop"])
            if risk <= 0:  # opened beyond the stop: no trade
                return None, None, None, False
            target = fill + s * TARGET_R * risk
        else:
            risk, target = pend["risk"], pend["target"]
        pos = dict(pend, entry=fill, risk=risk, target=target, settled="daily")
        # filled at the open: everything else in the bar happened after the fill
        kind = "open" if fill == (ao if s > 0 else bo) else pend["kind"]
    s, stop, target = pos["dir"], pos["stop"], pos["target"]
    if kind == "held":
        first = bo if s > 0 else ao
        if s * (first - stop) <= 0:
            return pos, first, "stop", False
        if s * (first - target) >= 0:
            return pos, first, "target", False
    if s > 0:
        stop_hit, tgt_hit = bl <= stop, bh >= target
    else:
        stop_hit, tgt_hit = ah >= stop, al <= target
    if not (stop_hit or tgt_hit):
        return pos, None, None, False
    if kind == "stop":     # filled on a stop: the stop level may have traded before the fill
        amb = stop_hit
    elif kind == "limit":  # filled on a limit: the target level may have traded before the fill
        amb = tgt_hit
    else:
        amb = stop_hit and tgt_hit
    if not amb:
        return (pos, stop, "stop", False) if stop_hit else (pos, target, "target", False)
    if rule is None:
        return pos, None, None, True
    if rule == "cons":
        return (pos, stop, "stop", True) if stop_hit else (pos, None, None, True)
    return (pos, target, "target", True) if tgt_hit else (pos, None, None, True)


def run_hours(hours, pend, pos, rule):
    """Replay one day hour by hour; ambiguities inside a single hour are settled by `rule`."""
    amb_any = False
    for hb in hours:
        p2, px, why, amb = run_bar(hb, pend, pos, rule)
        amb_any |= amb
        if p2 is None:  # order not filled yet
            continue
        pend, pos = None, p2
        if px is not None:
            return pos, px, why, amb_any
    return pos, None, None, amb_any


class Hourly:
    """Hourly bid/ask bars of one trading day, if those months have been downloaded."""

    def __init__(self, sym, frictionless):
        self.sym, self.frictionless, self.months = sym, frictionless, {}

    def _month(self, y, m):
        if (y, m) not in self.months:
            files = [raw_path(self.sym, "h1", side, y, m) for side in ("BID", "ASK")]
            ok = all(os.path.exists(f) and os.path.getsize(f) > 0 for f in files)
            h = hourly_month(self.sym, y, m) if ok else None
            if h is not None:
                h = h.assign(day=trading_day(h.index))
            self.months[(y, m)] = h
        return self.months[(y, m)]

    @staticmethod
    def months_for(day):
        days = [day] + ([day - pd.Timedelta(days=1)] if day.dayofweek == 0 else [])
        return sorted({(d.year, d.month) for d in days})

    def day(self, day):
        frames = [self._month(y, m) for y, m in self.months_for(day)]
        if any(f is None for f in frames):
            return None
        h = pd.concat(frames)
        h = h[h["day"] == day].sort_index()
        if h.empty:
            return None
        return list(bar_tuples(h, self.frictionless))


def bar_tuples(df, frictionless):
    bid = [df[f"bid_{k}"].to_numpy() for k in ("open", "high", "low", "close")]
    ask = bid if frictionless else [df[f"ask_{k}"].to_numpy() for k in ("open", "high", "low", "close")]
    return list(zip(*bid, *ask))


def close_trade(pos, exit_px, reason, exit_t, m, costs):
    s, entry = pos["dir"], pos["entry"]
    pnl = s * (exit_px - entry) - (COMMISSION * (entry + exit_px) if costs else 0.0)
    return dict(dir=s, signal_day=m.d.index[pos["signal_t"]].date(), entry_day=m.d.index[pos["entry_t"]].date(),
                exit_day=m.d.index[exit_t].date(), bars_held=exit_t - pos["entry_t"], entry=entry, stop=pos["stop"],
                target=pos["target"], exit=exit_px, reason=reason, risk=pos["risk"], r=pnl / pos["risk"],
                atr=pos["atr"], settled=pos["settled"], level=pos.get("level", np.nan),
                touches=pos.get("touches", np.nan), flipped=pos.get("flipped", np.nan),
                round_number=pos.get("round_number", np.nan))


def simulate(sym, m, v, rule, costs, hourly):
    bars = bar_tuples(m.d, frictionless=not costs)
    trades, needed = [], set()
    pend, pos = None, None
    for t in range(m.n):
        if pend is not None or pos is not None:
            p2, px, why, amb = run_bar(bars[t], pend, pos, None)
            settled = "daily"
            if amb:
                hrs = hourly.day(m.d.index[t]) if hourly is not None else None
                if hrs is not None:
                    p2, px, why, amb_h = run_hours(hrs, pend, pos, rule)
                    settled = "rule" if amb_h else "hourly"
                else:
                    if hourly is not None:
                        needed.update(Hourly.months_for(m.d.index[t]))
                    p2, px, why, _ = run_bar(bars[t], pend, pos, rule)
                    settled = "rule"
            if p2 is not None:
                if pos is None:
                    p2["entry_t"] = t
                if SETTLED_RANK[settled] > SETTLED_RANK[p2["settled"]]:
                    p2["settled"] = settled
                if px is None and t - p2["entry_t"] >= MAX_BARS:
                    px, why = (bars[t][3] if p2["dir"] > 0 else bars[t][7]), "time"
                if px is not None:
                    trades.append(close_trade(p2, px, why, t, m, costs))
                    p2 = None
            pend, pos = None, p2
        if pos is None and t < m.n - 1 and m.d.index[t + 1] >= TEST_START:
            pend = make_order(m, t, v)
    if pos is not None:  # still open when the data ends
        trades.append(close_trade(pos, bars[-1][3] if pos["dir"] > 0 else bars[-1][7], "end", m.n - 1, m, costs))
    return trades, needed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=list(INSTRUMENTS))
    ap.add_argument("--variants", nargs="*", default=list(VARIANTS))
    ap.add_argument("--out", default="trades.csv.gz")
    args = ap.parse_args()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    rows, needed_rows = [], []
    for sym in args.symbols:
        label, cls, _, tick, _ = INSTRUMENTS[sym]
        d = load_daily(sym)
        m = Market(d, tick, cls)
        hourly = {True: Hourly(sym, False), False: Hourly(sym, True)}
        for vk in args.variants:
            v = VARIANTS[vk]
            runs = [("cons", True, False), ("opt", True, False), ("cons", False, False),
                    ("cons", True, True), ("opt", True, True), ("cons", False, True)]
            for rule, costs, use_hourly in runs:
                trades, needed = simulate(sym, m, v, rule, costs, hourly[costs] if use_hourly else None)
                for tr in trades:
                    tr.update(symbol=sym, market=label, asset_class=cls, variant=vk, rule=rule, costs=costs,
                              hourly=use_hourly)
                rows += trades
                if rule == "cons" and use_hourly:
                    needed_rows += [dict(symbol=sym, year=y, month=mo, variant=vk) for y, mo in needed]
            n = sum(1 for r in rows if r["symbol"] == sym and r["variant"] == vk and r["rule"] == "cons"
                    and r["costs"] and not r["hourly"])
            print(f"{sym:14s} {vk:4s} {n:5d} trades", flush=True)
    cols = ["variant", "rule", "costs", "hourly", "symbol", "market", "asset_class", "dir", "signal_day", "entry_day",
            "exit_day", "bars_held", "entry", "stop", "target", "exit", "reason", "risk", "r", "atr", "settled",
            "level", "touches", "flipped", "round_number"]
    pd.DataFrame(rows)[cols].to_csv(os.path.join(RESULTS_DIR, args.out), index=False, float_format="%.6g")
    need = pd.DataFrame(needed_rows, columns=["symbol", "year", "month", "variant"])
    order = {k: i for i, k in enumerate(["V4", "V4d", "V4b", "V4c", "V4a", "V3", "V0", "V2", "V1"])}
    need["priority"] = need["variant"].map(order)
    need = need.groupby(["symbol", "year", "month"], as_index=False)["priority"].min().sort_values(["priority", "symbol", "year", "month"])
    need.to_csv(os.path.join(RESULTS_DIR, "hourly_needed.csv"), index=False)
    print(f"{len(rows)} trades written; {len(need)} hourly months would settle the remaining same-day cases")


if __name__ == "__main__":
    main()
