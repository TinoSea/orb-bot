# Research log

This folder is the lab notebook. It's what turns "I built a trading bot" into
"I can run a disciplined research process", which is the part institutions care about.

| File | What goes in it | Who fills it |
|---|---|---|
| `hypotheses.md` | Each idea, written **before** testing, with pass/fail rules and the final decision | You + Claude |
| `experiments.csv` | Every Python backtest run, including the failures | Automatic (`orb_backtest.py`) |
| `mt5_results.csv` | Every MT5 Strategy Tester run | Send Claude the screenshots, or fill it in yourself |
| `reviews/` | One review per week of demo (later live) trading | You, using `reviews/TEMPLATE.md` |

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
