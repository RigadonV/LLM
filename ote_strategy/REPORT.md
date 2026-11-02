# OTE strategy backtest: London session, last 12 months

**Strategy:** `OTE_Trading_Strategy.pdf`, as supplied.
- **Entry:** a 15-minute swing range retraces into the 0.705–0.79 Fibonacci zone, with an order block or fair value
  gap there and the trade in the trend's direction. The order is a limit at the 0.705 level.
- **Exits:** a 50-point stop, moved to breakeven at 2R, with a 3–4R target.
- **Rules:** 1% risk per trade, at most 2 losses a day, entries 02:00–09:30 New York time.

**Test setup:**
- **Market:** Nasdaq-100, Dukascopy's USATECHIDXUSD CFD, 1-minute bid candles. The PDF names no market; its
  50-point stop fits this one.
- **Window:** the last 12 months, 3 Nov 2025 – 30 Oct 2026.
- **Session:** London, 02:00–09:30 New York time, as the PDF specifies.

**Result: on this data the strategy loses money, and the PDF's statistics are not reproduced.**

- **Base version:** 273 trades, or 5.3 a week.
  - 15% were winners, 19% breakevens and 66% losers, for **−0.135R a trade** and −36.9R over the year.
  - $10,000 at 1% risk became **$6,578**, with a 41% drawdown.
- **Variants:** of the seven, only adding a 1-hour 50 EMA trend filter ended positive: +0.043R a trade, $10,000 →
  $10,374, about breakeven.
- **Compared with the PDF:**

  | | PDF | Backtest |
  |---|---|---|
  | Win rate | 84.4% | 15% |
  | Trades reaching 3R | 82.1% | 24% |
  | Average favourable move | 8.4R | 2.1R |
  | Average adverse move | 11.7 points | 47.5 points |

## The rules as tested

Parts the PDF leaves to judgement are marked *. For each I picked one reading and also ran the obvious
alternatives as variants, all decided before seeing any results.

| PDF rule | How it was made mechanical |
|---|---|
| Identify the 15-minute swing range; swing high and swing low | A swing high is a 15-minute candle whose high is above the 2 candles on each side (variants: 1 and 3), confirmed when the 2nd candle after it closes. A bullish range runs from the lowest low since the last swing low to a new swing high; bearish is the mirror image. |
| *Trade with the overall trend; *trending, ranging or choppy | The range must break structure in its direction: a bullish range's high is above the swing high before the range began, and the mirror for bearish. Only trending legs are traded. Variant: also on the right side of the 1-hour 50 EMA. |
| Wait for the 0.705–0.79 OTE zone | Measured on the range: 0.705 and 0.79 retracement from its end. |
| 15M / 30M / 1H order block or fair value gap | A 15M, 30M or 1H OB or FVG formed during the range must overlap the OTE zone. An FVG is a three-candle gap in the trade's direction. An OB is an opposite-colour candle that price later closed beyond in the trade's direction. Variant: not required. |
| *Key opening levels | Variant only: longs below and shorts above the New York midnight open. |
| Enter at the OB / 0.705 level | A limit order at the 0.705 level, placed when the swing is confirmed. If price is already inside the zone it fills at once; if price is already past 0.79, the range is skipped. The order lasts until filled, until price takes out the start of the range, until a newer range replaces it, or until 09:30. |
| Stop 50 points; breakeven at 2R; target 3–4R, average 4R | Stop 50 points from the fill. Stop moves to the entry price once price reaches +2R. Target 4R (variant: 3R). |
| Max 2 losses a day; trading hours 2:00–9:30 AM New York | No new entries after 2 losses (breakevens don't count) or after 09:30. One trade at a time. A trade still open runs to its stop or target, or is closed at 16:00 New York (variant: closed at 09:30). |
| Risk 1% per trade | $10,000 account, 1% of the current balance per trade, compounding. All open positions are kept under 20:1 leverage; a 50-point stop on the Nasdaq-100 needs about 6:1. |

**Prices and fills:**
- Spreads are Dukascopy's own median ask − bid for each hour; in the London session it was 1.2 points, about
  0.02R a trade.
- Buys fill at the ask, and shorts are stopped out and take profit on the ask. A stop that price jumps over fills
  at the next price.
- Within one minute the stop counts before the target. On the entry minute only the stop is checked. Breakeven
  applies from the minute after +2R is reached.

**Checks against the trade list:**
- Every trade's 0.705 and 0.79 levels match its swing range. For example, on 21 Nov 2025 the short range ran from
  24,143.3 down to 23,831.0, so 23,831.0 + 0.705 × 312.3 = 24,051.1, which is where it filled.
- Fills were at the 0.705 level; one fill came from a jump past 0.79.
- Stops came out at exactly −1R and targets at +4.0 to +4.2R.

## Results, 3 Nov 2025 – 30 Oct 2026, 02:00–09:30 New York

| Variant | Trades | Win / breakeven / loss | Win rate excl. breakeven | Avg R | Total R | Avg week | Positive weeks | Worst week | Max drawdown | $10k becomes |
|---|---|---|---|---|---|---|---|---|---|---|
| **Base (as written, target 4R)** | 273 | 15% / 19% / 66% | 18.6% | **−0.135** | −36.9 | −0.70% | 37% | −16.0% | 40.8% | **$6,578** |
| Target 3R | 278 | 22% / 13% / 65% | 24.8% | −0.061 | −16.9 | −0.31% | 35% | −16.0% | 30.3% | $8,061 |
| + 1-hour 50 EMA trend filter | 186 | 19% / 21% / 60% | 23.8% | +0.043 | +7.9 | +0.16% | 48% | −14.3% | 24.5% | $10,374 |
| + midnight-open filter | 142 | 18% / 14% / 68% | 20.5% | −0.094 | −13.4 | −0.26% | 42% | −16.0% | 33.2% | $8,444 |
| Swings of 1 candle each side | 305 | 16% / 15% / 69% | 18.6% | −0.105 | −32.0 | −0.63% | 37% | −7.7% | 40.2% | $6,941 |
| Swings of 3 candles each side | 219 | 13% / 19% / 68% | 15.7% | −0.267 | −58.5 | −1.11% | 37% | −17.7% | 46.9% | $5,356 |
| No OB/FVG needed | 328 | 15% / 19% / 66% | 18.4% | −0.125 | −40.9 | −0.80% | 29% | −13.6% | 42.4% | $6,265 |
| Close at 09:30 | 273 | 28% / 11% / 61% | 31.6% | −0.098 | −26.6 | −0.51% | 44% | −15.3% | 27.9% | $7,389 |

How far trades went, compared with the PDF's statistics:

| | PDF | Base | + 1-hour EMA filter |
|---|---|---|---|
| Win rate | 84.4% | 15.0% (18.6% excl. breakeven) | 18.8% (23.8% excl. breakeven) |
| Trades reaching 3R before the 50-point stop | 82.1% | 23.8% | 27.4% |
| Trades reaching 4R | 66.1% | 16.9% | 21.5% |
| Trades reaching 5R | 57.1% | 11.7% | 15.1% |
| Average favourable move before the stop (MFE) | 8.4R | 2.1R | 2.5R |
| Average adverse move (MAE) | 11.7 points | 47.5 points | 47.1 points |
| Average trade time | 32.9 (unit not stated) | 137 minutes | 134 minutes |

The base version by month, in R:

| Nov | Dec | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| −7.0 | −2.8 | −9.0 | −5.0 | −16.3 | +6.0 | −8.8 | +18.0 | −10.0 | +1.0 | −11.0 | +8.0 |

Four of 12 months were positive.

**One trade explains most of March.** On 23 Mar 2026 a short had moved its stop to breakeven. The feed then had a
13-minute gap, and the next price was 716 points (about 3%) higher, so the stop filled there for −14.3R. A stop
order does fill at the first price after such a jump. If it had been an ordinary breakeven instead, the base year
would total −22.5R rather than −36.9R, still clearly negative.

## Why the PDF's numbers and the backtest differ

- **Wrong entry point would show up as a big adverse move.** The PDF's average adverse move of 11.7 points on a
  50-point stop means its trades almost never went against the entry. In the price data, OTE entries from 15-minute
  swings went an average of 47.5 points against, and 66% hit the full stop. That gap is too large to come from
  details of the mechanical reading. All eight versions have average adverse moves of 42–50 points and reach 3R
  only 20–27% of the time.
- **Judgement could add an edge the rules don't capture.** Which swing to use, the trend and the market condition
  are partly judgement. If that judgement is what produces an 84% win rate, it can be tested by checking real trades
  against the data (below).
- **Journals and chart-marked backtests often see the swing after the move.** That is a common reason manual
  statistics look far better than the same idea traded forward.

## Limits

- **Market:** the market is my assumption, since the PDF names none. On another market the 50-point stop would mean
  something very different.
- **Data:** Dukascopy's CFD feed, not CME futures.
- **Intraminute order:** with 1-minute data the order of events inside a minute is unknown, so the tests take the
  pessimistic order. With a 250-point gap between stop and target this rarely matters.

## How to take this further

The most useful next step is a handful of real trades from your journal: date, time, direction and entry. I can
check each one against the same 1-minute data and see where my mechanical reading of the swing, order block or
trend differs from yours, then rerun with that reading. I can also run the same test on another market, such as
the S&P 500, Dow, DAX or gold, if the strategy was written for one of those.

## Files

- `pipeline/ote.py`: the backtest, all variants and the comparison with the PDF's statistics.
- `results/ote_variants.csv`: one row per variant.
- `results/ote_base_trades.csv`: every base trade, with its swing range, OTE levels, entry, exit, R, MFE and MAE.
- `results/ote_base_by_month.csv`: the base version by month.

**To reproduce:** `python pipeline/ote.py`. It uses the 1-minute data from `strategy_search/`; `fetch_m1.py` there
downloads it.
