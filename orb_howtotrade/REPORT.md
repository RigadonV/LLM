# ORB strategy backtest: gold and Nasdaq-100, 15-minute candles, last 12 months

**Strategy:** howtotrade.com's "Opening Range Breakout (ORB) Trading Strategy" PDF, as supplied. Its four steps:

1. **Trend:** read it from the 50 and 200 EMA.
2. **Opening range:** the high and low of the first 30 minutes, as in its worked example.
3. **Entry:** wait for "a full-body candle break" of the range in the trend's direction, with a volume spike as
   confirmation.
4. **Stop and target:** stop either beyond the breakout candle or at the other side of the range; target 2 or 3 R.

**Test setup:**
- **Markets:** Nasdaq-100 (Dukascopy USATECHIDXUSD CFD) and gold (XAUUSD), on 15-minute candles built from
  Dukascopy's 1-minute bid prices.
- **Window:** 3 Nov 2025 – 30 Oct 2026.
- **Account:** $10,000 at 1% risk per trade; the PDF sets no risk level.

**Result: on the Nasdaq-100 the strategy roughly broke even; on gold it lost a little. No version made
meaningful money.**

| | Nasdaq-100 | Gold |
|---|---|---|
| Trades | 145 (2.8 a week) | 178 (3.4 a week) |
| Average per trade, four PDF versions | +0.01R to +0.08R | −0.04R to −0.06R |
| $10,000 became | $9,980 – $11,046 | $8,843 – $9,186 |
| Win rate | 36–48% | 31–38% |

The PDF says "ORB enthusiasts often report winning rates ranging from 42% to 65%". The Nasdaq-100 with the range
stop sits inside that band at 48%, but it still barely makes money. The win rate isn't the problem: the average
trade is close to zero.

## The rules as tested

Choices the PDF leaves open are marked *.

| PDF step | How it was made mechanical |
|---|---|
| 1. Trend: 50 and 200 EMA | *On the 15-minute chart. 50 EMA above 200 EMA: longs only; below: shorts only. Variants: price above or below both EMAs, and no trend filter. |
| 2. Opening range: first 30 minutes | High and low of the session's first two 15-minute candles. *Nasdaq-100: 09:30–16:00 New York. *Gold trades almost 24 hours; the base uses the COMEX day session, 08:20–13:30 New York, which is gold's daily open in the futures market the PDF recommends. The London session, 03:00–11:30 New York, is a variant. Variant: a 15-minute range. |
| 3. Entry: "a full-body candle break", not a limit order at the level | A 15-minute candle closes beyond the range with its body in the breakout direction: a bullish candle closing above the high, or a bearish one below the low. Entry at the next candle's open. *One trade a day, from a breakout candle closing within 3 hours of the open. Variant: stricter full body, with the body at least 70% of the candle. |
| 3. Volume spike | *Not in the base, because this data can't show it (see below). Two readings are variants. |
| 4. Stop: below the breakout candle, or at the other side of the range; target 2R or 3R | All four combinations are tested. *Anything still open at the session close is closed. |

**The volume spike can't be tested properly here.** Dukascopy's volume is its own liquidity providers', not
exchange volume, and its behaviour changed during the year:
- Its level on the Nasdaq-100 rose about tenfold, from a median of 0.10 to 1.05 a candle between November 2025 and
  October 2026.
- US-session volume relative to the previous 20 candles fell from 1.75× to 1.1×.

The first run, with "above 1.5× the previous 20 candles", found almost no Nasdaq-100 trades in September and
October because of this. So the base has no volume condition, and both readings are shown as variants:
- above 1.5× the previous 20 candles;
- above 1.5× the average for the same 15-minute slot over the previous 20 days.

**Prices and fills:**
- Dukascopy's own ask − bid by hour: 1.2 points on the Nasdaq-100 and $0.61 on gold in session. Longs buy at the
  ask, and shorts are stopped out and take profit on the ask.
- Stops and targets are checked on the 1-minute prices inside each 15-minute candle, so when one candle touches
  both, the one reached first counts.
- $10,000 account, 1% of the current balance per trade, compounding, positions under 20:1 leverage.

**Checks:**
- Sampled trades were recomputed from the raw 1-minute prices: opening range, breakout candle, EMA trend, entry at
  the next open plus the spread, stop and target.
- Stops come out at −1R and targets at +2R / +3R.

## Nasdaq-100, 09:30–16:00 New York

| Version | Trades | Win rate | Target / stop / session close | Avg R | Total R | Avg risk | Positive weeks | Worst week | Max drawdown | $10k becomes |
|---|---|---|---|---|---|---|---|---|---|---|
| **Stop at other side of range, 2R** | 145 | 48% | 2% / 21% / 77% | **+0.042** | +6.1 | 231 pts | 50% | −2.4% | 9.4% | **$10,588** |
| Stop at other side of range, 3R | 145 | 48% | 1% / 21% / 79% | +0.052 | +7.6 | 231 pts | 50% | −2.4% | 9.4% | $10,742 |
| Stop beyond breakout candle, 2R | 145 | 37% | 25% / 59% / 16% | +0.007 | +1.0 | 88 pts | 42% | −3.9% | 18.9% | $9,980 |
| Stop beyond breakout candle, 3R | 145 | 36% | 14% / 60% / 26% | +0.080 | +11.6 | 88 pts | 46% | −3.9% | 18.5% | $11,046 |
| *Variants of the first version:* | | | | | | | | | | |
| Opening range of 15 minutes | 165 | 48% | 7% / 30% / 64% | +0.066 | +10.8 | 198 pts | 46% | −3.0% | 10.9% | $11,061 |
| Trend: price above/below both EMAs | 184 | 48% | 2% / 20% / 78% | +0.019 | +3.5 | 233 pts | 48% | −3.2% | 13.5% | $10,302 |
| + volume spike vs the previous 20 candles | 100 | 49% | 3% / 25% / 72% | +0.050 | +5.0 | 243 pts | 44% | −2.2% | 7.3% | $10,478 |
| + volume spike vs the same time of day | 9 | 33% | 0% / 33% / 67% | −0.327 | −2.9 | 425 pts | 2% | −1.8% | 2.9% | $9,708 |
| Stricter full body (70% of the candle) | 101 | 49% | 2% / 14% / 84% | +0.086 | +8.6 | 259 pts | 40% | −1.9% | 5.5% | $10,876 |
| No trend filter | 214 | 46% | 2% / 22% / 75% | −0.023 | −5.0 | 221 pts | 38% | −3.3% | 15.1% | $9,452 |

With the stop at the other side of the 30-minute range, the risk averaged 231 points, so a 2R target sat about
460 points away. Only 2% of trades reached it, and 77% were closed at 16:00, averaging +0.27R. In practice that
version means "hold the breakout direction until the close". The breakout-candle stop is tighter, so it is hit
more often (59%) and reaches more targets (25%), but ends at about the same place.

## Gold, COMEX day session 08:20–13:30 New York

| Version | Trades | Win rate | Target / stop / session close | Avg R | Total R | Avg risk | Positive weeks | Worst week | Max drawdown | $10k becomes |
|---|---|---|---|---|---|---|---|---|---|---|
| **Stop at other side of range, 2R** | 178 | 38% | 13% / 38% / 49% | **−0.048** | −8.6 | $27.74 | 37% | −3.0% | 17.8% | **$9,085** |
| Stop at other side of range, 3R | 178 | 38% | 5% / 38% / 57% | −0.063 | −11.2 | $27.74 | 40% | −3.0% | 19.0% | $8,843 |
| Stop beyond breakout candle, 2R | 178 | 35% | 25% / 58% / 16% | −0.039 | −7.0 | $15.24 | 37% | −3.9% | 15.3% | $9,186 |
| Stop beyond breakout candle, 3R | 178 | 31% | 14% / 62% / 24% | −0.046 | −8.1 | $15.24 | 40% | −3.9% | 21.5% | $9,046 |
| *Variants of the first version:* | | | | | | | | | | |
| Opening range of 15 minutes | 192 | 36% | 20% / 45% / 35% | −0.035 | −6.8 | $22.80 | 38% | −3.8% | 17.7% | $9,224 |
| Trend: price above/below both EMAs | 214 | 39% | 12% / 37% / 50% | −0.048 | −10.2 | $30.80 | 42% | −4.9% | 18.2% | $8,928 |
| + volume spike vs the previous 20 candles | 136 | 40% | 13% / 32% / 54% | −0.000 | −0.0 | $28.93 | 38% | −2.6% | 9.9% | $9,926 |
| + volume spike vs the same time of day | 26 | 50% | 15% / 19% / 65% | +0.201 | +5.2 | $45.34 | 25% | −1.5% | 3.4% | $10,523 |
| Stricter full body (70% of the candle) | 104 | 45% | 12% / 21% / 67% | +0.070 | +7.3 | $35.09 | 44% | −2.1% | 4.4% | $10,703 |
| No trend filter | 247 | 36% | 13% / 45% / 43% | −0.115 | −28.3 | $27.32 | 35% | −4.9% | 31.1% | $7,428 |
| London session, 03:00–11:30 New York | 146 | 32% | 24% / 66% / 10% | −0.139 | −20.2 | $16.91 | 31% | −4.9% | 20.6% | $8,069 |

## By month (stop at other side of range, 2R), in R

| | Nov | Dec | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Nasdaq-100 | −0.5 | +0.1 | −0.8 | −1.6 | +3.0 | +5.6 | +0.2 | +4.6 | −4.5 | −3.7 | +0.2 | +3.5 |
| Gold | −0.2 | −3.4 | +1.4 | −5.6 | +13.6 | −3.1 | −3.4 | −3.7 | −5.1 | +0.7 | −2.5 | +2.6 |

- **Nasdaq-100:** 7 of 12 months positive.
- **Gold:** 4 of 12 months positive. One month, March (+13.6R), did all the work; without it gold's year would
  total −22.2R.

## What the variants show

- **The trend filter helps in both markets.** Without it the Nasdaq-100 falls from +0.04R to −0.02R a trade and
  gold from −0.05R to −0.12R. Trading only in the EMA trend's direction is the one PDF rule that clearly earns its
  place here.
- **Only the stricter full-body candle was positive in both markets:** +0.09R on the Nasdaq-100 and +0.07R on gold,
  about 100 trades each. That is one year and one of nine variants per market. In the earlier OTE tests, changes of
  this size flipped sign from one year to the next, so it isn't an edge until it holds in another period.
- **Gold in the London session did worst:** −0.14R a trade, with 66% of trades stopped out.
- **Ignore the volume variants:** they mostly reflect Dukascopy's changing volume reporting, as explained above.
  The same-time-of-day version left only 9 Nasdaq-100 trades and 26 gold trades.

## Targets of 1R, 2R and 3R, breakeven and trailing stops, and the London bias

This section uses the same strategy as above: EMA trend, 30-minute opening range, full-body breakout candle, no
volume condition. It is run with both of the PDF's stops and with three ways of managing the trade:

- **Fixed:** the stop stays where it was placed.
- **Breakeven at 1R:** once price has gone 1R in the trade's favour, the stop moves to the entry price.
- **Trailing from 1R:** at 1R the stop moves to breakeven, then follows the best price at 1R behind it.

Stop moves count from the minute after 1R is reached. Script: `pipeline/orb15_manage.py`.

### Average R per trade, and what $10,000 became (last 12 months)

| Management, target | Nasdaq-100, range stop | Nasdaq-100, candle stop | Gold, range stop | Gold, candle stop |
|---|---|---|---|---|
| Fixed, 1R | +0.032 · $10,439 | +0.034 · $10,428 | −0.063 · $8,882 | −0.074 · $8,686 |
| Fixed, 2R | +0.042 · $10,588 | +0.007 · $9,980 | −0.048 · $9,085 | −0.039 · $9,186 |
| Fixed, 3R | +0.052 · $10,742 | +0.080 · $11,046 | −0.063 · $8,843 | −0.046 · $9,046 |
| Breakeven at 1R, 2R | +0.037 · $10,503 | +0.060 · $10,793 | −0.062 · $8,883 | −0.036 · $9,263 |
| Breakeven at 1R, 3R | +0.047 · $10,656 | +0.087 · $11,204 | −0.092 · $8,418 | −0.066 · $8,759 |
| Trailing from 1R, 2R | +0.025 · $10,325 | +0.059 · $10,788 | −0.070 · $8,759 | −0.040 · $9,210 |
| Trailing from 1R, 3R | +0.031 · $10,421 | +0.054 · $10,701 | −0.088 · $8,482 | −0.038 · $9,228 |
| Trailing from 1R, no target | +0.027 · $10,362 | +0.063 · $10,845 | −0.093 · $8,416 | −0.051 · $9,015 |

Trades: 145 on the Nasdaq-100 and 178 on gold. Win rates with a fixed stop at 1R / 2R / 3R:

| | 1R | 2R | 3R |
|---|---|---|---|
| Nasdaq-100, range stop | 48% | 48% | 48% |
| Nasdaq-100, candle stop | 52% | 37% | 36% |
| Gold, range stop | 44% | 38% | 38% |
| Gold, candle stop | 45% | 35% | 31% |

Every combination stays within ±0.1R a trade of breakeven. In the 12 months before the window, the ranking
changed (see below).

### What happened to trades that reached 1R (last 12 months)

Counts are numbers of trades. With the range stop on the Nasdaq-100, 1R averaged 231 points, so few trades got
that far.

| Market and stop | Reached 1R | Plan, target 2R | Target | Back to breakeven / full stop | Trailing stop (avg R) | Session close |
|---|---|---|---|---|---|---|
| Nasdaq-100, range | 29 of 145 | Fixed | 3 | 0 full stops | — | 26 |
| | | Breakeven at 1R | 3 | 2 breakeven | — | 24 |
| | | Trailing from 1R | 2 | — | 7 (+0.48R) | 20 |
| Nasdaq-100, candle | 70 of 145 | Fixed | 36 | 19 full stops | — | 15 |
| | | Breakeven at 1R | 31 | **28 breakeven** | — | 11 |
| | | Trailing from 1R | 26 | — | 37 (+0.37R) | 7 |
| Gold, range | 57 of 178 | Fixed | 24 | 6 full stops | — | 27 |
| | | Breakeven at 1R | 22 | **21 breakeven** | — | 14 |
| | | Trailing from 1R | 16 | — | 32 (+0.47R) | 9 |
| Gold, candle | 79 of 178 | Fixed | 45 | 15 full stops | — | 19 |
| | | Breakeven at 1R | 39 | **31 breakeven** | — | 9 |
| | | Trailing from 1R | 32 | — | 43 (+0.39R) | 4 |

**With a 3R target**, the trades that reached 1R ended like this:

| | Breakeven at 1R | Trailing from 1R |
|---|---|---|
| Nasdaq-100, range | 1 target, 2 breakeven, 26 close | 1 target, 7 trailing (+0.48R), 21 close |
| Nasdaq-100, candle | 16 target, 33 breakeven, 21 close | 8 target, 51 trailing (+0.67R), 11 close |
| Gold, range | 8 target, 25 breakeven, 24 close | 4 target, 43 trailing (+0.69R), 10 close |
| Gold, candle | 20 target, 42 breakeven, 17 close | 12 target, 61 trailing (+0.68R), 6 close |

**With trailing and no target**, the trailing stop closed 8 Nasdaq-100 range-stop trades (+0.72R), 56 Nasdaq-100
candle-stop trades (+0.91R), 46 gold range-stop trades (+0.83R) and 71 gold candle-stop trades (+0.97R). The rest
closed at the session end.

**Reading it:**
- Of the trades that reached 1R, roughly 40% came back to breakeven once the stop was moved there.
- With a fixed stop instead, about a quarter of them went on to the full −1R stop.
- So breakeven at 1R turns those full losses into scratches, but it also stops out some trades that dipped to
  the entry and would have gone on to the target. On the Nasdaq-100 candle stop with a 2R target, 36 targets
  became 31.
- The net effect is small either way: −0.03R to +0.05R a trade. Trailing gives similar results, with its
  trailing-stop exits averaging +0.4R to +1.0R.

### Did the London session's bias matter?

London bias is bullish if price at the session open (09:30 Nasdaq-100, 08:20 gold) is above its 03:00 New York
price, the London open, and bearish if below. It is known before the opening range forms. The table splits
fixed-stop trades into those in London's direction and those against it. The t-statistic tests whether the gap
could be chance; above about 2 it probably isn't.

| Market, stop, target | Last 12 months: with London | Against London | t | Year before: with London | Against London | t |
|---|---|---|---|---|---|---|
| Nasdaq-100, range, 1R | +0.05R (87 trades) | −0.00R (58) | 0.5 | +0.02R (79) | −0.15R (53) | 1.2 |
| Nasdaq-100, range, 2R | +0.08R | −0.01R | 0.7 | +0.07R | −0.17R | 1.6 |
| Nasdaq-100, range, 3R | +0.08R | +0.01R | 0.6 | +0.06R | −0.15R | 1.3 |
| Nasdaq-100, candle, 1R | +0.21R | −0.23R | **2.7** | −0.03R | −0.16R | 0.8 |
| Nasdaq-100, candle, 2R | +0.16R | −0.22R | 1.7 | −0.07R | −0.27R | 0.9 |
| Nasdaq-100, candle, 3R | +0.24R | −0.16R | 1.6 | −0.06R | −0.24R | 0.7 |
| Gold, range, 1R | −0.15R (105) | +0.07R (73) | −1.7 | +0.11R (107) | +0.04R (63) | 0.5 |
| Gold, range, 2R | −0.17R | +0.13R | −1.8 | +0.04R | +0.14R | −0.6 |
| Gold, range, 3R | −0.17R | +0.09R | −1.5 | +0.02R | +0.11R | −0.6 |
| Gold, candle, 1R | −0.09R | −0.05R | −0.2 | −0.13R | −0.12R | −0.0 |
| Gold, candle, 2R | −0.08R | +0.02R | −0.5 | −0.13R | +0.09R | −1.1 |
| Gold, candle, 3R | −0.11R | +0.04R | −0.7 | −0.18R | +0.10R | −1.3 |

**Used as a filter** (only breakouts in London's direction, fixed stop, targets 1R / 2R / 3R):

| | Last 12 months | Year before |
|---|---|---|
| Nasdaq-100, range stop | +0.06 / +0.08 / +0.08R; $10,485 – $10,728 | +0.03 / +0.05 / +0.04R; $10,255 – $10,412 |
| Nasdaq-100, candle stop | +0.20 / +0.17 / +0.26R; $11,491 – $12,438 | −0.02 / −0.09 / −0.07R; $9,253 – $9,805 |
| Gold, range stop | −0.16 / −0.18 / −0.17R | +0.11 / +0.04 / +0.02R |
| Gold, candle stop | −0.11 / −0.10 / −0.12R | −0.13 / −0.13 / −0.18R |

The year before is a robustness check only, outside the window asked for.

**Reading it:**
- **Nasdaq-100:** breakouts in London's direction beat those against it in all 12 comparisons over the two years.
  Only one gap was clearly beyond chance (t = 2.7). The London filter with the range stop was positive in both
  years, but only by +0.03R to +0.08R a trade, a few hundred dollars a year on $10,000. With the candle stop the
  filter made +0.17R to +0.26R in the window, then lost the year before.
- **Gold:** no consistent effect. In the window, breakouts against London's move did better; the year before it
  was mixed.

### The 12 months before the window, for comparison

Fixed stop, targets 1R / 2R / 3R, average R per trade:

| | Year before (Nov 2024 – Oct 2025) | Last 12 months |
|---|---|---|
| Nasdaq-100, range stop | −0.05 / −0.03 / −0.03R | positive |
| Nasdaq-100, candle stop | −0.08 / −0.15 / −0.13R | positive |
| Gold, range stop | +0.08 / +0.08 / +0.05R ($10,850 – $11,443) | negative |
| Gold, candle stop | −0.13 / −0.04 / −0.08R | negative |

Breakeven and trailing versions followed the same pattern. Which combination looks best changes from one year to
the next.

## Ideas 1–4 over 8 years (Jan 2019 – Oct 2026), Nasdaq-100 with the London filter

**History:** Dukascopy 1-minute data for the Nasdaq-100 was extended back to January 2019, almost 8 years in all.
Each year gets its own spread, the median hourly ask − bid during 09:00–16:00 New York, in points:

| 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| 1.06 | 1.38 | 1.30 | 1.35 | 1.38 | 1.45 | 1.40 | 1.09 |

**Base:** the strategy above with the London filter, target 2R, with the range stop or the candle stop.

**The changes**, fixed before this history was run:
1. **Early breakouts only:** the breakout candle closes by 10:30.
2. **Narrow opening range only:** at most 0.45× the average session range of the previous 14 sessions.
3. **Stop at the range midpoint.**
4. **Target at a real level:** (a) the previous session's high or low, or (b) the London session's high or low.
   If that level is less than 0.5R beyond the entry, the 2R target is used instead.

The combinations 1 + 2 and 1 + 2 + 3 were also fixed in advance. Script: `pipeline/orb15_history.py`.

**Fresh years versus the years ideas 1 and 2 came from.** Ideas 1 and 2, including the 0.45 cutoff, were picked
from the trades of Nov 2024 – Oct 2026. So 2019–2024 is the fair test for them, and 2025–2026 is shown separately.
"Years better" counts the fresh years in which a version beat its base on average R and on win rate. The
t-statistic is for the average R being above zero; above about 2 it probably isn't chance.

| Version | 2019–2024: trades | Win rate | Avg R | t | Years better (avg R · win rate) | 2025–2026: win rate · avg R | All 8 years: avg R | $10k after 8 years | Max drawdown |
|---|---|---|---|---|---|---|---|---|---|
| **Range stop, base** | 502 | 48.8% | −0.004 | −0.1 | — | 50.6% · +0.047 | +0.008 | $10,287 | 21.1% |
| 1. Early breakouts | 261 | 48.7% | +0.007 | 0.1 | 3/6 · 3/6 | 57.9% · +0.165 | +0.043 | $11,377 | 10.0% |
| 2. Narrow range | 290 | 49.0% | +0.020 | 0.4 | 3/6 · 4/6 | 50.6% · +0.071 | +0.031 | $11,008 | 14.3% |
| 3. Midpoint stop | 502 | 44.0% | +0.038 | 0.7 | 4/6 · 0/6 | 42.9% · +0.080 | +0.048 | $13,122 | 17.0% |
| 4a. Previous-session level | 502 | 49.2% | −0.010 | −0.3 | 1/6 · 1/6 | 51.3% · +0.054 | +0.005 | $10,112 | 22.1% |
| 4b. London level | 502 | 49.0% | −0.004 | −0.1 | 1/6 · 1/6 | 50.6% · +0.037 | +0.005 | $10,122 | 20.2% |
| 1 + 2 | 148 | 48.6% | +0.030 | 0.4 | 3/6 · 3/6 | 57.5% · +0.245 | +0.075 | $11,416 | 9.4% |
| 1 + 2 + 3 | 148 | 42.6% | +0.051 | 0.5 | 5/6 · 2/6 | 52.5% · +0.429 | +0.131 | $12,603 | 13.0% |
| Range stop, no London filter | 870 | 49.5% | +0.012 | 0.4 | 3/6 · 3/6 | 47.0% · −0.007 | +0.007 | $10,427 | 19.9% |
| **Candle stop, base** | 502 | 37.5% | +0.032 | 0.5 | — | 39.7% · +0.058 | +0.038 | $12,102 | 31.0% |
| 1. Early breakouts | 261 | 38.7% | +0.057 | 0.7 | 4/6 · 4/6 | 42.1% · +0.110 | +0.069 | $12,244 | 23.4% |
| 2. Narrow range | 290 | 39.0% | +0.080 | 1.0 | 4/6 · 4/6 | 40.3% · +0.100 | +0.085 | $13,224 | 18.5% |
| 4a. Previous-session level | 502 | 38.0% | −0.001 | −0.0 | 0/6 · 4/6 | 41.7% · +0.068 | +0.015 | $10,433 | 36.4% |
| 4b. London level | 502 | 38.2% | +0.026 | 0.4 | 2/6 · 4/6 | 40.4% · +0.033 | +0.027 | $11,278 | 32.1% |
| **1 + 2** | 148 | 41.9% | **+0.137** | 1.2 | 4/6 · 4/6 | 47.5% · +0.321 | +0.176 | **$13,689** | **10.5%** |
| Candle stop, no London filter | 870 | 38.2% | +0.043 | 1.0 | 3/6 · 3/6 | 34.0% · −0.076 | +0.016 | $10,867 | 42.4% |

The midpoint stop is the same whichever base it starts from. Against the candle base it was better in 3 of 6
fresh years on average R and 5 of 6 on win rate.

The best version, candle stop with 1 + 2, year by year:

| | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 (to Oct) |
|---|---|---|---|---|---|---|---|---|
| Avg R | +0.27 | +0.08 | +0.17 | +0.36 | −0.24 | +0.33 | +0.19 | +0.67 |
| Trades | 19 | 21 | 26 | 26 | 33 | 23 | 29 | 11 |

### What the 8 years say

- **The London filter didn't hold up.** In 2019–2024 it made both stops slightly worse: −0.004R against +0.012R
  without it for the range stop, and +0.032R against +0.043R for the candle stop. All its benefit is in
  2025–2026. It looks like a feature of those two years, not a lasting edge.
- **None of the four ideas reliably raised the win rate.**
  - In the fresh years the range-stop versions won 48.6–49.2% of the time, against 48.8% for the base.
  - Early breakouts won 48.7%; the ~60% seen in the exploration came from the years the idea was picked from.
  - With the candle stop, 1 + 2 lifted the win rate from 37.5% to 41.9%, the largest change, in 4 of 6 years.
  - The midpoint stop lowers the win rate (44%) while slightly raising the average R.
  - The win rate is mostly set by where the stop and target sit.
- **The level targets did nothing.** Most trades end at the 16:00 close or the stop anyway.
- **The most promising version:** narrow range plus early breakout, with the candle stop.
  - It made +0.137R a trade in the fresh years, against +0.032R for the base, and was positive in 7 of 8 years.
  - It cut the 8-year drawdown from 31% to 10.5%.
  - But it trades only about twice a month (about 24 trades a year), and its fresh-year t-statistic is 1.2. That
    is suggestive, not proven, and the 8-year $13,689 includes the two in-sample years.

## Limits

- **Data:** the feed is Dukascopy's CFD feed, not exchange futures or stock data, and its volume is not exchange
  volume.
- **The PDF's example:** it trades Apple stock. Applying it to the Nasdaq-100 and gold follows its own advice that
  ORB suits "stocks and commodities (futures)".
- **Open choices:** the EMA timeframe, the gold session, the 3-hour entry cutoff and closing at the session end are
  my readings of choices the PDF leaves open.
- **Sample:** 12 months only.

## Files

- `pipeline/orb15.py`: the backtest, all versions and variants.
- `results/orb15_results.csv`: one row per market and version.
- `results/orb15_trades.csv`: every trade, with its opening range, breakout candle, entry, stop, target, exit and
  R.
- `results/USATECHIDXUSD_by_month.csv`, `results/XAUUSD_by_month.csv`: the first version by month.
- `pipeline/orb15_manage.py` (`--period last|prior`): targets of 1R / 2R / 3R, breakeven and trailing from 1R, and
  the London-bias split and filter.
  - `results/orb15_management.csv`: one row per run, with the counts of what happened after 1R.
  - `results/orb15_london_bias.csv`: with-London and against-London results with their t-statistics.
  - `results/orb15_management_trades.csv`: every trade, with its London bias and whether it reached 1R.
  - `_prior` files hold the year-before check.
- `pipeline/orb15_explore.py`: the exploratory split that suggested ideas 1 and 2 → `results/orb15_explore.csv`.
- `pipeline/orb15_history.py`: ideas 1–4 over Jan 2019 – Oct 2026.
  - `results/orb15_history_summary.csv`: one row per version, over the whole period.
  - `results/orb15_history_years.csv`: each version by year.
  - `results/orb15_history_periods.csv`: 2019–2024, 2025–2026 and all 8 years, with t-statistics.
  - `results/orb15_history_trades.csv`: every trade.

**To reproduce:** `python pipeline/orb15.py`. It uses the 1-minute data from `strategy_search/`; its
`pipeline/fetch_m1.py` downloads it, with `--symbols USATECHIDXUSD XAUUSD`.
