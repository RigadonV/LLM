# How well the reconstructed strategy matches the journal

`replicate_strategy.py` codes the rules from `STRATEGY.md` and runs them minute by minute over
10 Mar – 16 Oct 2026 on 1-minute data. A generated trade **matches** a journal trade when it is on
the same day, in the same direction (where the direction is known), and enters within ±15 minutes.
Precision is measured on the 131 days the trader actually logged trades; trades generated on the 28
weekdays with no journal entries (holidays and a late-August gap) are reported separately.

All variants exit the way the trader's checklist says: **stop to break-even at +2R, take profit at 3R**.

## Result

| Round | Rules | Generated | Matched (recall) | Precision | Extra trades |
|---|---|---|---|---|---|
| Baseline | 0.79 limit on the most recent 15M leg ≥1.5 ATR; stop 0.14 × leg | 581 | 126 (50%) | 22% | 455 (+125 on unlogged days) |
| Refine 1 | + level must be untouched since the extreme; leg ≥2 ATR | 406 | 117 (47%) | 29% | 289 (+76) |
| **Refine 2 (final)** | + orders at both 0.705 and 0.79, first untouched level fills | **447** | **142 (57%)** | **32%** | **305 (+87)** |

- **Entries:** the final rules reproduce **142 of 250 journal trades (57%)**, at a median timing
  difference of 0 minutes; 90% of matches use the same swing anchor as the trader. They pick the
  same fib level only 51% of the time, so *which* of 0.705/0.79 the trader chooses is not captured.
- **Missed (108):**
  - 24 have no inferred direction.
  - 48 sit on the right fib level but were filtered out (leg too small, level already touched) or
    blocked by an open position.
  - 36 do not sit at the fib of the most recent leg.
- **Extra trades:** about 2.3 a day more than the trader took. The trader is far more selective
  than any rule found here.
- Tested and dropped: requiring a break of structure, and choosing the level by FVG/OB location.
  A 36-combination sensitivity grid (`results/sensitivity_grid.csv`) is fairly flat (F1 0.30–0.41),
  so the final rules are not a lucky corner of the parameter space.

## The trader's own checklist, coded

Each checklist item added on top of the final rules:

| Variant | Generated | Matched (recall) | Precision | Mechanical R / trade |
|---|---|---|---|---|
| Final rules | 447 | 142 (57%) | 32% | +0.09 |
| + 2 losses = done for the day, SL < 50 pts | 331 | 117 (47%) | 35% | +0.08 |
| + trend aligned (15M EMA50 trend) | 229 | 79 (32%) | 35% | +0.17 |
| + trend aligned (1H EMA50 trend) | 232 | 80 (32%) | 35% | +0.13 |
| + HTF OB/FVG at the entry (15M/30M/1H) | 299 | 107 (43%) | 36% | +0.10 |
| + 15M trend and OB/FVG | 198 | 70 (28%) | 35% | +0.11 |

The checklist items make the rules slightly more selective and slightly better, but they cut the
number of journal trades reproduced and leave the mechanical loss rate at ~67%. The 2-loss daily
stop costs recall because the mechanical rules lose earlier in the day than the trader did, so they
stop before reaching the trader's later trades. "Key open level" was not coded: the trader logged
it on only 24% of trades.

## Time zone and London-only trading

The journal's "Session Time (London)" column was re-read in five time zones and the whole chain
repeated each time (`pipeline/london_time_check.py`, `results/timezone_reading_check.csv`):

| Logged times read as… | Entries (UK clock) | Price path explains | Fib match (chance) | Backtest recall / precision |
|---|---|---|---|---|
| **New York clock** | 07:00–14:22 | **94%** | **69%** (11%) | **57% / 32%** |
| UK clock | 02:00–09:22 | 56% | 9% (5%) | 8% / 6% |
| UTC | 02:06–10:22 | 56% | 7% (7%) | 9% / 7% |
| Central Europe | 01:00–08:22 | 54% | 5% (16%) | 7% / 5% |
| South Africa | 00:06–08:22 | 54% | 6% (5%) | 7% / 5% |

Only the New York reading fits; under any other, the entries stop sitting on the fib levels the
trader logged. Read on the New York clock, the trades already are London-session trades
(07:00–14:22 UK), so the earlier analysis stands.

Restricted to the London session (`results/london_session_windows.csv`; journal scored 3R / 0 / −1R):

| Window | Journal trades | Journal R / trade | Backtest trades | Backtest recall | Backtest R / trade |
|---|---|---|---|---|---|
| 07:00–10:00 UK (London kill zone) | 111 | +1.99 | 187 | 59% | +0.04 |
| 10:00–13:00 UK | 93 | +2.01 | 187 | 62% | +0.34 |
| 13:00–14:30 UK (NY pre-open, 08:30 NY news) | 46 | +1.67 | 155 | 76% | −0.09 |
| As journaled (07:00–14:30 UK) | 250 | +1.94 | 447 | 57% | +0.09 |
| **London only (07:00–13:00 UK clock)** | **203** | **+2.02** | **347** | **57%** | **+0.21** |

The first four rows use the New York-clock windows the journal was logged on (UK = New York + 5h;
+4h from 8 to 28 March); the last row is the go-forward rule, set on the UK clock.
The 13:00–14:30 UK stretch is the weakest in both the journal and the backtest. Dropping it
(`replicate_strategy.py --variant london_only`) raises the mechanical result to +0.21R per trade:
95% bootstrap range +0.02R to +0.40R, positive in 6 of 8 months. It is a small edge, measured
on the same seven months, and still far below the journal's +2R.

## Outcomes do not reproduce

The journal is scored the way the checklist implies: Win = +3R, BE = 0R, Loss = −1R. The
"RR Achieved" column adds up to more (+2.54R per trade) because it logs "BE" trades at the R they
reached (1.7–2.9R) rather than 0R, and wins at values other than 3R.

| | Journal | Mechanical rules |
|---|---|---|
| Loss rate, all trades | 16% | 67% |
| Loss rate, the 142 matched trades | 20% | 51% |
| Average R, the 142 matched trades | +1.85R | +0.67R |
| Average R per trade, all trades | +1.94R | +0.09R |

All 29 journal losses among the matched trades are also losses in the backtest. But 35 of the 97
matched journal winners are stopped out mechanically. No exit variant closes the gap: a 2R target,
3R with or without break-even, or the leg extreme all give −0.03R to +0.12R per trade
(`results/validation_variants.csv`).

**What this means:**
- The *entry mechanics* — session window, 15M leg, 0.705/0.79 limit, stop at ~0.14 of the leg,
  BE at 2R, TP at 3R — are recoverable and explain over half of the trades.
- The trader's *selection* of which setups to take, and the journal's very high win rate, are not —
  not even with the trader's own checklist coded in. Either the edge lives in discretion that
  price-derived features do not capture (reading OB/FVG quality, context, momentum on lower
  timeframes), or the journal reflects hindsight. For example, manual backtesting on bar replay
  makes it easy to skip or mis-log setups that would have failed.
- Forward-test with live or replay trades logged *before* the outcome is known, before risking money.

## Limitations

- **Reconstructed inputs:** the journal has no direction, prices, stops or size. Direction and entry
  price were inferred from the entry minute, duration, MAE and MFE. Direction is identified for 213 of
  250 trades: 160 from the price path alone, 53 with the fib as a tie-breaker. The stop is inferred
  from MAE (losers) or the favourable move at the logged time ÷ RR (wins and "BE").
- **Proxy data:** Dukascopy's Nasdaq-100 CFD, not NQ futures. Against NQ=F 5-minute bars
  (Aug 20 – Oct 16) the 5-minute return correlation is 0.9965 and bar ranges agree within ~2%; the
  price level differs by ~177 pts, drifting ~6.5 pts per session.
- **1-minute resolution:** stops of 12–25 pts are close to the size of a 1-minute NQ candle, so the
  order of high and low within the entry bar is unknown. The backtest only counts a stop on the fill
  bar if that bar closes beyond it, and assumes the stop is hit first when stop and target share a bar.
- **Journal fields:** for "BE" trades, the logged time is when the trade peaked, not when it was
  stopped at the entry. For wins, "RR Achieved" does not match the stated 3–4R target on half the
  trades, so it is unclear what that column measures.
- **Sample:** one instrument, seven months, during a strong Nasdaq uptrend (~24,900 in March to
  ~30,000 by June). Results may not generalise.
