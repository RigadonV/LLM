# How well the reconstructed strategy matches the journal

`replicate_strategy.py` codes the rules from `STRATEGY.md` and runs them minute by minute over
10 Mar – 16 Oct 2026 on 1-minute data. A generated trade **matches** a journal trade when it is on
the same day, in the same direction (where the direction is known), and enters within ±15 minutes.
Precision is measured on the 131 days the trader actually logged trades; trades generated on the 28
weekdays with no journal entries (holidays and a late-August gap) are reported separately.

## Result

| Round | Rules | Generated | Matched (recall) | Precision | Extra trades |
|---|---|---|---|---|---|
| Baseline | 0.79 limit on the most recent 15M leg ≥1.5 ATR; stop 0.14 × leg; 3R target, break-even at 2R | 581 | 126 (50%) | 22% | 455 (+125 on unlogged days) |
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

## Outcomes do not reproduce

| | Journal | Mechanical rules |
|---|---|---|
| Loss rate, all trades | 16% | 67% |
| Loss rate, the 142 matched trades | 20% | 51% |
| Average R, the 142 matched trades | +2.40R | +0.67R |
| Average R per trade, all trades | +2.54R | +0.09R |

All 29 journal losses among the matched trades are also losses in the backtest. But 35 of the 97
matched journal winners are stopped out mechanically. No exit variant closes the gap: a 2R target,
3R with or without break-even, or the leg extreme all give −0.03R to +0.12R per trade
(`results/validation_variants.csv`).

**What this means:**
- The *entry mechanics* — session window, 15M leg, 0.705/0.79 limit, stop at ~0.14 of the leg — are
  recoverable and explain over half of the trades.
- The trader's *selection* of which setups to take, and the journal's very high win rate, are not.
  Either the edge lives in discretion that price-derived features do not capture (reading OB/FVG
  quality, context, momentum on lower timeframes), or the journal reflects hindsight. For example,
  manual backtesting on bar replay makes it easy to skip or mis-log setups that would have failed.
- Forward-test with live or replay trades logged *before* the outcome is known, before risking money.

## Limitations

- **Reconstructed inputs:** the journal has no direction, prices, stops or size. Direction and entry
  price were inferred from the entry minute, duration, MAE and MFE. Direction is identified for 213 of
  250 trades: 160 from the price path alone, 53 with the fib as a tie-breaker. The stop is inferred
  from MAE (losers) or the favourable move ÷ RR (non-losers).
- **Proxy data:** Dukascopy's Nasdaq-100 CFD, not NQ futures. Against NQ=F 5-minute bars
  (Aug 20 – Oct 16) the 5-minute return correlation is 0.9965 and bar ranges agree within ~2%; the
  price level differs by ~177 pts, drifting ~6.5 pts per session.
- **1-minute resolution:** stops of 12–25 pts are close to the size of a 1-minute NQ candle, so the
  order of high and low within the entry bar is unknown. The backtest only counts a stop on the fill
  bar if that bar closes beyond it, and assumes the stop is hit first when stop and target share a bar.
- **"BE" interpretation:** "BE" trades are treated as closed in profit at their logged RR (they never
  reached 2.98R). This fits the Stats sheet definition and the price path better than a break-even
  scratch, but it is an interpretation.
- **Exits** are modelled as a fixed R target; the trader's real exits are discretionary.
- **Sample:** one instrument, seven months, during a strong Nasdaq uptrend (~24,900 in March to
  ~30,000 by June). Results may not generalise.
