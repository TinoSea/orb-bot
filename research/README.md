# Research log

This folder is the lab notebook. It's what turns "I built a trading bot" into
"I can run a disciplined research process", which is the part institutions care about.

| File | What goes in it | Who fills it |
|---|---|---|
| `hypotheses.md` | Each idea, written **before** testing, with pass/fail rules and the final decision | You + Claude |
| `experiments.csv` | Every Python backtest run, including the failures | Automatic (`orb_backtest.py`) |
| `mt5_results.csv` | Every MT5 Strategy Tester run | Send Claude the screenshots, or fill it in yourself |
| `reviews/` | One review per week of demo (later live) trading | You, using `reviews/TEMPLATE.md` |
| `trials.csv` / `trials.py` | Every registered idea that looked at data, and the "luck bar" a result must clear given how many were tried (deflated Sharpe ratio) | Claude adds a row per hypothesis |
| `h026.py` | H-026: do Asia/London extremes and gaps turn price more than placebo levels? Run `python3 research/h026.py dev <US100_M1.csv>` | Claude, once data is attached |
| `prop_sim.py` | FundedNext futures rules (Rapid Pro 25K defaults): pass, bust and payout odds for any trade record or profile | Anyone: `python3 research/prop_sim.py --profile 0.40 3.4 --per-day 2` |
| `journal/predictions_log.csv` + `journal_score.py` | Your manual setups, written **before** entry with a confidence %, then scored: does your judgement beat chance and the market's base rate? | You, every setup (taken or skipped) |

## The rules (how professional research desks work)

1. **Write it down first.** State the hypothesis and the pass/fail numbers *before* you see any results.
   Deciding the bar after seeing the results is how people fool themselves.
2. **Log every run, especially the failures.** Rejected ideas are evidence of a good process, not something to hide.
3. **Look at out-of-sample data once.** If you change settings after seeing it, it isn't out-of-sample any more.
   Use the in-sample period for tuning, then run the unseen period once.
4. **One change at a time,** with a one-line note saying why (`--note "target 2R instead of 1.5R"`).
5. **Costs always on.** Commission, spread and slippage, with fills that are pessimistic rather than flattering.
6. **Count your tries.** Test 20 variations and one will look great by luck. The backtester warns you after 10.
7. **Close every hypothesis in writing:** keep, reject or park, and why.
8. **Compare live with backtest weekly.** If demo results drift from the backtest, find out why before going further.

## Logging a Python run

```
python orb_backtest.py --csv data/us500_5m.csv --hyp H-001 --note "baseline, default settings"
```

Each run appends a row with the settings, data range, code version (git commit), and in-sample vs
out-of-sample results. Demo-data runs are never logged. Add `--no-log` for throwaway checks.

## Judging trades: process over outcome

A trade is graded on **whether it followed the plan**, not on whether it made money.

| | Followed the rules | Broke the rules |
|---|---|---|
| **Won** | Good trade | Bad trade (lucky) |
| **Lost** | Good trade (the cost of doing business) | Bad trade |

Over hundreds of trades, good process produces the results. Single trades are mostly noise.

## Testing levels before entry rules (added 2026-11-01)

Before registering any new entry rule on her levels, check that the levels themselves matter: H-026 compares real
Asia/London highs and lows (and her fair value gaps) with placebo levels at the same distance from the open on other days.
Its checks run on synthetic data with a known answer: `python3 research/tests/test_h026.py` (no edge → NOT SUPPORTED;
planted edge → SUPPORTED; 1 false pass in 20 random markets, as designed).
