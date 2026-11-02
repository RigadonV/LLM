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

**To reproduce:** `python pipeline/orb15.py`. It uses the 1-minute data from `strategy_search/`; its
`pipeline/fetch_m1.py` downloads it, with `--symbols USATECHIDXUSD XAUUSD`.
