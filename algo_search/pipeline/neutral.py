"""Market-neutral families for round 4: spread mean reversion between linked markets, and cross-sectional momentum.

- pairs (after Gatev, Goetzmann & Rouwenhorst 2006, "Pairs Trading", Review of Financial Studies): the spread is
  ln(A) - ln(B), the same notional in each leg. Its z-score is taken against the last L days. At the close, buy the
  spread (A long, B short) below -Z or sell it above +Z; close at the first close back through 0, or as a stop at
  the first close beyond +-(Z + 2). One R is 2 standard deviations of the spread. The pairs are economically linked
  markets, fixed in advance.
- xsmom (cross-sectional momentum, after Asness, Moskowitz & Pedersen 2013, "Value and Momentum Everywhere",
  Journal of Finance): at each month end, within an asset class, buy the top third of markets by past return and
  sell the bottom third, for one month. Stop 3N, or none (sized as if 3N).
Costs as in daily.py: every leg pays its spread once per round trip, and overnight financing on its notional.
"""
import numpy as np
import pandas as pd

from daily import FINANCING, make_rec, prep
from data import UNIVERSE

PAIRS = [("BRENTCMDUSD", "LIGHTCMDUSD", "Commodity pairs"), ("XAUUSD", "XAGUSD", "Commodity pairs"),
         ("DEUIDXEUR", "EUSIDXEUR", "Index pairs"), ("FRAIDXEUR", "EUSIDXEUR", "Index pairs"),
         ("ESPIDXEUR", "EUSIDXEUR", "Index pairs"), ("NLDIDXEUR", "EUSIDXEUR", "Index pairs"),
         ("USA500IDXUSD", "USA30IDXUSD", "Index pairs"), ("USA500IDXUSD", "USATECHIDXUSD", "Index pairs"),
         ("USA500IDXUSD", "USSC2000IDXUSD", "Index pairs"), ("USTBONDTRUSD", "BUNDTREUR", "Bond pairs"),
         ("BUNDTREUR", "UKGILTTRGBP", "Bond pairs")]


def pairs(bars, a, b, cls, L, Z):
    (da, spa), (db, spb) = bars[a], bars[b]
    j = pd.concat([da["close"].rename("a"), db["close"].rename("b")], axis=1, join="inner").dropna()
    s = np.log(j["a"]) - np.log(j["b"])
    sd = s.rolling(L).std().to_numpy()
    z = ((s - s.rolling(L).mean()) / s.rolling(L).std()).to_numpy()
    sv, days = s.to_numpy(), j.index
    cost = spa / j["a"].to_numpy() + spb / j["b"].to_numpy()  # one spread per leg per round trip, as a fraction
    rate = FINANCING[UNIVERSE[a][1]] + FINANCING[UNIVERSE[b][1]]
    name, market = f"pairs L{L} z{Z:g}", f"{UNIVERSE[a][0]} - {UNIVERSE[b][0]}"
    rows, pos = [], None

    def close(t, reason):
        d, t0, s0, risk = pos
        nights = (days[t] - days[t0]).days
        r_gross = d * (sv[t] - s0) / risk - cost[t0] / risk  # after spreads, like the fills of daily.py
        fin = rate * nights / 365 / risk
        rows.append(dict(strategy=name, symbol=f"{a}-{b}", market=market, cls=cls, dir=d, entry_day=days[t0],
                         exit_day=days[t], entry_time=days[t0] + pd.Timedelta(hours=21),
                         exit_time=days[t] + pd.Timedelta(hours=21), entry=s0, exit=sv[t], risk_pts=risk,
                         nights=nights, r_gross=r_gross, fin_r=fin, r=r_gross - fin, reason=reason,
                         leverage_at_1pct=0.02 / risk))

    for t in range(L, len(sv)):
        if np.isnan(z[t]) or not sd[t] > 0:
            continue
        if pos is None:
            if abs(z[t]) > Z:
                pos = (1 if z[t] < 0 else -1, t, sv[t], 2 * sd[t])
            continue
        if pos[0] * z[t] >= 0:
            close(t, "back to the mean")
            pos = None
        elif -pos[0] * z[t] > Z + 2:
            close(t, "stop")
            pos = None
    if pos is not None:
        close(len(sv) - 1, "end of data")
    return rows


def xsmom(bars, cls, look, stop):
    members = [s for s in bars if UNIVERSE[s][1] == cls]
    if len(members) < 3:
        return []
    cf = pd.concat({s: bars[s][0]["close"] for s in members}, axis=1).ffill()
    ends = cf.index.to_series().groupby(cf.index.to_period("M")).max().to_numpy()
    M = cf.loc[ends]
    past = (M.shift(1) / M.shift(12) - 1) if look == "12-1" else (M / M.shift(look) - 1)
    n_side = max(1, len(members) // 3)
    name = f"xsmom {look}m, " + ("stop 3N" if stop else "no stop")
    cache = {s: (bars[s][0].index, *prep(bars[s][0]), make_rec(name, s, bars[s][0].index)) for s in members}
    rows = []
    for i in range(len(ends) - 1):
        ranked = past.iloc[i].dropna().sort_values()
        if len(ranked) < 3:
            continue
        for sym, side in [(x, 1) for x in ranked.index[-n_side:]] + [(x, -1) for x in ranked.index[:n_side]]:
            idx, o, h, l, c, N, rec = cache[sym]
            sp = bars[sym][1]
            t0, t1 = idx.searchsorted(ends[i], side="right") - 1, idx.searchsorted(ends[i + 1], side="right") - 1
            if t0 < 21 or t1 <= t0 or idx[t0] != ends[i]:  # the market must trade on the signal day
                continue
            fill, risk = (c[t0] + sp if side > 0 else c[t0]), 3 * N[t0]
            stop_px = fill - side * risk
            hit = next((t for t in range(t0 + 1, t1 + 1)
                        if (side > 0 and l[t] <= stop_px) or (side < 0 and h[t] + sp >= stop_px)), None) if stop else None
            if hit is not None:
                px = min(stop_px, o[hit]) if side > 0 else max(stop_px, o[hit] + sp)
                rows.append(rec(side, t0, hit, fill, px, risk, "stop", 21, 12))
            else:
                rows.append(rec(side, t0, t1, fill, c[t1] + (sp if side < 0 else 0.0), risk, "month end", 21, 21))
    return rows
