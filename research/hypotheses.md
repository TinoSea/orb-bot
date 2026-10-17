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

## H-002: Higher-timeframe market structure on gold (trend + pullback)

**Registered:** 2026-10-17  **Status:** OPEN  **Candidate primary strategy**

**Idea.** Source: "Trading Course Day 11: Market Structure Entries" (ICC creator, free YouTube series).
When the 4-hour trend turns (a higher low forms, then price breaks above the last swing high), the level
that broke is where sellers used to be. Price tends to come back near it, hold, and continue in the new
direction. Buying that pullback, with the stop under the pullback and the target at the next level where
sellers reacted before, should pay more than it loses. Mirror image for shorts.

His version is discretionary. This is a **mechanical approximation** so it can be tested honestly.
If it fails, that rejects *this rule set*, not necessarily everything he teaches.

**Exact rules tested** (code: `mt5/MS_Gold.mq5`)
- **Swing points (4H):** a swing high is a bar whose high is the highest of the 2 bars either side
  (5-bar fractal); swing lows likewise. Only confirmed swings are used.
- **Bullish setup (4H):** latest swing low is higher than the one before it (higher low), AND the last closed
  4H bar closes above the most recent swing high (fresh break). That swing high = the **level**.
  **Bearish:** lower high + 4H close below the most recent swing low.
- **Pullback (1H):** price must trade back to within 0.3 × ATR(14, 4H) of the level.
- **Entry (1H):** after the pullback, the first 1H bar that closes above the previous 1H bar's high and above
  the level (shorts: mirror). Entries only 08:00–17:00 New York time. No waiting for 4H confirmation.
- **Setup cancelled** if a 4H bar closes 0.5 × ATR(4H) back through the level, or no entry within 30 hours.
- **Stop:** pullback low − 0.1 × ATR(14, 1H) (shorts: pullback high + buffer).
- **Target:** the nearest earlier 4H swing high above entry that gives at least 1R; if none (e.g. all-time highs), 2R.
- **Exits:** stop, target, 5 days in the trade, or Friday 16:30 New York (no weekend gaps).
- **Risk:** 1% per trade, one trade at a time; same daily/weekly limits and kill switch as H-001.
- **Costs:** broker spread + commission + overnight swap (included by the MT5 tester); 1-minute OHLC modelling.

**Data.** FP Markets XAUUSD history in the MT5 Strategy Tester.
- In-sample (tuning allowed): **2023-01-01 → 2025-06-30**
- Out-of-sample (run once): **2025-07-01 → 2026-10-16**
- Research deposit **$5,000** so position sizes can match 1% risk on gold (see note below). Results judged in R.

**Pass, all on the out-of-sample period** (decided now, before any results)
1. At least 30 trades
2. Profit factor ≥ 1.2 and expectancy ≥ +0.15R per trade
3. Max drawdown ≤ 20%
4. **Beats the trend for free:** gold rose strongly in 2024–2026. Shorts must not be a disaster
   (short-side profit factor ≥ 0.9), so the result isn't just "long gold in a bull market".
5. **Robust:** swing size 3 instead of 2, and pullback zone 0.2 or 0.5 × ATR, still give profit factor ≥ 1.05
6. **Generalises:** the same rules on US500 are not clearly losing (profit factor ≥ 1.0)

**Fail:** out-of-sample profit factor below 1.05, or criteria 4–5 collapse → reject this rule set.

**Budget:** at most 10 in-sample variations before the single out-of-sample run.

**Practical note on account size:** the smallest gold trade (0.01 lot) moves about $1 per $1 move in gold.
A typical 1H stop of $10–25 therefore risks $10–25, which is **10–25% of a $100 account**. At $100, this
strategy cannot respect the 1% rule on gold. If H-002 passes, either the account grows to roughly
$1,500–2,500 first, or the strategy runs on US500 (which can be sized to $1 risk).

**If it passes:** 6–8 weeks demo trading, then decide on account size.

### Deepening protocol — pre-registered 2026-10-17, before any H-002 data exists

This amends H-002 from "does it work on gold?" to "does it work, beyond luck and beyond simple
trend exposure, across independent markets?". Everything below is fixed before any results.

**1. Universe (fixed).** The 17 markets in `research/h002_markets.csv`, in 8 sectors: US equity
(US500, US100, US30, US2000), non-US equity (UK100, GER40, JP225), rates (US 10Y or Bund), FX
(EURUSD, USDJPY, GBPUSD, AUDUSD), metals (gold, silver), energy (WTI), crypto (BTC), agriculture
(first available). Markets the broker doesn't offer are recorded as missing, never substituted after
seeing results. Losing markets are never dropped after the fact.

**2. One rule set.** Identical parameters everywhere. The only per-market differences, fixed in the
CSV now: the market's main exchange session (local time zone) and 24/7 mode for BTC.

**3. Raw data.** FP Markets 5-minute bars with spread for all markets and 1-minute bars for gold
(`mt5/ExportData.mq5`), Dec 2022 → Oct 2026, plus contract terms (`specs.csv`) recorded in
`research/contracts.md`. **Independent source:** Dukascopy historical data for gold and EURUSD
(minimum), used to repeat the gold and EURUSD in-sample runs.

**4. Gate 0 — implementation check (must pass before any result is interpreted).** The MT5 tester
and the independent Python replica (`research/ms_replica.py`) on gold, in-sample, 1-minute bars:
≥95% of trades match on entry minute and direction, median entry difference ≤2 ticks
(`research/compare_trades.py`). Replica already verified: exact match to the EA's swing logic,
a hand-built scenario, and zero expectancy on 40 random markets (no look-ahead bias).

**5. Costs.** Per-bar broker spreads from the export; swaps from contract terms; commission from
FP Markets' Raw schedule (to be filled in `contracts.md` before running). Sensitivity: spreads × 2.
**Cost filter (set now):** a market is excluded if its median spread at entry is more than 10% of
its median stop distance, measured on in-sample data before looking at strategy results.

**6. Periods.** In-sample 2023-01-01 → 2025-06-30. Out-of-sample 2025-07-01 → 2026-10-16, run
**once**, with code and settings frozen in git (commit hash recorded here before the run).
Stability: results reported per half-year within in-sample.

**7. Baselines (same markets, periods, costs).**
- **B1 Random entries:** for each market, the same number of trades at random in-session 1H bar
  opens, random direction, stop distances drawn from the strategy's own stops (in ATR units), same
  target rule, max hold and Friday close. 1,000 runs.
- **B2 Simple trend rule:** at each new 4H bar, if flat and the daily close is above its 50-day
  average, buy at the next in-session 1H bar (mirror for shorts); stop 1.5 × ATR(1H); target 2R;
  same max hold and Friday close.
- **B3 Buy-and-hold** of each market (context only).

**8. Ablations (does each ingredient earn its place?).** A1 without the higher-low/lower-high
condition, A2 without the pullback requirement, A3 without the session filter. Reported, not used
to change the rules.

**9. Robustness variants.** R1 swing size 3, R2 zone 0.2 × ATR, R3 zone 0.5 × ATR,
R4 pessimistic intrabar order, R5 spreads × 2.

**10. Statistics.** Trade-level bootstrap (10,000 resamples) 95% confidence intervals for
expectancy per market, per sector and for the portfolio; month-block bootstrap for the portfolio.
Deflated Sharpe ratio using the number of variants logged in `research/h002_runs.csv`.
Regime split per market-day: "trending" if |60-day return| > 60-day daily volatility × √60,
otherwise "ranging".

**11. Portfolio rules.** Equal risk budget per sector, split equally within a sector. Max 3% total
open risk. Max 2 same-direction positions per sector. Markets whose 60-day daily-return correlation
exceeds 0.7 count as the same bet for that limit. Report the effective number of independent bets
(from the eigenvalues of the correlation matrix of daily strategy returns).

**12. Decision rule (portfolio, out-of-sample).** All of: profit factor ≥ 1.2; expectancy ≥ +0.15R
with the bootstrap 95% lower bound > 0; beats the 95th percentile of B1; beats B2's expectancy
(bootstrap difference lower bound > 0); profit factor ≥ 1.0 in at least 4 of the sectors with data;
max drawdown ≤ 20%. Gold keeps its own original criteria above.

**13. Demo kill criterion.** From 10,000 reshuffles of the out-of-sample trades: stop demo trading
if the drawdown in R exceeds the simulated 95th percentile for that number of trades, or if after
30 trades expectancy is below the simulated 5th percentile.

**14. Variant budget.** Every run is logged automatically in `research/h002_runs.csv`. At most 15
distinct variants (V0 registered + A1–A3 + R1–R5 + up to 6 others), baselines excluded.

**14a. Symbol mapping and data-coverage rule — amendment 2026-10-17, made after seeing only the
broker's symbol list and before any H-002 price data was examined.** FP Markets names are recorded in
`research/contracts.md`. US2000 is not offered (recorded missing). For any market whose broker symbol is a
rolling futures contract (BOND = US10YR; AGRI candidates), the data must cover the in-sample period: first
bar on or before 2023-01-31 and no gap longer than 5 weekdays. AGRI = the first candidate in the registered
order (COFFEE, SUGAR, WHEAT, CORN, SOYBEAN, COCOA, COTTON) that passes; BOND is recorded missing if US10YR fails.
Futures roll jumps are measured and reported; trades open across a roll date are flagged.

**14b. Bitcoin weekends — amendment 2026-10-17 (contract fact, before any results).** FP Markets' BTCUSD
CFD does not trade at weekends (12 Saturday bars in almost four years). 24/7 mode is therefore dropped: BTC
uses all weekday hours (New York 00:00–24:00) and the normal Friday 16:30 New York close, so no position
sits through the weekend gap. Weekend Bitcoin would need a different broker and is outside H-002.

**14c. Cost data — amendment 2026-10-17 (before any results).** The cost filter (item 5) was run blind
(`research/cost_filter.py`: signal stops and spreads only, exits and P&L never recorded). With bar spreads,
**BOND (25% of median stop) and AGRI = COFFEE (18%) are excluded**; all other markets are under 4%.
MT5 bar history appears to store the lowest spread in each bar (gold median $0.02, FX 0.0), which would
understate costs for the strategy, the MT5 tester and the cost filter alike. Before any results:
real spreads at the start of each hour are sampled from tick history (`mt5/ExportSpreads.mq5`). For each
market, the median ratio (real tick spread ÷ bar spread, with the bar spread floored at 1 point) becomes
a spread multiplier used in every replica run and in a re-run of the cost filter; a market that then
exceeds 10% is excluded too. R5 (spreads × 2) is applied on top of the calibrated spreads.

**15. Separate question: tradable at $100?** From `contracts.md`, list which markets can be sized
to 1% risk on $100. This never affects the research verdict.

**16. The $200 gold account — amendment 2026-10-17, written before any dollar results were computed.**
This is a sizing question, not a new signal. It never changes the research verdict (items 12 and the
original gold criteria); it decides whether *this* account can trade *this* strategy safely.

*Facts fixed now (from contract terms and public prices, not strategy results).* The smallest gold position
anywhere Tino can trade is **1 troy ounce**: 0.01 lot of XAUUSD.r at FP Markets, or one CME 1-Ounce Gold
future (Micro Gold MGC is 10 oz). 1 oz moves $1 per $1 of gold. In-sample, the median stop was **0.50% of
price** (90th percentile 1.19%); stops scale with price. Gold was about **$4,190** on 2026-10-12. So at
today's price the median stop is about $21 = **~10% of $200** on the smallest possible trade.

*Sizing policies tested* (`research/small_account.py`), on the in-sample gold trade list only:
- **P1 Textbook:** 1% risk; skip any trade where 1 oz would risk more than 1%.
- **P2 Minimum lot:** every signal at least 1 oz; more only when the 1% rule allows it.
- **P3 Capped:** like P2, but skip the trade if 1 oz would risk more than **5%** of the balance.
  (P3 filters trades by stop width, which can change expectancy; that is why it is tested, not assumed.)

*Runs.* (a) Historical: the in-sample trades at their own prices, $200 start. (b) **Today's prices:** each trade
rescaled to a $4,190 gold price (stop, P&L, swap and spread in % of price), $200 start. (c) Cost stress:
(b) plus an extra **$0.30 per ounce per round trip** for spread and slippage the bar data may miss (amendment 14c).
(d) Monte Carlo: 10,000 random orderings (trades drawn with replacement) of 100 trades under (c).
Margin checked at leverage 1:20, 1:100 and 1:500; FP Markets' stop-out assumed at 50% margin level.

*Decision rule for trading gold with $200 (all at today's prices, run c/d):*
1. Probability of losing half the account within 100 trades ≤ 10%;
2. Median risk per trade ≤ 5% of the balance;
3. At the account's real leverage, margin for 1 oz never needs more than 50% of equity at entry.

If any fails, the $200 goes to demo-plus-US500 (same rules, sized at 1%) until gold is affordable at
1% risk (about $2,100 at today's price). Even if all pass, it stays provisional until Gate 0, calibrated
spreads and the single out-of-sample run.

*Result (2026-10-17, in-sample only; full report `research/small_account.md`).*
- **P1** takes **0 of 112** trades at $200: the textbook rule simply doesn't trade gold this small.
- **P2 fails** tests 1 and 2: at today's price the median trade risks 12–19% of the balance, there is a
  **41% chance of losing half within 100 trades**, and with cost stress the in-order replay is wiped out
  after 21 trades. It made money in the historical replay only because gold was cheaper then (median risk 6%),
  and even there it fell to $107 first.
- **P3 passes** tests 1–2, and test 3 only at leverage 1:100 or higher (13 breaches at 1:20). But it takes only
  **13 of 112** trades at today's price (about 5 a year) and earns about **$0.43 a month**. The rule as written
  had no minimum-activity test; that gap is recorded here rather than patched after seeing the numbers.
- **Edge check (context, not part of the rule):** in-sample expectancy +0.135R, but the 95% bootstrap range is
  −0.09R to +0.36R, and 12% of random walks run through the same rules did as well. Shorts were positive
  (+0.09R), so it isn't only "long gold". In-sample alone, the edge is not yet distinguishable from luck.

*Decision for the $200:* no live gold. P2 is a ruin policy at this size; P3 is safe but too inactive to
produce either income or evidence. Gold stays on demo (EA v1.12, `InpMinLotMaxRiskPct = 5`, to rehearse the
small-account mechanics) until the account can hold 1 oz at about 1% risk (~$2,100 at today's price).
Real money, if any, waits for Gate 0 and the out-of-sample verdict.

**17. FTMO $10,000 2-Step Challenge — amendment 2026-10-18, written before any FTMO numbers were computed.**
Question: if the gold bot ran an FTMO $10,000 2-Step Challenge, how likely is it to pass both phases,
how long would it take, and at what risk per trade? Like 16, this is a deployment question; it never
changes the research verdict, and no challenge is bought before Gate 0 and the out-of-sample pass.

*FTMO rules modelled* (ftmo.com Trading Objectives and FAQ, read 2026-10-18):
- Phase 1 target +10% ($11,000), Phase 2 (Verification) +5% ($10,500, fresh $10,000 account).
- **Maximum Daily Loss:** equity must stay above the balance at the previous 00:00 CE(S)T minus $500
  (5% of initial), commissions and swaps included. CE(S)T midnight = FP Markets server time 01:00.
- **Maximum Loss:** equity must stay above $9,000 (static).
- At least 4 trading days per phase; no time limit.
- **Gap-trading rule** (Forbidden Trading Practices, all phases): no new trades within 2 hours of a market
  closing for 2+ hours. Gold closes for the weekend at 17:00 New York, so Friday entries after **15:00 New York
  are removed**. (Gold's daily break is 1 hour, so it is unaffected.)
- **Account type: Swing.** FTMO's news window (no order execution, stops and targets included, 2 minutes either
  side of restricted USD releases) applies to Standard funded accounts and covers gold. The bot can't control
  when its stop or target is hit, so Standard would carry an unmanageable rule risk. Swing has no news window.

*How the trades are used.* The in-sample gold trade list (`results/h002/gate0/replica_XAUUSD_M1_IS.csv`) in R,
resized to the account: risk per trade × balance at entry. Worst equity during a trade = balance before it −
MAE × risk. For the daily limit the reference is the higher of the CE(S)T-midnight balance and the balance at
entry (conservative). Cost stress +$0.30 per ounce per round trip, as in amendment 16.
Approximation: removing Friday-afternoon trades could free the bot for a setup the list doesn't contain.

*Risk levels tested:* 0.5%, 1.0%, 1.5%, 2.0% per trade.

*Runs* (`research/ftmo_sim.py`)
- **A. Historical rolling starts:** a challenge started at the first trade of each month, January 2023 to June 2025,
  trading the real sequence. Each start ends passed, failed, or unfinished (data ran out).
- **B. Monte Carlo,** 10,000 challenges, resampling whole trading days (so same-day losses stay together), three
  edge scenarios: **as measured**, **edge halved** (half the in-sample mean R subtracted from every trade), and
  **no edge** (mean R subtracted). Pass = both phases.
- **C. Funded year:** 12 months on a funded $10,000 account at the chosen risk: expected profit, 80% split,
  and the chance of hitting the Maximum Loss within the year.

*Decision rule* (all in-sample; scenario "edge halved", because in-sample edges usually shrink out of sample):
1. Risk per trade = the level with the **highest probability of passing both phases**, among levels whose
   median time to pass is **≤ 18 months** at the in-sample trade rate.
2. If no level reaches **50%** pass probability, gold-only is not worth a challenge fee; revisit once more
   markets pass H-002 (more trades per year).
3. Nothing is bought before Gate 0 and the single out-of-sample run pass.

*Result (2026-10-18, in-sample only; full report `research/ftmo_10k.md`).*
- **Measurement fix made during this run, recorded openly:** the replica's worst-open-loss figure (MAE) counted
  the bar's extreme even when the stop filled inside that bar, so a few stopped trades showed up to 3.3R of
  "worst loss". The first FTMO run therefore overstated daily-loss failures. Fixed in `ms_replica.py` (trades and
  results unchanged; tests identical) and capped in `small_account.per_ounce`. The rule above was not changed;
  the decision is the same before and after (1.5% risk, 35% → 43%, both below 50%).
- 111 of 112 trades survive the Friday cutoff: **3.8 trades a month**. Mean after cost stress +0.108R.
- **Historical rolling starts:** at 1% risk, 9 passes and no fails, but 21 of 30 starts never finished
  (median 19 months to pass). At 1.5%: 16 pass, 3 fail, 11 unfinished, median 8 months. At 2%: 24 pass, 5 fail.
- **Monte Carlo, edge halved:** 0.5% → 70% pass but ~9 years; **1% → 51%, ~26 months**; **1.5% → 43%,
  ~12 months**; 2% → 38%, ~7 months. With **no edge**, 26–30% still pass at any level.
- **Decision rule:** eligible (median ≤ 18 months) are 1.5% and 2%; the best is **1.5% at 43%, below the 50% bar**.
  So, as pre-registered: **a gold-only challenge isn't worth the fee yet.** Revisit when more markets pass
  H-002 (more trades a month makes lower risk fast enough).
- Context, not part of the rule: the funded year at 1.5% (monthly payouts, 80% split) has a 52% chance of a
  breach within the year with the edge halved, mean payout about $730. Because losses stop at the firm's limit
  while payouts are kept, even the no-edge scenario shows positive payouts ($577 mean); that is the firm's
  business model, and exactly why passing a challenge is not evidence of an edge.

### Results
*(none yet)*

### Decision
*(keep / reject / park, and why)*

---

## H-003 (parked candidate): Intraday momentum, first half-hour → last half-hour

**Source:** Gao, Han, Li & Zhou, "Market Intraday Momentum", Journal of Financial Economics (2018).
**Idea:** the S&P 500's move from the previous close to 10:00 New York predicts the direction of the last
30 minutes (15:30–16:00). One trade a day, evenings in Harare. Small edge per trade; costs are the main risk.
**Status:** parked until H-001 is closed and H-002 has an in-sample result. Full rules to be written before any testing.

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
