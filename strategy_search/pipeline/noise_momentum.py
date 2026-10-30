"""Intraday momentum out of the "noise area", after Zarattini, Aziz & Barbon (2024), "Beat the Market: An Effective
Intraday Momentum Strategy for S&P500 ETF (SPY)", Swiss Finance Institute Research Paper 24-97.

  python pipeline/noise_momentum.py [--symbols ...]

Rules: for every minute of the session, the noise area is the average absolute move from the day's open to that
minute over the previous 14 days. Its upper boundary is max(today's open, yesterday's close) x (1 + that average)
and its lower boundary min(today's open, yesterday's close) x (1 - that average). Every half hour from 30 minutes
after the open, go long above the upper boundary or short below the lower one. A long is closed when the price is
back below the upper boundary or the day's VWAP, whichever is higher (a short: back above the lower boundary or
VWAP, whichever is lower), checked at the same half-hour marks; whatever is open is closed at the session close.
The published results (2007 - early 2024: +1,985% net, 19.6% a year, Sharpe 1.33) and the boundary-or-VWAP exit are
confirmed by the SFI and CXO Advisory summaries. The paper's PDF host is blocked from this environment, so the
half-hour decision times and the 14-day noise lookback are taken from descriptions of the paper, not checked
against its text. The paper sizes by volatility (2% daily target); here every trade risks 1% of the account with
the exit level at entry as the stop. "check" exits only at the half-hour marks, so a loss can be bigger than 1R;
"resting" keeps a stop order at the exit level between the marks.
VWAP uses Dukascopy's own volume, which is its liquidity providers' volume rather than the exchange's.
"""
import argparse
import os

import numpy as np
import pandas as pd

from intraday import LABEL, RESULTS, TEST_END, TEST_START, load_m1, spread_by_hour
from orb import COLS, SESSIONS, summarize

LOOKBACK, EVERY = 14, 30
_days = {}


def dense_days(sym):
    """Every full session day in the data, including the lookback days before the window, one value per minute.

    Minutes with no bar carry the last close forward with zero volume; days missing over 10% of minutes (half days,
    feed holes) are skipped.
    """
    if sym in _days:
        return _days[sym]
    tz, t_open, t_close = SESSIONS[sym]
    local = load_m1(sym).tz_convert(tz)
    spread = spread_by_hour(sym).values
    out = []
    for day, d in local.groupby(local.index.date):
        idx = pd.date_range(pd.Timestamp(f"{day} {t_open}", tz=tz), pd.Timestamp(f"{day} {t_close}", tz=tz),
                            freq="1min", inclusive="left")
        s = d.reindex(idx)
        if s["close"].notna().mean() < 0.9 or np.isnan(s["close"].iloc[0]):
            continue
        c = s["close"].ffill().values
        gap = s["open"].isna().values
        utc = idx.tz_convert("UTC")
        out.append(dict(day=day, t=utc, o=np.where(gap, c, s["open"].values), h=np.where(gap, c, s["high"].values),
                        l=np.where(gap, c, s["low"].values), c=c, v=np.nan_to_num(s["volume"].values),
                        sp=spread[utc.hour]))
    _days[sym] = out
    return out


def noise_trades(sym, exits="check", lookback=LOOKBACK, every=EVERY):
    days = dense_days(sym)
    move = np.abs(np.array([D["c"] for D in days]) / np.array([D["o"][0] for D in days])[:, None] - 1)
    rows = []
    for i in range(lookback, len(days)):
        D = days[i]
        if not (TEST_START.date() <= D["day"] <= TEST_END.date()):
            continue
        o, h, l, c, sp, v = D["o"], D["h"], D["l"], D["c"], D["sp"], D["v"]
        sig = move[i - lookback:i].mean(axis=0)
        prev_close = days[i - 1]["c"][-1]
        top, bottom = max(o[0], prev_close) * (1 + sig), min(o[0], prev_close) * (1 - sig)
        cv = np.cumsum(v)
        vwap = np.where(cv > 0, np.cumsum((h + l + c) / 3 * v) / np.maximum(cv, 1e-12), c)

        def close(pos, x, exit_px, reason):
            s, k, fill, risk, _ = pos
            rows.append(dict(symbol=sym, market=LABEL[sym], day=D["day"], dir=s, entry_time=D["t"][k],
                             exit_time=D["t"][x], entry=fill, exit=exit_px, risk_pts=risk,
                             r=s * (exit_px - fill) / risk, reason=reason, leverage_at_1pct=0.01 * fill / risk))

        pos = None  # [dir, entry minute, fill, risk, exit level]; shorts are stopped and closed on the ask
        for m in range(every, len(c)):
            if m % every == 0:
                px, ub, lb, vw = c[m - 1], top[m - 1], bottom[m - 1], vwap[m - 1]
                if pos is not None:
                    level = max(ub, vw) if pos[0] > 0 else min(lb, vw)
                    if (px - level) * pos[0] < 0:
                        close(pos, m, o[m] + (sp[m] if pos[0] < 0 else 0.0), "back inside")
                        pos = None
                    else:
                        pos[4] = level
                if pos is None and (px > ub or px < lb):
                    s = 1 if px > ub else -1
                    fill = o[m] + sp[m] if s > 0 else o[m]
                    stop = max(ub, vw) if s > 0 else min(lb, vw)
                    if s * (fill - stop) > 0:
                        pos = [s, m, fill, s * (fill - stop), stop]
            if pos is not None and exits == "resting":
                if pos[0] > 0 and l[m] <= pos[4]:
                    close(pos, m, min(pos[4], o[m]), "stop")
                    pos = None
                elif pos[0] < 0 and h[m] + sp[m] >= pos[4]:
                    close(pos, m, max(pos[4], o[m] + sp[m]), "stop")
                    pos = None
        if pos is not None:
            close(pos, len(c) - 1, c[-1] + (sp[-1] if pos[0] < 0 else 0.0), "close")
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=list(SESSIONS))
    args = ap.parse_args()
    rows, keep = [], []
    for exits in ("check", "resting"):
        t = pd.concat([noise_trades(s, exits) for s in args.symbols], ignore_index=True)
        keep.append(t.assign(exits=exits))
        rows += [summarize(f"Noise momentum {LABEL[s]}, {exits}", t[t.symbol == s]) for s in args.symbols]
        rows.append(summarize(f"Noise momentum, all these markets, {exits}", t))
    pd.concat(keep).to_csv(os.path.join(RESULTS, "noise_momentum_trades.csv"), index=False, float_format="%.6g")
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS, "noise_momentum_summary.csv"), index=False, float_format="%.4f")
    print(res[COLS].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
