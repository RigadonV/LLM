# The hybrid strategy: trend, level, signal

Price action decides **direction and timing**. Support and resistance decide **location**: where
to trade, where the stop goes and where to take profit. The reasons for each rule, with sources,
are in [RESEARCH.md](RESEARCH.md).

**These rules and the test plan below were written and committed before any backtest was run.**
Every number in them is a round, conventional value chosen in advance, not fitted to data.

- **Chart:** daily candles drawn from bid prices (UTC day; the short Sunday-evening session is
  folded into Monday, so there are 5 bars a week).
- **Markets:** EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF, NZD/USD, gold, silver, Brent
  crude, S&P 500, Nasdaq-100, DAX 40, FTSE 100, Nikkei 225 (spot forex and CFDs).

## The rules (long side; the short side is the mirror image)

| # | Gate | Rule | Principle it comes from |
|---|---|---|---|
| 1 | Trend | Only buy when the price is higher than it was 12 months (252 trading days) ago. | PA: trade with the trend (time-series momentum) |
| 2 | Level | Mark swing highs and lows: a bar whose high (low) is the highest (lowest) of the 5 bars on either side. Use the swings of the last 250 trading days. | S/R: levels come from earlier turning points; recent ones matter more |
| 3 | Level | A **key level** is a swing price with at least 2 swing points (highs or lows) within ±¼ ATR of it. Its **zone** is the level ± ¼ ATR. | S/R: zones, not lines; a level that has held before is more likely to hold again |
| 4 | Level | The level is below the market and the market came down to it: at least one of the 3 previous closes is above the zone. | S/R: support is tested from above |
| 5 | Signal | The signal bar's low reaches into the zone and the bar closes above the level. | PA + S/R: the level is rejected, or broken and reclaimed (false break) |
| 6 | Signal | The signal bar is a bullish **pin bar** (lower wick at least half of the bar's range) or a bullish **engulfing** bar. | PA: a signal bar shows who won the test |
| 7 | Room | No other key level lies between the entry and the 2R target. | S/R: don't buy straight into resistance |
| 8 | Entry | Buy stop 1 pip (one tick) above the signal bar's high, valid for the next day only. | PA: let the market confirm before you are in |
| 9 | Stop | Below the lower of the signal bar's low and the zone bottom, minus 0.1 ATR. | PA + S/R: the stop goes where the idea is wrong, and past the obvious stop cluster |
| 10 | Target | 2 × the risk (2R). If neither stop nor target is hit, exit at the close of the 20th day. | PA: the trader's equation; at 2R, winning 1 trade in 3 breaks even before costs |
| 11 | Size | Risk 1% of the account per trade. One position per market at a time. | Risk control |

**Short side:** the price is lower than 12 months ago; the key level is above the market and was
approached from below; the signal bar's high reaches into the zone and it closes below the level;
it is a bearish pin bar (upper wick at least half the range) or a bearish engulfing bar; sell stop
1 pip below its low; stop above the higher of its high and the zone top, plus 0.1 ATR.

**Definitions**

- **ATR:** 14-day average true range (Wilder smoothing), measured on the signal bar.
- **Bullish pin bar:** `min(open, close) − low ≥ 0.5 × (high − low)`.
- **Bullish engulfing:** the previous bar closed down; this bar closes up, opens at or below the
  previous close and closes at or above the previous open.
- **Pip / tick:** 0.0001 (0.01 for USD/JPY), gold 0.1, silver 0.001, Brent 0.01, indices 0.1
  (Nikkei 1).

## Test plan (fixed in advance)

**Data:** Dukascopy daily bid and ask candles, 2007 to September 2026 (index and oil CFDs start
later). Trading begins once a market has 12 months of history.

**Costs:** buys fill at Dukascopy's ask and sells at its bid, so the real historical spread is
paid on every entry and exit. On top of that, a commission of 0.0035% of the position value per
side (IC Markets' published $3.50 per lot per side on its Raw Spread account). Overnight
financing (swap) is **not** included.

**Same-day ambiguity:** when one daily bar contains both the stop and the target, or both the
entry and the stop, hourly data settles which came first. Where hourly data could not be
downloaded, the trade is counted the worse way, and the number of such trades is reported.

**Variants,** each a full backtest on the same engine, to show what each part contributes:

| Variant | Trend (rule 1) | Level (rules 2–4, 7) | Signal bar (rules 5–6) | Entry |
|---|---|---|---|---|
| V0 Trend only | ✓ | – | any bar | stop beyond the bar |
| V1 S/R only | – | ✓ | – | limit at the zone edge |
| V2 S/R + trend | ✓ | ✓ | – | limit at the zone edge |
| V3 PA only | ✓ | – | pin bar / engulfing anywhere | stop beyond the bar |
| **V4 Hybrid** | ✓ | ✓ | ✓ | stop beyond the bar |
| V4a Hybrid without trend | – | ✓ | ✓ | stop beyond the bar |
| V4b Hybrid without the room rule | ✓ | ✓ (no rule 7) | ✓ | stop beyond the bar |
| V4c Hybrid with 1-touch levels | ✓ | any swing point | ✓ | stop beyond the bar |
| V4d Hybrid entering at the next open | ✓ | ✓ | ✓ | next day's open |

- V0 and V3 put the stop 0.1 ATR beyond the signal bar. V1 and V2 buy at the zone top (sell at
  the zone bottom) and put the stop 0.1 ATR beyond the far side of the zone. All variants target
  2R with the 20-day time exit.
- **V4 is the strategy.** The other variants are there to measure the parts, not to pick a
  winner afterwards.

**Secondary checks on V4's trades:** levels that have flipped (the zone holds both swing highs
and swing lows) vs not; levels on a round number (forex: a multiple of 100 pips; other markets:
a multiple of half the second significant digit, e.g. gold $50, S&P 500 50 points) vs not; 2 vs
3+ touches; long vs short; forex vs commodities vs indices; 2008–2016 vs 2017–2026.
