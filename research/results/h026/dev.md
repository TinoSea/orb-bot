# H-026 dev: 2025-07-01 → 2026-03-31

**Verdict: NOT SUPPORTED** (194 days, 2025-07-01 → 2026-03-31)

## Primary: Asia/London highs and lows (UTC sessions)

| | Real levels | Placebo levels |
|---|---|---|
| Touched in 09:30-12:00 | 54.5% of 627 | 51.9% |
| Reversal rate (X before −X, 60 min) | 42.7% (95% 37.1%–48.4%) | mean 45.6%, 95th pct 50.0% |
| Touches | 342 (needs ≥ 150) | |
| Edge | -2.9 pp (needs ≥ +5) | real at 14.4th pct |

## Reported only

| Family | Touches | Reversal | Placebo mean | Pct vs placebo |
|---|---|---|---|---|
| asia_high | 64 | 37.5% | 44.4% | 16 |
| asia_low | 72 | 41.7% | 46.6% | 22 |
| london_high | 96 | 40.6% | 45.5% | 14 |
| london_low | 110 | 48.2% | 46.1% | 66 |
| mid_lines | 252 | 48.8% | 44.7% | 92 |
| gap_5min | 431 | 46.9% | 45.9% | 68 |
| gap_15min | 341 | 47.5% | 45.6% | 76 |
| extremes_sessions_ny | 357 | 45.9% | 45.8% | 51 |
| extremes_sessions_london_local | 327 | 41.3% | 45.7% | 5 |

## Splits (primary family; reported only)

| Condition | Value | Touches | Reversal (95%) | Placebo |
|---|---|---|---|---|
| touch_slot | 09:30-10:00 | 250 | 42.4% (36%–49%) | 43.8% |
| touch_slot | 10:00-12:00 | 92 | 43.5% (32%–55%) | 50.0% |
| on_range_tercile | large | 89 | 34.8% (26%–45%) | 45.4% |
| on_range_tercile | medium | 113 | 43.4% (33%–54%) | 46.8% |
| on_range_tercile | small | 128 | 48.4% (39%–58%) | 45.5% |
| open_in_london | False | 41 | 51.2% (33%–67%) | 47.8% |
| open_in_london | True | 301 | 41.5% (36%–48%) | 44.9% |
| news_proxy | False | 261 | 41.4% (35%–47%) | 43.7% |
| news_proxy | True | 81 | 46.9% (34%–60%) | 51.8% |
| day_type (hindsight) | range | 166 | 45.8% (38%–54%) | 51.0% |
| day_type (hindsight) | trend | 176 | 39.8% (32%–48%) | 39.9% |

*Descriptive study, not a trading rule. Not financial advice.*