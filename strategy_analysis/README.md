# strategy_analysis/

Reverse-engineering of the "Model 2 – London" NQ trade journal (`Model2_London_Journal_V4.xlsx`,
250 trades, Mar–Oct 2026).

| File | What it is |
|---|---|
| `STRATEGY.md` | The strategy as numbered rules, with confidence levels and an example chart |
| `VALIDATION.md` | How well the coded rules reproduce the journal, and the limitations |
| `trade_context.csv` | One row per journal trade: journal fields + inferred direction/prices + market context |
| `charts/` | Five representative trades (long win, short win, loss, "BE", one that does not fit), drawn on the UK clock |
| `replicate_strategy.py` | The validation backtest (baseline, two refinement rounds, exit alternatives, the trader's checklist) |
| `results/` | Intermediate outputs: timezone test, time-zone re-reading check, London session windows, direction inference, leg-definition test, condition table, sensitivity grid, backtest trades |
| `pipeline/` | The scripts that produce everything above |

## Reproduce

Python 3 with pandas, numpy, openpyxl and matplotlib. Needs network access to `datafeed.dukascopy.com`.

```bash
cd strategy_analysis/pipeline
python fetch_data.py                      # 1m + 1h Nasdaq-100 candles -> ../data/ (git-ignored)
J=/path/to/Model2_London_Journal_V4.xlsx
python infer_direction.py "$J"            # Step 2: timezone test, direction + entry price per trade
python leg_definition.py "$J"             # Step 4a: which swing-leg definition fits the logged fib levels
python build_context.py "$J"              # Step 3: ../trade_context.csv
python find_patterns.py                   # Step 4: ../results/patterns_report.txt
python sensitivity.py "$J"                # Step 5b: rule sensitivity grid
python ../replicate_strategy.py "$J"      # Step 5: validation backtest -> ../results/validation_variants.csv
python london_time_check.py "$J"          # journal times re-read in other time zones; London-only windows
python make_charts.py --ids 196:long_win,246:short_win,167:loss,61:be_at_2R,10:does_not_fit
python check_proxy.py nq_5m.json          # optional: CFD vs NQ futures check (Yahoo chart-API JSON)
```

## `trade_context.csv` columns

Times (`*_et`, `*_time`) are **New York clock**, as the journal logs them (UK = New York + 5h; +4h
from 8 to 28 March and 25 Oct to 1 Nov). Prices are **Dukascopy Nasdaq-100 CFD** prices, about 177 points below NQ futures over the sample.
Distances in points carry over to NQ within ~2%. Indicator values come from the last bar that
*closed before* the entry, except `entrybar*`, which describe the candle containing the entry.

| Group | Columns |
|---|---|
| Journal | `trade_id` (= sheet row), `date`, `entry_et`, `exit_et` (= entry + minutes), `fib_level`, `result`, `rr`, `mae_pts`, `mfe_r`, `minutes`, `trend_aligned`, `pa_type`, `fvg_tf`, `ob_tf`, `key_open`, `news`, `rating`, `notes`, `chart_url` |
| Time | `hour`, `dow`, `session`, `mins_after_0200`, `news_day` |
| Inferred trade | `direction`, `direction_confidence` (high = price path alone, medium = fib tie-break), `entry_price_est`, `stop_pts_est`, `stop_price_est`, `exit_price_est` (BE trades: the entry), `exit_time_est` (BE trades: first return to the entry after the peak) |
| Fib leg (most recent valid 15M leg) | `fib_anchor_time/price` (1.0), `fib_extreme_time/price` (0.0), `leg_size_pts`, `leg_minutes`, `mins_since_extreme`, `fib_ratio_at_entry`, `fib_match` (within ±0.05 of the logged level), `best_leg_ratio`, `best_leg_is_recent` |
| Stop / exit geometry | `stop_atr15`, `stop_leg_frac`, `stop_fib_coord`, `stop_beyond_anchor_pts`, `exit_fib_coord`, `target_nearest_level`, `target_dist_to_level_R` |
| Trend | `{15m,1h,4h,1D}_px_vs_ema{20,50,200}` (distance in ATRs, + = above), `_ema*_slope` (ATRs per 4 bars), `_trend` (up/down/mixed vs EMA50), `_trend_with_trade` |
| Momentum / volatility | `{15m,1h}_rsi14`, `_macd_hist`, `_stoch_k/_d`, `_atr14`, `_bb_pctb`; `4h/1D_rsi14` |
| Key levels | `open_1800`, `open_0000`, `asia_high/low` (20:00–00:00), `london_high/low_so_far`, `overnight_high/low`, `pdh`, `pdl`, `vs_0000_open`, `vs_1800_open`, `entry_favourable_vs_0000`, `pos_in_overnight_range`, `asia_high/low_swept` |
| Structure | `leg_anchor_swept_asia`, `leg_anchor_swept_pd`, `leg_broke_structure`, `{fvg,ob}_{15m,30m,1h}_at_entry` |
| Candles | `prev15_pattern`, `entrybar15_pattern`, `entrybar15_rejection_wick_frac`, `entrybar15_closed_in_favour`, `entrybar5_pattern` |
| At exit | `exit_15m_rsi14`, `exit_15m_px_vs_ema20`, `exit_session` |
