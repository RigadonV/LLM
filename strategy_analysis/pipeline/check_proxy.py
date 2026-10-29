"""Step 2b: how well does the Dukascopy Nasdaq-100 CFD track NQ futures intraday?

Compares 5-minute bars of USATECHIDXUSD (built from the 1m cache) against Yahoo Finance NQ=F 5m
bars saved as JSON (chart API response). Reports return correlation, range ratio and basis drift
over the 02:00-09:30 ET window, which is what matters for the trade-level analysis.
"""
import json
import sys

import numpy as np
import pandas as pd

from common import ET, load_prices, resample


def load_yahoo(path):
    r = json.load(open(path))["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    df = pd.DataFrame({k: q[k] for k in ("open", "high", "low", "close")},
                      index=pd.to_datetime(r["timestamp"], unit="s", utc=True).tz_convert(ET))
    return df.dropna()


def main(yahoo_json):
    nq = load_yahoo(yahoo_json)
    cfd = resample(load_prices("m1"), "5min")
    both = nq.join(cfd, lsuffix="_nq", rsuffix="_cfd", how="inner")
    hh = both.index.hour + both.index.minute / 60
    both = both[(hh >= 2) & (hh < 9.5)]
    ret_nq, ret_cfd = both.close_nq.pct_change(), both.close_cfd.pct_change()
    same_day = both.index.to_series().diff() == pd.Timedelta(minutes=5)
    corr = ret_nq[same_day].corr(ret_cfd[same_day])
    rng_ratio = ((both.high_nq - both.low_nq) / (both.high_cfd - both.low_cfd)).replace([np.inf, -np.inf], np.nan)
    basis = both.close_nq - both.close_cfd
    daily_basis = basis.groupby(both.index.date)
    print(f"overlap: {both.index.min()} -> {both.index.max()}, {len(both)} five-minute bars in 02:00-09:30 ET")
    print(f"5m return correlation: {corr:.4f}")
    print(f"5m high-low range ratio NQ/CFD: median {rng_ratio.median():.3f}, IQR {rng_ratio.quantile(.25):.3f}-{rng_ratio.quantile(.75):.3f}")
    print(f"basis NQ - CFD: mean {basis.mean():.1f} pts; mean intraday (02:00-09:30) drift range {daily_basis.apply(lambda b: b.max() - b.min()).mean():.1f} pts")
    print(f"price ratio NQ/CFD: {(both.close_nq / both.close_cfd).mean():.4f}")


if __name__ == "__main__":
    main(sys.argv[1])
