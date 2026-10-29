"""Step 2: align journal trades to 1m price data, infer direction + implied entry price, and test timezones.

The journal has no direction or prices, only entry minute, duration, MAE (points), MFE (R) and RR.
For a candidate direction the entry price is pinned down by the trade window:
    long : entry = lowest low during the trade  + MAE
    short: entry = highest high during the trade - MAE
That implied price must sit inside the candles at the logged entry minute, and the rest of the
journal row must then be consistent with the path price took:
    Loss : stop distance (1R) ~= MAE, favourable move before the stop ~= MFE x MAE
    Win/BE: favourable move by the logged time = RR x R with R > MAE (the stop was never hit). For "BE"
            trades RR is the peak (~2R, below 2.98R) before the stop, moved to entry at 2R, was hit later.
Only the true direction (and the true timezone) passes these tests consistently.
"""
import argparse
import os

import numpy as np
import pandas as pd

from common import LEG_MIN_ATR, LEG_PIVOT_N, RESULTS_DIR, load_journal, load_prices
from structure import Structure

TOL = 3.0          # points of slack for CFD-vs-futures wick differences
ENTRY_SLACK = 1    # +/- minutes around the logged entry minute
EXIT_SLACK = 2     # +/- minutes around the logged exit minute
MIN_R = 5.0        # smallest plausible stop on NQ (points)
MAX_R = 120.0      # largest plausible stop on NQ (points)


def direction_error(m1, tr, t0, d):
    """Smallest inconsistency (points) between the journal row and price path for direction d, plus best entry."""
    s = 1 if d == "long" else -1
    t_end = t0 + pd.Timedelta(minutes=tr.minutes)
    zone = m1.loc[t0 - pd.Timedelta(minutes=ENTRY_SLACK): t0 + pd.Timedelta(minutes=ENTRY_SLACK)]
    full = m1.loc[t0: t_end + pd.Timedelta(minutes=EXIT_SLACK)]
    core = m1.loc[t0: t_end - pd.Timedelta(minutes=EXIT_SLACK if tr.result != "Loss" else 1)]
    if len(zone) == 0 or len(full) == 0:
        return np.nan, np.nan
    if len(core) == 0:
        core = full.iloc[:1]
    zlo, zhi = zone["low"].min(), zone["high"].max()
    adv_col, fav_col = ("low", "high") if d == "long" else ("high", "low")

    def adverse_extreme(w):
        return w[adv_col].min() if d == "long" else w[adv_col].max()

    # entry interval implied by MAE (wider window -> more extreme adverse price)
    e1 = adverse_extreme(full) + s * tr.mae_pts
    e2 = adverse_extreme(core) + s * tr.mae_pts
    lo, hi = min(e1, e2), max(e1, e2)
    gap = max(0.0, zlo - hi, lo - zhi)
    if gap > TOL:
        return gap + 50.0, np.nan  # infeasible: penalise heavily but keep the size information
    grid = np.arange(max(lo, zlo - TOL), min(hi, zhi + TOL) + 0.25, 0.5)
    if len(grid) == 0:
        grid = np.array([(lo + hi) / 2])

    fav_path = full[fav_col].values
    best_err, best_e = np.inf, np.nan
    for e in grid:
        fav_run = s * (fav_path - e)  # favourable excursion bar by bar
        if tr.result == "Loss":
            r = tr.mae_pts
            # favourable move achieved before the stop, measured inside the trade window
            fav_before = max(0.0, s * ((core[fav_col].max() if d == "long" else core[fav_col].min()) - e))
            err = abs(fav_before - tr.mfe_r * r) - 0.25 * r
        else:
            # Win and "BE" alike: price stood at RR x R at the logged time. For "BE" that is the peak
            # (logged RR ~= MFE); the break-even exit at the entry price came afterwards.
            r = max(fav_run.max(), 0) / max(tr.rr, 0.1)
            err = max(0.0, tr.mae_pts + 0.5 - r) + max(0.0, MIN_R - r) + max(0.0, r - MAX_R)
        err = max(err, 0.0)
        if err < best_err:
            best_err, best_e = err, e
    return best_err, best_e


def run(journal, m1, offset_h=0):
    recs = []
    for tr in journal.itertuples():
        t0 = tr.entry_et + pd.Timedelta(hours=offset_h)
        rec = {"trade_id": tr.trade_id}
        for d in ("long", "short"):
            rec[f"{d}_err"], rec[f"{d}_entry"] = direction_error(m1, tr, t0, d)
        recs.append(rec)
    res = pd.DataFrame(recs)
    res["fit"] = res.apply(classify, axis=1)
    return res


def classify(row):
    le, se = row["long_err"], row["short_err"]
    if np.isnan(le) or np.isnan(se):
        return "no_data"
    ok_l, ok_s = le <= TOL, se <= TOL
    if ok_l and not ok_s:
        return "long"
    if ok_s and not ok_l:
        return "short"
    if ok_l and ok_s:
        if abs(le - se) >= 1.0:
            return ("long" if le < se else "short") + "*"
        return "ambiguous"
    return "no_fit"


FIB_TOL = 0.05  # retracement-ratio tolerance when matching the logged fib level


def fib_stage(m1, journal, res):
    """Stage 2: use the logged fib level to break ties and to pin the entry price to the fib level itself."""
    st = Structure(m1, LEG_PIVOT_N, LEG_MIN_ATR)
    jt = journal.set_index("trade_id")
    rows = []
    for r in res.itertuples():
        tr = jt.loc[r.trade_id]
        rec = {"trade_id": r.trade_id}
        for d in ("long", "short"):
            e = getattr(r, f"{d}_entry")
            recent = None
            if getattr(r, f"{d}_err") <= TOL and not np.isnan(e):
                recent, _ = st.leg_for_entry(tr.entry_et, d, e)
            rec[f"{d}_fib_ratio"] = recent["ratio"] if recent else np.nan
            rec[f"{d}_leg"] = recent
        rows.append(rec)
    fib = pd.DataFrame(rows).set_index("trade_id")
    res = res.set_index("trade_id").join(fib)

    out = []
    for tid, r in res.iterrows():
        f = jt.at[tid, "fib_level"]
        match = {d: abs(r[f"{d}_fib_ratio"] - f) <= FIB_TOL if not np.isnan(r[f"{d}_fib_ratio"]) else False for d in ("long", "short")}
        fit = r["fit"]
        if fit in ("long", "short"):
            direction, conf = fit, "high"
        elif match["long"] != match["short"]:
            direction, conf = ("long" if match["long"] else "short"), "medium"
        elif fit.endswith("*"):
            direction, conf = fit[:-1], "low"
        else:
            direction, conf = None, "none"
        rec = {"trade_id": tid, "fit": fit, "direction": direction, "direction_confidence": conf,
               "long_err": r["long_err"], "short_err": r["short_err"],
               "long_entry": r["long_entry"], "short_entry": r["short_entry"]}
        if direction:
            leg = r[f"{direction}_leg"]
            e_path = r[f"{direction}_entry"]
            rec["fib_ratio_at_entry"] = r[f"{direction}_fib_ratio"]
            rec["fib_matches_journal"] = bool(match[direction])
            rec["entry_price_path"] = e_path  # implied by the price path alone
            rec["entry_price_est"] = e_path
            if leg and match[direction]:
                # limit order sits exactly on the logged level; use it when consistent with the price path
                e_fib = leg["ext"] - f * (leg["ext"] - leg["anchor"])
                if abs(e_fib - e_path) <= 6.0:
                    rec["entry_price_est"] = e_fib
        out.append(rec)
    return pd.DataFrame(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("journal")
    args = ap.parse_args()
    journal = load_journal(args.journal)
    m1 = load_prices("m1")

    print("Timezone test (offset added to the logged time, hours):")
    tz_rows = []
    for off in (-6, -5, -4, -1, 0, 1, 4, 5, 6):
        vc = run(journal, m1, off)["fit"].value_counts()
        row = {"offset_h": off}
        row["clear_fit"] = int(sum(vc.get(k, 0) for k in ("long", "short")))
        row["weak_fit"] = int(sum(vc.get(k, 0) for k in ("long*", "short*", "ambiguous")))
        row["no_fit"] = int(vc.get("no_fit", 0))
        row["no_data"] = int(vc.get("no_data", 0))
        tz_rows.append(row)
    tz = pd.DataFrame(tz_rows)
    tz["fit_rate"] = ((tz["clear_fit"] + tz["weak_fit"]) / (len(journal) - tz["no_data"])).round(3)
    print(tz.to_string(index=False))
    tz.to_csv(os.path.join(RESULTS_DIR, "timezone_test.csv"), index=False)

    res = fib_stage(m1, journal, run(journal, m1, 0))
    res.to_csv(os.path.join(RESULTS_DIR, "direction_inference.csv"), index=False)
    print("\nStage 1 (price path) fit:\n" + res["fit"].value_counts().to_string())
    print("\nFinal direction confidence:\n" + res["direction_confidence"].value_counts().to_string())
    print("\nDirection:\n" + res["direction"].value_counts(dropna=False).to_string())
    print("\nMost recent 15M leg matches logged fib (+/-%.2f): %d of %d resolved trades"
          % (FIB_TOL, res["fib_matches_journal"].sum(), res["direction"].notna().sum()))


if __name__ == "__main__":
    main()
