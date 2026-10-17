# Bots for MetaTrader 5

| Bot | Hypothesis | Market | Chart to test on |
|---|---|---|---|
| `ORB_US500.mq5` | H-001 opening-range breakout | US500 | M5 |
| `MS_Gold.mq5` | H-002 4H market structure + 1H pullback | XAUUSD (gold) | **H1** |

Both share the same safety system: % risk sizing, daily/weekly loss limits, kill switch,
refuses real-money accounts unless `AllowLive` is on, phone alerts and a CSV journal.

## H-002 step 1: export the raw data (ExportData script, ~10–30 minutes)

1. **Allow full history:** MT5 → **Tools → Options → Charts → Max bars in chart → Unlimited** → OK, then quit and reopen MT5.
2. **Install the script:** MetaEditor → **File → New → Script** (not Expert Advisor) → name **ExportData** → Next/Finish →
   select all, delete, paste `mt5/ExportData.mq5` → **Compile**.
3. **Run it:** in MT5's **Navigator → Scripts**, drag **ExportData** onto any chart → keep the defaults → OK.
   Leave MT5 alone until the "Export finished" alert appears. **Don't start it again while it runs**:
   a second start stops the first (error 4022 in the log). If it does get stopped, just run it again:
   v1.10 skips markets already finished (they get a `.done` file) and appends to `export_log.txt`.
4. **Collect the files:** in Finder press **Cmd + Shift + G** and paste:
   ```
   ~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Files/orb_export
   ```
   Right-click the `orb_export` folder → **Compress** → attach the zip to the chat
   (expect very roughly 50–150 MB zipped; if it's too large, send `specs.csv`, `all_symbols.csv`,
   `export_log.txt` and `XAUUSD_M1.csv` first).

## H-002 step 1b: measure real spreads (ExportSpreads script, ~10–20 minutes)

MT5's bar history stores a spread that is usually the *lowest* in each bar, which understates costs.
This script reads the real first ticks at the start of every hour for the last 90 days.

1. MetaEditor → **File → New → Script** → name **ExportSpreads** → paste `mt5/ExportSpreads.mq5` → **Compile**.
2. MT5 **Navigator → Scripts → ExportSpreads** → double-click → OK. Don't start it twice; wait for the alert.
3. Attach `spread_samples.csv` and `spread_log.txt` from the same `orb_export` folder.

## H-002 step 2: Gate 0 — MT5 vs Python on gold

1. Delete any old `MS_journal.csv` in `…/MetaTrader 5/Tester/Agent-127.0.0.1-3000/MQL5/Files/`.
2. Run the MS_Gold in-sample test below with **Modelling: 1 minute OHLC**.
3. Attach the new `MS_journal.csv`. Claude runs `research/compare_trades.py` against the Python replica.
   Pass = ≥95% of trades identical. No result is interpreted until this passes.

## H-002 quick start: MS_Gold

1. **Install:** MetaEditor → File → New → Expert Advisor → name it **MS_Gold** → Next/Finish →
   select all, delete, paste the code from `mt5/MS_Gold.mq5` → **Compile** (expect 0 errors).
2. **Add gold:** Market Watch → "+ click to add…" → type **XAUUSD** (FP Markets may add a suffix, e.g. `XAUUSD.r`; use whatever appears).
3. **Strategy Tester (in-sample run only):**

| Setting | Value |
|---|---|
| Expert | MS_Gold |
| Symbol | **XAUUSD.r** (FP Markets' gold) |
| Timeframe | **H1** |
| Date | **Custom period: 2023.01.01 → 2025.06.30** (the EA also stops itself at 2025.07.01) |
| Modelling | 1 minute OHLC |
| Deposit / Leverage | **5000 USD**, 1:20 (research size so 1% risk is possible on gold) |
| Inputs | **Leave all defaults** (v1.12; the small-account inputs default to off, so Gate 0 is unchanged). In the tester it automatically ignores the loss limits and kill switch, and stops at 2025.07.01 (out-of-sample lock). `InpRiskPercent` must stay **1.0**. Session: zone **NEW_YORK**, **08:00–17:00** (other markets: use the zone and hours in `research/h002_markets.csv`; BTC: NEW_YORK 00:00–24:00, `InpMode24x7` = false, because FP Markets' BTC is closed at weekends) |

4. Send Claude the **Backtest** tab and the **Journal** (select all → copy → paste into a text file).

The out-of-sample period (July 2025 → today) is run **once**, after the in-sample review.

### Small account (v1.12, H-002 amendment 16) — demo only for now

At $200 the 1% rule can't trade gold: the smallest position (0.01 lot = 1 oz) risks about $21 at today's
price, ~10% of the account. `research/small_account.md` shows why the bot will not simply "always trade the
smallest lot". For a **demo** rehearsal at $200:

| Input | Value | What it does |
|---|---|---|
| `InpMinLotMaxRiskPct` | **5** | Trades 0.01 lot when it risks ≤ 5% of the balance; skips wider stops. The bot refuses values above 5. |
| `InpMaxMarginPct` | **50** | Skips a trade whose margin would use more than half the free margin. |

The bot also skips any trade where, at its stop, equity would be below the broker's stop-out level, so the
broker can't close it before the stop does. **Check your leverage first** (Navigator → right-click the account
→ Details): 1 oz of gold at ~$4,190 needs about $210 margin at 1:20, $42 at 1:100, $8 at 1:500.

The journal (`MS_journal.csv`) now records, for every entry, the planned risk in money and %, the stop
distance, the spread at entry, the margin, and whether the smallest-lot rule was used. That is what the weekly
review compares against the backtest.

### FTMO $10,000 2-Step (v1.13, H-002 amendment 17) — after Gate 0 and the out-of-sample pass only

Order the **Swing** account type (no news-time restrictions on stops and targets). Settings on the FTMO MT5 account:

| Input | Value | Why |
|---|---|---|
| `InpRiskPercent` | per `research/ftmo_10k.md` (1.0–1.5) | Decided by the pre-registered rule, not by feel |
| `InpFtmoInitial` | **10000** | Turns on the prop-firm guard |
| `InpFtmoDailyPct` / `InpFtmoMaxLossPct` | **5** / **10** | FTMO's 2-Step limits |
| `InpFtmoGapAllowance` | **1.5** | A trade is only opened (or is shrunk) if 1.5 × its stop still fits inside both limits |
| `InpServerMinusCET` | **1** (check) | FTMO's day resets at Prague midnight; compare MT5's Market Watch clock with Prague time |
| `InpFridayCutoffNY` | **15:00** | FTMO's gap rule: no new trades within 2 hours of gold's weekend close |
| `InpDailyLossPct` / `InpWeeklyLossPct` / `InpKillSwitchPct` | 4 / 100 / 100 | FTMO's limits and the guard replace the weekly cap and kill switch |
| `InpAllowLive` | false | FTMO accounts usually show as demo in MT5. If the bot refuses to start because it sees a REAL account, set true |

The guard keeps a 0.5% safety margin above both limits and sizes every trade so that 1.5 × its stop cannot reach that margin. Near the daily line it closes everything and pauses until Prague midnight; near the static maximum-loss floor it closes everything and stops for good (v1.14), because the floor never moves and the challenge is effectively over.
The Friday cutoff can be tested exactly: `python research/ms_replica.py ... --friday-cutoff 15:00`.

Exact replica of the small-account rules on the raw bars (instead of the quick trade-list replay):
`python research/ms_replica.py --data data/export --label XAUUSD --tf M1 --from 2023-01-01 --to 2025-06-30 --deposit 200 --min-lot-cap 5 --leverage 100 --max-margin-pct 50 --variant SA-P3 --no-log`

---

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

### Phone alerts (one-time setup, 2 minutes)

The bot messages the **MetaTrader 5 app on your phone**, so you don't need to watch the chart.

1. On your phone, install **MetaTrader 5** (App Store / Play Store) and open it.
2. Find your **MetaQuotes ID**: Settings → Messages (iPhone) or Menu → Messages (Android). It's a short code like `1A2B3C4D`.
3. In **desktop** MT5: **Tools → Options → Notifications** (on Mac this may be under the *MetaTrader 5* menu → *Settings*).
   Tick **Enable Push Notifications**, paste your MetaQuotes ID, and click **Test**. Your phone should buzz.
4. Done. Alerts arrive while desktop MT5 is open and the bot is running. (None are sent during backtests.)

What you'll get:

| When | Example message |
|---|---|
| Bot starts | `Bot started on a demo account. Risk 1.00% = 1.00 per trade.` |
| Range is set | `Range set 7650.25 - 7662.50 (12.25 pts). Watching for a breakout until 11:30 NY.` |
| Day skipped | `No trade today - skipped: range too wide (34.50 pts)` |
| Trade entered | `ENTERED LONG 0.10 @ 7665.20 \| stop 7650.25 \| target 7687.60 \| risk 1.00` |
| Trade closed | `TARGET hit: +1.48R (+1.48). Plan followed.` or `STOPPED out: -1.02R (-1.02). Plan followed - a good trade, even as a loss.` |
| No breakout | `No breakout by 11:30 NY. No trade today - that's the plan working.` |
| Limits | `Daily loss limit reached…`, `KILL SWITCH: …` |
| End of day | `Day done: 1 trade(s), +1.48 today \| week +2.10 over 3 trade(s) \| balance 102.10` |

If you ever close a trade by hand, you'll get `Closed MANUALLY … Note it in your weekly review.` That's deliberate.

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
| PushNotify | true | Send alerts to the MetaTrader app on your phone |
| DailySummary | true | Send an end-of-day summary on weekdays |

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
