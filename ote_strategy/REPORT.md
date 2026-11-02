# OTE strategy backtests: Nasdaq-100 and gold, London session

**What was tested:** the strategy in `OTE_Trading_Strategy.pdf`, and changes to it taken from ICT's own
descriptions of the optimal trade entry (OTE).

**Data and window:** Dukascopy 1-minute data for the Nasdaq-100 CFD (USATECHIDXUSD) and gold (XAUUSD). The test
window is the last 12 months, 3 Nov 2025 – 30 Oct 2026, with entries only in the London session. As a robustness
check only, the same tests were also run on the 12 months before, 4 Nov 2024 – 31 Oct 2025.

**Result: no version of the strategy works consistently.**

- **Gold, rules as written** (stop read as 50 pips = $5): 330 trades, 12% winners, **−0.22R a trade**. $10,000 at
  1% risk became **$4,675**, and all nine gold variants lost.
- **Nasdaq-100, rules as written** (50-point stop): 273 trades, 15% winners, **−0.135R a trade**, $10,000 →
  $6,578.
- **ICT's own OTE rules** (62–79% zone, stop beyond the swing, −0.27/−0.62 targets, London killzone, Asian-range
  sweep) helped in some tests and hurt in others.
  - Across the four tests (two markets × two years), **no version made money in all four**.
  - Every version averaged between −0.14R and +0.003R a trade.
  - The full ICT London model took only 12–20 trades a year, and its average ranged from +0.77R to −0.80R a trade
    across tests.
- **The PDF's statistics don't appear in either market:**

  | | PDF | Nasdaq-100 base | Gold base |
  |---|---|---|---|
  | Win rate | 84.4% | 15% | 12% |
  | Trades reaching 3R | 82.1% | 24% | 21% |

  None of the 17 versions came close; the highest was about 43%, on 12–14 trades.

## ICT's OTE according to public sources

ICT publishes no closed written rules. What follows comes from educators' write-ups, indicator documentation and
vendors, and the sources broadly agree on the core:

- **Zone:** the OTE zone is the 62%–79% retracement of an impulse leg, with 70.5% as its midpoint or "sweet spot".
- **Trigger:** a setup only counts after displacement and a market structure shift (MSS); the zone alone is not the
  trigger.
- **Stop:** most place it beyond the 100% level, the swing that started the leg, rather than at a fixed distance.
- **Targets:** the −0.27 extension as the first target and −0.62 as the second. Some use −1, −1.5, −2 or the
  previous high or low instead.
- **Timing:**
  - The London killzone is 02:00–05:00 New York time, and the Asian range is 20:00–00:00 New York time.
  - The "Judas swing" is a false push through the Asian high or low that takes out stops. Price then closes back
    inside, displaces and shifts structure.
  - One model targets the other side of the Asian range.
- **Evidence:** no audited or independent statistics exist. The vendor win rates found (60–80%) don't say how they
  were measured, and one critical source states that no reliable published win rate exists.

How the PDF differs from that description:

| | ICT (public sources) | The PDF |
|---|---|---|
| Zone and entry | 62–79%, entries from 62% to 70.5% | 70.5–79%, entry at 70.5% |
| Stop | Beyond the swing that started the leg | A fixed 50 points |
| Target | −0.27 / −0.62 extensions, or the opposite liquidity | 3–4R |
| Session | London killzone, 02:00–05:00 New York | 02:00–09:30 New York (London and the New York open) |
| Trigger | Liquidity sweep → displacement → structure shift | Trend alignment + OB/FVG in the zone |

## The changes tested

Each change was applied on its own on top of the PDF's rules, then combined. Every change was fixed before any
result was seen.

| Change | Rule |
|---|---|
| OTE zone 62–79%, entry at 62% | The order goes at the 62% level, and the OB/FVG must overlap 62–79%. |
| Stop beyond the swing | The stop goes beyond the swing that started the range by 5% of the range, instead of a fixed distance. It must be at least 3 spreads from the entry. Tested with a 4R target, the −0.27 extension and the −0.62 extension. |
| London killzone only | Entries 02:00–05:00 New York only. |
| Asian-range sweep first (Judas swing) | The range must start, after midnight New York, with a move beyond the Asian range's (20:00–00:00) high or low. |
| ICT London model | All of the above, plus displacement (a fair value gap in the leg). Entry at 70.5% of a 62–79% zone, stop beyond the swing. Half the position comes off at −0.27 and the stop moves to breakeven; the rest goes at −0.62. A second version aims the whole position at the other side of the Asian range. |

## Gold, last 12 months, 02:00–09:30 New York

**The stop.** The PDF's "50 points" is ambiguous on gold:
- at the MT4/MT5 point of $0.01 it is $0.50, less than gold's spread;
- at $1 a point it is $50, more than most London sessions' whole range.

So the base reads it as 50 pips, which is $5.00, with a $10 stop as a variant.

**The spread.** Dukascopy's gold spread in the London session was $0.57–0.68, which is 11–14% of a $5 stop, or
about 0.12R on every trade. A tighter broker would cut that cost, but even adding 0.12R back, the base would still
lose about 0.1R a trade.

| Variant | Trades | Win / breakeven / loss | Avg R | Total R | Positive weeks | Worst week | Max drawdown | $10k becomes |
|---|---|---|---|---|---|---|---|---|
| **Base (as written, $5 stop, target 4R)** | 330 | 12% / 17% / 71% | **−0.218** | −71.8 | 25% | −7.7% | 53.3% | **$4,675** |
| Target 3R | 332 | 17% / 12% / 70% | −0.190 | −63.0 | 33% | −7.7% | 50.6% | $5,136 |
| + 1-hour 50 EMA trend filter | 195 | 10% / 16% / 74% | −0.364 | −70.9 | 27% | −5.9% | 51.8% | $4,818 |
| + midnight-open filter | 176 | 14% / 20% / 66% | −0.119 | −21.0 | 33% | −5.9% | 21.5% | $7,919 |
| Swings of 1 candle each side | 356 | 13% / 15% / 72% | −0.201 | −71.7 | 33% | −7.7% | 53.8% | $4,648 |
| Swings of 3 candles each side | 276 | 12% / 18% / 70% | −0.222 | −61.3 | 23% | −6.8% | 47.9% | $5,215 |
| No OB/FVG needed | 427 | 13% / 18% / 70% | −0.187 | −79.8 | 23% | −8.7% | 57.9% | $4,255 |
| Close at 09:30 | 330 | 16% / 15% / 69% | −0.201 | −66.5 | 27% | −7.7% | 50.5% | $4,947 |
| $10 stop instead of $5 | 288 | 15% / 18% / 67% | −0.160 | −46.2 | 27% | −5.9% | 39.3% | $6,073 |

The gold base by month, in R:

| Nov | Dec | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| −7.0 | −13.0 | −3.8 | −7.0 | −2.0 | +4.0 | −17.0 | +2.0 | +1.0 | −9.1 | −7.0 | −13.0 |

Three of 12 months were positive.

## Nasdaq-100, last 12 months, 02:00–09:30 New York (from the first test)

| Variant | Trades | Win / breakeven / loss | Avg R | Total R | Positive weeks | Worst week | Max drawdown | $10k becomes |
|---|---|---|---|---|---|---|---|---|
| **Base (as written, 50 points, target 4R)** | 273 | 15% / 19% / 66% | **−0.135** | −36.9 | 37% | −16.0% | 40.8% | **$6,578** |
| Target 3R | 278 | 22% / 13% / 65% | −0.061 | −16.9 | 35% | −16.0% | 30.3% | $8,061 |
| + 1-hour 50 EMA trend filter | 186 | 19% / 21% / 60% | +0.043 | +7.9 | 48% | −14.3% | 24.5% | $10,374 |
| + midnight-open filter | 142 | 18% / 14% / 68% | −0.094 | −13.4 | 42% | −16.0% | 33.2% | $8,444 |
| Swings of 1 candle each side | 305 | 16% / 15% / 69% | −0.105 | −32.0 | 37% | −7.7% | 40.2% | $6,941 |
| Swings of 3 candles each side | 219 | 13% / 19% / 68% | −0.267 | −58.5 | 37% | −17.7% | 46.9% | $5,356 |
| No OB/FVG needed | 328 | 15% / 19% / 66% | −0.125 | −40.9 | 29% | −13.6% | 42.4% | $6,265 |
| Close at 09:30 | 273 | 28% / 11% / 61% | −0.098 | −26.6 | 44% | −15.3% | 27.9% | $7,389 |

**One gap trade.** On 23 Mar 2026 a Nasdaq-100 short lost 14.3R when price jumped 716 points through its
breakeven stop across a 13-minute gap in the feed. As a plain breakeven instead, the base year would be −22.5R.

## Every version, in both markets and both years

Average R per trade. The last 12 months is the test that was asked for; the year before is a robustness check
only. The ICT London model's trade count is shown in brackets.

| Version | Nasdaq-100, last 12 months | Nasdaq-100, year before | Gold, last 12 months | Gold, year before | Positive in | Average |
|---|---|---|---|---|---|---|
| PDF rules as written | −0.135 | +0.102 | −0.218 | −0.012 | 1/4 | −0.066 |
| Target 3R | −0.061 | +0.086 | −0.190 | +0.014 | 2/4 | −0.038 |
| + 1-hour 50 EMA trend filter | +0.042 | +0.028 | −0.364 | +0.147 | 3/4 | −0.037 |
| + midnight-open filter | −0.094 | −0.069 | −0.119 | −0.072 | **0/4** | −0.089 |
| Swings of 1 candle each side | −0.105 | −0.014 | −0.202 | +0.102 | 1/4 | −0.054 |
| Swings of 3 candles each side | −0.267 | +0.238 | −0.222 | +0.084 | 2/4 | −0.042 |
| No OB/FVG needed | −0.125 | +0.091 | −0.187 | +0.039 | 2/4 | −0.045 |
| Close at 09:30 | −0.098 | −0.045 | −0.201 | +0.008 | 1/4 | −0.084 |
| OTE zone 62–79%, entry at 62% | −0.022 | +0.033 | −0.238 | −0.039 | 1/4 | −0.067 |
| Stop beyond the swing, target 4R | +0.191 | −0.073 | −0.136 | −0.014 | 1/4 | −0.008 |
| Stop beyond the swing, target −0.27 | +0.150 | −0.094 | −0.149 | +0.040 | 2/4 | −0.013 |
| Stop beyond the swing, target −0.62 | +0.172 | −0.059 | −0.115 | +0.014 | 2/4 | +0.003 |
| London killzone only, 02:00–05:00 | −0.207 | +0.213 | −0.372 | −0.209 | 1/4 | −0.144 |
| Asian-range sweep first (Judas swing) | −0.016 | +0.110 | +0.085 | −0.217 | 2/4 | −0.010 |
| ICT London model, −0.27 / −0.62 | +0.753 (14) | −0.490 (17) | +0.326 (12) | −0.588 (20) | 2/4 | 0.000 |
| ICT London model, other side of Asia | +0.772 (14) | −0.492 (17) | +0.274 (12) | −0.799 (20) | 2/4 | −0.061 |

How far trades went, compared with the PDF's own statistics:

| | PDF | Nasdaq-100 base | Gold base |
|---|---|---|---|
| Win rate | 84.4% | 15.0% (18.6% excl. breakeven) | 12.4% (15.0% excl. breakeven) |
| Trades reaching 3R / 4R / 5R before the stop | 82.1% / 66.1% / 57.1% | 23.8% / 16.9% / 11.7% | 20.6% / 15.2% / 12.4% |
| Average favourable move | 8.4R | 2.1R | 2.2R |
| Average adverse move | 11.7 points | 47.5 points (of a 50-point stop) | $5.32 (of a $5 stop) |
| Average trade time | 32.9 (unit not stated) | 137 minutes | 41.5 minutes |

## Why no version holds up

- **Results flip between years and markets.** The best single change on the Nasdaq-100 in the last 12 months was the stop
  beyond the swing, at +0.19R. It lost in the year before (−0.07R) and on gold (−0.14R). The killzone-only rule
  made +0.21R in one test and lost in the other three. A version that is good in one year and bad in the next has
  no stable edge; it is showing the year's noise.
- **The full ICT London model is too rare to judge.** It took 12–20 trades a year, and its average moved from
  +0.75R to −0.49R and from +0.33R to −0.59R between years. Twenty trades cannot separate skill from luck.
- **The PDF's numbers would need near-perfect entries.** An average adverse move of 11.7 points on a 50-point stop,
  with 82% of trades reaching 3R, means its trades almost never went against the entry. In the data, OTE entries
  went most of the way to the stop on average, in both markets. That points to entries picked with hindsight or a
  small, selective sample. It does not point to details of the mechanical reading, because none of 17 versions
  came close.
- **Gold's trade time fits the PDF, its other statistics don't.** Trades on gold took 41.5 minutes on average,
  close to the PDF's 32.9, so the PDF may have been written for gold. Its other numbers still don't appear there.

## The rules as tested (PDF version)

Judgement calls are marked *.

| PDF rule | How it was made mechanical |
|---|---|
| 15-minute swing range | A swing high is a 15-minute candle whose high is above the 2 candles on each side (variants: 1 and 3), confirmed when the 2nd candle after it closes. A bullish range runs from the lowest low since the last swing low to a new swing high; bearish is the mirror image. |
| *Trend; *market condition | The range must break structure in its direction, so only trending legs are traded. Variant: also on the right side of the 1-hour 50 EMA. |
| OTE zone 0.705–0.79; 15M/30M/1H OB or FVG | Measured on the range. An OB or FVG formed during the range, on any of those timeframes, must overlap the zone. |
| *Key opening levels | Variant: longs below and shorts above the New York midnight open. |
| Entry at 0.705 | A limit order, placed when the swing is confirmed. It is kept until filled, until price takes out the start of the range, until a newer range replaces it, or until the session ends. |
| Stop 50 points; breakeven at 2R; target 4R | The Nasdaq-100 stop is 50 points; gold's is $5 (variant $10). At most 2 losses a day and one trade at a time. Anything still open at 16:00 New York is closed (variant: at 09:30). |

**Prices, fills and account:**
- Dukascopy's own ask − bid by hour. Buys fill at the ask, and shorts are stopped out and take profit on the ask.
- A stop that price jumps over fills at the next price. Within one minute the stop counts before a target, and on
  the entry minute only the stop is checked.
- $10,000 account, 1% risk per trade, compounding, all positions under 20:1 leverage.

**Checks:** on the Nasdaq-100 trade list, each trade's OTE levels match its swing range. Fills are at the order
level, stops come out at −1R and targets at +4R. After the code was generalised for gold and the ICT rules, the
Nasdaq-100 base reproduced exactly: 273 trades, −36.85R.

## Limits

- **ICT's rules:** there is no closed rulebook. The changes follow the public descriptions above, and each one is a
  single reading of rules that leave room for judgement.
- **Data:** the feed is a CFD feed (Dukascopy), not CME futures. Gold's spread here is wider than at some
  raw-spread brokers.
- **Intraminute order:** with 1-minute data the order of events inside a minute is unknown, so the pessimistic
  order is used.
- **Sample size:** 12 months per test, and only 12–20 trades a year for the full ICT model.

## Files

- `pipeline/ote.py`: the backtest. Run as `--market USATECHIDXUSD|XAUUSD --suite pdf|ict --period last|prior`.
- `results/<prefix>_variants.csv`: one row per version. The prefix is `ote` (Nasdaq-100, PDF rules), `ote_gold`,
  `ote_ict_nq` or `ote_ict_gold`; `_prior` marks the year-before check.
- `results/<prefix>_trades.csv`: every trade of every version, with its swing range, OTE levels, stop, R, MFE and
  MAE. `<prefix>_base_trades.csv` and `<prefix>_base_by_month.csv` hold the base version.

**To reproduce:** run these from `pipeline/`, using the 1-minute data from `strategy_search/` (its `fetch_m1.py`
downloads it, including `--symbols XAUUSD`):

```
for m in USATECHIDXUSD XAUUSD; do for s in pdf ict; do for p in last prior; do
  python ote.py --market $m --suite $s --period $p; done; done; done
```

## Sources

- **ICT's OTE:**
  - [TradingFinder](https://tradingfinder.com/education/forex/ict-optimal-trade-entry-pattern)
  - [ChartingLens](https://chartinglens.com/blog/ict-optimal-trade-entry-ote)
  - [LuxAlgo](https://www.luxalgo.com/library/concept/optimal-trade-entry/)
  - [Backtrex OTE guide](https://backtrex.com/en/blog/ict-optimal-trade-entry-ote-fibonacci-guide)
  - [Backtrex Fibonacci settings](https://backtrex.com/en/blog/ict-fibonacci-settings-levels-complete-guide)
- **Killzones, Asian range and the Judas swing:**
  - [Quantum Algo](https://www.quantum-algo.com/blog/guides/ict-trading-strategy-complete-guide/)
  - [El Trader Financiado](https://www.eltraderfinanciado.com/ar/blog/killzones-ict)
  - [ChartingLens kill zones](https://chartinglens.com/blog/ict-kill-zones-guide)
  - [FX Replay Judas Swing model](https://fxreplay.com/strategies/judas-swing-model)
  - [FX Replay backtesting session](https://www.fxreplay.com/events/ict-judas-swing-backtesting-session)
- **Vendor win-rate claims:** [TakeProfit](https://takeprofitapp.com/en/learn/ict-optimal-trade-entry-ote)
- **Data:** Dukascopy Bank SA historical datafeed (`datafeed.dukascopy.com`).
