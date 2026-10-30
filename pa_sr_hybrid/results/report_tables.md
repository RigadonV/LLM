## Data

| Market | Dukascopy symbol | History used from | Bars in test window | Median spread (pips/points) | Median spread (% of ATR) |
|---|---|---|---|---|---|
| EUR/USD | EURUSD | 2007-01-01 | 522 | 0.5 | 0.67% |
| GBP/USD | GBPUSD | 2007-01-01 | 522 | 0.9 | 1.02% |
| USD/JPY | USDJPY | 2007-01-01 | 522 | 0.7 | 0.56% |
| AUD/USD | AUDUSD | 2007-01-01 | 522 | 1.0 | 1.84% |
| USD/CAD | USDCAD | 2007-01-01 | 522 | 1.5 | 2.28% |
| USD/CHF | USDCHF | 2007-01-01 | 522 | 1.0 | 1.81% |
| NZD/USD | NZDUSD | 2007-01-01 | 522 | 1.1 | 2.16% |
| Gold | XAUUSD | 2007-01-01 | 520 | 7.0 | 1.10% |
| S&P 500 | USA500IDXUSD | 2013-05-22 | 520 | 5.3 | 0.74% |
| Nasdaq-100 | USATECHIDXUSD | 2013-05-22 | 520 | 14.6 | 0.38% |
| DAX 40 | DEUIDXEUR | 2015-01-01 | 520 | 74.2 | 2.20% |
| FTSE 100 | GBRIDXGBP | 2013-05-23 | 519 | 61.1 | 4.80% |
| Nikkei 225 | JPNIDXJPY | 2013-05-21 | 520 | 7.1 | 0.77% |
| Brent crude | BRENTCMDUSD | 2013-05-23 | 516 | 8.6 | 3.57% |
| Silver | XAGUSD | 2007-01-01 | 520 | 42.0 | 3.33% |


## Variants (same-day cases replayed on hourly bars; any left over counted the worse way)

| Variant | Trades | Per year | Win rate | Avg R | 95% CI | p(avg ≤ 0) | Profit factor | Max DD (R) | CAGR at 1% | Max DD at 1% | Settled by rule |
|---|---|---|---|---|---|---|---|---|---|---|---|
| V0 Trend only | 989 | 494.8 | 38% | +0.037 | -0.06 to +0.13 | 0.231 | 1.06 | 57.9 | +11.3% | 44.4% | 1% |
| V1 S/R only | 712 | 356.2 | 31% | -0.101 | -0.19 to -0.02 | 0.995 | 0.86 | 87.0 | -32.3% | 59.2% | 1% |
| V2 S/R + trend | 475 | 237.7 | 32% | -0.074 | -0.18 to +0.02 | 0.930 | 0.89 | 46.2 | -17.9% | 38.3% | 1% |
| V3 PA only | 650 | 325.2 | 37% | +0.020 | -0.15 to +0.21 | 0.418 | 1.03 | 50.3 | +1.3% | 38.1% | 0% |
| V4 Hybrid | 98 | 49.0 | 44% | +0.098 | -0.17 to +0.37 | 0.242 | 1.18 | 11.1 | +4.4% | 10.7% | 0% |
| V4a Hybrid without trend | 128 | 64.0 | 38% | -0.025 | -0.28 to +0.22 | 0.594 | 0.96 | 19.3 | -2.1% | 18.0% | 0% |
| V4b Hybrid without room rule | 250 | 125.1 | 39% | -0.003 | -0.21 to +0.20 | 0.507 | 1.00 | 25.8 | -1.8% | 23.5% | 0% |
| V4c Hybrid, 1-touch levels | 51 | 25.5 | 29% | -0.300 | -0.62 to +0.03 | 0.964 | 0.58 | 18.5 | -7.5% | 17.1% | 0% |
| V4d Hybrid, next-open entry | 124 | 62.0 | 39% | +0.057 | -0.14 to +0.24 | 0.286 | 1.10 | 11.4 | +3.2% | 10.1% | 1% |


## Average R under each way of settling same-day cases, and the cost of trading

| Variant | Daily bars, worse way | Daily bars, better way | Hourly, worse way | Hourly, better way | Hourly, before costs | Spread + commission per trade |
|---|---|---|---|---|---|---|
| V0 Trend only | -0.027 | +0.052 | +0.037 | +0.052 | +0.079 | 0.043R |
| V1 S/R only | -0.089 | +0.073 | -0.101 | -0.060 | -0.058 | 0.042R |
| V2 S/R + trend | -0.068 | +0.196 | -0.074 | -0.042 | -0.023 | 0.050R |
| V3 PA only | -0.000 | +0.000 | +0.020 | +0.021 | +0.045 | 0.025R |
| V4 Hybrid | +0.086 | +0.086 | +0.098 | +0.098 | +0.110 | 0.013R |
| V4a Hybrid without trend | -0.032 | -0.040 | -0.025 | -0.025 | -0.016 | 0.009R |
| V4b Hybrid without room rule | -0.007 | -0.007 | -0.003 | +0.001 | +0.017 | 0.020R |
| V4c Hybrid, 1-touch levels | -0.300 | -0.252 | -0.300 | -0.300 | -0.276 | 0.024R |
| V4d Hybrid, next-open entry | +0.057 | +0.082 | +0.057 | +0.082 | +0.154 | 0.097R |


## Hybrid (V4) breakdown (hourly-settled, cons)

| Split | Group | Trades | Win rate | Avg R | 95% CI | Profit factor |
|---|---|---|---|---|---|---|
| Period | Oct 2024 – Sep 2025 | 49 | 41% | +0.068 | -0.32 to +0.46 | 1.12 |
| Period | Oct 2025 – Sep 2026 | 49 | 47% | +0.128 | -0.28 to +0.49 | 1.25 |
| Asset class | Commodity | 16 | 38% | +0.024 | -0.71 to +0.83 | 1.04 |
| Asset class | FX | 51 | 37% | -0.047 | -0.47 to +0.33 | 0.92 |
| Asset class | Index | 31 | 58% | +0.373 | -0.07 to +0.83 | 1.94 |
| Side | long | 71 | 46% | +0.179 | -0.16 to +0.48 | 1.35 |
| Side | short | 27 | 37% | -0.117 | -0.55 to +0.35 | 0.81 |
| Level touches | 2 touches | 73 | 41% | +0.020 | -0.31 to +0.33 | 1.03 |
| Level touches | 3+ touches | 25 | 52% | +0.324 | -0.13 to +0.78 | 1.75 |
| Level type | flipped level | 32 | 47% | +0.147 | -0.27 to +0.52 | 1.27 |
| Level type | same-side level | 66 | 42% | +0.074 | -0.22 to +0.40 | 1.13 |
| Round number | not round | 85 | 44% | +0.072 | -0.22 to +0.36 | 1.13 |
| Round number | round number | 13 | 46% | +0.262 | -0.44 to +1.13 | 1.48 |
| Exit | end | 3 | 100% | +0.517 | +nan to +nan | – |
| Exit | stop | 51 | 0% | -1.030 | -1.07 to -1.01 | 0.00 |
| Exit | target | 25 | 100% | +1.992 | +1.99 to +1.99 | – |
| Exit | time | 19 | 79% | +0.566 | +0.31 to +0.79 | 12.08 |


## Hybrid vs baselines by asset class and side

| Asset class | Side | Hybrid trades | Hybrid avg R | PA only (V3) avg R | Trend only (V0) avg R |
|---|---|---|---|---|---|
| Commodity | long | 11 | +0.218 | +0.339 | +0.425 |
| Commodity | short | 5 | -0.402 | -0.299 | -0.148 |
| FX | long | 31 | -0.041 | -0.046 | -0.004 |
| FX | short | 20 | -0.055 | -0.260 | -0.164 |
| Index | long | 29 | +0.400 | +0.165 | +0.043 |
| Index | short | 2 | -0.028 | -0.438 | -0.249 |


## Hybrid (V4) by market

| Market | Trades | Win rate | Avg R | Total R |
|---|---|---|---|---|
| AUD/USD | 7 | 14% | -0.580 | -4.1 |
| Gold | 3 | 33% | -0.529 | -1.6 |
| USD/JPY | 6 | 17% | -0.511 | -3.1 |
| USD/CHF | 5 | 40% | -0.386 | -1.9 |
| GBP/USD | 5 | 20% | -0.360 | -1.8 |
| DAX 40 | 6 | 33% | -0.132 | -0.8 |
| Silver | 6 | 33% | -0.002 | -0.0 |
| USD/CAD | 14 | 50% | +0.210 | +2.9 |
| S&P 500 | 6 | 50% | +0.238 | +1.4 |
| Brent crude | 7 | 43% | +0.284 | +2.0 |
| EUR/USD | 9 | 44% | +0.364 | +3.3 |
| NZD/USD | 5 | 60% | +0.451 | +2.3 |
| FTSE 100 | 8 | 75% | +0.506 | +4.0 |
| Nikkei 225 | 7 | 71% | +0.571 | +4.0 |
| Nasdaq-100 | 4 | 50% | +0.720 | +2.9 |
