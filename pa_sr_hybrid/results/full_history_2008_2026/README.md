# Full history, January 2008 – September 2026

The run made before the backtest was narrowed to the last 24 months: same rules, same data and
same pipeline, with trades entering from 1 January 2008 instead of 1 October 2024. It is kept
because BACKTEST.md quotes it.

| File | What it is |
|---|---|
| `report_tables.md` | The report as generated then. Its first variant table is on **daily bars only** (same-day cases counted the worse way, with the better way and no-cost averages alongside), because the hourly files for every variant had not all been downloaded. The "Hybrid family" table is replayed on hourly bars, with 4% of trades still settled by rule. |
| `hybrid_trades.csv` | The hybrid's 701 trades from that run (hourly replay, leftovers the worse way, after costs): average −0.07R per trade; forex −0.18R; before October 2024 −0.09R. |

To reproduce, set `TEST_START = pd.Timestamp("2008-01-01")` in `pipeline/common.py` and the report
period split back to 2017, then run `fetch_data.py --needed` and `backtest.py`. Results will
differ slightly from these files where more hourly months are now available.
