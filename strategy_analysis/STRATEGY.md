# Model 2 – London: reconstructed strategy rules (NQ)

Reverse-engineered from `Model2_London_Journal_V4.xlsx`: 250 NQ (Nasdaq-100 E-mini) trades,
10 Mar – 16 Oct 2026, all times **New York (ET)**. The journal records no direction, prices, stops
or size, so these were reconstructed from 1-minute Nasdaq-100 data (Dukascopy CFD, which tracks NQ
with 0.9965 5-minute return correlation). See `VALIDATION.md` for how well the rules reproduce
the trades and what they cannot explain.

**In one sentence:** during the London session and the NY pre-open, wait for a 15-minute swing leg
to retrace into the 0.705–0.79 zone of its fib, enter there with a limit order, put the stop about
a seventh of the leg beyond the entry (still inside the swing point), and take profit at roughly
2–4R, usually before the leg's extreme.

Confidence levels: **High** = holds for (nearly) every trade and is clearly not chance.
**Medium** = holds for most trades or is strongly supported but not exact.
**Low** = a tendency only; the trader is likely using judgement that the data cannot see.

---

## 1. Market and timeframes — *High*

1. Instrument: **NQ** (Nasdaq-100 futures). All 250 trades.
2. Structure timeframe: **15-minute** chart. The journal's own checklist says
   "Fib 15M drawn = Y" on every trade, and the reconstructed legs confirm it (section 3).
3. Confluence timeframes: 15M, 30M and 1H order blocks / fair value gaps (journal tags).
4. Execution: intraday limit orders; trades last minutes (median 21 min, 90% under 70 min).

## 2. Session window — *High*

5. Only place entries between **02:00 and 09:30 ET** (London open to NY cash open).
   Observed entries: 02:00 to 09:22, spread evenly across the hours
   (02:00–09:00 each hold 23–33 trades; 7 after 09:00).
   The timestamps fit New York time for 93.6% of trades, versus at most 64% for any other
   offset (`results/timezone_test.csv`), so the "London" column in the journal is the session
   name, not the clock.

## 3. Define the fib leg — *Medium–High*

6. Mark 15M swing points as **2-bar fractals** (a candle whose high/low is the extreme of the two
   candles either side). A swing is only usable once the two candles after it have closed.
7. For a **long**: take the **most recent 15M swing low that price has not traded below**, and the
   **highest high made since it**. Draw the fib from that swing low (1.0) to that high (0.0).
   For a **short**: mirror image — most recent unbroken 15M swing high to the lowest low since.
8. Ignore legs smaller than **~1.5–2 × ATR(14) on 15M**. (Typical leg: 119 pts, 3.4 ATR,
   82 minutes from swing to extreme; entries come a median 63 minutes after the extreme.)
9. Legs usually start in the overnight/Asian session (44%) or the 02:00–05:00 London window (31%);
   the extreme is usually printed during London (42%) or 05:00–09:00 (36%).

*Evidence:* using only the entry price implied by the price path, the logged fib level (0.705 or
0.79, ±0.05) lands on this exact leg for **77% of trades** with a known direction (69% if only
counting trades whose direction was identified without using the fib). The same test at random
minutes of the same sessions hits 11% — a 7× lift. Weaker (1-bar) or stronger (3-bar) fractals and
larger size filters all fit worse (`results/leg_definition_test.csv`).

## 4. Direction — *High (that there is no bias) / Low (for the trader's trend read)*

10. Trade **with the leg**: buy retracements of up-legs, sell retracements of down-legs.
    The sample is evenly split: 108 longs, 105 shorts, with near-identical loss rates (12.0% vs 12.4%).
11. **No moving-average trend filter.** Price vs EMA 20/50/200 on 15M, 1H, 4H or daily, and the
    EMA slopes, agree with the trade direction only 46–57% of the time. The journal's "Aligned w/ Trend = Y" (82% of trades)
    is a discretionary read that could not be reproduced from price data.

## 5. Setup filters

12. **The level must be fresh** — price has not already touched it since the leg's extreme. *Medium.*
    Generated setups where the level was already touched were taken by the trader half as often
    (12% vs 25%).
13. **Order block / FVG confluence at the entry level.** *Medium (present, but not selective).*
    The journal logs an OB or FVG on 95% of trades; independent detection finds a 15M/30M/1H OB or FVG
    covering the entry price on 74% — but losers have one just as often as winners, so it does not
    separate good from bad trades.
14. Not part of the rules (each holds for roughly 35–62% of trades and does not separate winners
    from losers): RSI, MACD, Stochastic and Bollinger Band position; premium/discount versus the
    00:00 or 18:00 open; sweeps of the Asian or previous-day high/low.
15. Break of structure describes the typical leg (79% of legs took out the previous opposite 15M
    swing) but adds nothing as a filter: requiring it lowered the match with the journal without
    improving precision. *Low.* (`results/condition_prevalence.csv`, `results/sensitivity_grid.csv`)

## 6. Entry — *Medium*

16. Rest a **limit order at the 0.79** level (61% of trades) **or the 0.705** level (39%).
17. Which level: 0.705 entries more often have a **15M fair value gap** at the level (38% vs 17%),
    0.79 entries more often a **15M order block** (43% vs 29%); the journal's own tags agree.
    *Low confidence* — as a mechanical rule this choice was right only about half the time.
18. One position at a time; each leg is traded once. 1–5 trades a day (55 days with 1, 43 with 2,
    25 with 3, 8 with 4–5).

## 7. Stop loss — *Medium–High*

19. Place the stop **about 14% of the leg beyond the entry** — i.e. at roughly fib **0.84 for a 0.705
    entry** and **0.93 for a 0.79 entry**. The stop always stays inside the swing point (1.0).
20. In points this is a median 18.6 pts (IQR 12–25); it is *not* a fixed point stop or an ATR stop.

*Evidence:* the stop implied for losers (stop = MAE), winners and the "BE" class independently
comes out at 0.152, 0.141 and 0.141 of the leg. As a fraction of the leg the stop varies far less
(coefficient of variation 0.23) than in points (0.51) or ATR multiples (0.43).

## 8. Take profit and trade management — *Medium (that profit is taken from ~2R) / Low (exact target)*

21. Take profit at **roughly 2–4R**: winners closed at a median **3.1R** (IQR 2.4–4.2R, min 2.0R).
    On the fib this is usually around the 0.2–0.45 retracement, **before** the leg's extreme.
22. **No trade that reached 2R was allowed to lose.** Every loser but one peaked below 1.8R
    (trade 71, which ran +9.8R first, is the exception); every non-losing trade was closed at ≥1.7R. Practically: from about +2R, either take the profit or
    move the stop to break-even.
23. The journal's **"BE"** label is not a scratch trade. It is the Stats sheet's class for a trade
    that was **closed in profit (1.7–2.9R) but never reached 2.98R**. The price path confirms these
    were closed near their logged RR, not at the entry price.
24. The exact target is discretionary. The nearest obvious level to the exit was the leg's extreme in
    32% of winners, otherwise a session level (00:00/18:00 open, Asian high/low, previous day
    high/low), but typically 0.8R away from it — no single level explains the exits.
25. Trades are short: median 23 min for winners, 15 min for losers; all but one were closed by
    10:00 ET (latest exit 10:14).

## 9. Position sizing — *Medium (inferred)*

26. **Fixed risk per trade (1R)**: every full loss is recorded as exactly −1R. Size = account risk ÷
    (stop in points × $20 per point for NQ, or $2 for MNQ). There is no lot data in the journal.

## 10. When not to trade — *High for the window, Low for anything else*

27. No entries before 02:00 or after ~09:20 ET (NY cash open at 09:30).
28. The trader did **not** avoid news: 40% of trades were on days with high-impact US data,
    including entries right at the 08:30 CPI release, and the loss rate on news days was no worse
    (10% vs 14%).
29. No trades on US market holidays (Good Friday, Memorial Day, 3 Jul, Labor Day) and none logged
    19–31 Aug.

---

## Example: a typical trade

![Trade #196 — long at 0.79](charts/trade_196_long_win.png)

Trade #196 (4 Aug 2026). The 15M swing low at 01:00 (1.0) and the high at 04:21 (0.0) define a
153-point leg (3.5 × ATR). Price retraces through 0.705 and fills the long at the untouched 0.79
level at 05:17; the stop sits 22.5 pts below (0.15 of the leg, fib ≈ 0.94); the trade is closed
20 minutes later at +2.1R, around the 0.5 retracement.

More charts (one win each way, a loss, a "BE", and a trade the rules do **not** explain):
`charts/trade_246_short_win.png`, `charts/trade_167_loss.png`,
`charts/trade_061_closed_at_2R_be.png`, `charts/trade_010_does_not_fit.png`.

## Trades that do not fit

- **37 trades (15%)** — direction could not be identified from the price path (16 fit neither
  direction, 21 fit both). Possible causes: CFD-vs-futures wick differences on very short trades,
  or journal values entered loosely.
- **50 of the 213 trades with a direction (23%)** do not sit at the logged fib of the most recent leg.
  Most are either entries beyond a small recent swing (the trader used a bigger leg) or entries on
  a smaller, newer swing than a 2-bar fractal picks up (e.g. trade #10, entry at 0.43 of the leg).
- Two journal oddities: trade 9 is a "Loss" of −0.01R, and trade 71 is a −1R loss that had run +9.8R.

## Summary of confidence

| Section | Rule | Confidence | Main evidence |
|---|------|-----------|---------------|
| 1 | NQ, 15M structure | High | 250/250 trades; journal checklist |
| 2 | Entries 02:00–09:30 ET | High | 250/250; ET fits 93.6% vs ≤64% |
| 3 | Leg = most recent unbroken 15M fractal → extreme, ≥1.5–2 ATR | Medium–High | 77% match vs 11% chance |
| 4 | Trade with the leg, no EMA trend filter | High / Low for trader's trend read | 108 L / 105 S; EMA agreement 46–57% |
| 5 | Fresh (untouched) level | Medium | 2× higher take-rate in backtest |
| 6 | Limit at 0.79 or 0.705 | Medium (level) / Low (which one) | 61% / 39%; FVG vs OB tendency |
| 7 | Stop ≈ 0.14 × leg beyond entry | Medium–High | 0.141–0.152 in all three outcome groups |
| 8 | Profit from ~2R, median 3.1R; never let 2R become a loss | Medium | loser MFE ≤1.77R (one exception); exits ≥1.69R |
| 8b | Exact target | Low | no single level explains exits |
| 9 | Fixed 1R risk | Medium | all full losses = −1R |
| 10 | No news avoidance | High | 40% of trades on news days |
