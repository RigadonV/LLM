# Search for a strategy that averages 2% a week

**Goal:** about 2% a week on average over the last 12 months (1 Nov 2025 – 30 Oct 2026). The search starts from
algorithmic-trading principles and published strategies, tested on real market data only. The base case, as in
the earlier searches, is a $10,000 account risking 1% per trade. Larger risk is examined too.

**Result: not found.** No strategy or combination of strategies tested here reliably makes 2% a week.

- **Best at 1% risk:** the turn of the month on 15 equity indices made **+0.42% a week** compounded in the last 12
  months ($10,000 → $12,412). The same rule lost money over 2018–2025, positive in only 2 of 8 years.
- **Only route to about 2% a week:** a portfolio of 13 rule-based streams across 51 markets, sized by the Kelly
  criterion at 1.3–5% risk per trade. Every rule and weight was fixed on data from before the window. Trade by
  trade, with all positions under 20:1 leverage, it averaged **+2.17% a week**, or +1.93% compounded: $10,000
  became $27,038, with a 23% maximum drawdown.
- **That was a good year, not an edge.** The same process was set up at the start of each of the five previous
  years, using only the data available then. It lost money in four of them. At the same Kelly sizing, three of
  those years ended at $2,081–$5,097 out of $10,000, with drawdowns of 75–81%. Over the six test years its median
  week was **−1.0%**.

## What 2% a week takes

| | |
|---|---|
| 2% a week for 52 weeks, compounded | x2.80: $10,000 → $28,003 |
| At 1% risk per trade | about +2R of net profit every week |
| Fastest possible growth at the best leverage (Kelly) | S² / 2 a year in log terms, where S is the annual Sharpe ratio |
| Sharpe ratio needed for x2.80 a year | **at least 1.44** at full Kelly, 1.66 at half Kelly, year after year |
| EU/UK retail leverage limits (ESMA 2018) | 30:1 major FX pairs; 20:1 other FX, gold and major indices; 10:1 other commodities and indices; 2:1 crypto |

Full Kelly is the most aggressive sizing that still grows the account, and it brings deep drawdowns. A strategy
whose Sharpe is below 1.44 cannot compound 2% a week at any leverage. One with a higher Sharpe in one lucky year
does not have it every year.

## The algorithmic-trading principles the search was built on

1. **An edge after every cost.** Spreads and overnight financing decide whether a rule makes money. Before
   financing, the Turtle trend systems roughly broke even over 2017–2026 (−0.007R and −0.001R a trade); after
   financing they lost 0.06–0.09R a trade.
2. **Position sizing.** The base case is a fixed fraction of 1% risk per trade. The Kelly criterion is the
   growth-maximising size; for several correlated streams it maximises mean − variance / 2 of the portfolio return.
   Half Kelly is the usual safer choice.
3. **Diversification and breadth.** Grinold's fundamental law says the information ratio is roughly skill ×
   √(number of independent bets). The 13 streams here had an average pairwise correlation of 0.00.
4. **Validation.**
   - Rules are fixed before the test, and nothing is tuned on the test window.
   - Choices are made on earlier data only.
   - A walk-forward test re-runs the whole process year by year.
   - Testing many variants inflates the best backtest (Bailey et al. 2014; Harvey, Liu & Zhu 2016).
5. **Practical limits.** Broker leverage caps, financing, and negative-balance protection.

## Data and method

- **Markets:** 51 Dukascopy CFD markets. 52 were requested; orange juice is not on the feed.

  | Asset class | Markets |
  |---|---|
  | Forex | 17 pairs |
  | Metals | gold, silver, copper, platinum, palladium |
  | Energy | Brent, WTI, natural gas, gasoil |
  | Agricultural | cocoa, coffee, cotton, soybeans, sugar |
  | Equity indices | 15 |
  | Bonds | Bund, US T-Bond, Gilt |
  | Crypto | Bitcoin, Ether |

- **Daily bars:** bid prices from Dukascopy's yearly daily files (2017–2025) and hourly files (Jan – Oct 2026).
  Sunday evening is folded into Monday. Each market starts after its last feed gap of more than 7 days, so some
  start later than 2017: platinum and palladium in 2021, the Russell 2000 in March 2019 and the T-Bond in
  February 2019.
- **Spreads:** each market's median hourly ask − bid, sampled in Nov 2025, Feb 2026, Jun 2026 and Oct 2026.
- **Intraday strategies:** Dukascopy 1-minute bid candles for the Nasdaq-100, S&P 500, Dow 30 and DAX, Sep 2024 –
  Oct 2026, with spreads by hour of the day, as in `strategy_search/`.
- **Fills:**
  - Buys fill at bid + spread and sells at the bid, so shorts are stopped out and closed at the ask.
  - A stop that gaps fills at the open.
  - On the day a stop order enters, an exit level inside that day's range counts as hit.
- **Overnight financing (an assumption):** broker rates are not in the price data, so the charge is 1% a year on
  forex positions, 3% a year on metals, energy, agricultural, index and bond positions, and 10% a year on crypto.
  It is charged per night on the position's value. The final portfolio is also shown with financing removed and
  doubled.
- **Account:**
  - $10,000, risking a percentage of the current balance per trade, compounding, with profit and loss booked at
    exit.
  - All open positions together stay under 20:1 leverage; a trade that would need more is made smaller.
  - The balance never goes below $0.
  - Breakout systems hold at most 12 positions in one direction, the Turtle portfolio rule.
- **Periods:**
  - Window: trades entered 1 Nov 2025 – 30 Oct 2026, 52 weeks ending Friday.
  - History: Jan 2018 – Oct 2025 for daily strategies; Oct 2024 – Oct 2025 for intraday ones, because the 1-minute
    data starts in Sep 2024.
- **The target is judged compounded**, i.e. $10,000 must reach $28,003. A plain average of weekly returns can show
  2% while the account shrinks, when the weeks swing widely. Plain averages are shown too.

## Round 1 — published strategies, rules unchanged, 1% risk per trade

| Strategy | Markets | Sharpe before the window | Years positive before | Trades / week | Compound week, last 12 months | Sharpe | Max drawdown | $10k becomes |
|---|---|---|---|---|---|---|---|---|
| Turn of the month (Lakonishok & Smidt 1988; McConnell & Xu 2008) | 15 indices | −0.17 | 2/8 | 3.2 | **+0.42%** | 0.96 | 12.8% | $12,412 |
| RSI(2), no stop (Connors & Alvarez 2008) | 15 indices | 0.19 | 5/8 | 1.7 | +0.30% | 1.91 | 5.2% | $11,657 |
| RSI(2), 2N stop | 15 indices | 0.27 | 5/8 | 1.8 | +0.20% | 1.14 | 8.2% | $11,080 |
| Turtle System 2, 55/20 days (Faith 2007) | 51 | −0.45 | 2/8 | 3.6 | −0.35% | −0.52 | 29.6% | $8,315 |
| Turtle System 1, 20/10 days | 51 | −0.84 | 1/8 | 6.6 | −0.47% | −0.58 | 32.8% | $7,845 |
| Opening-range breakout, variants chosen Oct 2024 – Sep 2025 | 4 | 2.17 (in sample) | 2/2 | 19.7 | −0.47% | −0.06 | 52.9% | $7,812 |
| Opening-range breakout, published (Zarattini & Aziz 2023) | 4 | 0.97 | 1/2 | 19.7 | −1.15% | −0.39 | 67.8% | $5,470 |
| Noise-area momentum, half-hour exits (Zarattini, Aziz & Barbon 2024) | 4 | 0.32 | 0/2 | 18.2 | −1.18% | 0.03 | 71.6% | $5,405 |
| Noise-area momentum, resting stop | 4 | 0.33 | 1/2 | 28.1 | −2.31% | −1.68 | 77.2% | $2,973 |
| Every strategy–market pair positive before the window | 51 pairs | 0.93 (in sample) | 7/8 | 63.2 | −1.45% | 0.09 | 82.1% | $4,687 |
| All of the above in one account | 51 | −0.05 | 1/8 | 102.6 | −1.30% | −0.18 | 77.2% | $5,066 |

Across the 129 strategy–market pairs, the correlation between Sharpe before the window and Sharpe in it was 0.19,
so a rule's history said little about its last 12 months. The best rule in the window, the turn of the month, had
lost money before it. The best rule before the window, the chosen opening-range breakout variants, lost money in
it.

## Rounds 2 and 4 — variants chosen per asset class, on history only

**Variants.** Five families on daily bars, applied to every market they suit:

- **Round 2:**
  - *Breakout / trend:* 20/10, 55/20, 100/50 or 200/100-day channels × a 2N or 4N stop (8 variants).
  - *RSI(2) mean reversion:* thresholds 5/95, 10/90 or 25/75 × exit at the 5- or 10-day average × a 2N, 4N or no
    stop (18 variants).
- **Round 4**, two market-neutral families:
  - *Spread mean reversion between linked markets:* after Gatev, Goetzmann & Rouwenhorst 2006. The pairs are
    Brent/WTI, gold/silver, four European and three US index pairs, and two bond pairs. Each trade is entered at a
    1.5, 2 or 2.5 standard-deviation spread over a 20, 60 or 120-day lookback.
  - *Cross-sectional momentum within each asset class:* after Asness, Moskowitz & Pedersen 2013. It uses past 1,
    3, 6 or 12-1 month returns, with a 3N stop or none.

**Choosing.** For every family and asset class, the variant with the best Sharpe over Jan 2018 – Oct 2025 was
chosen. Across all 248 variant-by-class streams, the correlation between Sharpe before the window and Sharpe in it
was 0.48.

**The 13 streams admitted (positive Sharpe before the window):**

| Family | Asset class | Variant chosen before the window | Sharpe 2018 – Oct 2025 | Sharpe in the window |
|---|---|---|---|---|
| Mean reversion | Energy | RSI(2) 5/95, exit 5-day average, no stop | 1.44 | 1.09 |
| Spread mean reversion | Commodity pairs | 120-day lookback, entry at 1.5 standard deviations | 0.77 | 2.29 |
| Breakout | Crypto | 20/10 days, 4N stop | 0.76 | 1.39 |
| Mean reversion | FX | RSI(2) 5/95, exit 5-day average, 2N stop | 0.56 | 0.37 |
| Mean reversion | Bonds | RSI(2) 5/95, exit 5-day average, no stop | 0.52 | −0.90 |
| Breakout | Energy | 20/10 days, 4N stop | 0.35 | −0.84 |
| Breakout | Agricultural | 55/20 days, 4N stop | 0.33 | 0.06 |
| Mean reversion | Metals | RSI(2) 5/95, exit 10-day average, no stop | 0.28 | 0.94 |
| Mean reversion | Indices | RSI(2) 5/95, exit 5-day average, 2N stop | 0.27 | 1.14 |
| Breakout | Metals | 200/100 days, 2N stop | 0.14 | −0.22 |
| Cross-sectional momentum | Metals | 12-1 months, no stop | 0.12 | −0.61 |
| Cross-sectional momentum | Energy | 1 month, 3N stop | 0.10 | −0.37 |
| Breakout | Bonds | 20/10 days, 2N stop | 0.04 | −1.03 |

Ten family–class combinations were left out because their best variant was negative before the window: breakout
on FX and indices, mean reversion on crypto and agricultural, cross-sectional momentum on FX, indices, bonds and
agricultural, and the index and bond spreads. The intraday strategies were admitted by the same rule but lost
heavily in the window (Round 1). With them included, the portfolio fell to $1,644.

## Round 3 — sizing the streams as one portfolio (Kelly, set on history)

**Method:**
- Each stream's weekly returns at 1% risk are measured over Jan 2018 – Oct 2025.
- Each stream's risk per trade is set to maximise the growth of the combined account over that history, with at
  most 5% risk per trade.
- The intraday streams are left out: 13 months is too short to estimate how they move with the others.

Results in the last 12 months:

| Portfolio | Sizing | Compound week, history (fitted) | Compound week | Plain average week | Sharpe | Max drawdown | $10k becomes | Peak leverage |
|---|---|---|---|---|---|---|---|---|
| Round 3: 10 streams (no market-neutral families) | 1% each | +0.37% | +0.22% | +0.24% | 0.90 | 13.2% | $11,203 | 10:1 |
| | Half Kelly | +0.78% | +0.44% | +0.51% | 1.00 | 22.7% | $12,576 | 20:1 |
| | Full Kelly | +1.32% | +0.74% | +1.02% | 1.00 | 41.9% | $14,655 | 40:1 |
| Round 4: 13 streams | 1% each | +0.44% | +0.39% | +0.41% | 1.37 | 10.2% | $12,214 | 12:1 |
| | Half Kelly | +0.92% | +0.95% | +1.03% | 1.82 | 13.3% | $16,348 | 22:1 |
| | Full Kelly | +1.60% | **+1.73%** | **+2.07%** | 1.82 | 25.6% | $24,402 | 44:1 |

These figures scale each stream's weekly returns up from its 1% account. Re-run trade by trade at the full-Kelly
risks:

| Leverage limit | Financing | Plain average week | Compound week | Max drawdown | $10k becomes |
|---|---|---|---|---|---|
| 20:1 on all open positions | As assumed | +2.17% | +1.93% | 22.8% | $27,038 |
| 20:1 | Doubled | +1.81% | +1.56% | 24.2% | $22,378 |
| 20:1 | Removed | +2.54% | +2.29% | 21.3% | $32,533 |
| None | As assumed | +2.11% | +1.80% | 23.9% | $25,349 |

The half-Kelly version, at 20:1 with financing as assumed, made +0.90% a week compounded ($15,931).

## Round 5 — walk-forward: is it an edge, or was it a good year?

At the start of each test year the whole process runs again on the data before it only:

1. Choose each family-and-class variant.
2. Admit the streams that are positive so far.
3. Set the Kelly risk on the data so far.

The next 12 months are then traded from a fresh $10,000.

| Out-of-sample year | Streams | 1% each | Half Kelly | Full Kelly | Full Kelly, max drawdown | Full Kelly, $10k becomes |
|---|---|---|---|---|---|---|
| Nov 2020 – Oct 2021 | 15 | −0.12%/wk | −0.41%/wk | −1.26%/wk | 75.4% | $5,097 |
| Nov 2021 – Oct 2022 | 14 | +0.10% | +0.28% | +0.38% | 38.2% | $12,234 |
| Nov 2022 – Oct 2023 | 13 | −0.14% | −0.70% | −1.71% | 75.4% | $4,016 |
| Nov 2023 – Oct 2024 | 14 | −0.35% | −1.28% | −2.92% | 80.5% | $2,081 |
| Nov 2024 – Oct 2025 | 14 | −0.35% | −0.27% | −0.73% | 62.2% | $6,771 |
| **Nov 2025 – Oct 2026 (the window)** | 13 | +0.39% | +0.95% | +1.73% | 25.6% | $24,402 |
| Median of the six years | | −0.13% | −0.34% | −1.00% | | |

All figures are compounded per week. No year reached 2% a week compounded. Two of the six years were positive (Nov
2021 – Oct 2022 and the window), and the window was the best of the six for this process.

## Why I stopped here

1. **The closest candidate failed the walk-forward test.** The portfolio that came near 2% a week in the last 12
   months is the output of a process that lost money in four of the five years before. Recommending it would
   mean betting that the next 12 months look like the last 12, and nothing in the data supports that.
2. **The numbers don't allow it.** Compounding 2% a week needs a Sharpe of 1.44 or more, every year. The
   Kelly-sized process had out-of-sample Sharpe ratios of −1.48 to +1.82 across the six years. Over 2018–2025, none
   of the published daily rules had a Sharpe above 0.3 across its markets.
3. **More searching is the trap the walk-forward guards against.** Each extra family or variant raises the chance
   that something shows 2% a week in this one window by luck. Round 4 itself was added after I had seen Round 3's
   window result. The walk-forward years are the test that doesn't depend on those choices, and the process fails
   it.
4. **The leverage isn't available.** Full Kelly needed up to 44:1 across open positions, more than double the
   20:1 retail limit on major indices.

## What a $10k account could expect from this

At 1% risk per trade, the diversified process made −0.35% to +0.39% a week compounded across the six test years
(median −0.13%). Over a year that is anywhere from −17% to +22%, with drawdowns of 10–30%. None of the
rule-based approaches tested here showed a reliable positive edge from year to year. The ones that look best over
one year are the ones most likely to disappoint the next.

## Files

| File | What it is |
|---|---|
| `pipeline/data.py` | Downloads and builds the 51-market daily data and spreads (`fetch`, `build`) → `results/universe.csv` |
| `pipeline/daily.py` | Turtle Systems 1 and 2, RSI(2) with and without a stop, turn of the month → `results/daily_trades.csv.gz` |
| `pipeline/intraday_window.py` | The `strategy_search/` opening-range breakout and noise-area momentum through Oct 2026 → `results/intraday_trades.csv.gz` |
| `pipeline/evaluate.py` | Round 1: every strategy on the $10k account, before and in the window → `results/eval_*.csv` |
| `pipeline/neutral.py` | Round 4 families: spread mean reversion and cross-sectional momentum |
| `pipeline/search.py` | Rounds 2 and 4: variant grid, choice per family and class on history → `results/search_*.csv` (`--without-neutral` → `search_round3_*`) |
| `pipeline/portfolio.py` | Round 3: Kelly sizing set on history → `results/portfolio_*.csv` (`--source search_round3` → `portfolio_round3_*`) |
| `pipeline/walkforward.py` | Round 5: the whole process year by year, and the trade-by-trade window check → `results/walkforward.csv`, `results/window_exact.csv` |

**To reproduce**, from `algo_search/`:

```
python pipeline/data.py fetch && python pipeline/data.py build
(cd ../strategy_search && python pipeline/fetch_m1.py --symbols USATECHIDXUSD USA500IDXUSD USA30IDXUSD DEUIDXEUR --start 2024-09-02 --end 2026-10-30)
cd pipeline
python daily.py && python intraday_window.py && python evaluate.py
python search.py --without-neutral && python portfolio.py --source search_round3
python search.py && python portfolio.py && python walkforward.py
```

The downloads take a few hours because Dukascopy throttles requests.

## Limits

- **Assumed costs:** overnight financing is an assumption. The final portfolio is shown with it removed and
  doubled, and the conclusion holds either way. Spreads are one median per market, so spikes around news are not
  modelled, and spreads in earlier years may have been wider.
- **Rule sources:** Turtle and RSI(2) details come from secondary descriptions of the books, which agree with each
  other. The variants and families tested were my choices; the walk-forward test is the check on them.
- **Kelly approximation:** the Kelly figures scale each stream's 1% weekly returns linearly. For the window this
  was checked trade by trade.
- **Data:** prices are Dukascopy's CFD feed, not exchange data. P&L in non-USD markets is counted in R, without
  currency conversion.

## Sources

- Faith, C. (2007). *Way of the Turtle.* McGraw-Hill. Rules as summarised in
  [MQL5: The Original Turtle Trading Rules](https://www.mql5.com/en/articles/23448).
- Connors, L. & Alvarez, C. (2008). *Short Term Trading Strategies That Work.* TradingMarkets. Rules as summarised
  by [LuxAlgo](https://www.luxalgo.com/library/concept/rsi-2/).
- Lakonishok, J. & Smidt, S. (1988). Are Seasonal Anomalies Real? A Ninety-Year Perspective. *Review of Financial
  Studies* 1(4). McConnell, J. J. & Xu, W. (2008). Equity Returns at the Turn of the Month. *Financial Analysts
  Journal* 64(2). Summaries:
  [Quantpedia](https://quantpedia.com/strategies/turn-of-the-month-in-equity-indexes),
  [CXO Advisory](https://www.cxoadvisory.com/calendar-effects/the-turn-of-the-month-effect/).
- Gatev, E., Goetzmann, W. N. & Rouwenhorst, K. G. (2006). Pairs Trading: Performance of a Relative-Value Arbitrage
  Rule. *Review of Financial Studies* 19(3).
- Asness, C. S., Moskowitz, T. J. & Pedersen, L. H. (2013). Value and Momentum Everywhere. *Journal of Finance*
  68(3).
- Kelly, J. L. (1956). A New Interpretation of Information Rate. *Bell System Technical Journal* 35(4).
- Grinold, R. C. (1989). The Fundamental Law of Active Management. *Journal of Portfolio Management* 15(3).
- Bailey, D. H., Borwein, J. M., López de Prado, M. & Zhu, Q. J. (2014). Pseudo-Mathematics and Financial
  Charlatanism. *Notices of the AMS* 61(5).
- Harvey, C. R., Liu, Y. & Zhu, H. (2016). … and the Cross-Section of Expected Returns. *Review of Financial
  Studies* 29(1).
- Zarattini, C. & Aziz, A. (2023), SSRN 4416622; Zarattini, C., Aziz, A. & Barbon, A. (2024), Swiss Finance
  Institute Research Paper 24-97. See `strategy_search/REPORT.md`.
- ESMA (2018). Product intervention measures on CFDs (retail leverage limits).
- Data: Dukascopy Bank SA historical datafeed (`datafeed.dukascopy.com`).
