# LK_Forward on futures (FundedNext / Tradovate)

The same rules as `mt5/LK_Forward.mq5`, rebuilt for CME futures (Micro Nasdaq, **MNQ**), in two versions:

| Version | File | Runs on | Needs |
|---|---|---|---|
| **NinjaTrader** (start here) | `ninjatrader/LKForward.cs` | NinjaTrader 8 (Windows) | A Windows PC or Windows VPS |
| Tradovate API | `tradovate/lk_tradovate.py` | Python on your Mac | A Tradovate **API key**: ask FundedNext first whether their accounts allow one |

Both versions make **identical** entries on the same prices (checked: `ninjatrader/tests/`).

## What changed from the MT5 bot

| | MT5 `LK_Forward` (H-017) | Futures version |
|---|---|---|
| Signal windows (New York) | 09:30-09:57 | **Asia 18:00-03:00, London 03:00-08:00, New York 08:00-14:00** (input; your choice, 25 Oct 2026; v1.10) |
| Day | New York calendar day | **CME trading day**: 18:00 New York starts the next date's session (Sunday 18:00 = Monday, Thursday 18:00 = Friday) |
| Flat time | 11:45 | **14:30** (after the last possible 15-minute trade; nothing is held from 14:30 until the 18:00 reopen) |
| Prices | CFD bid candles, mid trigger | Futures **last trade** |
| Size | 1% of balance | **$100 risk** = 4 MNQ at the 12.5-point stop, capped at 10 contracts |
| Prop-firm guard | none | Skips or shrinks any trade whose stop-out would come within $50 of the **Maximum Loss Limit floor** |
| Everything else | zones, first try only, 15-second rejection candle, 45-second trigger, 12.5 / 16.25-point bracket, 15-minute cap, 3 trades / 2 losses a day, no Fridays | same, with "day" = trading day: the 3 trades / 2 losses count across Asia, London and New York together, and "earlier-day" zones are those formed before the 18:00 open |

**Honest note on the windows.** The backtests only ever tested 09:30-11:30 (45.1% wins, below the 45.4% break-even
after costs) and its 09:30-10:00 slice (49.1%). Asia and London have **never been tested** with this rule, and the
overnight market is thinner (wider slippage on the stop), so break-even there is probably a little higher. Because the
daily limits are shared, **losses in Asia can stop the bot before New York opens** (two Asia losses = no New York
trades that day). The windows are registered as H-025 in `research/hypotheses.md` (it replaces H-022, which never
started), so the forward test decides, and the journal now has a `session` column to judge each window separately.
The MT5 H-017 test keeps running unchanged on its own window.

To change the windows, edit the input (NinjaTrader *Signal windows*, Tradovate `LK_WINDOWS`), e.g.
`Asia=20:00-00:00,London=02:00-05:00,NY=08:00-14:00` for the narrower classic session hours. A window may cross
midnight but not 18:00.

In Harare time the bot is live from **00:00 to 20:30** until 1 Nov 2026, then **01:00 to 21:30** (US clocks go back):
it has to run through the night, so use a Windows VPS rather than a laptop that sleeps.

**FundedNext rules the bot already respects:** their trading day runs 5:00 PM to 3:10 PM Chicago (18:00 to 16:10
New York), so Asia and London trading are allowed; the bot is flat at 14:30 New York, long before their 3:10 PM close
(no overnight holding); the bot refuses a flat time after 16:10 New York; bots are allowed on
challenge and funded accounts; its trades almost never close within 10 seconds (the micro-scalping rule), because the
target is 16.25 points away.
**Yours to manage:** don't let the bot trade on a day you want to request a payout (put the date in
*No-trade dates*), and trade at least once every 30 days so the account isn't closed for inactivity.

---

## A. NinjaTrader (recommended)

NinjaTrader 8 runs on **Windows only**. On a MacBook the practical options are a Windows VPS (about $20-40 a month,
and the bot keeps running when the Mac sleeps) or Parallels with Windows 11 for Arm.

1. **Install NinjaTrader 8** (ninjatrader.com, free). Log in with your NinjaTrader account.
2. **Connect your FundedNext account:** Connections → Configure → add **Tradovate**, with the login FundedNext sends you.
   If NinjaTrader asks for a license key for live trading, ask FundedNext support for one.
3. **Add the strategy:** New → NinjaScript Editor → right-click *Strategies* → New Strategy → name it **LKForward**
   → finish → select all, delete, paste `ninjatrader/LKForward.cs` → **Compile** (F5). Expect 0 errors.
4. **Practise on Sim first:** Accounts tab → right-click **Sim101** → *Edit account* → set the balance to **25,000**.
5. **Start it:** New → Chart → instrument **MNQ 12-26**, 1 Minute, **Days to load: 15** (the zones need 5 trading days).
   Right-click the chart → Strategies → **LKForward** → Account **Sim101** → keep the defaults → tick **Enabled** → OK.
   The NinjaScript Output window (New → NinjaScript Output) shows `LKForward ... earlier-day zones live`.
6. **Leave it on all week**, from before Sunday 18:00 New York. It builds each trading day's zones on the first trade
   after the 18:00 reopen.
7. **Journal:** `Documents\NinjaTrader 8\LK_futures_journal_v110.csv` (every entry, skip, exit and end-of-day balance,
   with the trading day and session). Send it to Claude once a month. The old `LK_futures_journal.csv` is left as it was.

**On the FundedNext account** (only after Sim looks right): same steps, choose the FundedNext account, and set
**Allow non-Sim account = true** (the bot refuses any non-Sim account without it). Check these inputs:

| Input | Rapid / Legacy 25K | Notes |
|---|---|---|
| Start balance | 25000 | |
| Maximum Loss Limit | 1000 | |
| Max contracts | 10 | FundedNext's 25K limit in micros; check yours |
| Risk per trade ($) | 100 | 4 MNQ. The guard reduces it near the floor |
| Payout taken | false → **true after your first payout** | FundedNext then resets the floor to the start balance |
| Floor override | 0 | If the bot's floor ever differs from the dashboard, type the dashboard's floor here |
| No-trade trading days | e.g. `2026-11-04` | Days you'll request a payout. A trading day starts 18:00 the evening before |

The bot keeps its own record of the highest end-of-day balance (`Documents\NinjaTrader 8\LKForward_<account>_state.txt`)
to follow the trailing loss limit. Compare its "floor" in the journal with the FundedNext dashboard for the first week.

**Contract roll:** MNQ December (12-26) expires 18 Dec 2026. Around **10 December**, stop the strategy and restart it
on **MNQ 03-27**.

---

## B. Tradovate API (Python on your Mac)

This version has been tested offline only (rules, sizing, guard, settings), **not yet against Tradovate's servers**.
It starts in dry-run: it reads live prices and paper-trades its own signals, sending no orders.

1. **API key:** Tradovate's API needs a *cid* and *secret*. Ask FundedNext support whether their accounts can use one.
   If not, use NinjaTrader.
2. **Install:** in Terminal, `cd ~/orb-bot && source .venv/bin/activate && pip install requests websocket-client`
3. **Settings:** copy `futures/tradovate/lk.env.example` to `futures/tradovate/lk.env` and fill in the login and key.
   `lk.env` holds your password; git ignores it. Never send it to anyone (Claude included).
4. **Dry run on the demo server:** `python futures/tradovate/lk_tradovate.py`. Leave it running through a session.
   The log should show the zones, any signals and paper trades; the journal is
   `futures/tradovate/journal/LK_futures_journal_v110.csv`. Send Claude the log if anything looks wrong.
5. **Orders on, demo:** set `LK_DRY_RUN=0` (still `LK_ENV=demo`) for a few days.
6. **FundedNext:** only then point it at the FundedNext account (`LK_ENV=live`, `LK_ALLOW_LIVE_ENV=1`, `LK_ACCOUNT=`).

Tests: `python -m pytest futures/tradovate/tests -q`.

---

## Before buying a FundedNext challenge

Run the bot on Sim or the Tradovate demo for a while and look at the journal: does it trade when you expect, do the
zones match what you see on the chart, and is the win rate holding above break-even (about **45%** at 1.3R after
futures costs), in each session? H-025 in `research/hypotheses.md` has the stop rule and verdict for these windows.

## Changes in v1.10 (25 Oct 2026)

- Signal windows Asia / London / New York (inputs), CME trading day from 18:00 New York, `session` and `trading_day`
  columns in the journal (new file name, `_v110`).
- Flat time now means 14:30 until the 18:00 reopen only. (The old check, "clock time after 14:30", was fine for an
  08:00-14:00 window but would have closed every Asia trade the moment it opened.)
- Fixed (NinjaTrader): a stop or target filled in several pieces made several trade records, and only the last piece's
  profit was journalled; the exit now adds them all up.
- Fixed (Tradovate, orders on): the trade result was read from the cash balance the instant the position went flat; if
  Tradovate posted the cash a moment later, a loss read as $0 and did not count towards the 2-loss limit. It now waits
  up to 5 s and otherwise estimates the result from the last price.
- Fixed (Tradovate): the zone history request could wait a needless 30 s when the end-of-history marker arrived early,
  and the live part of each chart request was never cancelled.
