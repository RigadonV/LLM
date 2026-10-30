# Strategy search: 4% a week at 1% risk per trade

Looks for a strategy that averages about 4% a week over 1 Oct 2024 – 30 Sep 2026 on a $10,000 account risking 1%
per trade. It uses real Dukascopy 1-minute data for the Nasdaq-100, S&P 500, Dow 30 and DAX 40, with real spreads.

**Result: not found.** On data it was not tuned on, the best was the published opening-range breakout on the
Nasdaq-100: +0.34% a week, $10k to $12,698, 29% max drawdown. Strategies that looked strong on the data they were
tuned on lost on new data. See [REPORT.md](REPORT.md) for every result, the method, and the reasons the search
stopped.

Scripts are in `pipeline/` and outputs in `results/`. The 1-minute data in `data/` is not committed; it is
re-downloaded with `pipeline/fetch_m1.py`.
