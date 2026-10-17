# Data quality: FP Markets export (2026-10-17)

Produced by `research/prepare_export.py` from the `mt5/ExportData.mq5` export. Server time = New York + 7 h. No strategy results are used or shown here.

## Decisions from pre-registered rules

- AGRI = **COFFEE** (first candidate in the registered order that passes the coverage rule).
- BOND = US10YR passes the coverage rule.
- BTCUSD: only 12 weekend bars in the whole history - FP Markets' Bitcoin CFD is closed at weekends.

## Per file

| label       | tf   | symbol   |    bars | first      | last       |   server_sat_sun_bars |   max_missing_weekdays |   max_gap_hours |   bad_ohlc |   duplicates |   zero_spread_pct |   median_spread_points |   largest_jump_pct | largest_jump_at   | coverage_rule   |
|:------------|:-----|:---------|--------:|:-----------|:-----------|----------------------:|-----------------------:|----------------:|-----------:|-------------:|------------------:|-----------------------:|-------------------:|:------------------|:----------------|
| AGRI_COCOA  | M5   | COCOA    |   95160 | 2022-12-01 | 2026-10-16 |                     0 |                      2 |           112.3 |          0 |            0 |               0.3 |                   1400 |               9.5  | 2024-04-30 12:45  | pass            |
| AGRI_COFFEE | M5   | COFFEE   |  100831 | 2022-12-01 | 2026-10-16 |                     0 |                      2 |           111.8 |          0 |            0 |               0   |                     85 |               6.3  | 2025-11-18 11:15  | pass            |
| AGRI_CORN   | M5   | CORN     |  196988 | 2022-12-01 | 2026-10-16 |                     0 |                      2 |           101.8 |          0 |            0 |               0   |                     70 |               3.28 | 2026-05-18 03:00  | pass            |
| AGRI_COTTON | M5   | COTTON   |  127759 | 2024-03-11 | 2026-10-16 |                     0 |                     15 |           571.1 |          0 |            0 |               0   |                    212 |               6.6  | 2024-07-15 16:15  | FAIL            |
| AGRI_SUGAR  | M5   | SUGAR    |   69816 | 2024-03-11 | 2026-10-16 |                     0 |                      4 |           164.8 |          0 |            0 |               0   |                    203 |               7.15 | 2025-02-25 11:30  | FAIL            |
| AGRI_WHEAT  | M5   | WHEAT    |  201473 | 2022-12-01 | 2026-10-16 |                     0 |                      2 |           101.8 |          0 |            0 |               0   |                    210 |               3.29 | 2023-12-27 03:00  | pass            |
| AUDUSD      | M5   | AUDUSD.r |  289086 | 2022-12-01 | 2026-10-16 |                    12 |                      2 |            96.1 |          0 |            0 |              71.5 |                      0 |               1.06 | 2026-03-02 00:00  | pass            |
| BOND        | M5   | US10YR   |  230227 | 2022-12-01 | 2026-10-16 |                     0 |                      2 |           114.4 |          0 |            0 |               0   |                      8 |               0.82 | 2025-04-07 01:00  | pass            |
| BTCUSD      | M5   | BTCUSD   |  289185 | 2022-12-01 | 2026-10-16 |                    12 |                      2 |            96.2 |          0 |            0 |               0.8 |                   1500 |              11.76 | 2025-03-03 00:05  | pass            |
| EURUSD      | M5   | EURUSD.r |  289116 | 2022-12-01 | 2026-10-16 |                    12 |                      2 |            96.1 |          0 |            0 |              88.5 |                      0 |               1.11 | 2025-02-03 00:00  | pass            |
| GBPUSD      | M5   | GBPUSD.r |  289092 | 2022-12-01 | 2026-10-16 |                    12 |                      2 |            96.1 |          0 |            0 |              73.5 |                      0 |               0.86 | 2025-02-03 00:00  | pass            |
| GER40       | M5   | GER40    |  270128 | 2022-12-01 | 2026-10-16 |                     1 |                      3 |           123.3 |          0 |            0 |               0.1 |                     80 |               2.44 | 2026-03-23 14:15  | pass            |
| JP225       | M5   | JP225    |  273662 | 2022-12-01 | 2026-10-16 |                     0 |                      3 |           121.1 |          0 |            0 |               0.1 |                    460 |               2.84 | 2025-10-06 01:00  | pass            |
| UK100       | M5   | UK100    |  266447 | 2022-12-01 | 2026-10-16 |                     0 |                      3 |           130.2 |          0 |            0 |               0.1 |                    120 |               2.07 | 2025-04-07 01:00  | pass            |
| US100       | M5   | US100    |  274006 | 2022-12-01 | 2026-10-16 |                     0 |                      2 |            97.2 |          0 |            0 |               0.7 |                    140 |               2.77 | 2025-04-07 01:00  | pass            |
| US30        | M5   | US30     |  274026 | 2022-12-01 | 2026-10-16 |                     0 |                      2 |            97.2 |          0 |            0 |               0.6 |                    140 |               2.59 | 2025-04-07 01:00  | pass            |
| US500       | M5   | US500    |  274059 | 2022-12-01 | 2026-10-16 |                     0 |                      2 |            97.2 |          0 |            0 |               0.1 |                     50 |               2.09 | 2025-04-07 01:00  | pass            |
| USDJPY      | M5   | USDJPY.r |  289107 | 2022-12-01 | 2026-10-16 |                    12 |                      2 |            96.1 |          0 |            0 |              63   |                      0 |               1.31 | 2025-10-06 00:00  | pass            |
| WTI         | M5   | XTIUSD   |  273754 | 2022-12-01 | 2026-10-16 |                     0 |                      2 |            97.3 |          0 |            0 |               0   |                      5 |              11.38 | 2026-03-02 01:00  | pass            |
| XAGUSD      | M5   | XAGUSD.r |  274586 | 2022-12-01 | 2026-10-16 |                    12 |                      2 |            97.1 |          0 |            0 |               0   |                     11 |               3.03 | 2026-02-02 01:00  | pass            |
| XAUUSD      | M1   | XAUUSD.r | 1372326 | 2022-12-01 | 2026-10-16 |                    58 |                      2 |            97.1 |          0 |            0 |               6.2 |                      4 |               2.27 | 2026-04-13 01:00  | pass            |
| XAUUSD      | M5   | XAUUSD.r |  274658 | 2022-12-01 | 2026-10-16 |                    12 |                      2 |            97.1 |          0 |            0 |               8.2 |                      4 |               2.27 | 2026-04-13 01:00  | pass            |

## How to read it

- **zero_spread_pct / median_spread_points:** MT5 stores one spread value per bar (in points). FX on the Raw account is often 0.0 pips; its cost is the commission instead. Bar spreads understate costs at busy moments, hence the spreads x 2 robustness run (R5).
- **largest_jump:** biggest move between one bar's close and the next bar's open. For futures-based CFDs (COFFEE, US10YR) some of these are contract rolls, not market moves.
- **max_missing_weekdays:** longest run of weekdays with no bars at all (holidays give 1-2).
