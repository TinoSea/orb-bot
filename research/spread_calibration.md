# Spread calibration (real tick spreads vs stored bar spreads)

From `mt5/ExportSpreads.mq5`; multipliers written to `research/h002_costs.csv`. A multiplier below 1 is set to 1 (costs are never reduced).

| label   | symbol   |   hours_sampled |   median_bar_spread_pts |   median_tick_spread_pts |   p90_tick_spread_pts |   spread_mult |
|:--------|:---------|----------------:|------------------------:|-------------------------:|----------------------:|--------------:|
| AGRI    | COFFEE   |             252 |                     100 |                      100 |                   100 |          1    |
| AUDUSD  | AUDUSD.r |             908 |                       0 |                        2 |                     5 |          2    |
| BOND    | US10YR   |             356 |                       4 |                        4 |                     4 |          1    |
| BTCUSD  | BTCUSD   |            1466 |                    1700 |                     1720 |                  2590 |          1    |
| EURUSD  | EURUSD.r |             908 |                       0 |                        0 |                     3 |          1    |
| GBPUSD  | GBPUSD.r |             908 |                       0 |                        2 |                     5 |          2    |
| GER40   | GER40    |             585 |                      50 |                       50 |                    50 |          1    |
| JP225   | JP225    |             390 |                     450 |                     1050 |                  1550 |          2.33 |
| UK100   | UK100    |             576 |                     100 |                      100 |                   100 |          1    |
| US100   | US100    |             386 |                      60 |                       60 |                    60 |          1    |
| US30    | US30     |             386 |                     110 |                      110 |                   110 |          1    |
| US500   | US500    |             386 |                      25 |                       25 |                    25 |          1    |
| USDJPY  | USDJPY.r |             908 |                       1 |                        3 |                     7 |          2.5  |
| WTI     | XTIUSD   |             389 |                      10 |                       20 |                    20 |          2    |
| XAGUSD  | XAGUSD.r |             581 |                      25 |                       35 |                    41 |          1.38 |
| XAUUSD  | XAUUSD.r |             581 |                       7 |                        9 |                    14 |          1.1  |
