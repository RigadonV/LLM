# pa_sr_hybrid/

A hybrid of **price action** and **support/resistance**, built from published research and
tested on real historical prices (forex majors, gold, silver, Brent, five stock indices,
2008 to September 2026).

| File | What it is |
|---|---|
| `RESEARCH.md` | The core principles of each discipline, what the research says about each one, and what the hybrid keeps |
| `STRATEGY.md` | The hybrid's rules and the test plan, committed before any backtest was run |
| `BACKTEST.md` | The results: the hybrid against its parts, after real spreads and commission |
| `results/` | Every trade (`trades.csv`), summary tables, equity curves |
| `charts/` | Charts used in `BACKTEST.md` (light and dark versions) |
| `pipeline/` | The scripts that produce everything above |

## Reproduce

Python 3 with pandas, numpy and matplotlib. Needs network access to `datafeed.dukascopy.com`
(free, no account). The feed throttles hard, so the first download takes about an hour.

```bash
cd pa_sr_hybrid/pipeline
python fetch_data.py            # daily bid/ask candles 2007-2025 + hourly Jan-Sep 2026 -> ../data/ (git-ignored)
python test_engine.py           # checks of the order-execution engine on hand-made bars
python backtest.py              # every variant -> ../results/trades.csv, ../results/hourly_needed.csv
python fetch_data.py --needed   # hourly months that settle same-day stop/target cases
python backtest.py              # run again with those hours
python report.py                # ../results/summary_*.csv, ../results/report_tables.md
python charts.py                # ../charts/*.png
```

`strategy.py` holds every rule and parameter; `backtest.py` holds the order-execution engine.

## `results/trades.csv` columns

| Column | Meaning |
|---|---|
| `variant` | V0–V4d, see `STRATEGY.md` |
| `rule` | how a daily bar holding both stop and target (or entry and stop) was settled: `cons` = the worse way, `opt` = the better way |
| `costs` | `True`: fills at Dukascopy bid/ask + commission; `False`: bid prices only, no commission |
| `hourly` | `True`: such bars were replayed hour by hour where the hourly file was downloaded |
| `signal_day`, `entry_day`, `exit_day` | trading days (UTC; Sunday evening folded into Monday) |
| `entry`, `stop`, `target`, `exit` | prices; `risk` = planned distance from entry to stop |
| `r` | result in R: profit or loss after costs divided by `risk` |
| `reason` | `target`, `stop`, `time` (20-day exit) or `end` (still open at the end of the data) |
| `settled` | `daily` (no ambiguity), `hourly` (settled from hourly bars) or `rule` (settled by `rule`) |
| `level`, `touches`, `flipped`, `round_number` | the key level traded (level-based variants only) |
