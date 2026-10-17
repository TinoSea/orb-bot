# $ 200 gold account — H-002 amendment 16 (in-sample only)

Trade list: `research/results/h002/gate0/replica_XAUUSD_M1_IS.csv` (112 signals, 2023-01-04 → 2025-06-19, 46 a year). Produced by `research/small_account.py`.
Smallest position 1 oz. Today's price used: $4,190. Cost stress: +$0.30/oz per trade. P3 cap: 5%. Stop-out assumed at 50% margin level.

## Is there an edge to size? (in-sample, every signal, $5,000 research run)

- 112 trades, expectancy **+0.135R**, profit factor 1.27, win rate 46%.
- 95% bootstrap range for expectancy: **-0.089R to +0.355R** (12% of resamples at or below zero).
- Longs: 67 trades, +0.163R each. Shorts: 45 trades, +0.093R each.
- Same rules on 60 random walks (no edge possible, no costs), same span: expectancy 5th–95th percentile **-0.211R to +0.185R** (median -0.017R). 12% of them did at least as well as gold.

## Stop size: what one ounce risks

| | historical prices | at today's price |
|---|---|---|
| 25th percentile stop | $7.50 (4% of $200) | $14.90 (7% of $200) |
| median stop | $11.88 (6% of $200) | $21.08 (11% of $200) |
| 90th percentile stop | $28.07 (14% of $200) | $49.71 (25% of $200) |

Account needed for 1 oz = 1% at the median stop today: about **$2,100**.

## Replays (one pass through the in-sample trades, in order)

| run                   | policy   |   signals |   taken |   median_risk_% |   max_risk_% |   expectancy_R |   end_balance |   lowest_balance |   max_drawdown_% |   usd_per_month |   margin>50%eq_1:20 |   margin>50%eq_1:100 |   margin>50%eq_1:500 |   stop_out_1:20 |   stop_out_1:100 |   stop_out_1:500 |
|:----------------------|:---------|----------:|--------:|----------------:|-------------:|---------------:|--------------:|-----------------:|-----------------:|----------------:|--------------------:|---------------------:|---------------------:|----------------:|-----------------:|-----------------:|
| a historical          | P1       |       112 |       0 |           nan   |        nan   |        nan     |        200    |           200    |              0   |            0    |                   0 |                    0 |                    0 |               0 |                0 |                0 |
| a historical          | P2       |       112 |     112 |             5.9 |         24.5 |          0.135 |        522.92 |           106.79 |             49.8 |           10.97 |                  80 |                    0 |                    0 |               0 |                0 |                0 |
| a historical          | P3       |       112 |      47 |             3.4 |          5   |          0.04  |        199.85 |           187.9  |             21.3 |           -0.01 |                  29 |                    0 |                    0 |               0 |                0 |                0 |
| b today's price       | P1       |       112 |       0 |           nan   |        nan   |        nan     |        200    |           200    |              0   |            0    |                   0 |                    0 |                    0 |               0 |                0 |                0 |
| b today's price       | P2       |       112 |     112 |            12.1 |        833.9 |          0.138 |        639.17 |             3.68 |             98.4 |           14.92 |                  99 |                   34 |                    2 |              40 |                4 |                2 |
| b today's price       | P3       |       112 |      13 |             3.5 |          4.7 |          0.222 |        216.61 |           193.92 |              8.3 |            0.56 |                  13 |                    0 |                    0 |               0 |                0 |                0 |
| c today + cost stress | P1       |       112 |       0 |           nan   |        nan   |        nan     |        200    |           200    |              0   |            0    |                   0 |                    0 |                    0 |               0 |                0 |                0 |
| c today + cost stress | P2       |       112 |      21 |            18.9 |         93.2 |         -0.344 |         -2.62 |            -2.62 |            101.1 |           -6.88 |                  21 |                   10 |                    0 |              12 |                1 |                1 |
| c today + cost stress | P3       |       112 |      13 |             3.5 |          4.7 |          0.182 |        212.71 |           193.62 |              8.9 |            0.43 |                  13 |                    0 |                    0 |               0 |                0 |                0 |

A replay stops when the balance reaches zero (a broker stop-out would usually come earlier). `taken` below `signals` for P2 means the account was wiped out; for P3 it means wide-stop trades were skipped. margin>50%eq counts trades whose margin needed more than half the equity; stop_out counts trades whose worst open loss would have triggered the broker's stop-out.

## Monte Carlo (run d): 10,000 random orderings at today's price with cost stress

| policy   |   trades |   P(lose half)_% |   P(end below start)_% |   P(reach $2,100)_% |   end_p5 |   end_median |   end_p95 |   median_max_dd_% |
|:---------|---------:|-----------------:|-----------------------:|--------------------:|---------:|-------------:|----------:|------------------:|
| P2       |      100 |             41   |                   22   |                   0 |      -19 |          544 |      1099 |              56.8 |
| P2       |       46 |             35.4 |                   24.3 |                   0 |      -13 |          363 |       738 |              48.8 |
| P3       |      100 |              0   |                   33.2 |                   0 |      167 |          212 |       274 |              12.5 |
| P3       |       46 |              0   |                   37.6 |                   0 |      175 |          207 |       250 |               7.7 |

Lag-1 autocorrelation of trade results: -0.09 (near zero supports drawing trades independently).

## Decision rule (amendment 16)

| Test | P2 | P3 |
|---|---|---|
| 1. P(lose half in 100 trades) ≤ 10% | 41.0% FAIL | 0.0% pass |
| 2. Median risk per trade ≤ 5% | 18.9% FAIL | 3.5% pass |
| 3. Margin ≤ 50% of equity at 1:20 (trades breaching) | 21 FAIL | 13 FAIL |
| 3. Margin ≤ 50% of equity at 1:100 (trades breaching) | 10 FAIL | 0 pass |
| 3. Margin ≤ 50% of equity at 1:500 (trades breaching) | 0 pass | 0 pass |

Test 3 depends on the account's real leverage (MT5: right-click the account in Navigator, or the account details at FP Markets).

