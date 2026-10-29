"""Step 4a: which swing-leg definition explains the logged fib levels best?

For every trade with an inferred direction we take the entry price implied by the price path alone
(not snapped to any fib), find the single most recent valid 15M leg under a given definition and
check whether the entry sits at the logged retracement (+/-0.05). Only one leg is scored per trade,
so adding definitions cannot cherry-pick. A chance baseline repeats the test at random minutes of
the same sessions.
"""
import os

import numpy as np
import pandas as pd

from common import RESULTS_DIR, load_journal, load_prices
from structure import Structure

TOL = 0.05


def score(st, trades, fib_col="fib_level"):
    hits, near_ote, n = 0, 0, 0
    for tr in trades.itertuples():
        recent, _ = st.leg_for_entry(tr.t0, tr.direction, tr.entry)
        n += 1
        if recent is None:
            continue
        r = recent["ratio"]
        hits += abs(r - getattr(tr, fib_col)) <= TOL
        near_ote += 0.705 - TOL <= r <= 0.79 + TOL
    return hits / n, near_ote / n


def random_baseline(m1, trades, seed=7):
    """Same days and directions, random minute in 02:00-09:30, entry = that minute's close."""
    rng = np.random.default_rng(seed)
    rows = []
    for tr in trades.itertuples():
        day = tr.t0.normalize()
        t = day + pd.Timedelta(minutes=int(rng.integers(120, 570)))
        bar = m1.loc[t: t + pd.Timedelta(minutes=2)]
        if len(bar):
            rows.append({"t0": bar.index[0], "direction": tr.direction, "entry": bar["close"].iloc[0], "fib_level": tr.fib_level})
    return pd.DataFrame(rows)


def main(journal_path):
    journal = load_journal(journal_path)
    inf = pd.read_csv(os.path.join(RESULTS_DIR, "direction_inference.csv"))
    inf = inf[inf.direction.isin(["long", "short"])]
    m1 = load_prices("m1")
    path_entry = inf.entry_price_path
    trades = inf.assign(entry=path_entry).merge(journal[["trade_id", "entry_et", "fib_level"]], on="trade_id")
    trades = trades.rename(columns={"entry_et": "t0"})[["trade_id", "t0", "direction", "entry", "fib_level"]]
    base = random_baseline(m1, trades)
    rows = []
    for n in (1, 2, 3):
        for min_atr in (0.0, 1.0, 1.5, 2.0, 2.5):
            st = Structure(m1, pivot_n=n, min_leg_atr=min_atr)
            hit, ote = score(st, trades)
            bhit, bote = score(st, base)
            rows.append({"pivot_n": n, "min_leg_atr": min_atr, "match_logged_fib": round(hit, 3), "in_0.705-0.79_zone": round(ote, 3),
                         "chance_match": round(bhit, 3), "chance_zone": round(bote, 3), "lift": round(hit / bhit, 2) if bhit else np.nan})
            print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    res.to_csv(os.path.join(RESULTS_DIR, "leg_definition_test.csv"), index=False)
    print(res.to_string(index=False))


if __name__ == "__main__":
    import sys
    main(sys.argv[1])
