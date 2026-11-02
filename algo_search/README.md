# Algo strategy search: 2% a week over the last 12 months

Looks for an algorithmic strategy that averages about 2% a week over 1 Nov 2025 – 30 Oct 2026. It uses real
Dukascopy data for 51 markets (forex, metals, energy, agricultural, equity indices, bonds, crypto) and a $10,000
account. The base case is 1% risk per trade, with larger risk examined too.

**Result: not found.** At 1% risk per trade the best published rule made +0.42% a week (turn of the month). A
13-stream portfolio sized by Kelly, with everything fixed before the window, came close to 2% a week in the last
12 months: +2.17% average, +1.93% compounded. The same process, run year by year, lost money in four of the five
years before the window. See [REPORT.md](REPORT.md) for every table, the method and the limits.

Scripts are in `pipeline/` and outputs in `results/`. The raw data is not committed;
`python pipeline/data.py fetch && python pipeline/data.py build` downloads it again.
