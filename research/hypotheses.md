# Hypotheses

Each entry is written **before** testing. Results and the decision are added at the end, never edited away.

## Status board (updated 2026-10-24) — start here

Search this file for the code (e.g. "H-002") to read the full entry: idea, exact rules, results, decision.

| Code | Idea | Status | One-line result |
|---|---|---|---|
| H-001 | Opening-range breakout, S&P 500 | open (stalled) | −0.32R a trade on Jan-Mar 2024; not pursued |
| H-002 | Gold 4H structure + 1H pullback (MS_Gold) | **rejected out of sample** | gold +0.27R unseen, but shorts and US500 failed; 14 markets no better than random |
| H-003 | Morning move → last half hour, S&P 500 | failed | −0.21 points a trade after costs |
| H-004 | Her supply/demand scalp (our guess of her rules) | parked | no edge after costs |
| H-005 | Her own filmed trades vs random | closed | 85th percentile, not distinguishable from luck |
| H-006 | Her daily/4H/1H zones + failed-extreme entry | failed | ~+0.10R before costs, ~0 after |
| H-007 | London X / New York X framework | stopped at gate | not reproducible as a rule |
| H-008 | Opening-range break-and-retest, Nasdaq | failed | retest no better than random timing |
| H-009 | H-006 entries, wider brackets | failed | edge did not hold in 2023-25 |
| H-010 | NY opening-range break, 2 trades a day | not pursued | second trade loses every year |
| H-011 | Her fair value gaps + rejection candle | stopped at gate | finds her zone, trades far too often |
| H-012 | H-011 + 2 selection rules | failed | −0.07R after costs |
| H-013 | H-011 + earlier-day zones only | failed | beat random before costs, −0.04R after |
| H-014 | H-013 with 50-tick bracket | failed | −0.02R on unseen months |
| H-016 | Her zones + her own bracket (12.5/16.25) | failed | beats random (98.8th pct) but −0.016R after costs |
| H-018 | BOS model (break of structure, zone tap, 2R) | failed | −0.14R after costs; worse than random (4th pct) |
| H-019 | Build-up breakout at levels, with trend, 2R | failed | only 4 trades in 9 months; build-up filter too strict |
| H-020 | AMD at the NY open: sweep/gap tap 09:25–09:33, then reverse (GS Trades video) | failed | 24% win at 2R, −0.34R after costs; 5th pct vs coin-flip direction |
| **H-017** | **Her zones, first try 09:30-10:00, forward on demo** | **open from 2026-10-19** | 49.1% win in the past slice; is it real? |
| **H-015** | **Gold long-only, forward test (demo; live allowed under rules)** | **open from 2026-10-19** | **the only live lead** |
| **H-022** | **H-017 rules on MNQ futures, signals 08:00-14:00 NY** | **registered 2026-10-22, not started** | window never tested; forward on Sim / demo |
| H-023 | ICT 2022 NY model: overnight-range sweep → 5-min MSS → FVG entry, target range end | failed | only 9 trades in 9 months; price kept going after the sweep on 42% of days |
| H-024 | ICT macro windows (HH:50–HH:10) vs rest of the hour (descriptive) | not supported | 1 of 13 windows moves more: 09:50–10:10, the 10:00 news slot |

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

**Registered:** 2026-10-17  **Status:** REJECTED out of sample (2026-10-18)

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

**Cost calibration — amendment 14c closed (2026-10-18, before any universe results).** `mt5/ExportSpreads.mq5`
(last 90 days, first ticks of each hour) → `research/spread_calibration.md`; multipliers in `h002_costs.csv`: JP225 2.33,
USDJPY 2.5, AUDUSD/GBPUSD/WTI 2.0, XAGUSD 1.38, XAUUSD 1.1, others 1.0. Blind cost filter rerun: BOND (25%) and
AGRI/COFFEE (17.7%) excluded as before; all other markets ≤ 4.5%. US2000 missing at broker. **14 markets, 6 sectors.**

**Universe, in-sample 2023-01-01→2025-06-30 (replica, M5, calibrated spreads; gold M1 = M5 = 112 trades, +0.135R):**
| Market | Trades | Exp. R | PF | | Market | Trades | Exp. R | PF |
|---|---|---|---|---|---|---|---|---|
| US500 | 78 | +0.112 | 1.25 | | EURUSD | 134 | −0.006 | 0.99 |
| US100 | 85 | +0.083 | 1.19 | | USDJPY | 138 | −0.040 | 0.93 |
| US30 | 92 | +0.154 | 1.37 | | GBPUSD | 123 | −0.249 | 0.64 |
| UK100 | 95 | −0.225 | 0.64 | | AUDUSD | 127 | +0.017 | 1.03 |
| GER40 | 103 | +0.215 | 1.45 | | XAUUSD | 112 | +0.135 | 1.27 |
| JP225 | 100 | −0.013 | 0.98 | | XAGUSD | 89 | −0.270 | 0.57 |
| WTI | 95 | −0.033 | 0.94 | | BTCUSD | 127 | −0.176 | 0.71 |
**Portfolio (all trades pooled): 1,498 trades, −0.027R (PF 0.95, 95% −0.09 to +0.03).** Sectors: US equity +0.117R,
non-US equity −0.002, FX −0.067, metals −0.045, energy −0.033, crypto −0.176.
**B1 random entries** (`research/h002_baselines.py`; same markets, stop sizes in ATR units, target rule, max hold and
Friday close; calibration: the simulator reproduces the strategy's own trades, correlation 0.99-1.00, +0.01-0.03R
generous because swaps are not charged): random mean −0.031R; **strategy at the 55th percentile** (95th = +0.020R).
Per market: gold 85th, GER40 97th, US30 83rd, US500 80th; silver 2nd, GBPUSD 6th, BTC 8th.
**B2 simple trend rule:** 13,923 trades, −0.017R pooled (strategy below it).
**Ablations / robustness (portfolio exp. R; gold exp. R, PF):** A1 no higher-low −0.016 (gold +0.079, 1.15); A2 no
pullback −0.050 (+0.048, 1.09); A3 no session −0.033 (+0.089, 1.16); R1 swing 3 −0.073 (+0.048, 1.09); R2 zone 0.2
−0.034 (+0.030, 1.06); R3 zone 0.5 −0.028 (+0.065, 1.13); R4 pessimistic: identical to V0 on M5 bars; R5 spreads ×2
−0.074 (gold unchanged, +0.135).
**Item 12 decision rule, applied to in-sample (a pass in-sample is necessary for a pass out of sample):** PF ≥ 1.2 — no
(0.95); expectancy ≥ +0.15R with CI > 0 — no; beats B1 95th — no (55th); beats B2 — no; PF ≥ 1.0 in ≥ 4 sectors — no
(1 of 6). **The portfolio fails every criterion in-sample.** Gold's own criteria are out-of-sample ones; in-sample it
meets the robustness and US500 criteria (R1-R3 PF 1.06-1.13; US500 PF 1.25) but is not distinguishable from random
entries (85th percentile), and silver, its sector partner, is the worst market (−0.27R).

**Out-of-sample run, registered 2026-10-18 before it was run (Tino's choice).** Gold only, once, 2025-07-01→2026-10-16,
V0 settings unchanged, calibrated spreads, $5,000, code frozen at the commit that adds this paragraph. Engine: the Python
replica on FP Markets XAUUSD M1 bars (Gate 0: 112/112 trades identical to MT5; real ticks changed the mean by +0.003R),
instead of the MT5 real-tick run named in the Gate 0 note — a disclosed deviation. Same window and settings for the
registered checks: criterion 5 (R1 swing 3, R2 zone 0.2, R3 zone 0.5 on gold) and criterion 6 (US500, M5). Gold's
original pass criteria apply unchanged; the B1 random-entry percentile is reported, not judged. The portfolio
out-of-sample run is not made (rejected in-sample).

**Out-of-sample result (2026-10-18, run once at 0f8a2bc).** Gold 2025-07-01→2026-10-16 (gold $3,349 → $4,176):
**41 trades, win 46.3%, +0.265R, PF 1.58, max DD 2.8%** (M1 and M5 identical). Longs 26, PF 2.82 (+0.59R); **shorts 15,
PF 0.55** (−0.30R). By year: 2025 +0.36R (20), 2026 +0.17R (21).
Registered criteria: (1) ≥ 30 trades — yes (41); (2) PF ≥ 1.2 and ≥ +0.15R — yes; (3) DD ≤ 20% — yes; **(4) short PF ≥ 0.9
— no (0.55)**; (5) R1/R2/R3 PF ≥ 1.05 — yes (1.16 / 1.26 / 1.40; +0.09 / +0.13 / +0.19R); **(6) US500 PF ≥ 1.0 — no
(47 trades, PF 0.60, −0.22R).**
Descriptive (not judged): vs random entries with random direction, 93rd percentile; vs random long-only entries, 90th;
the strategy's longs alone at the 99th percentile of random longs (26 trades). Simple trend rule on gold: +0.09R.
### Decision (2026-10-18): REJECT as registered. Criterion 4 (shorts) and criterion 6 (US500) fail, and the registered
fail rule rejects on a collapse of criteria 4-5. The profit came from long trades in a 25% gold rally, which is exactly
what criterion 4 was written to catch; the same rules lost on US500 and, in-sample, across 14 markets (55th percentile
vs random). Not deployable on FTMO or a live account.
**What survives, as a question only:** gold's long entries beat random long entries in both periods (in-sample long PF
1.34; out-of-sample 99th percentile on 26 trades). A long-only gold rule would be a new hypothesis chosen after seeing
this result, so no historical data is left to test it fairly: only a forward demo (new data from 2026-10-19) could, at
about two long trades a month.

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

## H-006: Higher-time-frame supply/demand + failed-extreme entry (her fuller description)

**Registered:** 2026-10-18, before any H-006 rule was run on any data.  **Status:** FAILED (2026-10-18)

**Idea.** The user's summary of her method (YouTube WJleLLue6LA, nsdhIVKwjuQ; Instagram reel; beacons.ai/lakeratrades):
key supply/demand zones on the **daily, 4-hour and 1-hour** charts; no bias before the open, react at the zones;
entry on a rejection candle, a candle break, or a **failure to make a new high/low** at a zone; sit out chop and
low volume; step away around news; scalps of under a couple of minutes. New versus H-004/H-005: the zone time frames,
the failed-extreme entry, a news blackout, entries until 11:30.

**Exact rules (V0).** US100, New York time, 15-second bid candles built from real ticks, mid-price scoring.
- **Zones** at 09:30 from server-time H1, H4 and D bars (built from M1): impulse candle body ≥ 1.5 × ATR(14) of its
  own time frame and ≥ 60% of its range; zone = the candle before it (demand below an up-impulse, supply above a
  down-impulse). Look-back: H1 10 days, H4 30 days, D 60 days (less where the M1 file starts, 2025-06-30). A zone is
  dropped once any later bar of its time frame closes beyond its far side, or a 15-s candle does during the session.
- **Entry (failed extreme):** a 15-s candle that touches a supply zone and makes the highest high of the last 8 candles
  (2 minutes) arms a SELL stop at its low − 0.01 for 4 candles; a higher high cancels it (and may re-arm from the new
  candle). Demand mirrors it. This covers "rejection candle + break" and "failure to make a new high".
- **Stop/target:** 6.25 / 6.25 points (her 25 ticks), 15-minute cap; flat by 11:45.
- **Time:** new entries 09:30-11:30; none 09:57-10:03 (10:00 releases; no calendar available, so every day).
- **Limits:** one position at a time; each zone trades once; ≤ 4 trades a day; stop after 2 losses; Fridays traded.
**Variants (budget 3, chosen now):** V0 as above. V1 = V0 + "sit out chop": no new arm if the last 10 minutes' range
< 0.75 × ATR(14) of M15. V2 = V0 with a structure stop: stop at the arming candle's extreme + 0.25, target the same
distance (1:1), trade skipped if that stop is < 3 or > 12.5 points.
**Data and periods.** Development 2025-07-01→2026-03-31 (pick one variant: highest futures-estimate expectancy);
test 2026-04-01→2026-10-16, run once. That test period was already used by H-005 Q4 (two aggregate results for
different rules were seen), so it is near-clean, not clean: **a pass only earns a 2-3-month forward demo, not money.**
**Pass (test period):** ≥ 100 trades; futures-cost estimate (gross − 0.09R) PF ≥ 1.2 and expectancy ≥ +0.10R; mean R
above the 95th percentile of a random-entry null (same days, same count and directions, entry seconds uniform in
09:30-11:30 outside the news blackout). Diagnostic, not a criterion: how many of her 8 aligned trades (10-31, 11-03)
the chosen variant takes within 30 s.

### Results (2026-10-18)
**Development (2025-07-01→2026-03-31):** V0 256 trades, win 55.1%, gross +0.102R, futures estimate +0.012R (PF 1.02,
95% −0.11 to +0.13); V1 253 trades, gross +0.091R, futures +0.001R; V2 233 trades, gross +0.090R, futures +0.000R.
Pick: V0. Her 8 aligned trades taken within 30 s: 0 of 8 (V0 shorts 11-03 at 09:31:27 and 09:33:49 from a 4-hour zone; hers 09:34:30).
**Test, run once (2026-04-01→2026-10-16), V0:** 156 trades, win 54.5%, gross +0.090R, futures estimate **−0.000R**
(PF 1.00, 95% −0.15 to +0.17), 87th percentile vs random → **FAIL** (PF, expectancy and null criteria).
By zone time frame (descriptive, not a result): daily-zone trades +0.26R (43) and +0.30R (23) gross; H1 +0.13R / −0.03R;
H4 −0.06R / +0.14R.
### Decision (2026-10-18): FAIL — no tradable edge after futures costs. Not built as an EA.
The gross edge is the most consistent seen in H-004/5/6: ~55% wins and ≈ +0.09-0.10R gross in both periods (412 trades),
but the 0.09R futures cost (≈ $11 per NQ round trip on a 6.25-point stop) takes all of it. Anything further must be a new
registration: (a) replicate H-006 V0 unchanged on 2023-01→2025-06 real ticks (never used for any H-006 rule) to see if the
gross edge is real; only then (b) a cost-reducing bracket (wider stop/target) or daily-zone-only, tested forward.


**Amendment H-006/1 (2026-10-18): exit study and one confirmatory test, registered before the run.**
Development only (2025-07-01→2026-03-31, V0 entries): an exit map over stops 4-12.5 and targets 4-25 points; the pick
rule (best neighbourhood-smoothed cell) was written in the code before the map was seen → **stop 4.0 / target 25.0 points**
(raw +0.43R, smoothed +0.36R on the futures estimate). Control: random entries, same days and directions, same bracket:
−0.12R. Zone settings (impulse 1.25/1.5/1.75 × ATR, look-back ×0.5/1/2) all +0.04 to +0.13R gross at 6.25/6.25 (a plateau).
Caveats: the pick is a grid corner; 48 cells were compared; a 4-point stop is sensitive to slippage.
**Rule H-006/X:** H-006 V0 entries unchanged; exit stop 4.0 / target 25.0 points, 15-minute cap, flat 11:45; the
full rule is simulated (one position at a time, so trade count changes).
**Test, once, on 2026-04-01→2026-10-16** (seen before only as V0 at 6.25/6.25). **Pass:** ≥ 100 trades; futures
estimate (0.5625 points per round trip) PF ≥ 1.2 and expectancy ≥ +0.10R; mean R above the 95th percentile of a
random-entry null (same days, directions and bracket, entry seconds uniform in 09:30-11:30 outside 09:57-10:03); and
a **stress case** (target must trade through by 0.25, stop fills 0.25 worse, costs doubled) with expectancy > 0.
A pass leads to one more run, unchanged, on 2023-01→2025-06 ticks (never used), then an MT5 demo.
**H-006/1 results (2026-10-18).** Development, full rule: 234 trades, win 22.2%, gross +0.60R, futures +0.46R (PF 1.52),
stress +0.27R, 99.95th percentile vs random (in-sample: the exit was chosen here).
**Test, run once (2026-04-01→2026-10-16): 141 trades, win 17.0%, gross +0.23R, futures estimate +0.09R (PF 1.10,
95% −0.32 to +0.56), 85th percentile vs random (95th = +0.35R), stress −0.10R → FAIL** (PF, expectancy, null and stress).
**Decision: FAIL.** The 4/25 exit lost most of its development advantage out of sample (+0.46R → +0.09R); with a
17-22% win rate the result is too noisy to separate from zero, and it turns negative with one tick of slippage.
Not run on 2023-2025 (a pass was required). No MT5 bot.

---

## H-007: New York X bias + BPB / BOS entries on 5-minute bars (her full framework)

**Registered:** 2026-10-18, before any H-007 code existed.  **Status:** STOPPED at gate (2026-10-18)

**Sources.** Her videos (bias from London high/low; no trade before one is tested; never trade consolidation; zone,
rejection or candle-break entries; done before 10:00 news), her own chart of 2026-10-05 (BPB, London high/low/50%),
member posts (BPB = Bias, Pause, Break; 5-minute pause box, stop beyond it, far targets; BOS model: break of the
previous 5-min high/low, enter on the tap of the last opposite candle, 1:2, max 2 trades; stops scale with volatility),
and a summary of London X / New York X (sweep-and-fail → reversal; break-and-hold → continuation).
H-004..H-006 most likely tested her "Prop Firm" 15-second scalp, not this framework.

**Data.** FP Markets US100 1-minute bars (all hours), New York time (server − 7 h). Prices are CFD bid; costs use the
futures estimate 0.5625 points per round trip (≈ $11.25 per NQ), converted to R per trade (cost / stop distance).

**Levels (per day).** Asia 20:00-24:00 (previous evening); London 03:00-08:00 high (LH), low (LL), 50%;
06:00-07:00 high/low; previous New York session 09:30-16:00 high, low, 50%. ATR = ATR(14) of 5-minute bars.

**Bias (from 08:00, on closed 5-minute bars), per London extreme:**
- a bar trades beyond the extreme and closes back inside → *swept-fail* → reversal bias;
- a bar closes beyond the extreme → *broken*; later a bar comes back to within 0.25 ATR of the level and closes on
  the far side → *held* → continuation bias; a later close back inside → *failed* → reversal bias.
- The most recent event across both extremes sets the bias. No bias → no trade.

**V0 (BPB, target 2R).** After the bias is set: a *pause* = the last 2 or 3 closed 5-minute bars (all after the bias bar)
with combined range ≤ 1.5 ATR, within 1 ATR of a key level. A stop order at the pause extreme + 0.25 in the bias
direction, valid 3 bars, cancelled by a 5-minute close through the other side. Stop = other side of the pause ∓ 0.25
(kept between max(4 pts, 0.25 ATR) and 3 ATR, else no trade). Target 2R. Exit at 12:00 if still open.
Fills on 1-minute bars: stop order fills at max(trigger, open); a 1-minute bar touching both stop and target counts as
a loss; the fill bar only checks the stop.
**V1** = V0 with target = next key level ≥ 1R beyond the entry (2R if none).
**V2 (BOS).** After the bias is set: a 5-minute close beyond the extreme of the previous 6 bars in the bias direction;
zone = the most recent opposite-colour bar before it (within 6 bars); limit order at the zone's near edge, valid
6 bars, cancelled by a close through the zone; stop = far edge ∓ 0.25 (same limits); target 2R.
**V3** = V0 skipping days when London already expanded: London range ≥ 2 × Asia range and London traded outside the Asia range.
**All:** fills 08:00-11:00, none 09:57-10:03; one position at a time; ≤ 2 trades a day.

**Gate (before any statistics are looked at).** G1: 2026-06-09 — continuation bias (long) by 09:45 and a V0 or V2 long
filled 09:25-09:55. G2: 2025-10-31 and 2025-11-03 — bias bearish at 09:31-09:41 (her on-camera shorts).
Diagnostics only: 2026-10-05 (her news-based long, expected to be missed by design), 2026-10-12 (London-session
1-minute short, outside this engine's window). A gate failure allows bug fixes only, recorded here.

**Development** 2025-07-01→2026-03-31: pick the variant with the highest futures-estimate expectancy (min 60 trades).
Secondary check of the pick on 2026-04-01→2026-10-16 (already used by H-005/H-006 for other rules).
**Final test, once:** 2023-01-01→2025-06-30 (never used). **Pass:** ≥ 100 trades; futures estimate PF ≥ 1.2 and
expectancy ≥ +0.10R; mean R above the 95th percentile of a random-entry null (same days, directions, stop distances,
target rule; entry minutes uniform in the fill window); reported also with costs doubled. Pass → MT5 bot → 2-3 months demo.

**Amendment H-007/1 (2026-10-18): the gate failed; rule change before any statistics.**
Gate traces (only the six gate days were looked at): G1 failed — on 2026-06-09 the London-extreme bias turns long at
09:55, after her 09:42 entry; her trade was a pause just under the London high and a buy on the break through it.
G2 failed for 2025-11-03 (no bias at 09:34-09:38; the London high broke at 09:00 and failed only at 09:40) and passed
for 2025-10-31 09:31-09:39; both days are 15-second "Prop Firm" scalps, not BPB, so G2 becomes a diagnostic.
2026-10-05 never gets a London bias (her bias was news). This is a rule change, not a bug fix, and is recorded as such.
**New rules (replace V0-V3):** a *pause* = the last 2 or 3 closed 5-minute bars, combined range ≤ 1.5 ATR, with a key
level inside the pause range or within 0.5 ATR of it. Stop orders on **both** sides (pause high + 0.25 / low − 0.25),
one-cancels-other, valid 3 bars (a fill on one side cancels the other). Direction = the side that breaks. Stop = other side of the pause; same risk limits, fills, times and limits.
- **V0** BPB both directions, target 2R. **V1** V0 with next-level target. **V2** BOS in either direction (5-min close
  beyond the previous 6 bars' extreme sets the direction), zone tap as before, 2R.
- **V3** V0 but only in the direction allowed by the original London-extreme bias (the registered rule, kept for comparison).
**New gate:** G1 2026-06-09 — V0 long filled 09:35-09:50; G3 2026-10-05 — V0 long filled 09:10-09:35. Diagnostics:
2025-10-31, 2025-11-03, 2026-10-12. If the new gate fails, H-007 stops here and is reported as not reproducible.
Pass criteria, periods and the single final test are unchanged.

### Result (2026-10-18): STOPPED at the amended gate — her BPB is not reproducible as a rule.
New gate traces: on 2026-06-09 and 2026-10-05, V0 found earlier "pauses at a key level" in premarket (08:05/08:55 and
08:05/08:30), filled both (all four lost) and reached the 2-trade limit before her setups (09:40 and 09:20). The BOS
variant (V2) did take a long at 09:24 on 10-05 (+2R), but the gate was registered on V0. As registered, H-007 stops:
no development, secondary or final statistics were run or looked at.
**What it shows:** "a pause at a key level, then a break" occurs several times every morning; the traders choose which
one to take (news, which level matters, the day's context), and that choice is not in the rules we could recover.
Two pre-registered attempts (London-extreme bias; pause-at-level) both failed to reproduce dated trades.
Any further BPB/BOS work needs a new registration (H-008) with an explicit selection rule and counts as a new trial.

---

## H-008: Opening-range break-and-retest on Nasdaq (a member's written rule)

**Registered:** 2026-10-18, before any H-008 code existed.  **Status:** FAILED final test (2026-10-18)

**Source.** A member (Keisha) of La'Kera's community, in her own words: range = the session's opening candle
(Asia: the 1-hour candle 18:00-19:00 New York, "Asia is less volatile"; New York: 15-minute 09:30-09:45); wait for it to
close; on the 5-minute chart wait for a break, then a retest, and enter; NQ stop 37.5 / target 75 points (2:1) on both
dated August trades; one trade a day; holds overnight. Different from H-001 (S&P 500, entry on the breakout bar, stop at
the far side of the range, −0.32R): here the entry waits for the retest and the market is Nasdaq.

**Exact rules.** US100 1-minute bars, New York time. Range = high/low of the opening window. After it closes, on closed
5-minute bars: a close above the range high (below the low) is a *break* and sets the direction; a later break of the
other side replaces it. While a break is live, a limit order rests at the broken edge (buy at the range high / sell at
the range low); it fills when a 1-minute bar trades to it (fill at the edge, or the open if it gapped through). The fill
bar checks only the stop; a 1-minute bar touching stop and target counts as a loss. One trade per session.
Entry windows: Asia 19:00-01:00; New York 09:45-11:30. Flat at 15:55 New York (Asia trades: the next day).
- **V0** Asia 1-hour range, stop 37.5 / target 75 points. **V1** New York 15-minute range, 37.5 / 75.
- **V2** Asia, stop at the far side of the range (range height), target 2 × that. **V3** New York, same as V2.
  V2/V3 skip ranges under 5 or over 150 points.
Costs: futures estimate 0.5625 points per round trip. **Stress case:** target must trade through by 0.25, stop fills
1.0 point worse (thin overnight books), costs doubled.

**Gate (before any statistics).** 2026-08-12 (Wed evening session): V0 must fill a **long at the Asia range high**
between 21:35 and 22:05 New York (her entry: the 20:50 Central = 21:50 New York 5-minute candle, at the ORB high
29,832 in futures). If it does not, fix bugs only; if it still does not, H-008 stops.

**Development** 2025-07-01→2026-03-31: pick the variant with the highest futures-estimate expectancy (min 60 trades).
Secondary check of the pick on 2026-04-01→2026-10-16. **Final test, once:** 2023-01-01→2025-06-30 (never used).
**Pass (final):** ≥ 100 trades; PF ≥ 1.2 and expectancy ≥ +0.10R after futures costs; mean R above the 95th percentile
of a random-entry null (same sessions, directions and bracket; entry minute uniform in the entry window); stress
expectancy > 0. Pass → MT5 bot → 2-3 months demo.

**Amendment H-008/1 (2026-10-18): gate correction, before any statistics.** Gate trace 2026-08-12: Asia range
29,750.25 / 29,699.90 (cash; her ORB high 29,832 in futures = a premium of ~82, consistent); 5-minute break up at 20:05;
**V0 fills long at the range high at 20:31**, stop 37.5 / target 75, target hit at **01:13** (+2R). Her trade: long at the
range high, same bracket, target hit "a little under 4 hours" after ~21:50, i.e. ~01:13. Price sat on the range high
from 20:25 to 21:50 with 8-9 touches; she took a later touch, the bot (her written rule: "once it breaks and retest I get
in") takes the first. The registered gate tested the entry minute (21:35-22:05) and fails by the letter; the trade
itself (level, direction, bracket, exit, result) is reproduced. The gate is corrected to trade identity and H-008
continues; this is disclosed as a correction made after seeing the gate trace, with no statistics seen.

### Results (2026-10-18)
**Development (2025-07-01→2026-03-31), after futures costs:** V0 Asia 37.5/75: 174 trades, win 37%, +0.11R (PF 1.17);
V1 NY 37.5/75: 161, 36%, +0.03R (1.04); V2 Asia range-stop 2R: 169, 38%, +0.13R (1.21); **V3 NY range-stop 2R: 130, 48%,
+0.14R (1.29) → pick.** All 95% ranges include zero.
**Secondary check (2026-04-01→2026-10-16), V3:** 72 trades, win 40%, **−0.11R** (PF 0.81), 22nd percentile vs random,
stress −0.12R. Descriptive only (does not change the final variant): her own rule V0 on the same period: 128 trades,
win 32%, −0.05R (PF 0.92), 33rd percentile vs random.
**Status:** the registered final test (V3, once, 2023-01→2025-06) still needs the 2023-2025 export; given the secondary
result a pass is unlikely. No MT5 bot unless the final test passes.
**Final test, run once (2023-01-01→2025-06-30), V3:** 501 trades, win 42.5%, futures estimate **+0.095R** (PF 1.18,
95% −0.01 to +0.21), stress +0.08R; **random entries (same sessions, directions, bracket): +0.108R — 46th percentile.**
**Decision: FAIL.** The small profit is what any entry at those times and directions earned in 2023-2025; the
opening-range break-and-retest adds nothing over random timing. Data: FP Markets US100 2022-10-03→2025-06-30
(707 days, 46.97 M ticks, 971,859 M1 bars; clock checked; 9 holidays missing).

---

## H-009: H-006 entries, traded so that costs are a small share of each trade

**Registered:** 2026-10-18, before any H-009 run.  **Status:** FAILED confirmation (2026-10-18)

**Problem.** H-006 V0 entries win ~55% at 6.25/6.25 (+0.09-0.10R before costs in both periods, a plateau across zone
settings), but the futures cost (0.5625 points ≈ $11 per NQ round trip) is 0.09R at a 6.25-point stop. The 4/25 exit
(H-006/1) scored +0.09R out of sample and failed under slippage. H-009 keeps the entries and widens the trade.
**Entries:** H-006 V0 unchanged (zones D/H4/H1, failed-extreme stop entry, 09:30-11:30, news blackout, ≤4 trades,
stop after 2 losses). One position at a time; 15-minute cap replaced by flat at 11:45.
**Variants (all four fixed now):**
- **A** stop 12.5 / target 25 points (cost 0.045R).
- **B** stop 0.5 × ATR(14) of M15 at entry, target 2 × stop; skip if the stop is under 6 or over 40 points.
- **C** stop 8 / target 20 points.
- **D** as A, but only trades from **daily** zones (the time frame that was best in both H-006 periods).
**Development** 2025-07-01→2026-03-31: pick the highest futures-estimate expectancy with ≥ 40 trades. (Note: the
H-006 exit map already showed development numbers for brackets like A and C; development is allowed to be seen.)
Apr-Oct 2026 is reported only descriptively (already used twice).
**Confirmation, once, on 2023-01-01→2025-06-30** (never used; needs a tick export from 2022-10-01, see below).
**Pass:** ≥ 100 trades; futures estimate PF ≥ 1.2 and expectancy ≥ +0.10R; mean R above the 95th percentile of a
random-entry null (same days, directions, bracket); stress (target trades through by 0.25, stop 0.5 worse, costs
doubled) expectancy > 0. Pass → MT5 bot → 2-3 months demo on NQ/MNQ costs.

### Development results (2026-10-18), after futures costs
A 12.5/25: 248 trades, win 39.5%, **+0.14R** (PF 1.23); B ATR: 243, 37.4%, +0.07R (1.11); C 8/20: 245, 35.5%, +0.17R (1.25);
**D daily zones 12.5/25: 44 trades, 47.7%, +0.39R (1.71) → pick.** All 95% ranges touch zero.
Apr-Oct 2026, descriptive (already used twice): A 151 trades **+0.13R** (PF 1.20); B 137, +0.12R; C 147, +0.02R; D 24, +0.21R.
**Amendment H-009/1 (before any 2023-2025 data exists here):** A held almost unchanged on Apr-Oct 2026 (+0.14R → +0.13R)
with 6× D's trade count, so A is added as a second candidate for the confirmation. Because two rules are confirmed,
each must beat the **97.5th** percentile of its random-entry null (Bonferroni); other pass rules unchanged. A was added
after seeing the Apr-Oct descriptive numbers; the confirmation data is untouched.
**Data needed:** FP Markets US100 ticks 09:00-11:45 NY and M1 bars from 2022-10-01 to 2025-07-01 (ExportTicks, default
NY window), converted to 1-second bars like H-005.

### Confirmation, run once each (2023-01-01→2025-06-30, never used before), after futures costs
**A (12.5/25): 778 trades, win 32.8%, −0.07R (PF 0.90, 95% −0.16 to +0.03), 76th percentile vs random, stress −0.14R → FAIL.**
**D (daily zones, 12.5/25): 52 trades, win 40.4%, +0.17R (PF 1.27, 95% −0.24 to +0.57), 87th percentile vs random
(97.5th needed), stress +0.04R → FAIL** (fewer than 100 trades; not distinguishable from random).
### Decision (2026-10-18): FAIL. The H-006 entry edge seen in 2025-26 (≈55% at 1:1; +0.13-0.14R for A after costs)
did not exist in 2023-2025 (A won 32.8% at 2:1, below the 33.3% break-even before costs). Treated as a 2025-26 effect,
not a durable edge. H-006/H-009 closed; no MT5 bot.

---

## H-010: New York opening-range break, entry on the break close, up to two trades a day

**Registered:** 2026-10-18, before any H-010 run.  **Status:** PASSED the registered bar, weakly (2026-10-18)

**Idea.** In the H-008 final test, random entries in V3's directions earned the same as the retest entry (+0.108R vs
+0.105R gross). So the value is in the *direction* of the 15-minute opening-range break, not in the retest. H-010 drops
the retest, enters on the break, and allows one more try in the same direction after a stop-out.
**Exact rules tested** (agreed with Tino before any data was loaded). US100 1-minute bars, New York time.
1. Range = high/low 09:30-09:45; skip the day if the range is under 5 or over 150 points (as V3).
2. On closed 5-minute bars from 09:45, the first close above the high (below the low) sets the direction for the day.
3. Trade 1: market order on that close, filled at the next 1-minute open. Stop = range height, target = 2 × range (as V3).
4. Trade 2 only if trade 1 is stopped out: the next 5-minute close beyond the range in the same direction, same bracket.
   Never the opposite direction.
5. At most two trades; none after a winner or a 12:00 exit. No entries after 11:30 (a 5-minute bar closing at 11:30 counts).
   Flat at 12:00 (close of the 11:59 bar). A 1-minute bar touching stop and target counts as a loss.
Differences from V3: entry on the close instead of a retest limit; direction fixed for the day; up to two trades;
flat at 12:00 instead of 15:55.
**Data.** FP Markets US100 M1 exports (2022-10→2025-06 and 2025-07→2026-10), as in H-008. Costs 0.5625 points per
round trip (futures estimate).
**Pass (decided before testing).** 2023-01-01→2024-12-31: futures-estimate expectancy > 0 over ≥ 300 trades.
2025-2026 reported only as a check. Reported but not part of the verdict: trade 1 vs trade 2, longs vs shorts, each
year, random-entry comparison, stress (stop 1 point worse, costs doubled).
**Caveats, stated now.** This bar is lower than H-008's (PF ≥ 1.2, ≥ +0.10R, beat random), and 2023-24 is not unseen:
it was in H-008's final test. A pass here means "worth a demo", not "proven". **Budget:** one run; no changes after.
### Results (2026-10-18, run once), after futures costs
Data check first: the two exports reproduce H-008 V3 exactly (final 501 trades, +0.1047R gross, 251/250; second 72, −0.1031R).
**2023-24 (judged): 550 trades, win 47.5%, +0.033R (PF 1.08, 95% −0.05 to +0.12) → PASS by the registered bar.**
Stress +0.015R. Trade 1: 494, +0.040R. **Trade 2: 56, −0.026R.** Longs 287, +0.072R; shorts 263, −0.010R.
Exits: 274 at 12:00, 212 stop, 64 target. **Random entry (same days, directions, bracket): +0.128R gross vs the rule's
+0.043R** (rule below the random mean).
By year: 2023 −0.009R (280); 2024 +0.077R (270); 2025 +0.047R (228); 2026 −0.025R (135). All 2023-26: 913, +0.028R.
Trade 2 is negative in every year (all years 86 trades, −0.076R).
Compared with V3 on 2023-01→2025-06 (+0.095R after costs), entering on the break close and closing at 12:00 earned less.
### Decision (2026-10-18, Tino): NOT PURSUED, despite passing the registered bar.
The second trade loses money in every year, and the rule earns less than random entry timing in the same directions
(+0.043R vs +0.128R gross), so entering on the break adds nothing. No demo, no MT5 bot. The direction of the opening
break remains the only consistent effect found in H-008/H-010; there is no unseen 2023-2026 data left for it.
The La'Kera / community line (H-004 to H-010) is closed: re-open only with a full broker trade history.

---

## H-011: Her fair-value-gap zones + 15-second rejection candle (her definitions, from her own charts)

**Registered:** 2026-10-18, before any H-011 rule was run on market data (only the July 2025 tick file's format
and coverage were checked).  **Status:** STOPPED at the gate (2026-10-18)

**Why this re-opens the H-004..H-010 line.** Her marked-up charts of 2025-10-23 (YouTube WJleLLue6LA, frames at
09:17 NY, 15- and 5-minute NQ1!) were matched to FP Markets US100 with a futures premium of 143.4 points:
- **Sessions:** Asia box 20:00-03:00 NY (25,112.6 / 24,950.7 vs data 25,113.5 / 24,952.0); **London 03:00-09:00**
  (her Fibonacci 0 / 1 = 25,128 / 24,937 vs data 25,126.8 / 24,937.5); 0.5 = London halfway. We had used 03:00-08:00.
- **Zones are fair value gaps** (three candles; candle 3 does not overlap candle 1), not "the candle before an
  impulse": all five small Thursday zones match 5-minute gaps within ~1 point (exact labels 24,981.25-24,999.50 vs
  24,981.7-25,000.0 + premium); the two Friday 17 Oct zones with labels match 15-minute gaps within a few points.
  Zones reach back about five trading days.
- **Her 23 Oct trades** (long 25,187.75; shorts 25,172.50, 25,156.25, 25,157.75, 25,162.50; long 25,176.25) all sit
  inside one still-open supply gap from Wed 22 Oct 10:15 (15-minute: 25,141.8-25,210.3 in NQ terms).
- Her words: "zone, rejection candle, or break of candle entry"; "supply zone, we broke below it, I entered".
None of H-004..H-007 used fair value gaps or her session times, so they did not test her method as she draws it.

**Exact rules.** US100, New York time, mid prices from real ticks; zones from M1 bars.
1. **Zones:** every 5- and 15-minute fair value gap ≥ 5 points, formed in the last 5 trading days, live from the close
   of its third candle until a later candle of the same time frame closes beyond its far edge.
2. **Rejection candle (15 seconds, closed):** at a supply gap, its high is inside the gap, it closes down, and its upper
   wick ≥ its body. Demand mirrors it.
3. **Entry:** sell stop 1 tick (0.25) below the rejection candle's low, valid for the next 3 candles (45 s); fill at the
   first tick through it. Only with the zone (sell at supply, buy at demand).
4. **Exit:** stop and target 6.25 points (her 25 NQ ticks), 15-minute cap, flat 11:45.
5. **Time and limits:** new entries 09:30-11:30, none 09:57-10:03 (no news calendar); one position at a time; ≤ 7
   trades a day; stop after 2 losses; **no Fridays** (her rule).
Costs: futures estimate 0.5625 points per round trip (0.09R). Stress: stops 0.25 worse, costs doubled.
Not modelled: her 25-or-50-tick choice "by feel", her two counter-zone longs, which gaps she chooses not to draw
(on 23 Oct she left out some ≥5-point gaps), news days, sizing.

**Gate (before any statistics), 2025-10-23:** at least one short inside the Wed 22 Oct 15-minute supply gap, filled
09:45-11:30. Diagnostic: entries within 3 points of her prices (US100 = NQ − 143.4). A failure allows bug fixes only,
recorded here; a second failure stops H-011.
**Development** 2025-07-01→2026-03-31, seen once, no changes after (bug fixes only). The test is spent only if the
development futures-estimate expectancy is above zero.
**Test, once:** 2026-04-01→2026-10-16. Both periods were used by H-005, H-006 and H-009 for other zone rules, so they
are near-clean, not clean. 2023-2025 ticks (ExportTicks2023) remain for a confirmation run.
**Pass (test):** ≥ 100 trades; futures-estimate PF ≥ 1.2 and expectancy ≥ +0.10R; mean R above the 95th percentile of a
random-entry null (same days and directions, same bracket, entry seconds uniform in 09:30-11:30 outside 09:57-10:03);
stress expectancy > 0. Break-even win rate after costs is 54.5%. Pass → confirmation on 2023-2025 → demo, not money.
**Budget:** this one rule; any change after seeing development results is a new hypothesis.
### Results (2026-10-18): gate FAILED — no bug; stopped as registered.
Data: FP Markets US100 ticks 2025-07 and 2025-10→2026-10 received (2025-08/09 missing); only 2025-10-23 was run.
Gate trace: 09:31 short at the Thu 07:30 15-minute supply gap (24,876-24,893 US100) and 09:35 short at the Thu 07:10
5-minute gap (24,888-24,895, her own "~25,031-25,038" box): both stopped within 12 s as price rose through them; the
2-loss limit ended the day before price reached the Wed 22 Oct gap (24,996-25,064 US100 = her 25,142-25,210 NQ).
Checked: both gaps are valid by the rule (formed 07:10/07:30 Thu, not closed through until 09:40/09:45); the fills
follow the rule. No bug, so a rerun would repeat the result and H-011 stops here. No development or test statistics
were computed; the 2026-04→10 tick files are untouched.
**Diagnostic, gate day only (limits removed; not a result):** 39 trades, 18 wins (46%); 28 in the Wed gap; 14 within
3 points of her prices. The rule does find her zone and trades where she traded, but fires on nearly every 15-second
rejection (her day: 7 trades, all winners), including four losing shorts into her own zones during the opening rally.
### Decision (2026-10-18): STOP. Her zones (fair value gaps) and sessions are now reproduced exactly; her entry
selection is not. Which rejection candle she takes, and which zones she ignores (she did not short the Thursday gaps
during the opening rally), is the part that carries her results, and it is not in her stated rules. Any further work
needs a new registration with an explicit selection rule, counted as a new try.

---

## H-012: H-011 plus two selection rules (which rejection candles count)

**Registered:** 2026-10-18, before any H-012 run and before any H-011 development statistics.  **Status:** FAILED development (2026-10-18)
**Why.** H-011's gate day (2025-10-23) showed the rule finds her zone but fires far too often, including four losing
shorts at the open into gaps formed that morning, which she did not trade. Two selection rules chosen by Tino:
1. **Only zones from earlier days:** gaps formed before 00:00 New York time of the trading day (up to 5 trading days back).
2. **No trades against a strong opening move:** for signals closing 09:30-09:45, skip a trade against the move since the
   09:30 open when that move is at least 0.5 × ATR(14) of 15-minute bars (last closed bar before 09:30). From 09:45 on,
   no restriction. (Defined for the first 15 minutes only: on 23 Oct her shorts came after a ~150-point rally from the
   open, so a whole-morning version would have blocked her own trades. This choice was informed by that day.)
Everything else exactly as H-011 (zones ≥ 5 points on 5/15-minute bars, 15-second rejection candle, sell/buy stop 1 tick
beyond it for 45 s, 6.25/6.25 points, 15-minute cap, entries 09:30-11:30 except 09:57-10:03, ≤ 7 trades, stop after 2
losses, no Fridays, futures-estimate costs 0.5625, same stress case). Code: `research/h012.py`.
**Caveat.** Both rules come from one filmed day, so 2025-10-23 is no longer a check: it is traced only to confirm the
code (no shorts at Thursday-morning gaps; trades in the Wed 22 Oct gap).
**Development** 2025-07-01→2026-03-31, seen once, no changes after (bug fixes only). The test is spent only if the
development futures-estimate expectancy is above zero. **Test, once:** 2026-04-01→2026-10-16 (near-clean, as H-011).
**Pass (test):** as H-011: ≥ 100 trades; PF ≥ 1.2 and ≥ +0.10R after futures costs; mean R above the 95th percentile of
the random-entry null; stress > 0. **Tries:** counts as a new try after H-011 (12th registered hypothesis).
### Results (2026-10-18)
Code trace 2025-10-23 (not evidence): Thursday-morning gaps ignored; four early shorts skipped by rule 2 (+42 to +62
points since the open, limit 16.6); trades in the Wed 22 Oct gap: +1, −1, +1, −1, then the 2-loss stop.
**Development, run once (2025-07-01→2026-03-31, 194 tick days, Fridays excluded):** 357 trades on 105 days, win 51.3%,
gross +0.021R, futures estimate **−0.069R** (PF 0.87, 95% −0.17 to +0.03), stress −0.18R, 82nd percentile vs random
entries (random mean −0.027R, 95th +0.059R). Shorts −0.13R (155), longs −0.02R (202); 5-minute zones −0.06R,
15-minute −0.08R. Months after costs: −0.01, +0.03, +0.11, −0.24, −0.33, −0.09, −0.16, −0.07, +0.03.
### Decision (2026-10-18): FAIL at development — expectancy below zero, so the test period (2026-04→10) is not spent.
A 51% win rate at 1:1 is close to random timing and below the 54.5% needed after costs. With her zones and sessions
reproduced, and the two selection rules added, the rejection-candle entry has no edge. The La'Kera line is closed
again; re-open only with her full broker trade history.

---

## H-013: H-012 without rule 2 (earlier-day zones only)

**Registered:** 2026-10-18, after H-012's development result was seen, before any H-013 run.  **Status:** FAILED development (2026-10-18)
**Rules:** H-012 with rule 2 removed: only fair value gaps formed before 00:00 NY of the trading day (up to 5 trading
days back); everything else as H-011/H-012. Code: `research/h013.py` (h012.py with the opening-move filter off).
**Why:** Tino's choice; rule 2 was the one that conflicted with her 23 Oct trades.
**Protocol.** Development 2025-07-01→2026-03-31 was already seen through H-012 (the versions differ only for signals
09:30-09:45), so development can only stop H-013, not support it. The test 2026-04-01→2026-10-16 (unused by any
H-011..H-013 rule) runs once, only if development futures-estimate expectancy > 0. Pass rules as H-011.
**Tries:** 13th registered hypothesis; 3rd variant of her zone + rejection method (H-011, H-012, H-013).
### Results (2026-10-18)
**Development, run once (2025-07-01→2026-03-31):** 401 trades on 114 days, win 52.9%, gross **+0.054R**, futures
estimate **−0.036R** (PF 0.93, 95% −0.13 to +0.06), stress −0.15R. Random entries (same days, directions, bracket):
mean −0.035R gross, 95th percentile +0.045R → the rule's gross result is at the **96.6th percentile** (above random
timing, before costs). Signals 09:30-09:45: 177 trades, −0.005R after costs; later: 224 trades, −0.06R.
Caveat: this period was already seen through H-012 and rule 2 was removed after that, so the percentile is mildly flattered.
### Decision (2026-10-18): FAIL at development — expectancy after costs below zero, so the 2026-04→10 test is not spent.
For the first time in H-004..H-013 the entry timing beats random entries before costs (+0.054R, about +0.09R better
than random), but the 25-tick bracket's cost (0.09R) is larger than the edge: the same pattern as H-006.

---

## H-014: H-013 with her 50-tick bracket (12.5 / 12.5 points)

**Registered:** 2026-10-18, after H-013's development result, before any H-014 run.  **Status:** FAILED test (2026-10-18)
**Rules:** exactly H-013 (her fair value gaps from earlier days only, 15-second rejection candle, stop entry 1 tick
beyond it for 45 s, entries 09:30-11:30 except 09:57-10:03, 15-minute cap, flat 11:45, ≤ 7 trades, stop after 2
losses, no Fridays), with **stop and target 12.5 points each** (her "50 ticks"). Code: `research/h014.py` (h013.py with
the bracket changed and a lighter tick loader that gives identical data, checked on July 2025).
Costs: futures estimate 0.5625 points = **0.045R**; stress: stops 0.25 worse, costs doubled.
**Why:** H-013's entries beat random timing before costs (+0.054R, 96.6th percentile) but the 25-tick bracket costs 0.09R.
**Run once, on the test period 2026-04-01→2026-10-16** (no H-011..H-014 rule has been run on it; it was used by
H-005 Q4, H-006 and H-009 for other rules, so near-clean). No development run: development data informed this choice.
**Pass:** ≥ 100 trades; futures-estimate PF ≥ 1.2 and expectancy ≥ +0.10R; mean R above the 95th percentile of the
random-entry null (same days and directions, same bracket, entry seconds uniform in 09:30-11:30 outside 09:57-10:03);
stress expectancy > 0. Pass → confirmation on 2023-2025 ticks → demo, not money.
**Tries:** 14th registered hypothesis; 4th variant of her zone method. This spends the last clean period for it.
### Results (2026-10-18, run once at commit 6b1f5ac)
**Test 2026-04-01→2026-10-16 (143 tick days, Fridays excluded): 231 trades on 73 days, win 51.1%, gross +0.022R,
futures estimate −0.023R (PF 0.95, 95% −0.15 to +0.11), 86th percentile vs random entries (95th = +0.060R),
stress −0.078R → FAIL** (PF, expectancy, null and stress). Exits: 118 targets, 113 stops. Shorts −0.00R (113), longs
−0.05R (118). Months after costs: Apr +0.19, May −0.40, Jun −0.05, Jul −0.14, Aug +0.05, Sep +0.14, Oct +0.10 (14 trades).
### Decision (2026-10-18): FAIL. Closes her zone method (H-011..H-014). The timing advantage seen in H-013's
development period (96.6th percentile) did not repeat out of sample at the wider bracket (86th, gross +0.02R).
Her zones and sessions are reproduced; no mechanical version of her entries has an edge after costs. Re-open only with
her full broker trade history (several months, losing days included).

---

## H-015: Gold long-only (MS_Gold with shorts off), forward test on demo or live

**Registered:** 2026-10-18, before any forward trade.  **Status:** OPEN — forward period starts 2026-10-19.

**Why.** H-002 was rejected as registered (shorts and US500 failed), but its gold *long* entries beat random long
entries in both periods: in-sample 67 longs, +0.16R; out-of-sample 26 longs, +0.59R (99th percentile of random longs).
This was noticed after the out-of-sample result, so all historical gold data is used up for it. Only new data can test it.

**Exact rules.** MS_Gold v1.14 on XAUUSD.r H1 (FP Markets), every input at its default **except `InpAllowShort = false`**
(and `InpAllowLive = true` only on a real-money account). So: H-002 V0 rules, longs only; 1% risk per trade; daily
loss limit 2%, weekly 5%, kill switch 15%; Friday 16:30 NY close; 5-day max hold; `InpMinLotMaxRiskPct = 0` (never
force the smallest lot: if 1% is too small for 0.01 lot, the trade is skipped and logged).

**Account size (contract fact, from the 93 historical longs).** Median stop 0.59% of price ≈ $24.6 per 0.01 lot at
gold $4,176, so 1% risk on every trade needs a balance of about **$2,500** (0.5% risk: about $5,000). Smaller balances
skip most trades. Demo: use a $10,000 balance so the test sees every trade.

**Demo or live.** Both are allowed by this plan, under the same rules and stop rules. Recommended: demo until the
30-trade checkpoint. Live requires all of: balance ≥ $2,500; money Tino can afford to lose; `InpAllowLive = true`;
risk ≤ 1%. MT5 must stay running while a trade is open (Mac awake or an MT5 VPS), because the 5-day and Friday exits
are done by the bot; stops and targets sit at the broker.

**Expected pace.** About 2 long trades a month (in-sample 2.2, out-of-sample 1.7): ~15 months to 30 trades.

**Stop rules (from 20,000 resamples of the 93 historical longs; protocol item 13).** Stop the test, on demo or live, if:
- the drawdown since the start reaches **5.5R within the first 10 trades**, or **8.5R within the first 30**
  (95th percentile of simulated drawdowns); or
- after 15 trades the average is **below −0.25R** (5th percentile).
The EA's own limits (2% day, 5% week, 15% kill switch) stay on.

**Verdict.**
- **Checkpoint at 30 trades:** average ≥ +0.15R after real costs and PF ≥ 1.2 → continue (live allowed if not already);
  average < 0 → stop and close H-015; in between → continue to 50.
- **Final at 50 trades:** same bar. Pass → keep running at 1%; only then consider more size or a prop challenge.
- Honest power: with no real edge, a 30-trade test still passes about **25%** of the time by luck; with the historical
  edge it passes about 72%, with half of it about 48%. So a pass is encouragement, not proof.

**Record keeping.** `MQL5/Files/MS_journal.csv` (every fill) sent to Claude monthly; a weekly review with
`research/reviews/TEMPLATE.md`; monthly reconciliation: the Python replica on the same dates must reproduce ≥ 90% of the
bot's trades (otherwise find out why before going on). Any rule change ends H-015 and starts a new hypothesis.
### Results
### Decision

---

## H-016: Her zone entries with the bracket from her own trade boxes (12.5 / 16.25 points)

**Registered:** 2026-10-18, before any H-016 run on 2023-2025 data.  **Status:** FAILED (2026-10-18)
**Why.** Her short videos (Oct 2025) show TradingView position boxes: stops 12.5-17.25 points (50-69 ticks), targets
16.5-18.75, risk/reward 1.14-1.71; the 25-tick bracket of H-011..H-013 was not what she uses. Her captioned 20-EMA rule
was broken on 2 of 3 checkable trades (17 Oct short above the EMA on 1/5/15-minute bars; 15 Oct long below it), so it
is not included.
**Rules:** exactly H-013 (fair value gaps ≥ 5 points on 5/15-minute bars from earlier days only, 15-second rejection
candle, stop entry 1 tick beyond it for 45 s, entries 09:30-11:30 except 09:57-10:03, 15-minute cap, flat 11:45, ≤ 7
trades, stop after 2 losses, no Fridays), with **stop 12.5 points and target 16.25 points (1.3R)**. Code:
`research/h016.py`. Costs 0.5625 points = 0.045R; stress: stops 0.25 worse, costs doubled.
**Run once on 2023-01-01→2025-06-30** (US100 ticks 09:00-11:45 NY from `ExportTicks2023.mq5`; no H-011..H-016 rule has
been run on it; H-009 used it for different rules, so near-clean). No development run.
**Pass:** ≥ 100 trades; futures-estimate PF ≥ 1.2 and expectancy ≥ +0.10R; mean R above the 95th percentile of the
random-entry null; stress expectancy > 0. Pass → demo practice with this bracket, not money.
**Tries:** 16th registered hypothesis; 5th variant of her zone method; the last clean period for it.
### Results (2026-10-18, run once at 685b943)
**2023-01-01→2025-06-30 (643 tick days, Fridays excluded): 1,025 trades on 363 days, win 45.1% (break-even after costs
45.4%), gross +0.029R, futures estimate −0.016R (PF 0.97, 95% −0.08 to +0.05), stress −0.072R → FAIL** (PF,
expectancy, stress). **Random entries (same days, directions, bracket): mean −0.047R gross, 95th +0.009R → the rule is at
the 98.8th percentile** (passes the null criterion). Years after costs: 2023 +0.03R (399), 2024 −0.02R (424), 2025 H1
−0.09R (202). Shorts +0.02R (514), longs −0.05R (511). Exits: 543 stops, 440 targets, 42 time.
### Decision (2026-10-18): FAIL. On clean data her zone + rejection timing is better than random (about +0.08R a trade
better than random entries, the second time after H-013's development period, now out of sample), but the edge is
smaller than the costs and weakening year by year. Not tradable as a rule. Her zone method is closed for backtesting
(no clean data left); the remaining question, whether a trader's selection among these setups adds enough to beat
costs, can only be answered by forward demo records (`research/journal/setups_log.csv`).

---

## H-017: Forward test of her zone method's best slice (first try, 09:30-10:00) on demo

**Registered:** 2026-10-18, before any forward trade.  **Status:** OPEN — forward period starts 2026-10-19.
**Why.** In H-016's trades (2023-01→2025-06), first tries at a zone with signals 09:30-10:00 won **49.1%** (389 trades,
+0.081R after futures costs) against 45.1% for all trades. The slice was chosen after seeing the results, so only new
data can show whether it is real.
**Rules (code `mt5/LK_Forward.mq5` v1.00, all inputs at defaults).** US100 on FP Markets demo. Zones: 5/15-minute fair
value gaps ≥ 5 points formed on the last 5 trading days before today, live until a candle of their time frame closes
beyond the far edge. **First try only** (a zone is used once per day). Signals on 15-second candles (from live bid ticks)
closing 09:30-09:57 NY: touch of the gap, close against it, wick ≥ body; stop order 0.25 beyond the candle (mid price),
valid 45 s. Stop 12.5, target 16.25 points; 15-minute cap; flat 11:45; one position; ≤ 3 trades and ≤ 2 losses a day;
no Fridays; 1% risk. Differences from the backtest, stated now: live bid candles instead of mid, CFD fills and costs.
**Costs.** The CFD spread (≈ 1.2 points ≈ 0.10R) is about twice the futures estimate, so break-even on demo is a
**47.7%** win rate (futures: 45.4%).
**Pace.** About 0.6 trades a trading day (155 a year).
**Stop early** if after 50 trades the win rate is below 38% (more than two standard errors below 49%).
**Verdict at 150 trades:** win rate ≥ 47.7% and demo net profit > 0 → the edge looks real; continue to 300 before
any real money. Win rate < 45% → the 49% was luck; close. In between → continue to 300.
Honest power: at 150 trades the win rate is known to about ±8 points (95%), so a single checkpoint cannot prove 49% vs 45%.
**Records:** `MQL5/Files/LK_journal.csv`, sent to Claude monthly; Tino's manual journal runs alongside it.
### Results
### Decision

---

## H-018: The BOS model (break of structure) on its own

**Registered:** 2026-10-18 (Mon 19 Oct), before any BOS statistics.  **Status:** FAILED development (2026-10-19)
**Why.** Tino wants to try the community's BOS model. It was coded as H-007/1 variant V2 but never measured: H-007
stopped at its gate (registered on V0) before any statistics; V2's only trace was a +2R long on 2026-10-05.
**Rules (h007.py V2, unchanged; driver `research/h018.py`).** US100 5-minute bars, NY time. A 5-minute close beyond the
highest high (lowest low) of the previous 6 bars sets the direction; zone = the most recent opposite-colour bar of those 6;
limit order at its near edge, valid 30 minutes, cancelled by a 5-minute close through the zone; stop beyond the far edge
± 0.25 (risk limits as H-007); target 2R. Fills 08:00-11:00 NY except 09:57-10:03; one position; ≤ 2 trades a day;
flat 12:00. Futures-estimate costs 0.5625 points per round trip.
**Development** 2025-07-01→2026-03-31, seen once, no changes after. **Final, once:** 2023-01-01→2025-06-30, only if the
development futures expectancy is above zero (that period was used by other rules, not by BOS: near-clean).
**Pass (final):** ≥ 100 trades; PF ≥ 1.2 and ≥ +0.10R after futures costs; mean R above the 95th percentile of random
entries (same days, directions, stop and target). **Tries:** 18th registered hypothesis.
### Results (2026-10-19, development run once)
**2025-07-01→2026-03-31: 309 trades on 184 days, win 30.7% (2R needs ≥ 33.3% before costs), gross −0.097R, futures
estimate −0.137R (PF 0.81, 95% −0.28 to +0.02), median stop 17 points.** Random entries with the same days, directions,
stops and targets: +0.028R mean → the rule is at the **4th percentile** (worse than random). Exits: 211 stops, 88 targets,
10 time. Longs 172, shorts 137.
### Decision (2026-10-19): FAIL at development; the 2023-2025 final run is not spent (as registered). Entering on the tap
of the last opposite candle after a 5-minute break of structure did worse than random timing in the same direction.

---

## H-022: LK rules on futures (MNQ), signals 08:00-14:00 New York, forward on Sim / demo

**Registered:** 2026-10-22, before any trade or test on this window.  **Status:** REGISTERED, not started.
**Why.** Tino wants the bot on a FundedNext futures account (Tradovate) and chose a wider signal window, 08:00-14:00 NY,
instead of H-017's 09:30-09:57. Nothing in H-011..H-017 tested this window: 09:30-11:30 won 45.1% (break-even 45.4%
after futures costs) and only the 09:30-10:00 slice looked better (49.1%). The pre-market (08:00-09:30) and midday
(11:30-14:00) have no record at all, so this is a new hypothesis, tested forward only.
**Rules.** `futures/ninjatrader/LKForward.cs` (or `futures/tradovate/lk_tradovate.py`, same entries) v1.00-futures at
defaults: H-017's zones, first try only, 15-second rejection candle, 45 s trigger 0.25 beyond it, stop 12.5 / target 16.25,
15-minute cap, ≤ 3 trades and ≤ 2 losses a day, no Fridays; **signals 08:00-14:00 NY, flat 14:30**; MNQ last-trade prices;
$100 risk (4 MNQ), max 10 contracts, Maximum Loss Limit guard. Sim or Tradovate demo first; a FundedNext challenge
only after the verdict below.
**Costs.** About 0.04-0.05R a trade (commission ≈ $1 per contract round trip, 1 tick of slippage on the stop), so
break-even is about **45.4%** wins at 1.3R.
**Stop early** if after 50 trades the win rate is below 37%.
**Verdict at 150 trades:** win rate ≥ 47% and net profit after costs > 0 → continue to 300 before money; < 43% → close;
in between → continue to 300. Also report the win rate by hour (08-09:30, 09:30-11:30, 11:30-14:00) without
changing the rule mid-test.
**Records:** `LK_futures_journal.csv` (NinjaTrader user folder, or `futures/tradovate/journal/`), sent to Claude monthly.
### Results
### Decision

---

## H-003: Intraday momentum, first half-hour → last half-hour (S&P 500)

**Source:** Gao, Han, Li & Zhou, "Market Intraday Momentum", Journal of Financial Economics (2018).
**Idea:** the S&P 500's move from the previous close to 10:00 New York predicts the direction of the last
30 minutes (15:30–16:00). One trade a day, evenings in Harare. Small edge per trade; costs are the main risk.
**Registered (full rules):** 2026-10-18, before any H-003 code was run on market data.  **Status:** FAILED (2026-10-18). The first outside-sourced idea after H-004..H-010; the same family (short-term
momentum) as the only consistent effect found so far.

**Exact rules.** FP Markets US500 5-minute bars, New York time (server − 7 h), 2023-01-01→2026-10-16, weekdays.
1. Trading days = the NYSE calendar (holidays dropped even if the CFD prints bars). Previous close = the close of the
   previous NYSE day's bar ending at its close (15:55 bar; on a half day, the 12:55 bar).
2. Signal = close of the 09:55 bar (price at 10:00) minus the previous close. Above zero → long; below → short; zero → no trade.
3. Enter at the open of the 15:30 bar; exit at the close of the 15:55 bar (16:00). No stop and no target, as in the paper.
4. No trade on half days, or if the previous close, the 09:55 bar or any of the six bars 15:30-16:00 is missing.
Costs 0.50 index points per round trip (≈ MES 1-tick spread + commission; the CFD's recorded spread is 0.44).
Stress: 1.00 point. Results in index points, per $-per-MES (× $5), and as a % of price.
**Benchmarks:** (a) always long 15:30-16:00 (end-of-day drift); (b) random direction each day, 10,000 runs.
**Pass (all, decided now):** ≥ 500 trades; after costs mean > 0 with the 95% bootstrap range above zero; mean above
always-long and above the 95th percentile of random direction; stress mean > 0; at least 3 of 4 years positive after costs.
**Reported, not part of the verdict:** each year; longs vs shorts; days with a large vs small 10:00 move (split at the
median); days where the 15:00-15:30 move agrees with the signal (the paper's second predictor).
**Caveats, stated now.** Published 2018 on 1993-2013 data; published patterns often weaken after publication. No stop:
a bot would need a catastrophe stop, which this test does not model. US500 2024-01→03 bars were looked at in H-001
(a different rule). **Budget:** one rule, one run, no variants. A pass earns a forward demo, not money.
### Results (2026-10-18, run once)
Data: FP Markets US500 M5, 2022-11-30→2026-10-16 (274,059 bars; tick volume jumps at 09:30 NY, so the clock is right).
**940 trades, win 47.6%, gross +0.29 points, after costs −0.21 points (−$1.05 per MES; PF 0.95, 95% −0.96 to +0.56)
→ FAIL** on every criterion except trade count. Always long 15:30-16:00 earned +0.21 points gross, so the signal adds
~0.08 points; 78th percentile vs random direction (95th = +0.14 net). Stress −0.71. Years after costs: 2023 +0.26,
2024 −0.68, 2025 −0.25, 2026 −0.16 (1 of 4 positive). Descriptive: the paper's stronger cases go the wrong way here —
large 10:00 moves −0.23 gross (small +0.81); 15:00-15:30 move agreeing −0.02 gross (disagreeing +0.62).
### Decision (2026-10-18): FAIL — the published effect is not present in 2023-2026 S&P 500 data after costs. Closed.

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


## H-019: Build-up breakout at support/resistance, in the trend direction
Registered 2026-10-18, before any data was run. Code: research/h019.py. US100 1-minute bars, New York time.

**Rules**
- Trend: last closed 15-minute bar. Close above a 20 EMA that is higher than 4 bars ago = up; mirrored = down; otherwise no trade.
- Levels: previous day's 09:30–16:00 high and low; Asia (20:00–03:00) high and low after 03:00; London (03:00–09:00) high and low after 09:00.
- Build-up: the last 4 five-minute candles span at most 0.75 × ATR(14, 5-minute). For longs the build-up high sits between 0.5 ATR below a level and 0.1 ATR above it (shorts mirrored).
- Entry: stop order 0.25 beyond the build-up, valid for 3 five-minute bars. Cancelled if a 5-minute candle closes beyond the other side.
- Stop 0.25 beyond the other side; at least 5 points. Target 2R.
- Time (made flexible on 18 Oct): new orders 03:00–15:30 NY, flat by 16:00, at most 2 trades a day, weekdays only.
- Costs: 0.5625 points per round trip. Stress test: 0.25 stop slippage plus double costs.

**Pass (development 2025-07 to 2026-03, run once):** at least 100 trades; after-cost profit factor ≥ 1.2; expectancy ≥ +0.10R; gross R above the 95th percentile of random entries (same days, direction and stop); stress expectancy > 0.
**Final run** (2023-01 to 2025-06), once, only if development expectancy after costs is above zero.

### Results (development, run once 2026-10-18)
4 trades on 4 days; 3 winners, 1 loser; +1.21R after costs; random entries 81st percentile. One code fix before the run counted: the position key was `dir`, not `d`. No rule changed.
### Decision
**Fail: fewer than 100 trades.** Four tight 5-minute candles spanning at most 0.75 ATR almost never form next to a level with the trend agreeing. Four trades say nothing either way. The final period stays unspent. Any looser version is a new hypothesis (H-020), registered first.


## H-020: AMD at the New York open — sweep or gap tap, then reverse (GS Trades video)
Registered 2026-10-20, before any H-020 code was run on market data. Code: `research/h020.py`. US100 1-minute bars, New York time.
(The H-019 decision mentioned "H-020" for a looser H-019; that was never registered, so the number is used here and a looser H-019 would be H-021.)

**Source.** A short video by "GS Trades" (shared by Tino, 2026-10-20), sold as "accumulation, manipulation, distribution" (AMD):
(A) in the 5 minutes before the open, if price runs into an untapped fair value gap or sweeps a swing high/low, "almost
guaranteed" to reverse — short with the stop at the high and hold through the open; (B) more often, 09:30–09:33 sweeps a gap or
liquidity point and you enter the reversal "the second it does that". He reports a 17-day winning streak. No target, size,
swing definition or time exit is given; those below are ours, fixed now. Failing rejects **this rule set**, not every reading of AMD.
His "9:00 Eastern Standard" is read as the 09:30 open on the New York clock (EDT in summer); the data is already on that clock.

**Exact rules**
- **Liquidity (both scenarios):** previous NYSE day 09:30–16:00 high and low; Asia 20:00–03:00 and London 03:00–09:00 high and low
  (H-011's sessions); 5-minute swing highs/lows (high above the 2 bars either side; mirrored for lows) formed since the previous day's 09:30.
  A level counts only if no 1-minute price has gone beyond it since it formed (untaken), checked at the start of each window.
- **Untapped fair value gaps:** 5-minute three-candle gaps ≥ 5 points (H-011's definition) formed in the last 5 trading days, that no
  1-minute bar has entered since the third candle closed. A gap above price is a sell line at its lower edge; below price, a buy line at its upper edge.
- **Scenario A (pre-open, bars 09:25–09:29):** the first bar whose high goes above an untaken high, or reaches a sell line, → **short at that bar's close**;
  mirrored for lows → long. Both in one bar → no trade that day.
- **Scenario B (bars 09:30–09:32, only if A did not trade):** levels re-checked at 09:30. Once a bar in this window goes beyond an untaken high (or reaches
  a sell line), the first bar up to 09:32 that **closes back below that line** → short at its close (mirrored for longs). Both in one bar → none.
- **Stop:** 0.25 beyond the highest high (lowest low) of the window up to the entry bar ("stop at the high"); at least 5 points from entry.
- **Target 2R.** Otherwise out at the 10:29 bar's close (10:30). On 1-minute bars a bar that touches both stop and target counts as a stop.
- One trade a day, weekdays, skip days with any 1-minute bar missing from 09:20 to 09:35.
- **Costs:** futures estimate 0.5625 points per round trip. Stress: stops 0.25 worse, costs doubled. **Also reported:** FP Markets CFD cost 1.45 points
  (the average open spread measured in H-004), because that is where Tino trades US100 today.

**Development** 2025-07-01→2026-03-31, seen once, no changes after (bug fixes only, recorded here).
**Final, once:** 2023-01-01→2025-06-30, only if development futures expectancy is above zero. Both periods were used by other rules (H-018, H-019): near-clean.
**Pass (final, all):** ≥ 100 trades; futures PF ≥ 1.2 and expectancy ≥ +0.10R; mean gross R above the 95th percentile of a **random-direction** null
(same days, entry bars, stops, 2R target, exit time; only the direction is a coin flip — this tests the video's actual claim, that the sweep tells you
which way price goes next); stress expectancy > 0.
**Reported, not part of the verdict:** A vs B; longs vs shorts; gap vs liquidity triggers; win rate against the "almost guaranteed" claim (break-even
for 2R after costs is about 34-35%); the hold-to-10:30 version with no target; each year.
**Budget:** this one rule set (20th registered hypothesis). Any change after seeing development results is a new hypothesis.
A pass earns a forward demo with a stop on every trade, not money.
### Results (development, run once 2026-10-21)
Data: FP Markets US100 M1 export (`orb_export/US100_M1.csv`, 2025-06-30 → 2026-10-16). Code unchanged since registration.
**148 trades on 194 days, win 24.3% (2R needs ≥ 33.3% before costs), gross −0.27R, futures estimate −0.34R (PF 0.58, 95% −0.55 to −0.12),
median stop 7.3 points.** CFD costs (1.45 pts): −0.46R. Stress: −0.44R. Exits: 112 stops, 36 targets. Longest winning streak: 3.
**Random direction** (same entries, stops, target, exit time; coin-flip side): mean −0.12R, 95th pct +0.04R → the rule sits at the
**5th percentile**: fading the sweep did worse than a coin flip on direction.
Breakdown (none part of the verdict): pre-open A 78 trades −0.48R; open B 70 trades −0.18R; longs and shorts the same (−0.34R each);
gap triggers 33 trades −0.54R, swing 91 −0.35R, London 22 +0.04R (too few to mean anything); 2025 −0.42R, 2026 −0.21R.
Hold to 10:30 with no target: 10% win, +0.20R after costs, 95% range −0.59 to +1.23 — a handful of large moves, indistinguishable from zero.
### Decision (2026-10-21): FAIL at development; the 2023-2025 final run is not spent (as registered).
A sweep or gap tap at 09:25-09:33 happened on three days in four and did not mark a reversal; the "almost guaranteed" reversal is not in
2025-26 Nasdaq data under these rules. Any other reading (another target, a confirmation candle, fewer levels) is a new hypothesis.


## H-023: ICT 2022 model at the New York open — overnight-range sweep, structure shift, fair-value-gap entry
Registered 2026-10-24, before any H-023 code was run on market data. Code: `research/h023.py`. US100 1-minute bars, New York time.

**Source.** The ICT 2022 mentorship model as written up by two teaching sites Tino shared (2026-10-24: a 10-step guide and a
TradingFinder article with Nasdaq examples). Their New York scenario: mark the range from NY midnight to the open; the open sweeps one
side; a market structure shift (MSS) with displacement follows on 5/3/1-minute bars; enter when price returns to the fair value gap
(FVG) left by the shift; stop beyond the sweep; target the other side of the range; "at least 1:3". The bias step is left out of the
verdict (the guides give no mechanical rule); a fixed bias rule is reported only. Failing rejects **this rule set**, not every reading of ICT.

**Exact rules**
- **Range:** high and low of 1-minute bars 00:00–09:29. Skip days missing any bar 09:20–09:35 or with fewer than 400 range bars.
- **Sweep (09:30–10:59 bars):** the first bar whose high goes above the range high → short setup; low below the range low → long.
  Both in one bar → no trade. Only the first sweep of the day counts.
- **Sweep extreme:** the highest high (short) / lowest low (long) from the sweep bar onward, updated until the MSS.
- **MSS on 5-minute bars** (clock-aligned): the most recent 5-minute swing low (a low below the bars either side, N = 1) whose right
  neighbour closes at or before the 5-minute bar holding the sweep extreme; MSS = a 5-minute bar closing below it (mirrored for longs).
  A new extreme resets the reference swing. The MSS bar must close by 11:00.
- **Displacement / FVG:** a bearish 5-minute three-candle gap ≥ 5 points (H-011's size) whose first candle is at or after the extreme bar
  and whose third candle is at or before the MSS bar; if several, the latest.
- **Entry:** limit at the gap's near edge (bottom edge for shorts), live from the MSS bar's close to the 10:59 bar. Filled only when a
  1-minute bar trades 0.25 through it. Cancelled if, before the fill, price reaches the target or the stop.
- **Stop:** 0.25 beyond the sweep extreme; at least 5 points. **Target:** the opposite end of the range. **Skip** if that is under 2R.
- **Exit:** stop, target, or the 11:59 bar's close (NY lunch). Stop and target in one bar → stop. A fill bar that also reaches the stop → stop.
- One trade a day, weekdays only.
- **Costs:** futures 0.5625 points per round trip; stress: stops 0.25 worse, costs doubled; also reported: FP Markets CFD cost 1.45 points.

**Development** 2025-07-01→2026-03-31, run once, no changes after (bug fixes recorded here). **Final, once:** 2023-01-01→2025-06-30,
only if development futures expectancy is above zero (both periods used by other rules: near-clean).
**Pass (final, all):** ≥ 100 trades; futures PF ≥ 1.2 and expectancy ≥ +0.10R; mean gross R above the 95th percentile of a
random-direction null (same entry bars, stop distance, target in R, exit time; coin-flip side); stress expectancy > 0.
**Reported, not part of the verdict:** fixed 2R and 3R targets instead of the range end; a bias filter (trade only in the direction of
the previous day's close relative to that day's 09:30–16:00 midpoint); longs vs shorts; setups skipped (no MSS, no gap, no fill, under 2R); each year.
**Budget:** this one rule set (23rd registered hypothesis). A pass earns a forward demo with a stop on every trade, not money.
### Results (development, run once 2026-10-24)
Data: FP Markets US100 M1 export (2025-06-30 → 2026-10-16, attached by Tino 2026-10-24). One bug fix before any result was seen:
the first run crashed on a day with no bars before noon (the day's start was read from its first bar); the day is now passed in. No rule changed.
**193 days with data → only 9 trades.** Where the sequence stopped: no sweep 13; sweep but **no structure shift by 11:00 on 81 days**
(price kept going past the range); shift but no 5-point gap 73; target under 2R 13; no fill 4.
The 9 trades: 3 wins, futures −0.21R (PF 0.60, 95% −0.78 to +0.41), median stop 73.5 points; exits 4 stops, 5 at 12:00, no targets
reached. Random-direction null 30th percentile. Fixed 2R −0.15R, fixed 3R −0.21R. Bias filter: with bias 5 trades 0 wins; against 4 trades 3 wins.
### Decision (2026-10-24): FAIL at development (9 trades, needs ≥ 100); the 2023-2025 final run is not spent.
Too few trades to judge the edge either way. What the run does show: after the open takes out the overnight range, price **continued**
rather than shifting structure on 42% of days, and only 5% of days produced the full sweep → shift → gap → fill sequence. A looser
version (1-minute shift, smaller gaps, later cut-off) is a new hypothesis, registered first.


## H-024: Do ICT "macro" windows move more than the rest of the hour? (descriptive, no trading rule)
Registered 2026-10-24, before any H-024 code was run on market data. Code: `research/h024.py`. US100 1-minute bars, New York time.

**Claim tested.** ICT (2024 mentorship, as quoted in a guide Tino shared) says a macro runs in the last 10 minutes of each hour and the
first 10 of the next, when price seeks liquidity or fills a gap. If true, those 20 minutes should move more, and take out nearby highs
and lows more often, than the other 40 minutes of the same hour.

**Method**
- Blocks of one hour from HH:50 to the next HH:50, for HH = 02..14 (13 blocks, 02:50–15:50). In each: **macro** HH:50–HH+1:10,
  **control 1** HH+1:10–HH+1:30, **control 2** HH+1:30–HH+1:50. Block 08:50: control 2 contains the 09:30 open, so only control 1 is used.
- Per window and day: **range** = highest high − lowest low; **sweep** = 1 if the window goes beyond the high or the low of the 60
  minutes before it starts. Days missing more than 2 bars in a block are skipped for that block.
- Per block: mean of log(macro range / control range) across days (controls averaged), with a 95% day-bootstrap interval;
  sweep rate of macro minus control, with a 95% interval.
- Also reported: ICT's named NY windows on the same footing — 13:10–13:40 vs 13:40–14:10 and 15:15–15:45 vs 14:45–15:15.

**Data:** 2025-07-01→2026-03-31 (the development period above; no trading rule is fitted, so the final period is not spent).
**Supported if** in at least 9 of the 13 blocks the macro range is ≥ 10% larger (log ratio ≥ 0.095) with the interval above zero
**and** the macro sweep rate is higher with the interval above zero. **Not supported** otherwise.
**Known confound, stated now:** US data at 10:00 (and other on-the-hour releases) lands inside macro windows; no news calendar is used,
so a "supported" result could be scheduled news rather than an algorithm. The 09:50 block is reported with that warning.
### Results (run once 2026-10-24)
196 weekdays, 2025-07-01 → 2026-03-31. **1 of 13 blocks** meets both conditions: **09:50–10:10**, range 99.9 vs 81.6 points (+20%,
95% +14% to +27%), sweep rate 80% vs 54%. Every other block: macro range between −22% and +9% of the controls, sweep rate no different.
07:50–08:10 is **22% smaller** than its control (08:10–08:30), which holds the 08:30 US data releases. Named PM windows: 13:10–13:40 +3%
(interval spans zero), 15:15–15:45 −0.5%.
### Decision (2026-10-24): NOT SUPPORTED.
Outside 09:50–10:10 the "macro" minutes move like any other 20 minutes of the hour. The one window that stands out holds the 10:00
data releases, and the 07:50 block shows the reverse pattern where the news sits in the control instead. Both point to scheduled
news, not a time-based algorithm. Practical reading: 09:50–10:10 is a high-volatility slot to plan around (as her 09:57 news stop does), not an edge.
