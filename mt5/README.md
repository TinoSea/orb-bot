# ORB bot for MetaTrader 5 (US500)

`ORB_US500.mq5` is the trading bot (an MT5 "Expert Advisor"). It runs the same opening-range breakout
and the same risk rules as the Python backtester, on FP Markets' **US500** (S&P 500 index CFD).

> **You need the desktop MetaTrader 5, not the phone/iPad app.**
> The app with *Quotes / Chart / Trade / History* tabs along the bottom cannot run bots and has no Strategy Tester.
> The desktop version has a menu bar (File, View, Insert, Charts, Tools…) and a **Navigator** panel.

---

## 1. Install desktop MT5 on the Mac

1. Download **MetaTrader 5 for Mac** from FP Markets' platforms page (or metatrader5.com → Download → macOS).
2. Install and open it. The first launch can take a few minutes while it sets itself up.
3. **File → Login to Trade Account**: your account number, trading password, and server.
   - Demo account → its demo server (from the demo email)
   - The live account 85928909 → **FPMarketsSC-Live** (log in only to look; **don't fund it yet**)
4. Add the symbol: **View → Market Watch**, right-click → **Symbols**, search **US500**, **Show Symbol**.

## 2. Install the bot

1. In MT5: **File → Open Data Folder**. Finder opens.
2. Go into **MQL5 → Experts** and copy `ORB_US500.mq5` there.
   (Get it from GitHub Desktop: your `orb-bot` folder → `mt5`.)
3. Open **MetaEditor**: **Tools → MetaQuotes Language Editor** (or the IDE button on the toolbar).
4. In MetaEditor's Navigator, open **Experts → ORB_US500.mq5**, then press **Compile** (F7).
5. The bottom panel should say **0 errors**. If there are errors, screenshot them and send them to Claude.
   (Warnings are OK.)

## 3. Backtest it in the Strategy Tester  ← do this before anything else

**View → Strategy Tester** (Ctrl+R), then:

| Setting | Value |
|---|---|
| Expert | ORB_US500 |
| Symbol | US500 |
| Timeframe | M5 |
| Date | Custom: as far back as FP Markets has data (aim for 1–2 years) |
| Modelling | **Every tick based on real ticks** (or *1 minute OHLC* if that's not available) |
| Deposit | **100 USD** |
| Leverage | **1:20** |

Click **Start**. Then check:

- **Backtest tab:** total trades, profit factor, max drawdown, expected payoff
- **Journal tab:** why days were skipped (range too small/wide, risk too big for limits, etc.)
- **Graph tab:** the equity curve

### Do it honestly: two runs

1. **Run A (tuning period):** the first ~70% of the dates. You may adjust settings here.
2. **Run B (unseen period):** the last ~30%, **with the exact settings from Run A, no changes.**

Only Run B tells you anything about the future. If Run A is great and Run B is bad, the settings are overfit: don't trade it.

| Out-of-sample result (Run B) | Meaning |
|---|---|
| Fewer than ~50 trades | Not enough evidence yet |
| Profit factor below 1.05 | No edge. Don't trade this version |
| 1.05–1.2 | Marginal. Needs more testing |
| 1.2+ on both runs | Promising → paper trade on demo for 6–8 weeks |
| Above 2 | Suspicious. Probably too good to be true |

## 4. Paper trade on the demo account

1. Log into your **demo** account.
2. Open a **US500** chart (any timeframe), then drag **ORB_US500** from Navigator → Expert Advisors onto it.
3. In the window that opens, tick **Allow Algo Trading**, check the Inputs, and click OK.
4. Turn on the **Algo Trading** button in the toolbar (it turns green).
5. Top-left of the chart shows the bot's status, e.g. *"range 7650.25 – 7662.50, waiting for breakout"*.

The bot refuses to run on a real-money account unless `AllowLive` is set to true. That's deliberate.

### When the Mac must be on (Harare time)

| Period | Range forms | Last entry | Bot closes everything |
|---|---|---|---|
| Until 1 Nov 2026 (US summer time) | 15:30–15:45 | 17:30 | 21:55 |
| 1 Nov 2026 – 14 Mar 2027 | 16:30–16:45 | 18:30 | 22:55 |

- Keep the Mac **awake, online, and MT5 open** from the range start until the trade closes.
  (System Settings → Battery/Energy → stop it sleeping while plugged in.)
- If the Mac does sleep mid-trade, the **stop and target are held by the broker**, so your risk stays capped.
  Only the end-of-day close needs the Mac.

## 5. Settings (Inputs tab)

| Input | Default | Meaning |
|---|---|---|
| ORMinutes | 15 | Opening range length |
| TargetR | 1.5 | Target = 1.5 × risk |
| StopAtMid | false | Stop at range midpoint instead of the far side |
| MinRangePts / MaxRangePts | 3 / 30 | Skip days with a tiny or huge range |
| LastEntryNY / FlatNY | 11:30 / 15:55 | Entry cut-off and end-of-day close (New York time) |
| **RiskPercent** | **1.0** | Risk per trade, % of balance ($1 on $100) |
| DailyLossPct / WeeklyLossPct | 2 / 5 | Stop for the day / week after these losses |
| KillSwitchPct | 15 | Stop for good after a 15% drop from peak equity |
| MaxSpreadPts | 1.5 | Ignore signals when the spread is unusually wide |
| ResetKillSwitch | false | Set true once to clear a tripped kill switch |
| AllowLive | false | Must be true to run on real money |
| ServerMinusNY | 7 | FP Markets' server clock is 7 hours ahead of New York |

**Don't loosen the risk settings to make results look better.** That's how overfitting starts.

## 6. What to check on first start

The **Experts** tab (bottom panel) prints a start-up report, for example:

```
ORB bot on US500 | contract size 1.00 | min lot 0.10, step 0.10 | 1.0000 per point per lot | ...
Clock: server is 7 h ahead of New York (09:30 NY = 16:30 server time)
Risk per trade: 1.00% of balance = 1.00.  Smallest trade on a 10-point stop risks 1.00.
```

If you see **"WARNING: at this balance most trades will be SKIPPED"**, the broker's smallest trade size
is too big for 1% of $100. Send Claude a screenshot of that report and we'll adjust.

## 7. Trade journal

Every fill is written to `MQL5/Files/ORB_journal.csv` (File → Open Data Folder).
Send it to Claude for the weekly review.

---

*Not financial advice. A backtest is evidence, not a promise.*
