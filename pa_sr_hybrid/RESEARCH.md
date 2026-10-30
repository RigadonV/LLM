# Price action and support/resistance: what the evidence says

The research behind [STRATEGY.md](STRATEGY.md). For each discipline: its core principles, what
published research says about each one, and what the hybrid keeps.

**How the sources were checked.** Only published research and the standard practitioner texts
are used. This environment could not open most publisher sites (newyorkfed.org, arxiv.org, SSRN,
ESMA), so findings were checked through search-engine extracts of the papers and their abstracts,
cross-checked between sources where possible. **A number is quoted only where an extract
confirmed it**; where sources disagreed or could not be confirmed (for example the exact sample
months of Osler 2000), the claim is left out or flagged.

**Evidence grades used below:** *strong* = several peer-reviewed studies agree; *mixed* = studies
disagree; *weak* = mostly negative results; *untested* = practitioner teaching with no published
test found.

## 1. Price action: principles and evidence

Price action (PA) trading reads the bars themselves (trend structure, swing points, the shape of
individual candles) instead of indicators.

| Principle | What practitioners teach | What the research says | Grade |
|---|---|---|---|
| **Trade with the trend** | Dow Theory: an uptrend is a series of rallies that exceed the previous peak, with each decline ending above the previous low (Hamilton 1922; Rhea 1932). Brooks: with-trend setups are the higher-probability trades. Elder's Triple Screen: take the direction from the longer timeframe. | Moskowitz, Ooi & Pedersen (2012) find **time-series momentum in every one of 58 liquid futures** (equity indices, currencies, commodities, bonds): returns persist for 1–12 months, then partly reverse. Hurst, Ooi & Pedersen (2017) find strong positive trend-following returns in 67 markets back to 1880. **Against:** Kim, Tse & Wald (2016) show the 2012 result is largely driven by volatility scaling; unscaled, it is close to buy-and-hold. Huang, Li, Wang & Zhou (2020) find little evidence asset by asset: only 8 of 55 assets significant at 10%. | Strong across a portfolio, **contested for any single market** |
| **A signal bar shows who won** | Nison (1991): a hammer only counts after a decline, with a lower shadow at least twice its body; candlestick texts generally ask for confirmation from the next bar. Brooks: the signal bar's strength (close near its extreme) matters. | Candlestick patterns **on their own** show little or no value: Marshall, Young & Rose (2006) on Dow Jones stocks 1992–2002 found none; Fock, Klein & Zwergel (2005) found no predictive power on 5-minute DAX and Bund futures (2002–2003), alone or combined with indicators. Caginalp & Laurent (1998) found some 3-day reversal patterns predictive on S&P 500 stocks (1992–1996). Lu, Chen & Hsu (2015) reconcile the two: profitability depends on **how the trend is defined and how the trade is exited**; with one exit rule some patterns stay profitable after 0.5% costs and a data-snooping correction. | **Weak alone**; may help in context |
| **Let the market confirm** | Brooks: enter on a stop one tick beyond the signal bar, so the market has to move your way to fill you. Second entries (H2/L2) are better than first ones. | No published test found. | Untested (tested in this backtest: V4 vs V4d) |
| **Breakouts usually fail; trade the trap** | Brooks: most attempts to break out of a trading range fail (often quoted as 80%; his own figures vary by context). Wyckoff: a *spring* dips below a range's support and closes back above it; an *upthrust* is the mirror image at resistance. | Osler (2005): when prices reach levels where stop-loss orders cluster, moves accelerate, but the effect is significant for **hours, not days**. A spike through a level that is then reclaimed is consistent with a stop run that ran out. | Plausible, indirectly supported |
| **Chart patterns** | Head-and-shoulders, double tops/bottoms, flags. | Lo, Mamaysky & Wang (2000): on US stocks 1962–1996, several patterns carry **some incremental information**. Chang & Osler (1999): head-and-shoulders on daily dollar exchange rates (1973–1994) was profitable but **dominated by simpler rules**. | Small effect |
| **The trader's equation** | Brooks: probability × reward must exceed (1 − probability) × risk. | Arithmetic, not an empirical claim: at a 2:1 reward-to-risk, a strategy breaks even when it wins 1 trade in 3 (before costs). | (Definition) |

**What price action gets right:** direction (the trend has the best evidence of anything in the
toolkit) and a precise, bar-based place to enter and to be proven wrong. **What it gets wrong:** a
candle pattern in the middle of nowhere is close to noise. Every study that tested patterns on
their own found little.

## 2. Support and resistance: principles and evidence

Support and resistance (S/R) are price areas where falls tend to stop (support) or rises tend to
stop (resistance), usually earlier turning points.

| Principle | What practitioners teach | What the research says | Grade |
|---|---|---|---|
| **Levels at earlier turning points stop prices** | Murphy (1999): a level matters more the longer price traded there, the more volume traded, and the more recently. | Osler (2000), the key study for forex: S/R levels published by six firms for dollar-yen, dollar-mark and dollar-pound (1996–98), against 10,000 sets of random levels. Intraday rates **bounced off published levels 60.8% of the time vs 56.2% for random levels**, and published levels did better in all 16 firm-currency pairs. The predictive power lasted at least 5 business days and varied a lot by firm and currency. Kavajecz & Odders-White (2004): S/R levels **coincide with peaks of resting orders** on the limit order book. Garzarelli et al. (2014): prices bounce off identified S/R levels more often than they cross them. | **Strong but small** |
| **Levels that have held before hold again** | "The more touches, the stronger the level." | Chung & Bellotti (2021): price entering a level that has **bounced more times before is more likely to bounce again**. | Supported |
| **Recent levels matter more** | Murphy: recency. | Chung & Bellotti (2021): the probability of a bounce **falls as the level ages**. Osler (2000): the effect lasted at least 5 days. | Supported |
| **Round numbers are levels** | Watch the "big figure" (1.1000, 150.00, $2,000). | Osler (2003), about 9,700 stop-loss and take-profit orders at a large dealing bank (1999–2000; dollar-yen, dollar-pound, euro-dollar): **take-profit orders cluster at round numbers** (prices reverse there) and **stop-loss orders cluster just beyond them** (prices accelerate once through). Osler (2005): those stop clusters produce price cascades. Bhattacharya, Holden & Jacobsen (2012): in over 100 million stock trades, buying piles up just below round numbers and selling just above. Aggarwal & Lucey (2007): round numbers act as barriers in gold. | **Strong mechanism** |
| **Levels are zones, not lines** | Draw a band, not a line. | Follows from the order clustering above: orders sit around a level, and stops sit just past it. | Supported by mechanism |
| **Broken resistance becomes support (role reversal)** | Murphy: a level penetrated by a significant amount reverses its role. | **No published empirical test found.** | Untested (secondary check in this backtest) |
| **Trade the breakout** | Buy new highs above resistance. | Brock, Lakonishok & LeBaron (1992): trading-range-break rules worked on the Dow 1897–1986. Sullivan, Timmermann & White (1999): with a data-snooping test, **scant evidence of value in 1987–1996**. Neely, Weller & Ulrich (2009): forex rule profits had **disappeared by the early 1990s** for filter and moving-average rules. Park & Irwin (2007): technical rules were profitable in many markets until the early 1990s, but most studies suffer from data snooping and weak cost assumptions. | **Decayed** |

**What S/R gets right:** location. Real orders sit at these levels, so they mark where a move is
likely to pause, where a stop is safe and where to take profit. **What it gets wrong:** a level on
its own is only slightly better than chance (60.8% vs 56.2%), says nothing about the direction of
the bigger move, and simple breakout trading has stopped working.

## 3. The hybrid: what it keeps from each

The two disciplines fail in opposite ways, which is the case for combining them:

- **From S/R, where.** Only trade at a level that has held at least twice in the last year (more
  bounces, more likely to bounce; levels decay). Treat it as a zone. Don't trade into the next
  level, because take-profit orders sit there.
- **From price action, which way and when.** Only trade in the direction of the 12-month trend
  (the best-evidenced principle of all). Wait for a signal bar that rejects the level, or breaks it
  and closes back inside (the trap), and enter on a stop beyond it so the market confirms.
- **From both, the stop.** Beyond the zone *and* the signal bar, plus a buffer, because stop
  orders cluster just past obvious levels and get run.

| Rule in STRATEGY.md | Principle | Evidence |
|---|---|---|
| 1. 12-month trend | Trade with the trend | Moskowitz et al. 2012; Hurst et al. 2017 (contested: Kim et al. 2016; Huang et al. 2020) |
| 2. Swings of the last 250 days | Recent turning points are levels | Osler 2000; Chung & Bellotti 2021 (decay) |
| 3. Key level = 2+ swing points in a ±¼ ATR zone | Levels that held before; zones | Chung & Bellotti 2021; Osler 2003 (clustering) |
| 4–5. Tested from the right side; close back past the level | Rejection or false break | Osler 2000 (bounces); Osler 2005 (short-lived cascades) |
| 6. Pin bar or engulfing | Signal bar | Weak alone (Marshall et al. 2006; Fock et al. 2005), used here only at a level and with the trend |
| 7. Room to the target | Take-profit orders sit at the next level | Osler 2003 |
| 8. Stop entry | Confirmation | Untested; compared with a next-open entry (V4d) |
| 9. Stop beyond zone and bar + 0.1 ATR | Stops cluster just past levels | Osler 2003, 2005 |
| 10. 2R target, 20-day exit | Trader's equation | Arithmetic |

**Two things this research cannot settle,** which is why there is a backtest: whether the
combination beats its parts, and whether any edge survives real spreads and commissions after
2008, when most simple technical rules had already stopped working.

## 4. The base rate: most retail traders lose

- **ESMA (2018):** national regulators' analyses across EU countries found that **74–89% of
  retail CFD accounts typically lose money**, with average losses of €1,600 to €29,000 per client.
  ESMA capped leverage at 30:1 on major currency pairs and 20:1 on gold, major indices and
  non-major pairs.
- **Chague, De-Losso & Giovannetti (2019):** of the people who day traded Brazilian equity index
  futures for at least 300 days (2013–2015 starters), **97% lost money**.
- **Usage is not evidence:** Taylor & Allen (1992) found 90% of London chief forex dealers put
  some weight on technical analysis over intraday-to-one-week horizons, and Menkhoff & Taylor
  (2007) document how widespread it is. Wide use does not mean it pays.

So the starting assumption is that a retail strategy loses money, and the hybrid has to show
otherwise on real data, after costs.

## Sources

**Support and resistance, order flow, round numbers**
- Osler, C. (2000). Support for Resistance: Technical Analysis and Intraday Exchange Rates. *FRBNY Economic Policy Review* 6(2), 53–68. [PDF](https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf) · [RePEc](https://ideas.repec.org/a/fip/fednep/y2000ijulp53-68nv.6no.2.html) · [NY Fed summary](https://www.newyorkfed.org/newsevents/news/research/2000/rp000622a)
- Osler, C. (2003). Currency Orders and Exchange Rate Dynamics: An Explanation for the Predictive Success of Technical Analysis. *Journal of Finance* 58(5), 1791–1819. [Wiley](https://onlinelibrary.wiley.com/doi/abs/10.1111/1540-6261.00588) · [NY Fed Staff Report 125](https://www.newyorkfed.org/research/staff_reports/sr125.html)
- Osler, C. (2005). Stop-loss orders and price cascades in currency markets. *Journal of International Money and Finance* 24(2), 219–241. [RePEc](https://ideas.repec.org/a/eee/jimfin/v24y2005i2p219-241.html) · [NY Fed Staff Report 150](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.html)
- Kavajecz, K. & Odders-White, E. (2004). Technical Analysis and Liquidity Provision. *Review of Financial Studies* 17(4), 1043–1071. [RePEc](https://ideas.repec.org/a/oup/rfinst/v17y2004i4p1043-1071.html)
- Garzarelli, F., Cristelli, M., Pompa, G., Zaccaria, A. & Pietronero, L. (2014). Memory effects in stock price dynamics: evidences of technical trading. *Scientific Reports* 4, 4487. [arXiv](https://www.arxiv.org/abs/1110.5197)
- Chung, K. & Bellotti, A. (2021). Evidence and Behaviour of Support and Resistance Levels in Financial Time Series. arXiv:2101.07410. [RePEc](https://ideas.repec.org/p/arx/papers/2101.07410.html)
- Bhattacharya, U., Holden, C. & Jacobsen, S. (2012). Penny Wise, Dollar Foolish: Buy–Sell Imbalances On and Around Round Numbers. *Management Science* 58(2), 413–431. [INFORMS](https://pubsonline.informs.org/doi/10.1287/mnsc.1110.1364)
- Aggarwal, R. & Lucey, B. (2007). Psychological barriers in gold prices? *Review of Financial Economics* 16(2), 217–230. [RePEc](https://ideas.repec.org/a/wly/revfec/v16y2007i2p217-230.html)

**Technical trading rules**
- Brock, W., Lakonishok, J. & LeBaron, B. (1992). Simple Technical Trading Rules and the Stochastic Properties of Stock Returns. *Journal of Finance* 47(5), 1731–1764. [RePEc](https://ideas.repec.org/a/bla/jfinan/v47y1992i5p1731-64.html)
- Sullivan, R., Timmermann, A. & White, H. (1999). Data-Snooping, Technical Trading Rule Performance, and the Bootstrap. *Journal of Finance* 54(5), 1647–1691. [DOI](https://doi.org/10.1111/0022-1082.00163)
- Neely, C., Weller, P. & Ulrich, J. (2009). The Adaptive Markets Hypothesis: Evidence from the Foreign Exchange Market. *Journal of Financial and Quantitative Analysis* 44(2), 467–488. [RePEc](https://econpapers.repec.org/RePEc:cup:jfinqa:v:44:y:2009:i:02:p:467-488_09)
- Park, C.-H. & Irwin, S. (2007). What do we know about the profitability of technical analysis? *Journal of Economic Surveys* 21(4), 786–826. [RePEc](https://ideas.repec.org/a/bla/jecsur/v21y2007i4p786-826.html)
- Taylor, M. & Allen, H. (1992). The use of technical analysis in the foreign exchange market. *Journal of International Money and Finance* 11(3), 304–314. [RePEc](https://econpapers.repec.org/RePEc:eee:jimfin:v:11:y:1992:i:3:p:304-314)
- Menkhoff, L. & Taylor, M. (2007). The Obstinate Passion of Foreign Exchange Professionals: Technical Analysis. *Journal of Economic Literature* 45(4), 936–972. [RePEc](https://econpapers.repec.org/RePEc:aea:jeclit:v:45:y:2007:i:4:p:936-972)

**Candles, chart patterns, trend**
- Marshall, B., Young, M. & Rose, L. (2006). Candlestick technical trading strategies: Can they create value for investors? *Journal of Banking & Finance* 30(8), 2303–2323. [RePEc](https://econpapers.repec.org/RePEc:eee:jbfina:v:30:y:2006:i:8:p:2303-2323)
- Fock, H., Klein, C. & Zwergel, B. (2005). Performance of Candlestick Analysis on Intraday Futures Data. *Journal of Derivatives* 13(1), 28–40. [EconBiz](https://www.econbiz.de/Record/performance-of-candlestick-analysis-on-intraday-futures-data/10005920607)
- Caginalp, G. & Laurent, H. (1998). The predictive power of price patterns. *Applied Mathematical Finance* 5(3–4), 181–205. [RePEc](https://econpapers.repec.org/RePEc:taf:apmtfi:v:5:y:1998:i:3-4:p:181-205)
- Lu, T.-H., Chen, Y.-C. & Hsu, Y.-C. (2015). Trend definition or holding strategy: What determines the profitability of candlestick charting? *Journal of Banking & Finance* 61, 172–183. [RePEc](https://econpapers.repec.org/RePEc:eee:jbfina:v:61:y:2015:i:c:p:172-183)
- Lo, A., Mamaysky, H. & Wang, J. (2000). Foundations of Technical Analysis. *Journal of Finance* 55(4), 1705–1765. [NBER w7613](https://www.nber.org/system/files/working_papers/w7613/w7613.pdf)
- Chang, P.H.K. & Osler, C. (1999). Methodical Madness: Technical Analysis and the Irrationality of Exchange-Rate Forecasts. *Economic Journal* 109(458), 636–661. [RePEc](https://ideas.repec.org/a/ecj/econjl/v109y1999i458p636-61.html)
- Moskowitz, T., Ooi, Y.H. & Pedersen, L.H. (2012). Time series momentum. *Journal of Financial Economics* 104(2), 228–250. [RePEc](https://econpapers.repec.org/RePEc:eee:jfinec:v:104:y:2012:i:2:p:228-250)
- Hurst, B., Ooi, Y.H. & Pedersen, L.H. (2017). A Century of Evidence on Trend-Following Investing. *Journal of Portfolio Management*, Fall 2017. [AQR](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- Kim, A., Tse, Y. & Wald, J. (2016). Time series momentum and volatility scaling. *Journal of Financial Markets* 30, 103–124. [RePEc](https://econpapers.repec.org/RePEc:eee:finmar:v:30:y:2016:i:c:p:103-124)
- Huang, D., Li, J., Wang, L. & Zhou, G. (2020). Time series momentum: Is it there? *Journal of Financial Economics* 135(3), 774–794. [RePEc](https://econpapers.repec.org/RePEc:eee:jfinec:v:135:y:2020:i:3:p:774-794)

**Practitioner texts** (principles as taught; not evidence)
- Brooks, A. *Trading Price Action Trends* (2011), *Trading Ranges* and *Reversals* (2012), Wiley. Breakout-failure rule as discussed on [his course forum](https://www.brookstradingcourse.com/support-forum/12-market-cycle/breakout-fail/).
- Nison, S. (1991). *Japanese Candlestick Charting Techniques*. New York Institute of Finance.
- Murphy, J. (1999). *Technical Analysis of the Financial Markets*. New York Institute of Finance.
- Elder, A. (1993). *Trading for a Living*. Wiley (Triple Screen).
- Hamilton, W.P. (1922). *The Stock Market Barometer*; Rhea, R. (1932). *The Dow Theory*. Summary: [Incredible Charts](https://www.incrediblecharts.com/technical/dow_theory_trends.php).
- Wyckoff method (springs and upthrusts): [summary](https://www.tradingsim.com/blog/wyckoff-method-trading).

**Retail outcomes and costs**
- ESMA (2018). ESMA agrees to prohibit binary options and restrict CFDs to protect retail investors. [ESMA](https://www.esma.europa.eu/node/84933)
- Chague, F., De-Losso, R. & Giovannetti, B. (2019). Day Trading for a Living? [RePEc](https://econpapers.repec.org/RePEc:fgv:eesptd:525)
- IC Markets, Raw Spread account: $3.50 per lot per side. [IC Markets](https://www.icmarkets.com/global/en/start-forex-trading)

**Price data:** Dukascopy Bank SA historical data feed (`datafeed.dukascopy.com`): daily and hourly
bid and ask candles.
