# Search for a strategy that makes 4% a week

**Goal:** about 4% a week on average, consistently, over the last 24 months (1 Oct 2024 – 30 Sep 2026), on a
$10,000 account risking 1% per trade, using real market data only.

**Result: not found.** Nothing tested comes close on data it was not tuned on. The best results, both on the
Nasdaq-100 only:

- The published opening-range breakout made **+0.34% a week**: $10k became $12,698 in 24 months, with a 29% drawdown.
- Noise-area momentum made **+0.83% a week**: $10k became $16,620, with a 37% drawdown. It lost in year 1 and the
  same rules lost on the other three markets.

The one strategy that did make more than 1.5% a week (the repo's own "Model 2") only did so in the months its rules
were tuned on. Out of sample it lost 0.55% a week.

## What 4% a week means

| | |
|---|---|
| 4% a week for 105 weeks, compounded | x61: $10,000 → $614,470 |
| In R (1R = the 1% risked per trade) | about +4R of profit every week, after costs |
| Best published intraday index result found (noise-area momentum, SPY, 2007 – early 2024) | 19.6% a year = **0.35% a week** |

At 5 trades a week, +4R a week needs +0.8R profit on every trade on average. At 50 trades a week it needs +0.08R a
trade after spreads. Compounding also takes a cut: risking 1% of the balance each time loses about
½ × (1%)² × R² per trade. For the breakout trades here (10R winners against many full losers) that is about
0.025R a trade, four times their average edge.

## Data and method

- **Prices:** Dukascopy 1-minute bid candles for the Nasdaq-100, S&P 500, Dow 30 and DAX 40 CFDs; 543 trading days
  each, downloaded from Dukascopy's datafeed. Nothing is simulated.
- **Costs:** the real spread, as the median ask − bid for each UTC hour from Dukascopy's hourly bid and ask candles.
  Longs buy at bid + spread. Shorts are stopped out and take profit at bid + spread. A stop that gaps fills at the
  bar's open. If the stop and target are both inside one bar, the stop is assumed hit first.
- **Account:** $10,000. Every trade risks 1% of the current balance, and profit or loss is booked at the exit.
  - *20:1 cap:* figures with the cap hold all open positions together under 20:1 leverage. That is the EU/UK
    retail limit on major indices, so it is what a regulated broker would let this account do. A trade that would
    need more is made smaller.
  - *Balance floor:* the balance never goes below $0 (negative-balance protection).
- **Out of sample:** rules published before October 2024 are tested unchanged, so nothing in them was fitted to
  this window. Anything tuned here is chosen on year 1 (Oct 2024 – Sep 2025) and judged only on year 2 (Oct 2025 –
  Sep 2026).
- **Weeks** end on Friday. All 105 weeks count, including weeks with no trades.

## Round 1 — published rules, unchanged

The **opening-range breakout** follows Zarattini & Aziz (2023). The first 5-minute candle of the cash session sets
the direction. The trade enters at the next candle, with the stop at the other end of the first candle, a 10R
target, and otherwise an exit at the close.

**Noise-area momentum** follows Zarattini, Aziz & Barbon (2024, SFI Research Paper 24-97). Every half hour the
strategy goes long above the day's "noise area" or short below it. It exits when the price is back inside the
noise area or VWAP, whichever is closer, or at the close. The paper sizes trades by volatility. At 1% risk the
stop has to be that exit level, so two versions were run:

- **Half-hour exits:** exits only at the half-hour checks, as published.
- **Resting stop:** a stop order sits at the exit level between the checks.

All figures use the 20:1 cap.

| Strategy, 24 months | Trades / week | Avg R per trade | Year 1 / Year 2 avg R | Avg week | Weeks ≥ 4% | Positive weeks | Worst week | Max drawdown | $10k becomes |
|---|---|---|---|---|---|---|---|---|---|
| Breakout, Nasdaq-100 | 4.9 | +0.066 | +0.136 / −0.003 | **+0.34%** | 18% | 41% | −4.9% | 28.5% | **$12,698** |
| Breakout, S&P 500 | 4.9 | +0.007 | +0.100 / −0.086 | +0.13% | 19% | 40% | −4.9% | 36.5% | $9,970 |
| Breakout, Dow 30 | 4.9 | −0.079 | −0.058 / −0.100 | −0.35% | 15% | 36% | −6.4% | 44.9% | $6,175 |
| Breakout, DAX 40 | 4.9 | +0.031 | +0.105 / −0.043 | +0.19% | 20% | 45% | −4.9% | 24.7% | $10,666 |
| Breakout, all 4 in one account | 19.6 | +0.006 | — | +0.08% | 27% | 38% | −17.8% | 65.6% | $5,747 |
| Noise momentum, resting stop, Nasdaq-100 | 5.9 | +0.171 | −0.108 / +0.480 | **+0.83%** | 14% | 33% | −12.1% | 37.1% | **$16,620** |
| Noise momentum, resting stop, S&P 500 | 6.8 | −0.343 | −0.301 / −0.381 | −0.90% | 11% | 36% | −12.3% | 67.6% | $3,433 |
| Noise momentum, resting stop, Dow 30 | 6.5 | −0.833 | −0.251 / −1.416 | −0.76% | 14% | 31% | −10.3% | 68.0% | $3,976 |
| Noise momentum, resting stop, DAX 40 | 8.4 | −0.106 | −0.046 / −0.160 | −0.18% | 17% | 37% | −10.2% | 57.3% | $6,903 |
| Noise momentum, resting stop, all 4 | 27.6 | −0.276 | — | −0.85% | 31% | 37% | −20.2% | 84.4% | $2,116 |
| Noise momentum, half-hour exits, all 4 | 18.0 | (see below) | — | −0.17% | 34% | 40% | −33.1% | 91.9% | $1,820 |
| All 8 breakout + resting-stop pairs in one account | 47.2 | −0.159 | — | −0.46% | 30% | 39% | −29.0% | 92.5% | $1,510 |

**Weeks of 4% or more do happen, in 11–34% of weeks.** They are cancelled by the losing weeks; no strategy has more
than 45% positive weeks.

**Noise momentum's half-hour exits can't be run at 1% risk.** Some entries come only a fraction of a point above
the exit level. Sized at 1%, those positions need hundreds of times leverage. A move against them before the next
half-hour check then costs up to 500R in one trade, which is why the average R isn't meaningful. Without a leverage
limit, 4 of the 10 noise-momentum accounts went to $0 and 5 more ended under $3,000. With the 20:1 cap, half-hour
exits made +0.76% a week on the Nasdaq-100 and +0.58% on the DAX, but lost 1.5% and 1.3% a week on the S&P 500
and Dow.

**Combining makes it worse.** The four breakout markets add up to a positive +0.12R a week, but the joint account
still shrank to $5,747. That is the compounding cut described above, plus up to four losers on the same day.

Two details of the noise-area rules come from descriptions of the paper, not its text: the half-hour decision times
and the 14-day lookback. The paper's PDF host is blocked from this environment. The published results and the
noise-area-or-VWAP exit are confirmed by the SFI and CXO Advisory summaries.

## Round 1b — the repo's optimised "Model 2" strategy, out of sample

`strategy_analysis/OPTIMISED_BACKTEST.md` chose the Model 2 rules on 2 March – 16 October 2026: London session
07:00–13:00 UK, 15-minute EMA50 trend filter, spike filter, 2 losses a day, stop under 50 points. October 2024 –
February 2026 was never used to choose them, so it is a clean test. Same code, same Nasdaq-100 data, same
1.5-point cost per trade.

| Period | Exit | Trades | Win rate | Avg R | Avg week | Positive weeks | Max drawdown | Total return |
|---|---|---|---|---|---|---|---|---|
| Mar – Sep 2026 (rules tuned here) | TP 4R, break-even at 2R | 121 | 28% | +0.457 | **+1.76%** | 68% | 6.4% | +68.9% |
| Mar – Sep 2026 (rules tuned here) | TP 2R | 122 | 43% | +0.199 | +0.78% | 58% | 4.7% | +25.7% |
| **Oct 2024 – Feb 2026 (out of sample)** | TP 4R, break-even at 2R | 305 | 18% | −0.135 | **−0.54%** | 35% | 40.4% | −37.0% |
| **Oct 2024 – Feb 2026 (out of sample)** | TP 2R | 308 | 35% | −0.136 | −0.55% | 39% | 42.2% | −36.3% |

This is what a strategy found by tuning looks like: excellent on the months it was fitted to, and a steady loser
on the 17 months it never saw.

## Round 2 — tuning on year 1, judged on year 2

Each market got 30 breakout variants:

- opening range of 5, 15 or 30 minutes;
- target of 2, 3, 5 or 10R, or hold to the close;
- entry on the first candle's direction, or on a break of the range.

For each market, the variant with the best year-1 average R (at least 100 trades) was chosen, then run on year 2:

| Market | Chosen on year 1 | Year 1 | Year 2 |
|---|---|---|---|
| Nasdaq-100 | 15-min range, hold to close, candle direction | +0.297R a trade (+1.46R a week) | −0.101R (−0.50R a week) |
| S&P 500 | 15-min range, 10R target, candle direction | +0.178R (+0.88R a week) | +0.092R (+0.45R a week) |
| Dow 30 | 5-min range, 5R target, range break | +0.107R (+0.53R a week) | −0.056R (−0.27R a week) |
| DAX 40 | 5-min range, hold to close, range break | +0.217R (+1.07R a week) | +0.048R (+0.24R a week) |

All four chosen variants together in one account, year 2 only: 19.4 trades a week, **−0.12% a week**, 54% max
drawdown, and $10k becomes $7,419.

Across all 120 variants, **the correlation between year-1 and year-2 average R is 0.01**. How a variant did in year
1 says nothing about year 2. The typical variant made money in year 1 in every market (median +0.03R to +0.14R a
trade) and lost in year 2 in every market (median −0.01R to −0.04R). Only 32% of variants were positive in year 2,
and the best of them made +0.092R a trade.

## Why I stopped searching here

1. **What tests well hasn't held up later.** Every strategy that looked strong in one period failed in the next:
   Model 2's 1.76% a week, the year-1 breakout picks, and noise momentum on the S&P 500, Dow and DAX. The two
   rule sets fixed in advance that worked on the Nasdaq-100 made 0.3–0.8% a week, and even those were not
   consistent from one year to the next.
2. **The gap is too large.** The best honest result is about a fifth of the target, and the published benchmark is
   less than a tenth.
3. **More searching would produce a fake answer.** Running thousands of variants would eventually throw up one that
   shows 4% a week over these 24 months. Bailey et al. (2014) show why: the best of many backtests is expected to
   look good by chance. The year-1 to year-2 correlation of 0.01 above is that effect measured on this data.
   Presenting such a result would break the requirement that everything be real.

## What a $10k, 1%-risk account could realistically aim for

On this evidence, a few tenths of a percent a week, with drawdowns of 25–40%. That is roughly the breakout on the
Nasdaq-100 (+0.34% a week, 28.5% drawdown, flat in year 2) and in line with the published 19.6% a year for
noise-area momentum. Getting near 4% a week would take far more than 1% risk per trade, which is outside the brief
and would likely wipe out the account in the bad weeks shown above.

## Files

| File | What it is |
|---|---|
| `pipeline/fetch_m1.py` | Downloads Dukascopy 1-minute candles (`--symbols --start --end --sides --workers --reverse`) |
| `pipeline/intraday.py` | Data loading, hourly spreads, the $10k / 1% account (20:1 cap, $0 floor), weekly statistics |
| `pipeline/orb.py` | Opening-range breakout, published rules and variants → `results/orb_published_*.csv` |
| `pipeline/orb_search.py` | 120-variant year-1 / year-2 search → `results/orb_search_*.csv` |
| `pipeline/noise_momentum.py` | Noise-area momentum, both exit versions → `results/noise_momentum_*.csv` |
| `pipeline/model2_oos.py` | Model 2 out-of-sample test with the `strategy_analysis` engine → `results/model2_oos_*.csv` |
| `pipeline/compare.py` | Every strategy on the same account, without a cap and at 20:1 → `results/comparison.csv` |

**To reproduce:** run these from `strategy_search/`. Downloading the data takes several hours because Dukascopy
throttles requests.

```
python pipeline/fetch_m1.py --symbols USATECHIDXUSD USA500IDXUSD USA30IDXUSD DEUIDXEUR --start 2024-09-02 --end 2026-09-30
cd pipeline && python orb.py && python orb_search.py && python noise_momentum.py && python model2_oos.py && python compare.py
```

## Limits

- **Dukascopy CFD feed:** prices and volume are Dukascopy's CFD feed, not exchange data. VWAP uses Dukascopy's
  volume.
- **Spreads:** medians for each hour, so spikes around news are not modelled.
- **Commission:** none is added. A broker that charges one would make every result worse.
- **Currency:** DAX profit and loss is counted in R, without EUR/USD conversion.

## Sources

- Zarattini, C. & Aziz, A. (2023). *Can Day Trading Really Be Profitable? Evidence of Sustainable Long-term Profits
  from Opening Range Breakout (ORB) Day Trading Strategy vs. Benchmark in the US Stock Market.* SSRN 4416622.
- Zarattini, C., Aziz, A. & Barbon, A. (2024). *Beat the Market: An Effective Intraday Momentum Strategy for S&P500
  ETF (SPY).* Swiss Finance Institute Research Paper 24-97.
  [SFI](https://www.sfi.ch/de/publications/n-24-97-beat-the-market-an-effective-intraday-momentum-strategy-for-s-p500-etf-spy),
  [CXO Advisory summary](https://www.cxoadvisory.com/momentum-investing/complex-intraday-time-series-momentum-strategy-applied-to-spy/).
- Bailey, D. H., Borwein, J. M., López de Prado, M. & Zhu, Q. J. (2014). *Pseudo-Mathematics and Financial
  Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance.* Notices of the AMS 61(5).
- Data: Dukascopy Bank SA historical datafeed (`datafeed.dukascopy.com`).
