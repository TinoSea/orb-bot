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
| Signal window (New York) | 09:30-09:57 | **08:00-14:00** (input; your choice, 22 Oct 2026) |
| Flat time | 11:45 | **14:30** (after the last possible 15-minute trade) |
| Prices | CFD bid candles, mid trigger | Futures **last trade** |
| Size | 1% of balance | **$100 risk** = 4 MNQ at the 12.5-point stop, capped at 10 contracts |
| Prop-firm guard | none | Skips or shrinks any trade whose stop-out would come within $50 of the **Maximum Loss Limit floor** |
| Everything else | zones, first try only, 15-second rejection candle, 45-second trigger, 12.5 / 16.25-point bracket, 15-minute cap, 3 trades / 2 losses a day, no Fridays | same |

**Honest note on the window.** The backtests only ever tested 09:30-11:30 (45.1% wins, below the 45.4% break-even
after costs) and its 09:30-10:00 slice (49.1%). 08:00-14:00 has **never been tested**; it adds the pre-market and the
midday, when this rule has no record. It is registered as H-022 in `research/hypotheses.md`, so the forward test
decides. The MT5 H-017 test keeps running unchanged on its own window.

New York 08:00-14:30 is **14:00-20:30 Harare** until 1 Nov 2026, then **15:00-21:30** (US clocks go back).

**FundedNext rules the bot already respects:** flat long before their 3:10 PM Chicago close; bots are allowed on
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
6. **Leave it on** from before 08:00 New York until after 14:30. It builds the day's zones on the first trade after
   midnight New York, so the simplest is to leave NinjaTrader running all week.
7. **Journal:** `Documents\NinjaTrader 8\LK_futures_journal.csv` (every entry, skip, exit and end-of-day balance).
   Send it to Claude once a month.

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
| No-trade dates | e.g. `2026-11-04` | Days you'll request a payout |

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
   `futures/tradovate/journal/LK_futures_journal.csv`. Send Claude the log if anything looks wrong.
5. **Orders on, demo:** set `LK_DRY_RUN=0` (still `LK_ENV=demo`) for a few days.
6. **FundedNext:** only then point it at the FundedNext account (`LK_ENV=live`, `LK_ALLOW_LIVE_ENV=1`, `LK_ACCOUNT=`).

Tests: `python -m pytest futures/tradovate/tests -q`.

---

## Before buying a FundedNext challenge

Run the bot on Sim or the Tradovate demo for a while and look at the journal: does it trade when you expect, do the
zones match what you see on the chart, and is the win rate holding above break-even (about **45%** at 1.3R after
futures costs)? H-022 in `research/hypotheses.md` has the stop rule and verdict for this window.
