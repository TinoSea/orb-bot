# FTMO $10,000 2-Step Challenge — gold bot, in-sample (H-002 amendment 17)

Trades: `research/results/h002/gate0/replica_XAUUSD_M1_IS.csv`: 112 signals, 1 removed by the Friday 15:00 New York cutoff, 111 kept = **3.8 trades a month**. Cost stress +$0.30/oz. Mean result after costs **+0.108R** per trade.
Rules: +10% then +5%; equity above CE(S)T-midnight balance − $500 and above $9,000; ≥4 trading days; no time limit. Produced by `research/ftmo_sim.py`.

## A. Historical: one challenge started each month (real trade order)

|   risk_% |   starts |   passed |   failed |   unfinished |   pass_%_of_finished |   median_months_to_pass |
|---------:|---------:|---------:|---------:|-------------:|---------------------:|------------------------:|
|      0.5 |       30 |        0 |        0 |           30 |                  nan |                  nan    |
|      1   |       30 |        9 |        0 |           21 |                  100 |                   18.8  |
|      1.5 |       30 |       16 |        3 |           11 |                   84 |                    8.05 |
|      2   |       30 |       24 |        5 |            1 |                   83 |                    6.9  |

<details><summary>Every start at 1% risk</summary>

| start   | phase1     |   p1_trades | phase2     |   p2_trades |   months | result     |
|:--------|:-----------|------------:|:-----------|------------:|---------:|:-----------|
| 2023-01 | pass       |         111 | unfinished |           0 |    nan   | unfinished |
| 2023-02 | pass       |         105 | unfinished |           2 |    nan   | unfinished |
| 2023-03 | pass       |         104 | unfinished |           2 |    nan   | unfinished |
| 2023-04 | pass       |          99 | unfinished |           2 |    nan   | unfinished |
| 2023-05 | pass       |          94 | unfinished |           5 |    nan   | unfinished |
| 2023-06 | pass       |          88 | unfinished |           5 |    nan   | unfinished |
| 2023-07 | pass       |          38 | pass       |          51 |     23.2 | PASS       |
| 2023-08 | pass       |          36 | pass       |          51 |     22   | PASS       |
| 2023-09 | pass       |          31 | pass       |          51 |     20.4 | PASS       |
| 2023-10 | pass       |          29 | pass       |          51 |     20.1 | PASS       |
| 2023-11 | pass       |          25 | pass       |          50 |     18.8 | PASS       |
| 2023-12 | pass       |          23 | pass       |          51 |     18   | PASS       |
| 2024-01 | pass       |          19 | pass       |          51 |     16.8 | PASS       |
| 2024-02 | pass       |          15 | pass       |          51 |     16.1 | PASS       |
| 2024-03 | pass       |          12 | pass       |          51 |     15.3 | PASS       |
| 2024-04 | unfinished |          59 | -          |           0 |    nan   | unfinished |
| 2024-05 | unfinished |          55 | -          |           0 |    nan   | unfinished |
| 2024-06 | unfinished |          53 | -          |           0 |    nan   | unfinished |
| 2024-07 | pass       |          47 | unfinished |           0 |    nan   | unfinished |
| 2024-08 | unfinished |          43 | -          |           0 |    nan   | unfinished |
| 2024-09 | unfinished |          39 | -          |           0 |    nan   | unfinished |
| 2024-10 | pass       |          32 | unfinished |           2 |    nan   | unfinished |
| 2024-11 | pass       |          27 | unfinished |           4 |    nan   | unfinished |
| 2024-12 | unfinished |          27 | -          |           0 |    nan   | unfinished |
| 2025-01 | pass       |          21 | unfinished |           2 |    nan   | unfinished |
| 2025-02 | unfinished |          20 | -          |           0 |    nan   | unfinished |
| 2025-03 | unfinished |          16 | -          |           0 |    nan   | unfinished |
| 2025-04 | unfinished |          12 | -          |           0 |    nan   | unfinished |
| 2025-05 | unfinished |          10 | -          |           0 |    nan   | unfinished |
| 2025-06 | unfinished |           5 | -          |           0 |    nan   | unfinished |

</details>

## B. Monte Carlo: 10,000 challenges, whole trading days resampled

| scenario    |   risk_% |   pass_% |   fail_daily_% |   fail_max_% |   months_median |   months_p90 |
|:------------|---------:|---------:|---------------:|-------------:|----------------:|-------------:|
| as measured |      0.5 |     92.8 |            0   |          7.2 |            75.8 |        158   |
| as measured |      1   |     71   |            0   |         29   |            23.6 |         50.6 |
| as measured |      1.5 |     57.5 |            0   |         42.5 |            11.7 |         25.2 |
| as measured |      2   |     50   |            0   |         50   |             7.2 |         15.1 |
| edge halved |      0.5 |     69.8 |            0   |         30.2 |           105.8 |        236   |
| edge halved |      1   |     50.8 |            0   |         49.2 |            25.7 |         57   |
| edge halved |      1.5 |     43   |            0   |         57   |            11.9 |         26   |
| edge halved |      2   |     37.6 |            2.8 |         59.6 |             7.2 |         15.1 |
| no edge     |      0.5 |     27.2 |            0   |         72.8 |           116.1 |        271.5 |
| no edge     |      1   |     29.8 |            0   |         70.2 |            26.4 |         57.8 |
| no edge     |      1.5 |     29   |            0   |         71   |            12.2 |         26.5 |
| no edge     |      2   |     26   |            8.1 |         65.9 |             6.9 |         14.6 |

pass_% = both phases passed. fail_daily / fail_max = which FTMO limit ended the attempt. Months from the first trade to passing Phase 2, at the in-sample trade rate.

## Decision rule (amendment 17, scenario "edge halved")

- Eligible levels (median ≤ 18 months): 1.5%, 2%.
- Highest pass probability: **1.5% risk → 43.0%**, median 11.9 months (90th percentile 26.0).
- This is BELOW the 50% bar.

## C. Funded year at 1.5% risk (monthly payouts, 80% split)

| scenario    |   breach_in_year_% |   payout_mean_$ |   payout_median_$ |   payout_p10_$ |   payout_p90_$ |
|:------------|-------------------:|----------------:|------------------:|---------------:|---------------:|
| as measured |               41   |             904 |               786 |              0 |           1928 |
| edge halved |               51.7 |             728 |               595 |              0 |           1682 |
| no edge     |               61.9 |             577 |               426 |              0 |           1404 |

A breach ends the account; payouts already taken are kept. FTMO also refunds the fee with the first reward.

