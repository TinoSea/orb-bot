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
- **MT5 rehearsal (2026-10-18, real ticks, single run, Jan 2023 start, 1.5% risk):** never reached +10%; the
  2023 losing streak took equity to $9,049 by 30 Oct 2023, after which the guard stopped trading. Effectively a
  fail after 10 months, matching the Python simulator (the same start fails at 1.5% there too). It also exposed a
  guard design flaw, fixed in EA v1.14 (see `mt5_results.csv`). Consistent with the decision above: not yet.

**18. FTMO Futures (Nasdaq) — deployment check, 2026-10-18, no strategy results involved.**
FTMO Futures (ftmo.com, read 2026-10-18): NinjaTrader, Tradovate or TradingView only (no MetaTrader, so the bot
would need rewriting); EOD-trailing max drawdown ($2,000 on $50K Growth); and **positions may not be held past
the end of the trading day (16:10 ET) — open positions are liquidated, and strategies that depend on holding past
the close are prohibited.** H-002 holds trades overnight by design: on the in-sample gold list, 82 of 112 trades
were held past 16:10 ET (mean +0.23R) while the 30 same-day trades averaged −0.12R. A forced daily close would
therefore remove the part of the strategy that carries the edge. **Decision: H-002 is not deployable on FTMO
Futures as registered.** An intraday version would be a new hypothesis with its own rules and tests. Nasdaq
itself stays in H-002 through US100 (the CFD on the same index), testable in MT5 and tradable on FTMO's CFD
challenge (Swing account, overnight allowed). Sizing note: Micro Nasdaq (MNQ) is $2 per point; the in-sample
median US100 stop (~136 points) is ~$272 per MNQ; the full NQ ($20 per point) is ~$2,700 per contract.

### Results
**Gate 0 — PASSED (2026-10-18).** MT5 Strategy Tester, MS_Gold v1.13 (commit 251b9c8), XAUUSD.r H1,
2023-01-01 → 2025-06-30, 1-minute OHLC, $5,000, research mode. Compared with the independent Python replica
(`results/h002/gate0/`): **112 of 112 trades match** on entry hour and direction (rule: ≥95%), median entry
difference **0 ticks** (rule: ≤2), identical lot sizes and stops, same exit reason on every trade, R per
trade correlation 1.0000; net $631.25 (MT5) vs $631.70 (Python). Three trades exit a few minutes apart
inside the same bar (tick generation), with the same result. Gold commission of USD 3/lot/side confirmed.
Both implementations use the broker's stored bar spreads, so the cost question of amendment 14c is still open.

**Real-tick cost check — 2026-10-18.** Same settings, "Every tick based on real ticks" (FP Markets' recorded
ticks, real spreads). 110 of 112 trades identical in timing and exit reason (2 lost to MT5 splitting the run
while downloading ticks). Matched trades: mean +0.121R (1-minute bars) vs **+0.124R (real ticks)**; median entry
price difference $0.01. Real ticks do show slippage through stops on news gaps (worst: −1.73R on 2024-07-05,
a payrolls day). **For gold, real spreads do not erode the result; the amendment 14c cost question is closed for
gold** (other markets still use the ExportSpreads calibration). The out-of-sample run uses real ticks.

### Decision
*(keep / reject / park, and why)*

---

## H-004: Supply/demand rejection scalp at the New York open (Nasdaq)

**Registered:** 2026-10-18  **Status:** OPEN (before any data was looked at)

**Idea.** Source: a "trade with me" video by a futures trader (Nasdaq futures, 16 contracts, 25-tick target,
~$2,000 risk to make ~$2,000, 7 winners in one session, average hold 48 seconds). Before the open she marks
supply and demand zones. After the open, when price reaches a zone and prints a rejection candle, she enters on
the break of that candle and takes a fixed 25-tick bracket. Her version is discretionary ("depending on how far I
feel"); this is a **mechanical approximation** so it can be tested. Failing rejects *this rule set*, not her.

**Exact rules tested** (code: `mt5/SD_Scalp.mq5`)
- **Market:** US100 (FP Markets' Nasdaq 100 CFD, the index NQ futures follow). New York time throughout.
- **Zones, fixed at 09:30:** on 15-minute bars from 18:00 the previous evening to 09:30, an *impulse* candle has a
  body ≥ 1.5 × ATR(14, M15) and ≥ 60% of its range. The candle before it is the zone (its low to its high):
  **demand** if the impulse is up, **supply** if down. A zone is dropped if any later 15-minute close (before 09:30)
  goes through its far side. The 6 most recent surviving zones of each kind are kept.
- **Signal (1-minute bars, 09:30–11:00):** **sell** when a closed 1-minute bar's high reaches into a supply zone,
  the bar is bearish, and it closes below the zone's low (a rejection). The trigger is 1 tick below that bar's low.
  **Buy** is the mirror at demand. A trigger stays armed for 3 bars.
- **Entry:** market order when price crosses the trigger. **Stop and target: 6.25 index points each (25 NQ ticks), 1:1.**
- Each zone trades once. A 1-minute close through a zone's far side removes it.
- **Limits:** one position at a time; at most 4 trades a day; stop for the day after 2 losses; no new entries after
  11:00; everything flat by 11:30 or after 15 minutes in a trade; **no Friday trading** (her rule).
- **Skip** an entry if the spread is above 30% of the stop. **Risk:** 1% per trade. Same live-account guard,
  research mode and out-of-sample lock as MS_Gold.

**Data.** FP Markets US100 in the MT5 Strategy Tester, **"Every tick based on real ticks" only** (48-second trades
cannot be judged on 1-minute bars). In-sample **2023-01-01 → 2025-06-30**; out-of-sample **2025-07-01 → 2026-10-16**,
run once. No Python replica is possible without tick data, so Gate 0 here is an audit: the bot logs every zone and
signal, and the first 20 trades are checked by hand against the chart.

**Costs — the first hurdle, stated before testing.** FP Markets' stored US100 spread is ~1.25 points, already
**20% of a 6.25-point stop**, double the 10% cost limit used in H-002. On NQ futures her own figures ($645
commission for 112 contract-sides, about $5.76 per contract round trip, plus a 1-tick spread) come to about
**0.09R per trade**. So results are reported three ways: (1) after CFD costs as tested, (2) **gross** (spread added
back), and (3) gross minus 0.09R, an estimate of futures costs. If the edge only exists in (2), there is no edge.

**Pass, all on the out-of-sample period** (decided now)
1. At least 100 trades
2. **Futures-cost estimate (3):** profit factor ≥ 1.2 and expectancy ≥ +0.10R per trade
3. Win rate at least 5 points above break-even after costs (break-even for 1:1 with cost c is (1+c)/2)
4. Max drawdown ≤ 20% at 1% risk
5. **Robust:** zones from 5-minute instead of 15-minute bars, and a 50-tick (12.5-point) target, keep profit factor ≥ 1.05 on (3)
6. **Beats random:** better than the 95th percentile of random entries in the same window with the same bracket
   (1,000 runs, computed from the tester's trade times)

**Fail:** profit factor below 1.05 on (3), or 5–6 collapse. **Budget:** 10 in-sample variants.

**Amendment H-004/1 — 2026-10-18, before any H-004 data or results exist.** Six more of her videos show three
things the registered rules leave out: she enters on the **15-second** chart (trades last 16–48 seconds), she
uses the **London session high/low** and an **EMA** for direction, and she **avoids consolidation**. Her exact
EMA and London times are never stated, so the definitions below are ours, fixed now. Variants (inputs in `SD_Scalp.mq5` v1.10):
- **V0** as registered (1-minute entry candles, no filters).
- **V1 15-second candles:** entry candles of 15 seconds, built by the bot from real ticks (bid). Rejection, break
  and zone-breaking rules unchanged; a trigger stays armed for 3 candles.
- **V2 EMA direction:** buys only if the last closed 15-minute close is above EMA(20) of 15-minute closes; sells only below.
- **V3 London sweep:** London range = high/low of 03:00–08:00 New York. From 08:00, if price has traded above the
  London high but not below the low, sells only; below the low but not above the high, buys only; otherwise both.
  (She called a bearish bias after price went above the London high.)
- **V4 No consolidation:** no new signal when the high-low range of the last 30 one-minute bars is under 1.0 × ATR(14, 15-minute).
- **V5 Her version:** V1 + V2 + V3 + V4 together.
Together with the two registered robustness runs (5-minute zones, 50-tick target) that is 8 of the 10-variant budget.
**Selection:** the variant with the highest in-sample expectancy on the futures-cost estimate (3) is the one run
out-of-sample; all six are reported, and the pass rules above apply to it unchanged. Not modelled: her news
filter (the tester has no news calendar), trailing winners, and her variable position size, which a bot must not copy.

### Results (H-004)
**V0, in-sample, 2026-10-18** (US100, real ticks): 239 trades, **win rate 40.6%** (she reports 65–70%).
After CFD costs **−0.203R per trade** (PF 0.68); the spread averaged 1.45 points = **23% of the stop**, as warned.
**Gross +0.023R** (PF 1.05), i.e. no edge before costs; **futures-cost estimate −0.067R** (PF 0.88).
**V1 (15-second candles):** 285 trades, win 38.6%, net −0.240R, **gross −0.013R**, futures estimate −0.103R. Worse than V0.
**V1+V2 (15 s + EMA; unplanned combination from a settings slip, counted toward the budget):** 175 trades, win 40.6%,
net −0.196R, **gross +0.031R** (95% range −0.12 to +0.19), futures estimate −0.059R. The trend filter removed 492 signals without creating an edge.
**V5 (her version):** filters blocked 1,026 signals (EMA 620, London bias 405; the consolidation filter almost never
bound, so V4 as defined is close to inactive). 70 trades, win 42.9%, net −0.136R, **gross +0.084R** (95% range −0.16 to
+0.33), **futures-cost estimate −0.006R** (PF 0.99). Best of the variants, but break-even at futures costs and losing at CFD costs.

**Decision (2026-10-18): PARK H-004.** Four variants (V0, V1, V1+V2, V5) show no in-sample edge after realistic costs; the best
is break-even on futures and needs ~0.10R more than it has. At V5's rate (~2 trades a month) the out-of-sample period
(15.5 months) would give ~35 trades, so pass criterion 1 (≥100 trades) is unreachable by design; running it would spend the
unseen data for no possible pass. Her reported 65–70% win rate did not appear in any mechanical version (39–43%); whatever edge
she has is not captured by these rules. The remaining planned variants (V2, V3, V4 alone; 5-minute zones; 50-tick target) are
not run: changing thresholds now, after seeing results, would be fitting to the data. Not tradable on FP Markets in any version
(spread = 23% of the stop).

**Even if it passes on (3),** it is only tradable on real futures (another platform and a rewrite), since the CFD
costs in (1) are part of the test.

---

## H-005: Where does her edge live? Replication from her own trades

**Registered:** 2026-10-18, before any market data around her trades was looked at. **Status:** CLOSED (no edge found, 2026-10-18)

**Why.** H-004 coded her *described* rules and found no edge. Traders describe their own rules poorly; their
trades are the better evidence. H-005 reconstructs what she *did* from seven of her videos (screen recordings
of NQ on 15-second charts, position boxes such as "−16 @ 26224.50", performance screens), then asks where any
edge sits: in her entries, in which setups she takes, or in sizing and exits.

**Material.** The video frames (1 per second), read by text recognition and checked by eye. Her trades are
recorded with date, side, entry and exit price, contracts and result; times from the chart clock where visible,
otherwise aligned to market data (below). Her own stats screens are recorded as she showed them.
**Market data:** FP Markets US100 bid/ask ticks (09:00–11:45 New York) and 1-minute bars, 2025-07-01 → 2026-10-16
(`mt5/ExportTicks.mq5`). US100 is the cash Nasdaq 100 CFD; NQ futures trade at a premium (basis) that is near
constant within a day. **Alignment:** for each video day one basis b is fitted so that her entry prices minus b
match US100 mid prices at her (ordered) entry times, inside the chart-clock minute where visible. Days that cannot
be aligned to within 1.5 index points are reported and dropped.

**Questions and tests (fixed now)**
- **Q1 Do her entries carry an edge?** Replay every reconstructed entry on US100 with her bracket (6.25 points each
  way, 15-minute cap). Compare with 10,000 sets of random entries on the same days, 09:30–11:00, same count and
  direction mix. Reported gross and with the futures-cost estimate (−0.09R).
- **Q2 How much of her money comes from sizing and exits?** Her shown P&L vs Q1's fixed-bracket result for the
  same trades (risk changes, doubling, trailing).
- **Q3 What distinguishes her moments?** At every 15-second candle close 09:30–11:00 on her days: (1) nearest
  zone distance (H-004 definition, ATR units), (2) inside a zone, (3) rejection candle, (4) break of the previous
  candle in the trade direction, (5) side vs EMA20 of 15-minute closes, (6) London high/low taken (H-004 V3),
  (7) minutes since 09:30, (8) 5-minute move in the trade direction (ATR units), (9) 30-minute range / ATR,
  (10) distance from the day's 09:30 open (ATR units). Her entries are positives; all other candle closes are
  negatives. L1-regularised logistic regression, leave-one-day-out cross-validation; report AUC. The clone rule
  uses at most 3 features with thresholds set on her days only.
- **Q4 Does the clone rule work?** Development 2025-07-01 → 2026-03-31; **holdout 2026-04-01 → 2026-10-16, run once**.
  Same pass rules as H-004 on the futures-cost estimate: ≥100 trades, profit factor ≥ 1.2, expectancy ≥ +0.10R,
  and better than the 95th percentile of random entries.

**Known biases, stated now.** (a) She chooses which days to film and publish, so her visible trades over-represent
good days; a positive Q1 cannot prove an edge, while a negative Q1 is strong evidence against one. (b) A small sample
(expected 25–40 trades). (c) US100 is a proxy for NQ. (d) Her October–November 2025 days are inside the H-004
out-of-sample window; H-004 is parked, so this is recorded rather than a conflict.

**Decision.** Edge "lives in entries" only if Q1 beats the random 95th percentile *and* Q4 passes on the holdout.
If Q1 fails, the conclusion is that what she shows is explained by sizing, exits or selection of days, not entries.

**Amendment H-005/1 (2026-10-18, before any tick data was seen): what the frames actually gave.**
Trade list in `research/h005_her_trades.csv`: 15 rows on 4 days (2025-10-01, 10-23, 10-31, 11-03).
Two of the seven videos (car talk, Aspen) contain no trade screens; the August 2026 journal is inside the holdout and is not used.
- Exact entry prices: 3 trades on 11-03 and 5 positions on 10-23 (10-23 shows no time axis: times must come from the tick data).
- Times to about ±20 s but prices truncated by the video crop: 5 trades on 10-31.
- 10-01: two longs, price ±5 points, time unknown (camera-filmed screen).
- Her own day statistics show 7 trades on 10-23 and 6+ on 10-31, so the sample is about 15 of roughly 20 trades taken on filmed days.
Consequences, written down now: Q1 (her entries vs random) and Q3 (what distinguishes her moments) have about 15 positives,
so a Q3 AUC will carry a confidence interval roughly ±0.15 wide and the clone rule cannot be *learned* from her trades with any
reliability. The clone rule for Q4 will therefore be her stated rule (H-004 V0 definitions) plus at most the ≤3 features Q3 ranks
highest, and Q4's holdout pass rule is unchanged. Alignment rule tightened for 10-23: basis and times are solved together by
requiring the five entry prices, in order, to be touched by US100 mid within 09:30–10:30 with 6.25-point wins after each; if more
than one solution exists within 1.5 points of basis, 10-23 is used only for Q2 and dropped from Q1/Q3.

**Amendment H-005/2 (2026-10-18, after Q1-Q3, before any Q4 run on development or holdout data).**
Data received: FP Markets US100 real ticks 09:00-11:45 NY, 2025-07-01 to 2026-10-16 (337 days, 84.2 M ticks; density changes
in March 2026 and mid-August 2026), converted to 1-second bid/ask bars. Server = NY + 7 h confirmed on all four of her days.
Alignment outcome: 11-03 (premium 97-105) and 10-31 (premium 109-124) align; 10-23 has feasible premiums 138.5-150 with
different times (dropped from Q1/Q3 by the H-005/1 rule; every solution places her trades 10:37-11:29); 10-01 cannot be aligned.
Q1-Q3 used 8 trades on 2 days. In Q3 the coded H-004 rejection fired on 0 of 8 of her trades and on 11-03 the H-004
zone definition finds no zones, so H-004 V1 does not describe what she does. Two rules go to Q4, fixed now:
- **Q4a (as H-005/1 said):** H-004 V1 (15-second candles, zones/rejection/break, 6.25/6.25, 15-min cap, ≤4 trades, stop after
  2 losses, no Fridays) plus the L1 model's top three features with thresholds that keep all 8 of her trades:
  minutes since 09:30 ≤ 11 (binding); zone distance ≤ 10 ATR and EMA side ∈ {−1,+1} (not binding). So: H-004 V1, entries 09:30-09:41.
- **Q4b (the original H-005 "≤3 features" clone, from the univariate ranking):** direction = London bias (London 03:00-08:00
  high taken before 09:30 and low not → short only; low taken and high not → long only; otherwise no trade);
  entries only 09:30-09:41; entry at the close of any 15-second candle that closes beyond the previous candle in that
  direction (her stated "break" entry); fill at the next second's mid; same bracket, cap, one position at a time,
  ≤4 trades a day, stop after 2 losses; Fridays traded (she trades them).
Development run first (2025-07-01→2026-03-31, may be looked at, no changes allowed after looking except bug fixes),
then each rule runs **once** on the holdout (2026-04-01→2026-10-16).
**Holdout pass, per rule:** ≥100 trades; on the futures-cost estimate (gross − 0.09R) PF ≥ 1.2 and expectancy ≥ +0.10R;
and mean R above the **97.5th** percentile of a random-entry null (two rules → Bonferroni), where the null keeps each day's
trade count and directions and draws entry seconds uniformly from 09:30-09:41 on the same days.
If a rule cannot reach 100 trades it fails criterion 1 and is reported as such.

### Results (2026-10-18)
**Q1 her entries vs random (8 aligned trades, 2 days; mid prices, entry time averaged over the ±15-30 s frame uncertainty):**
her mean +0.361R gross (futures estimate +0.271R; her own P&L implies +0.44R). Random entries on the same days, same
directions, 09:30-11:00: mean +0.004R, 95th percentile +0.500R → **her 85th percentile: not passed**. Restricted to 09:30-09:45
(descriptive): random +0.144R, her 74th percentile — most of her result on these two days is "short on a falling open".
Her trades resolved in 3-27 s; shifting an entry by a few seconds inside the frame uncertainty flips outcomes
(window win share 44-97% per trade), so second-level timing — the part frames cannot record — decides each trade.
**Q2 sizing/exits:** her exits are the fixed 25-tick bracket (every full win/loss = $2,000 at 16 NQ). On 10-31 she doubled
to 32 contracts after two losses; at fixed size the day is +1R instead of +2R. Sizing changes the dollars, not the edge.
Filmed days: 100%, 100% and 72% win rates (her own statistics) — selected days.
**Q3 (8 positives / 1,440 candidates):** L1 logistic leave-one-day-out AUC 0.78 (bootstrap 0.68-0.88), driven by
minutes since 09:30 (all 8 in the first 11 min) and London-sweep direction (7/8). H-004 zone rejection fired on 0/8 and
"inside a zone" on 0/8; 11-03 has no zones by the H-004 definition. Her stated rule, as coded, is not what she trades.
**Q4 development (2025-07-01→2026-03-31):** Q4a 54 trades, win 48.1%, gross −0.037R, futures −0.127R; Q4b 389 trades,
win 50.9%, gross +0.018R, futures −0.072R (95% −0.17 to +0.03), 69th percentile vs random. Both fail; no changes made.
**Q4 holdout, run once (2026-04-01→2026-10-16):** Q4a **28 trades**, win 57.1%, gross +0.143R, futures +0.053R (PF 1.11),
80th percentile vs random → **FAIL** (too few trades; PF and expectancy below bar). Q4b **331 trades**, win 52.0%,
gross +0.039R, futures **−0.051R** (PF 0.90), 71st percentile vs random → **FAIL**.
Checks: 1-second engine vs raw-tick replay same outcome on 2,400/2,400 sampled entries; random-entry nulls average ≈ 0R.
Break-even win rate for a 1:1 bracket after futures costs is 54.5%; her claimed 65-70% is not reproduced by any rule here.

### Decision (2026-10-18): CLOSE H-005 — no mechanical edge found; whatever edge she has is not in the visible rule.
Her edge, if real, lives in what the frames and her description do not contain: second-by-second execution at the open
(reading the order book / tape on a 15-second chart) and choice of days. Neither the stated rule (H-004), nor the
features that distinguish her filmed trades (time of day, London-sweep direction), produce an edge after futures costs.
Nothing from H-004/H-005 goes to demo or live. Re-open only with her full trade export (e.g. a Tradovate fills CSV
for ≥3 consecutive months including losing days), which would allow Q1 on ≥100 trades with exact times.

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
