# ORB Bot

| Part | What it is |
|---|---|
| `mt5/ORB_US500.mq5` | **The trading bot** for MetaTrader 5 on US500 (FP Markets). Setup: [`mt5/README.md`](mt5/README.md) |
| `orb_backtest.py` | Independent Python backtester, used to cross-check the MT5 results. Logs every run to the research log |
| `research/` | The lab notebook: hypotheses, every test result, weekly trade reviews. See [`research/README.md`](research/README.md) |
| `LEARNING.md` | Roadmap from this project to institutional-level trading skills |

---

## Python backtester v1

Opening-range breakout on MES (micro S&P 500 futures), with hard risk rules and honest costs.
This stage spends **$0**. Its only job is to find out whether the strategy has a real edge.

## 1. One-time setup on your MacBook Air (about 10 minutes)

1. Open **Terminal** (press Cmd + Space, type `Terminal`, press Enter).
2. Check Python:
   ```
   python3 --version
   ```
   If you see 3.10 or higher, skip to step 3. If not, install Python from python.org (macOS installer) and reopen Terminal.
3. Get the code from GitHub with **GitHub Desktop** (free, desktop.github.com):
   sign in, then **File → Clone Repository → orb-bot**, and set the Local Path to your home folder so it lands in `~/orb-bot`.
   Then in Terminal:
   ```
   cd ~/orb-bot
   ```
   Whenever Claude pushes a change: in GitHub Desktop click **Fetch origin**, then **Pull origin**.
4. Create a private Python environment and install the libraries:
   ```
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
   Each time you come back later: `cd ~/orb-bot && source .venv/bin/activate`

## 2. Run it

**a) Check the install works (fake data):**
```
python orb_backtest.py --demo
```
This should say **NO EDGE YET**. The fake data has no edge in it, so a profit here would mean the backtester was cheating.

**b) Real MES data (last ~60 days from Yahoo):**
```
python orb_backtest.py --source yf --symbol MES
```

**c) Let it tune settings on the first 70% only, then test on the unseen 30%:**
```
python orb_backtest.py --source yf --symbol MES --sweep
```

Each run saves `trades.csv` (every trade, opens in Numbers or Excel) and `equity.png` (the equity curve). Open the chart with `open equity.png`.

## 3. How to read the results

| Metric | What "good" looks like |
|---|---|
| **Out-of-sample profit factor** | 1.2+ is good. Above 2 is suspicious. This is the number that matters. |
| Win rate | 40–55% is normal for this strategy |
| Expectancy (R) | Above +0.1R per trade after costs |
| Max drawdown | Know it. You'll live through it. |
| Trades | Under 100 = not enough evidence yet |

The verdict line sums it up: **NOT ENOUGH TRADES / NO EDGE YET / LIKELY OVERFIT / MARGINAL / PROMISING**.

## 4. Important limits

- **60 days of Yahoo data is only ~40 trading days.** That's enough to test the code, not to trust the strategy. Next step is a year or more of 5-minute MES data as a CSV, then run `python orb_backtest.py --csv yourfile.csv`. The CSV needs columns `datetime, open, high, low, close, volume` (New York time).
- **Check your real fees.** The default is $1.00 per contract per side. Change it with `--commission 0.85` (or your actual all-in figure) once you know your Tradovate costs.
- **A good backtest is not permission to trade real money.** Next is 6–8 weeks of paper trading on Tradovate's demo.

## 5. The risk rules (in `Config` at the top of the script)

| Rule | Default |
|---|---|
| Contracts | 1 MES |
| Max risk per trade | $100 (trade skipped if the stop is wider) |
| Daily loss limit | $150 |
| Weekly loss limit | $400 |
| Kill switch | Stop for good after a $1,500 drawdown |
| Trades per day | 1 |

Don't loosen these to make results look better. That's how overfitting starts.

*Not financial advice. A backtest is evidence, not a promise.*
