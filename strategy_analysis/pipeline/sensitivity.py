"""Step 5b: sensitivity grid over the few entry-rule choices (reported in full to show it is not cherry-picked)."""
import itertools
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from replicate_strategy import Market, Rules, backtest, match  # noqa: E402
from common import RESULTS_DIR, load_journal, load_prices  # noqa: E402


def main(journal_path):
    journal = load_journal(journal_path)
    inferred = pd.read_csv(os.path.join(RESULTS_DIR, "direction_inference.csv"))
    mk = Market(load_prices("m1"), 2)
    logged = set(journal.entry_et.dt.normalize())
    rows = []
    grid = itertools.product([("0.79 only", "fixed", (0.79,)), ("both", "fixed", (0.705, 0.79)), ("fvg choice", "fvg", (0.79,))],
                             [1.5, 2.0, 2.5], [False, True], [False, True])
    for (lvl_name, choice, levels), min_atr, fresh, bos in grid:
        r = Rules(name="grid", fib_levels=levels, level_choice=choice, min_leg_atr=min_atr, fresh_level=fresh, require_bos=bos)
        jt, bt = match(journal, backtest(mk, r, journal.date.min(), journal.date.max()), inferred)
        b = bt[bt.entry_et.dt.normalize().isin(logged)]
        rec, prec = jt.matched.mean(), b.matched_trade_id.notna().mean()
        rows.append({"levels": lvl_name, "min_leg_atr": min_atr, "fresh_level": fresh, "require_bos": bos,
                     "generated": len(b), "recall": round(rec, 3), "precision": round(prec, 3),
                     "f1": round(2 * rec * prec / (rec + prec), 3), "bt_avg_R": round(b.r.mean(), 3)})
        print(rows[-1], flush=True)
    res = pd.DataFrame(rows).sort_values("f1", ascending=False)
    res.to_csv(os.path.join(RESULTS_DIR, "sensitivity_grid.csv"), index=False)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1])
