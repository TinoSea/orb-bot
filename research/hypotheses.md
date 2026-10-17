# Hypotheses

Each entry is written **before** testing. Results and the decision are added at the end, never edited away.

---

## H-001: Opening-range breakout on the S&P 500

**Registered:** 2026-10-17  **Status:** OPEN

**Idea.** The first 15 minutes after the New York open set a range. A 5-minute close outside that range
tends to continue far enough to pay 1.5× the risk often enough to be profitable after costs.

**Exact rules tested** (code: `orb_backtest.py`, `mt5/ORB_US500.mq5`)
- Range = high/low of 09:30–09:45 New York time
- Entry: next bar after a 5-minute close beyond the range; one trade per day; no entries after 11:30
- Stop: far side of the range. Target: 1.5 × risk. Flat at 15:55
- Skip days with a range under 3 or over 30 index points
- Costs: broker spread + commission; pessimistic fills (stop assumed hit first if both touched in one bar)

**Data.** FP Markets US500 history in the MT5 Strategy Tester (main), cross-checked in Python.
Split by date: first 70% in-sample, last 30% out-of-sample.

**Pass, all of these on the out-of-sample period** (decided now, before seeing results)
1. At least 60 trades
2. Profit factor ≥ 1.2
3. Expectancy ≥ +0.10R per trade
4. Max drawdown ≤ 15% (the kill-switch level)
5. Robust: neighbouring settings (range 10 or 20 min; target 1.25R or 1.75R) still have profit factor ≥ 1.05
6. MT5 and Python results broadly agree (same direction, similar trade count)

**Fail:** out-of-sample profit factor below 1.05, or criterion 5 collapses → reject.

**Budget:** at most 10 variations before deciding. After that, write H-002 instead of tweaking further.

**If it passes:** 6–8 weeks of demo trading. Demo expectancy must stay within a reasonable band of the backtest
before any real money.

### Results
**Run A1, 2026-10-17 (MT5, US500 M5, FP Markets data, 1-min OHLC, $100, in-sample from 2024-01-01)**
- Bot mechanics verified: ~1% risk per trade ($0.83-0.96), stops -1.00R, targets +1.50R, entries at 09:50 NY, skips and kill switch working.
- 56 trades in Jan-Mar 2024: 12 targets, 35 stops, 9 end-of-day exits. **-17.7R total, about -0.32R per trade.**
- Kill switch tripped 2024-03-26 at -15%. Many stops within minutes of entry (false breakouts).
- Break-even win rate at 1.5R is 40%; achieved about 21-25%.
- Note: tester end date was set to 2025-12-31 by mistake, but no trades happened after March 2024, so the out-of-sample period is still untouched.
- Next: Run A2, same rules, full in-sample period (2024-01-01 to 2025-08-31) with kill switch and loss limits set to 100% for measurement only. Counts as run 2 of 10.

### Decision
*(keep / reject / park, and why)*

---

<!--
Template for the next one:

## H-00X: Title

**Registered:** YYYY-MM-DD  **Status:** OPEN

**Idea.**
**Exact rules tested**
**Data**
**Pass (decided before testing)**
**Fail**
**Budget**
### Results
### Decision
-->
