//+------------------------------------------------------------------+
//|                                                     MS_Gold.mq5 |
//|  H-002: higher-timeframe market structure + pullback entries.    |
//|  A mechanical version of the "market structure / ICC" approach:  |
//|  4H trend turn (higher low + break of the last swing high),      |
//|  then buy the 1H pullback toward the broken level. Mirror for    |
//|  shorts. Built for XAUUSD; works on any symbol.                  |
//|  Part of github.com/TinoSea/orb-bot.  Not financial advice.      |
//+------------------------------------------------------------------+
//
//  Rules (see research/hypotheses.md, H-002):
//    Swings (4H): 5-bar fractals (InpSwingN = 2 bars each side), confirmed only.
//    Bullish setup: latest swing low > previous swing low (higher low) AND the last
//      closed 4H bar closes above the most recent swing high (fresh break) -> level.
//    Bearish setup: latest swing high < previous swing high AND 4H close below the
//      most recent swing low.
//    Pullback (1H): price trades back to within InpZoneATR x ATR(4H) of the level.
//    Entry (1H): after the pullback, first 1H close beyond the previous 1H bar's
//      extreme and beyond the level, inside the market's main exchange session
//      (InpSessionZone + local times), or any time in 24/7 mode (crypto).
//    Cancel: 4H close InpFailATR x ATR(4H) back through the level, or no entry
//      within InpSetupExpiry 1H bars.
//    Stop: pullback extreme +/- InpStopBufATR x ATR(1H).
//    Target: nearest earlier 4H swing level giving >= InpMinRR; else InpDefaultR.
//    Exits: stop, target, InpMaxHoldBars, Friday close.
//    Risk engine identical to ORB_US500: % risk sizing, daily/weekly loss limits,
//    persistent kill switch, live-account guard, phone alerts, CSV journal.
//
#property copyright   "orb-bot"
#property version     "1.13"
#property description "H-002: 4H market structure + 1H pullback entries (built for XAUUSD)."
#property description "Hard limits: % risk per trade, daily/weekly loss caps, kill switch."

#include <Trade\Trade.mqh>

//--- session time zones (each market trades its own main exchange hours)
enum SessionZone
  {
   ZONE_NEW_YORK  = 0,   // New York (US indices, metals, energy, US bonds, agriculture)
   ZONE_LONDON    = 1,   // London (FTSE 100, currencies)
   ZONE_FRANKFURT = 2,   // Frankfurt (DAX, Bund)
   ZONE_TOKYO     = 3    // Tokyo (Nikkei)
  };

//--- inputs ---------------------------------------------------------
input group "Structure (higher timeframe)"
input ENUM_TIMEFRAMES InpStructTF = PERIOD_H4; // Structure timeframe
input int    InpSwingN         = 2;        // Swing size: bars each side (2 = 5-bar fractal)
input int    InpSwingLookback  = 300;      // Structure bars scanned for swings

input group "Entry (lower timeframe)"
input ENUM_TIMEFRAMES InpEntryTF = PERIOD_H1; // Entry timeframe
input double InpZoneATR        = 0.3;      // Pullback must come within this x ATR(structure) of the level
input double InpFailATR        = 0.5;      // Cancel if structure closes this x ATR back through the level
input int    InpSetupExpiry    = 30;       // Cancel setup after this many entry bars without entry
input double InpStopBufATR     = 0.1;      // Stop buffer beyond the pullback extreme, x ATR(entry)
input double InpMinRR          = 1.0;      // Target must be at least this many R away
input double InpDefaultR       = 2.0;      // Target (in R) when no swing level qualifies
input int    InpMaxHoldBars    = 120;      // Close after this many entry bars (120 x 1H = 5 days)
input SessionZone InpSessionZone = ZONE_NEW_YORK; // Time zone of the session times below
input string InpSessionStart   = "08:00";  // Entries allowed from (local time of that zone)
input string InpSessionEnd     = "17:00";  // Entries allowed until (local time of that zone)
input bool   InpMode24x7       = false;    // Crypto mode: entries any time incl. weekends, no Friday close
input bool   InpCloseFriday    = true;     // Close everything on Friday afternoon (no weekend gaps)
input string InpFridayCloseNY  = "16:30";  // Friday close time (New York)
input bool   InpAllowLong      = true;     // Allow long trades
input bool   InpAllowShort     = true;     // Allow short trades

input group "Risk (hard limits)"
input double InpRiskPercent     = 1.0;     // Risk per trade, % of balance
input double InpDailyLossPct    = 2.0;     // Stop for the day after losing this % of balance
input double InpWeeklyLossPct   = 5.0;     // Stop for the week after losing this % of balance
input double InpKillSwitchPct   = 15.0;    // Stop for good after this % drawdown from peak equity
input double InpMaxSpreadFrac   = 0.15;    // Skip entry if spread is more than this fraction of the stop
input double InpMinLotMaxRiskPct = 0.0;    // Small account: trade the smallest lot when 1% is below it, if it risks <= this % (0 = never, max 5)
input double InpMaxMarginPct    = 100.0;   // Skip a trade whose margin would use more than this % of free margin (small account: 50)
input bool   InpResetKillSwitch = false;   // Set true ONCE to clear a tripped kill switch
input bool   InpAllowLive       = false;   // Must be true to run on a real-money account

input group "Prop firm (FTMO) - off while FtmoInitial = 0"
input double InpFtmoInitial      = 0.0;    // Prop account's initial capital (e.g. 10000). 0 = off
input double InpFtmoDailyPct     = 5.0;    // Firm's max daily loss, % of initial, below the balance at the firm's midnight
input double InpFtmoMaxLossPct   = 10.0;   // Firm's max loss, % of initial (static floor)
input double InpFtmoGapAllowance = 1.5;    // A new trade's full stop x this must fit inside both limits
input int    InpServerMinusCET   = 1;      // Server time minus Prague time, hours (FTMO's day resets at Prague midnight)
input string InpFridayCutoffNY   = "";     // No new entries on Friday from this NY time ("15:00" for FTMO gold). Empty = off

input group "Research (Strategy Tester only - ignored on demo/live)"
input bool     InpTesterNoLimits = true;                 // Tester: ignore loss limits + kill switch (measure the strategy)
input datetime InpTesterStopAt   = D'2025.07.01 00:00';  // Tester: stop here (out-of-sample lock). 1970.01.01 = off, for the ONE out-of-sample run

input group "Clock"
input int    InpServerMinusNY   = 7;       // Server time minus New York time, hours (FP Markets = 7)
input bool   InpAutoDetectClock = true;    // Live/demo only: detect from the broker clock

input group "Other"
input long   InpMagic           = 202611;  // Magic number (identifies this bot's trades)
input bool   InpWriteJournal    = true;    // Write every fill to MQL5/Files/MS_journal.csv
input bool   InpPushNotify      = true;    // Send alerts to the MetaTrader app on your phone
input bool   InpDailySummary    = true;    // Send a short summary at the end of the NY session

//--- types and state ------------------------------------------------
struct Swing
  {
   datetime          t;
   double            p;
  };

CTrade   trade;
int      g_offsetHrs     = 7;
int      g_dayKey        = -1;
datetime g_dayStartSrv   = 0;
datetime g_weekStartSrv  = 0;
datetime g_lastEntryBar  = 0;
datetime g_lastStructBar = 0;
int      g_sessStart     = 0;
int      g_sessEnd       = 0;
int      g_friClose      = 0;
string   g_gvPeak        = "";
string   g_gvKill        = "";
bool     g_killLogged    = false;
bool     g_summarySent   = false;
bool     g_dayBlocked    = false;
double   g_limDaily      = 2.0;    // effective limits (research mode in the tester sets 100)
double   g_limWeekly     = 5.0;
double   g_limKill       = 15.0;
bool     g_lockDone      = false;
string   g_status        = "";
double   g_entryRisk     = 0.0;
// filled at entry, written to the journal on the IN deal (live vs backtest reconciliation)
double   g_jRiskPct      = 0.0;
double   g_jStop         = 0.0;
double   g_jSpread       = 0.0;
double   g_jMargin       = 0.0;
bool     g_jMinLot       = false;
// prop-firm guard
int      g_cetDayKey     = -1;
double   g_cetMidBal     = 0.0;    // balance at the firm's last midnight (Prague time)
bool     g_propBlocked   = false;  // limit came close today: no new trades until the firm's next day
int      g_friCutoff     = -1;     // minute of day (NY) after which no Friday entries; -1 = off
int      g_atrStruct     = INVALID_HANDLE;
int      g_atrEntry      = INVALID_HANDLE;
// active setup
int      g_setupDir      = 0;      // +1 long, -1 short, 0 none
double   g_level         = 0.0;
int      g_setupBars     = 0;
bool     g_touched       = false;
double   g_pbExtreme     = 0.0;

//+------------------------------------------------------------------+
//| Phone alerts                                                      |
//+------------------------------------------------------------------+
void Notify(const string msg)
  {
   Print(msg);
   if(!InpPushNotify || MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      return;
   if(!TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED))
      return;
   string text = "MS " + _Symbol + ": " + msg;
   if(StringLen(text) > 255)
      text = StringSubstr(text, 0, 255);
   if(!SendNotification(text))
      PrintFormat("Phone alert not sent (error %d)", GetLastError());
  }

//+------------------------------------------------------------------+
//| Time helpers (same as ORB_US500)                                  |
//+------------------------------------------------------------------+
int ParseHHMM(const string s)
  {
   string parts[];
   if(StringSplit(s, StringGetCharacter(":", 0), parts) != 2)
      return -1;
   return (int)StringToInteger(parts[0]) * 60 + (int)StringToInteger(parts[1]);
  }

int MinuteOfDay(const datetime t)
  {
   MqlDateTime s;
   TimeToStruct(t, s);
   return s.hour * 60 + s.min;
  }

int DayKey(const datetime t)
  {
   MqlDateTime s;
   TimeToStruct(t, s);
   return s.year * 10000 + s.mon * 100 + s.day;
  }

int DayOfWeek(const datetime t)
  {
   MqlDateTime s;
   TimeToStruct(t, s);
   return s.day_of_week;
  }

datetime ToNY(const datetime srv)
  {
   return (datetime)((long)srv - (long)g_offsetHrs * 3600);
  }

datetime NthSunday(const int year, const int mon, const int n)
  {
   MqlDateTime s;
   ZeroMemory(s);
   s.year = year;
   s.mon  = mon;
   s.day  = 1;
   datetime first = StructToTime(s);
   MqlDateTime f;
   TimeToStruct(first, f);
   int firstSunday = 1 + (7 - f.day_of_week) % 7;
   s.day = firstSunday + 7 * (n - 1);
   return StructToTime(s);
  }

bool IsUSDST(const datetime gmt)
  {
   MqlDateTime s;
   TimeToStruct(gmt, s);
   long start = (long)NthSunday(s.year, 3, 2) + 7 * 3600;
   long end   = (long)NthSunday(s.year, 11, 1) + 6 * 3600;
   return ((long)gmt >= start && (long)gmt < end);
  }

void UpdateClock()
  {
   g_offsetHrs = InpServerMinusNY;
   if(MQLInfoInteger(MQL_TESTER) || !InpAutoDetectClock)
      return;
   datetime gmt = TimeGMT();
   int srvGmt = (int)MathRound((double)((long)TimeTradeServer() - (long)gmt) / 3600.0);
   int nyGmt  = IsUSDST(gmt) ? -4 : -5;
   int det    = srvGmt - nyGmt;
   if(det < 0 || det > 14)
     {
      PrintFormat("Clock: detection looked wrong (%d h). Keeping input value %d h.", det, InpServerMinusNY);
      return;
     }
   if(det != InpServerMinusNY)
      PrintFormat("Clock: broker server is %d h ahead of New York (input says %d). Using %d.",
                  det, InpServerMinusNY, det);
   g_offsetHrs = det;
  }

void NewDay(const datetime nyNow)
  {
   g_dayKey = DayKey(nyNow);
   MqlDateTime s;
   TimeToStruct(nyNow, s);
   long nyMidnight   = (long)nyNow - (s.hour * 3600 + s.min * 60 + s.sec);
   int  daysSinceMon = (s.day_of_week + 6) % 7;
   g_dayStartSrv  = (datetime)(nyMidnight + (long)g_offsetHrs * 3600);
   g_weekStartSrv = (datetime)((long)g_dayStartSrv - (long)daysSinceMon * 86400);
   g_killLogged   = false;
   g_summarySent  = false;
   g_dayBlocked   = false;
  }

// Last Sunday of a month (00:00 of that day)
datetime LastSunday(const int year, const int mon)
  {
   MqlDateTime s;
   ZeroMemory(s);
   s.year = year;
   s.mon  = mon;
   s.day  = 31;                       // only used for March and October
   datetime d = StructToTime(s);
   MqlDateTime f;
   TimeToStruct(d, f);
   return (datetime)((long)d - (long)f.day_of_week * 86400);
  }

// EU/UK summer time: last Sunday of March 01:00 UTC -> last Sunday of October 01:00 UTC
bool IsEUDST(const datetime gmt)
  {
   MqlDateTime s;
   TimeToStruct(gmt, s);
   long start = (long)LastSunday(s.year, 3) + 3600;
   long end   = (long)LastSunday(s.year, 10) + 3600;
   return ((long)gmt >= start && (long)gmt < end);
  }

// Local time of the session zone, from New York time
datetime ZoneTime(const datetime nyNow)
  {
   if(InpSessionZone == ZONE_NEW_YORK)
      return nyNow;
   long approxGmt = (long)nyNow + 5 * 3600;
   long gmt = (long)nyNow + (IsUSDST((datetime)approxGmt) ? 4 : 5) * 3600;
   if(InpSessionZone == ZONE_LONDON)
      return (datetime)(gmt + (IsEUDST((datetime)gmt) ? 3600 : 0));
   if(InpSessionZone == ZONE_FRANKFURT)
      return (datetime)(gmt + (IsEUDST((datetime)gmt) ? 7200 : 3600));
   return (datetime)(gmt + 9 * 3600);                    // Tokyo, no summer time
  }

bool InSession(const datetime nyNow)
  {
   if(InpMode24x7)
      return true;
   if(InpCloseFriday && DayOfWeek(nyNow) == 5 && MinuteOfDay(nyNow) >= g_friClose)
      return false;
   if(g_friCutoff >= 0 && DayOfWeek(nyNow) == 5 && MinuteOfDay(nyNow) >= g_friCutoff)
      return false;   // prop-firm gap rule: no new trades shortly before the weekend close
   datetime local = ZoneTime(nyNow);
   int dow = DayOfWeek(local);
   if(dow < 1 || dow > 5)
      return false;
   int m = MinuteOfDay(local);
   return (m >= g_sessStart && m < g_sessEnd);
  }

//+------------------------------------------------------------------+
//| Position and history helpers (same as ORB_US500)                  |
//+------------------------------------------------------------------+
bool IsMine()
  {
   return (PositionGetInteger(POSITION_MAGIC) == InpMagic &&
           PositionGetString(POSITION_SYMBOL) == _Symbol);
  }

int MyPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0)
         continue;
      if(IsMine())
         n++;
     }
   return n;
  }

double FloatingPnL()
  {
   double p = 0.0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetTicket(i) == 0)
         continue;
      if(IsMine())
         p += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
     }
   return p;
  }

void CloseAll(const string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !IsMine())
         continue;
      if(trade.PositionClose(t))
         PrintFormat("Closed position #%I64u (%s)", t, reason);
      else
         PrintFormat("FAILED to close #%I64u (%s): %u %s", t, reason,
                     trade.ResultRetcode(), trade.ResultRetcodeDescription());
     }
  }

// Time stop: close positions held for longer than InpMaxHoldBars entry bars.
void TimeStop()
  {
   long maxSecs = (long)InpMaxHoldBars * PeriodSeconds(InpEntryTF);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !IsMine())
         continue;
      long held = (long)TimeCurrent() - (long)PositionGetInteger(POSITION_TIME);
      if(held >= maxSecs)
        {
         if(trade.PositionClose(t))
            PrintFormat("Closed position #%I64u (time stop after %d bars)", t, InpMaxHoldBars);
        }
     }
  }

void ClosedStats(const datetime from, double &pnl, int &entries)
  {
   pnl = 0.0;
   entries = 0;
   if(!HistorySelect(from, TimeCurrent() + 86400))
      return;
   int n = HistoryDealsTotal();
   long ids[];
   ArrayResize(ids, 0);
   for(int i = 0; i < n; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0)
         continue;
      if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol)
         continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic)
         continue;
      if(HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
        {
         entries++;
         int k = ArraySize(ids);
         ArrayResize(ids, k + 1);
         ids[k] = HistoryDealGetInteger(d, DEAL_POSITION_ID);
        }
     }
   for(int i = 0; i < n; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0)
         continue;
      long pid = HistoryDealGetInteger(d, DEAL_POSITION_ID);
      bool ours = false;
      for(int k = 0; k < ArraySize(ids); k++)
         if(ids[k] == pid)
           {
            ours = true;
            break;
           }
      if(!ours)
         continue;
      pnl += HistoryDealGetDouble(d, DEAL_PROFIT)
             + HistoryDealGetDouble(d, DEAL_COMMISSION)
             + HistoryDealGetDouble(d, DEAL_SWAP);
     }
  }

//+------------------------------------------------------------------+
//| Risk engine (same as ORB_US500)                                   |
//+------------------------------------------------------------------+
bool KillSwitch()
  {
   if(GlobalVariableCheck(g_gvKill))
     {
      if(MyPositions() > 0)
         CloseAll("kill switch");
      if(!g_killLogged)
        {
         Print("KILL SWITCH is active - no trading. Review what happened, then re-attach the bot with ResetKillSwitch = true.");
         g_killLogged = true;
        }
      g_status = "KILL SWITCH ACTIVE";
      return true;
     }
   double eq   = AccountInfoDouble(ACCOUNT_EQUITY);
   double peak = GlobalVariableGet(g_gvPeak);
   if(eq > peak)
     {
      GlobalVariableSet(g_gvPeak, eq);
      return false;
     }
   if(peak > 0 && eq <= peak * (1.0 - g_limKill / 100.0))
     {
      GlobalVariableSet(g_gvKill, 1.0);
      CloseAll("kill switch");
      g_setupDir = 0;
      string msg = StringFormat("KILL SWITCH: equity %.2f is %.1f%% below peak %.2f. Bot stopped until you review and reset it.",
                                eq, 100.0 * (1.0 - eq / peak), peak);
      Notify(msg);
      if(!MQLInfoInteger(MQL_TESTER))
         Alert(msg);
      g_killLogged = true;
      g_status = "KILL SWITCH ACTIVE";
      return true;
     }
   return false;
  }

bool LossLimitHit()
  {
   if(g_dayBlocked)
      return true;
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double fl  = FloatingPnL();
   double dayPnl, weekPnl;
   int    e;
   ClosedStats(g_dayStartSrv, dayPnl, e);
   if(dayPnl + fl <= -bal * g_limDaily / 100.0)
     {
      Notify(StringFormat("Daily loss limit reached (%.2f). No more trades today.", dayPnl + fl));
      g_dayBlocked = true;
      return true;
     }
   ClosedStats(g_weekStartSrv, weekPnl, e);
   if(weekPnl + fl <= -bal * g_limWeekly / 100.0)
     {
      Notify(StringFormat("Weekly loss limit reached (%.2f). No more trades this week.", weekPnl + fl));
      g_dayBlocked = true;
      return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Market data helpers                                               |
//+------------------------------------------------------------------+
double ATRValue(const int handle)
  {
   double b[];
   if(handle == INVALID_HANDLE || CopyBuffer(handle, 0, 1, 1, b) != 1)
      return 0.0;
   return b[0];
  }

double NormPrice(double p)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts > 0)
      p = MathRound(p / ts) * ts;
   return NormalizeDouble(p, _Digits);
  }

double ValuePerPoint()   // account currency per 1.0 price move per 1 lot
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(ts <= 0 || tv <= 0)
      return 0.0;
   return tv / ts;
  }

// Confirmed swing highs and lows on the structure timeframe, oldest first.
// A swing high is strictly higher than the InpSwingN older bars and at least as
// high as the InpSwingN newer bars (so equal highs are counted once).
bool GetSwings(Swing &highs[], Swing &lows[])
  {
   ArrayResize(highs, 0);
   ArrayResize(lows, 0);
   double   h[], l[];
   datetime t[];
   ArraySetAsSeries(h, true);
   ArraySetAsSeries(l, true);
   ArraySetAsSeries(t, true);
   int got = CopyHigh(_Symbol, InpStructTF, 1, InpSwingLookback, h);
   if(got < 2 * InpSwingN + 3)
      return false;
   if(CopyLow(_Symbol, InpStructTF, 1, got, l) != got)
      return false;
   if(CopyTime(_Symbol, InpStructTF, 1, got, t) != got)
      return false;
   for(int i = got - 1 - InpSwingN; i >= InpSwingN; i--)
     {
      bool isH = true, isL = true;
      for(int k = 1; k <= InpSwingN; k++)
        {
         if(h[i] <= h[i + k] || h[i] < h[i - k])
            isH = false;
         if(l[i] >= l[i + k] || l[i] > l[i - k])
            isL = false;
        }
      if(isH)
        {
         int s = ArraySize(highs);
         ArrayResize(highs, s + 1);
         highs[s].t = t[i];
         highs[s].p = h[i];
        }
      if(isL)
        {
         int s = ArraySize(lows);
         ArrayResize(lows, s + 1);
         lows[s].t = t[i];
         lows[s].p = l[i];
        }
     }
   return (ArraySize(highs) >= 2 && ArraySize(lows) >= 2);
  }

//+------------------------------------------------------------------+
//| Strategy                                                          |
//+------------------------------------------------------------------+
void CancelSetup(const string why)
  {
   if(g_setupDir == 0)
      return;
   PrintFormat("Setup cancelled (%s): %s level %.2f", why, (g_setupDir > 0) ? "long" : "short", g_level);
   g_setupDir = 0;
   g_touched  = false;
   g_status   = "watching 4H structure (" + why + ")";
  }

// Called once per new structure bar while flat and without a setup.
void CheckForSetup()
  {
   datetime sb = iTime(_Symbol, InpStructTF, 1);
   if(sb == 0 || sb == g_lastStructBar)
      return;
   g_lastStructBar = sb;

   Swing hs[], ls[];
   if(!GetSwings(hs, ls))
      return;
   int nh = ArraySize(hs), nl = ArraySize(ls);
   double lastH = hs[nh - 1].p, prevH = hs[nh - 2].p;
   double lastL = ls[nl - 1].p, prevL = ls[nl - 2].p;
   double c1 = iClose(_Symbol, InpStructTF, 1);
   double c2 = iClose(_Symbol, InpStructTF, 2);

   if(InpAllowLong && lastL > prevL && c1 > lastH && c2 <= lastH)
     {
      g_setupDir = 1;
      g_level    = lastH;
     }
   else
      if(InpAllowShort && lastH < prevH && c1 < lastL && c2 >= lastL)
        {
         g_setupDir = -1;
         g_level    = lastL;
        }
   if(g_setupDir != 0)
     {
      g_setupBars = 0;
      g_touched   = false;
      g_pbExtreme = 0.0;
      Notify(StringFormat("4H %s break of %.2f (after a %s). Watching for a pullback to enter.",
                          (g_setupDir > 0) ? "bullish" : "bearish", g_level,
                          (g_setupDir > 0) ? "higher low" : "lower high"));
      g_status = StringFormat("%s setup: level %.2f, waiting for pullback",
                              (g_setupDir > 0) ? "LONG" : "SHORT", g_level);
     }
   else
      g_status = "watching 4H structure";
  }

double FindTarget(const int dir, const double entry, const double risk)
  {
   Swing hs[], ls[];
   double best = 0.0;
   if(GetSwings(hs, ls))
     {
      if(dir > 0)
        {
         for(int i = 0; i < ArraySize(hs); i++)
            if(hs[i].p >= entry + InpMinRR * risk && (best == 0.0 || hs[i].p < best))
               best = hs[i].p;
        }
      else
        {
         for(int i = 0; i < ArraySize(ls); i++)
            if(ls[i].p <= entry - InpMinRR * risk && (best == 0.0 || ls[i].p > best))
               best = ls[i].p;
        }
     }
   if(best > 0.0)
      return best;
   return entry + dir * InpDefaultR * risk;
  }

void TryEnter(const int dir, const double atrE)
  {
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk))
      return;
   double entry = (dir > 0) ? tk.ask : tk.bid;
   double stop  = (dir > 0) ? g_pbExtreme - InpStopBufATR * atrE
                            : g_pbExtreme + InpStopBufATR * atrE;
   double risk  = (entry - stop) * dir;
   if(risk <= 0)
     {
      CancelSetup("price already through the stop");
      return;
     }
   double spread = tk.ask - tk.bid;
   if(spread > InpMaxSpreadFrac * risk)
     {
      PrintFormat("Entry skipped this bar: spread %.2f is too wide for a %.2f stop", spread, risk);
      return;
     }
   double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(risk < stopsLevel)
     {
      CancelSetup("stop inside broker minimum");
      return;
     }

   double vpp    = ValuePerPoint();
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vpp <= 0 || step <= 0)
     {
      Print("Symbol data unavailable - no trade.");
      return;
     }
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPercent / 100.0;
   double lots      = MathFloor(riskMoney / (risk * vpp) / step + 1e-9) * step;
   lots = MathMin(lots, maxLot);
   bool minLotMode = false;
   if(lots < minLot - 1e-9)
     {
      // Small-account mode (H-002 amendment 16, policy P3): the smallest lot is allowed
      // only while it risks no more than InpMinLotMaxRiskPct of the balance.
      double minRisk = minLot * risk * vpp;
      if(InpMinLotMaxRiskPct > 0.0 && minRisk <= balance * InpMinLotMaxRiskPct / 100.0)
        {
         lots = minLot;
         minLotMode = true;
        }
      else
        {
         Notify(StringFormat("Setup skipped: the smallest trade (%.2f lots) would risk %.2f (%.1f%% of balance), above your limit (%.2f%%).",
                             minLot, minRisk, 100.0 * minRisk / balance,
                             MathMax(InpRiskPercent, InpMinLotMaxRiskPct)));
         CancelSetup("risk too big for limits");
         return;
        }
     }
   int volDigits = (int)MathMax(0.0, MathCeil(-MathLog10(step) - 1e-9));
   lots = NormalizeDouble(lots, volDigits);

   // Prop-firm guard: the full stop, times a gap allowance, must fit inside both firm limits.
   if(InpFtmoInitial > 0.0)
     {
      double eq   = AccountInfoDouble(ACCOUNT_EQUITY);
      double room = MathMin(eq - (g_cetMidBal - InpFtmoInitial * InpFtmoDailyPct / 100.0),
                            eq - InpFtmoInitial * (1.0 - InpFtmoMaxLossPct / 100.0));
      double fit  = MathFloor(room / InpFtmoGapAllowance / (risk * vpp) / step + 1e-9) * step;
      if(fit < lots - 1e-9)
        {
         if(fit < minLot - 1e-9)
           {
            Notify(StringFormat("Setup skipped: only %.2f of room left before the firm's loss limits; even the smallest trade could breach them.",
                                room));
            CancelSetup("prop-firm limit");
            return;
           }
         PrintFormat("Prop-firm guard: size cut from %.2f to %.2f lots (room %.2f before the firm's limits).", lots, fit, room);
         lots = NormalizeDouble(fit, volDigits);
        }
     }

   // Margin and stop-out checks: on a small account the broker can close the trade
   // (stop-out) before it ever reaches its own stop.
   double margin = 0.0;
   ENUM_ORDER_TYPE ot = (dir > 0) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(OrderCalcMargin(ot, _Symbol, lots, entry, margin) && margin > 0.0)
     {
      double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
      if(margin > freeMargin * InpMaxMarginPct / 100.0)
        {
         Notify(StringFormat("Setup skipped: margin %.2f for %.2f lots is above %.0f%% of free margin (%.2f). Check the account leverage.",
                             margin, lots, InpMaxMarginPct, freeMargin));
         CancelSetup("margin too large");
         return;
        }
      if(AccountInfoInteger(ACCOUNT_MARGIN_SO_MODE) == ACCOUNT_STOPOUT_MODE_PERCENT)
        {
         double soPct       = AccountInfoDouble(ACCOUNT_MARGIN_SO_SO);
         double equityAtStop = AccountInfoDouble(ACCOUNT_EQUITY) - lots * risk * vpp;
         if(equityAtStop < margin * soPct / 100.0)
           {
            Notify(StringFormat("Setup skipped: at the stop, equity (%.2f) would be below the broker's %.0f%% stop-out level for this margin (%.2f).",
                                equityAtStop, soPct, margin));
            CancelSetup("stop-out before stop");
            return;
           }
        }
     }

   double target = FindTarget(dir, entry, risk);
   double sl = NormPrice(stop);
   double tp = NormPrice(target);

   bool ok = (dir > 0) ? trade.Buy(lots, _Symbol, 0.0, sl, tp, "MS long")
                       : trade.Sell(lots, _Symbol, 0.0, sl, tp, "MS short");
   uint rc = trade.ResultRetcode();
   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED))
     {
      g_entryRisk = lots * risk * vpp;
      g_jRiskPct  = 100.0 * g_entryRisk / balance;
      g_jStop     = risk;
      g_jSpread   = spread;
      g_jMargin   = margin;
      g_jMinLot   = minLotMode;
      Notify(StringFormat("ENTERED %s %.2f lots @ %.2f | stop %.2f | target %.2f (%.1fR) | risk %.2f (%.1f%%%s)",
                          (dir > 0) ? "LONG" : "SHORT", lots, trade.ResultPrice(), sl, tp,
                          MathAbs(tp - entry) / risk, g_entryRisk, g_jRiskPct,
                          minLotMode ? ", smallest lot" : ""));
      g_status   = StringFormat("in trade: %s %.2f lots", (dir > 0) ? "LONG" : "SHORT", lots);
      g_setupDir = 0;
      g_touched  = false;
     }
   else
      PrintFormat("Entry FAILED: %u %s. Will retry next bar if the setup is still valid.",
                  rc, trade.ResultRetcodeDescription());
  }

// Called once per new entry-timeframe bar while a setup is active.
void ManageSetup(const datetime nyNow)
  {
   g_setupBars++;
   double atrS = ATRValue(g_atrStruct);
   double atrE = ATRValue(g_atrEntry);
   if(atrS <= 0 || atrE <= 0)
      return;

   double sc1 = iClose(_Symbol, InpStructTF, 1);
   if(g_setupDir > 0 && sc1 < g_level - InpFailATR * atrS)
     {
      CancelSetup("failed break");
      return;
     }
   if(g_setupDir < 0 && sc1 > g_level + InpFailATR * atrS)
     {
      CancelSetup("failed break");
      return;
     }
   if(g_setupBars > InpSetupExpiry)
     {
      CancelSetup("expired without an entry");
      return;
     }

   double eh = iHigh(_Symbol, InpEntryTF, 1);
   double el = iLow(_Symbol, InpEntryTF, 1);
   double ec = iClose(_Symbol, InpEntryTF, 1);
   double ph = iHigh(_Symbol, InpEntryTF, 2);
   double pl = iLow(_Symbol, InpEntryTF, 2);

   if(g_setupDir > 0)
     {
      if(!g_touched && el <= g_level + InpZoneATR * atrS)
        {
         g_touched   = true;
         g_pbExtreme = el;
         g_status    = StringFormat("LONG setup: pullback reached %.2f, waiting for the turn", el);
        }
      else
         if(g_touched)
            g_pbExtreme = MathMin(g_pbExtreme, el);
      if(g_touched && ec > ph && ec > g_level && InSession(nyNow) && !LossLimitHit())
         TryEnter(1, atrE);
     }
   else
     {
      if(!g_touched && eh >= g_level - InpZoneATR * atrS)
        {
         g_touched   = true;
         g_pbExtreme = eh;
         g_status    = StringFormat("SHORT setup: pullback reached %.2f, waiting for the turn", eh);
        }
      else
         if(g_touched)
            g_pbExtreme = MathMax(g_pbExtreme, eh);
      if(g_touched && ec < pl && ec < g_level && InSession(nyNow) && !LossLimitHit())
         TryEnter(-1, atrE);
     }
  }

//+------------------------------------------------------------------+
//| Exit alerts and journal                                           |
//+------------------------------------------------------------------+
string ReasonText(const long r)
  {
   if(r == DEAL_REASON_SL)
      return "stop";
   if(r == DEAL_REASON_TP)
      return "target";
   if(r == DEAL_REASON_EXPERT)
      return "bot";
   if(r == DEAL_REASON_CLIENT)
      return "manual-desktop";
   if(r == DEAL_REASON_MOBILE)
      return "manual-mobile";
   if(r == DEAL_REASON_SO)
      return "stop-out";
   return "other";
  }

bool PositionIsOurs(const long pid)
  {
   if(!HistorySelectByPosition(pid))
      return false;
   int n = HistoryDealsTotal();
   for(int i = 0; i < n; i++)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d != 0 && HistoryDealGetInteger(d, DEAL_MAGIC) == InpMagic)
         return true;
     }
   return false;
  }

void NotifyExit(const long pid, const long reason)
  {
   double total = 0.0;
   if(HistorySelectByPosition(pid))
      for(int i = 0; i < HistoryDealsTotal(); i++)
        {
         ulong d = HistoryDealGetTicket(i);
         if(d != 0)
            total += HistoryDealGetDouble(d, DEAL_PROFIT) + HistoryDealGetDouble(d, DEAL_COMMISSION)
                     + HistoryDealGetDouble(d, DEAL_SWAP);
        }
   string rText = (g_entryRisk > 0) ? StringFormat("%+.2fR (%+.2f)", total / g_entryRisk, total)
                                    : StringFormat("%+.2f", total);
   string head, tail;
   if(reason == DEAL_REASON_TP)
     {
      head = "TARGET hit";
      tail = "Plan followed.";
     }
   else
      if(reason == DEAL_REASON_SL)
        {
         head = "STOPPED out";
         tail = "Plan followed - a good trade, even as a loss.";
        }
      else
         if(reason == DEAL_REASON_EXPERT)
           {
            head = "Closed by the bot (time stop, Friday close or safety rule)";
            tail = "";
           }
         else
           {
            head = "Closed MANUALLY";
            tail = "Note it in your weekly review.";
           }
   Notify(StringFormat("%s: %s. %s", head, rText, tail));
   g_entryRisk = 0.0;
   g_status = "watching 4H structure";
  }

void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   ulong d = trans.deal;
   if(!HistoryDealSelect(d))
      return;
   if(HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol)
      return;
   long   magic  = HistoryDealGetInteger(d, DEAL_MAGIC);
   long   pid    = HistoryDealGetInteger(d, DEAL_POSITION_ID);
   long   entry  = HistoryDealGetInteger(d, DEAL_ENTRY);
   long   type   = HistoryDealGetInteger(d, DEAL_TYPE);
   long   reason = HistoryDealGetInteger(d, DEAL_REASON);
   double vol    = HistoryDealGetDouble(d, DEAL_VOLUME);
   double price  = HistoryDealGetDouble(d, DEAL_PRICE);
   double profit = HistoryDealGetDouble(d, DEAL_PROFIT);
   double comm   = HistoryDealGetDouble(d, DEAL_COMMISSION);
   double swap   = HistoryDealGetDouble(d, DEAL_SWAP);
   datetime t    = (datetime)HistoryDealGetInteger(d, DEAL_TIME);
   if(magic != InpMagic && !PositionIsOurs(pid))
      return;

   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
      NotifyExit(pid, reason);

   if(!InpWriteJournal)
      return;
   int h = FileOpen("MS_journal.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE)
      return;
   if(FileSize(h) == 0)
      FileWrite(h, "server_time", "ny_time", "entry", "side", "lots", "price",
                "profit", "commission", "swap", "reason", "balance",
                "risk_money", "risk_pct", "stop_dist", "spread", "margin", "min_lot_mode");
   bool isIn = (entry == DEAL_ENTRY_IN);
   FileSeek(h, 0, SEEK_END);
   FileWrite(h,
             TimeToString(t, TIME_DATE | TIME_MINUTES),
             TimeToString(ToNY(t), TIME_DATE | TIME_MINUTES),
             (entry == DEAL_ENTRY_IN) ? "IN" : "OUT",
             (type == DEAL_TYPE_BUY) ? "BUY" : "SELL",
             DoubleToString(vol, 2),
             DoubleToString(price, _Digits),
             DoubleToString(profit, 2),
             DoubleToString(comm, 2),
             DoubleToString(swap, 2),
             ReasonText(reason),
             DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2),
             isIn ? DoubleToString(g_entryRisk, 2) : "",
             isIn ? DoubleToString(g_jRiskPct, 2) : "",
             isIn ? DoubleToString(g_jStop, _Digits) : "",
             isIn ? DoubleToString(g_jSpread, _Digits) : "",
             isIn ? DoubleToString(g_jMargin, 2) : "",
             isIn ? (g_jMinLot ? "1" : "0") : "");
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Start-up report and status                                        |
//+------------------------------------------------------------------+
void ReportSymbol()
  {
   double vpp       = ValuePerPoint();
   double minLot    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step      = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double contract  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0;
   PrintFormat("MS bot on %s | contract size %.2f | min lot %.2f, step %.2f | %.4f per point per lot | %.4f per point at min lot",
               _Symbol, contract, minLot, step, vpp, vpp * minLot);
   PrintFormat("Clock: server is %d h ahead of New York. Entries %s-%s local time (%s%s), structure %s, entries %s.",
               g_offsetHrs, InpSessionStart, InpSessionEnd, EnumToString(InpSessionZone),
               InpMode24x7 ? ", 24/7 mode" : "",
               EnumToString(InpStructTF), EnumToString(InpEntryTF));
   double atrE = ATRValue(g_atrEntry);
   if(atrE > 0)
     {
      double typical = 1.5 * atrE;
      double minRisk = minLot * vpp * typical;
      PrintFormat("Risk per trade: %.2f%% of balance = %.2f. A typical stop (~%.2f) at the smallest size risks %.2f.",
                  InpRiskPercent, riskMoney, typical, minRisk);
      if(minRisk > riskMoney)
        {
         double bal = AccountInfoDouble(ACCOUNT_BALANCE);
         if(InpMinLotMaxRiskPct > 0.0)
            PrintFormat("Small-account mode: the smallest lot is used when it risks at most %.1f%% (= %.2f). "
                        "A typical stop at the smallest lot is %.1f%% of balance; setups with wider stops are skipped.",
                        InpMinLotMaxRiskPct, bal * InpMinLotMaxRiskPct / 100.0, 100.0 * minRisk / bal);
         else
            Print("WARNING: at this balance most setups will be SKIPPED - even the smallest trade risks more than your limit.");
        }
     }
   else
      PrintFormat("Risk per trade: %.2f%% of balance = %.2f.", InpRiskPercent, riskMoney);
  }

void ShowStatus()
  {
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))
      return;
   Comment(StringFormat("MS bot | %s\nNY time %s | server +%d h | risk %.2f%% | magic %I64d",
                        g_status, TimeToString(ToNY(TimeCurrent()), TIME_MINUTES),
                        g_offsetHrs, InpRiskPercent, InpMagic));
  }

//+------------------------------------------------------------------+
//| Prop-firm guard (FTMO-style daily and maximum loss)               |
//+------------------------------------------------------------------+
// Returns true when no new trades may be opened right now.
bool PropGuard()
  {
   if(InpFtmoInitial <= 0.0)
      return false;
   datetime cet = (datetime)((long)TimeCurrent() - (long)InpServerMinusCET * 3600);
   int k = DayKey(cet);
   if(k != g_cetDayKey)
     {
      g_cetDayKey   = k;
      g_cetMidBal   = AccountInfoDouble(ACCOUNT_BALANCE);
      g_propBlocked = false;
     }
   double eq        = AccountInfoDouble(ACCOUNT_EQUITY);
   double dailyLine = g_cetMidBal - InpFtmoInitial * InpFtmoDailyPct / 100.0;
   double maxLine   = InpFtmoInitial * (1.0 - InpFtmoMaxLossPct / 100.0);
   double buffer    = 0.005 * InpFtmoInitial;      // act 0.5% before the firm would
   if(!g_propBlocked && (eq < dailyLine + buffer || eq < maxLine + buffer))
     {
      if(MyPositions() > 0)
         CloseAll("prop-firm limit close");
      g_propBlocked = true;
      g_setupDir    = 0;
      Notify(StringFormat("PROP LIMIT: equity %.2f is within 0.5%% of the firm's %s line (%.2f). Positions closed; no new trades until the firm's next day.",
                          eq, (eq < maxLine + buffer) ? "maximum-loss" : "daily-loss",
                          (eq < maxLine + buffer) ? maxLine : dailyLine));
     }
   if(g_propBlocked)
      g_status = "prop-firm limit: paused until the firm's next day";
   return g_propBlocked;
  }

//+------------------------------------------------------------------+
//| Expert lifecycle                                                  |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpRiskPercent <= 0.0 || InpRiskPercent > 3.0)
     {
      Print(StringFormat("RiskPercent = %.2f looks wrong (allowed 0.01-3). Did you mean to change a loss limit instead?",
                         InpRiskPercent));
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpMinLotMaxRiskPct < 0.0 || InpMinLotMaxRiskPct > 5.0)
     {
      Print(StringFormat("MinLotMaxRiskPct = %.2f is outside 0-5. Above 5%% per trade a run of normal losses can halve the account "
                         "(research/small_account.md).", InpMinLotMaxRiskPct));
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpMaxMarginPct <= 0.0 || InpMaxMarginPct > 100.0)
     {
      Print("MaxMarginPct must be between 1 and 100.");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_friCutoff = (StringLen(InpFridayCutoffNY) > 0) ? ParseHHMM(InpFridayCutoffNY) : -1;
   if(StringLen(InpFridayCutoffNY) > 0 && g_friCutoff < 0)
     {
      Print("FridayCutoffNY must be HH:MM (e.g. 15:00) or empty.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpFtmoInitial < 0.0 || InpFtmoDailyPct <= 0.0 || InpFtmoMaxLossPct <= 0.0 || InpFtmoGapAllowance < 1.0)
     {
      Print("Prop-firm inputs: initial >= 0, limits > 0, gap allowance >= 1.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpFtmoInitial > 0.0)
      PrintFormat("Prop-firm guard ON: initial %.2f, daily %.1f%% below the Prague-midnight balance, max loss %.1f%% (floor %.2f), gap allowance x%.2f.",
                  InpFtmoInitial, InpFtmoDailyPct, InpFtmoMaxLossPct,
                  InpFtmoInitial * (1.0 - InpFtmoMaxLossPct / 100.0), InpFtmoGapAllowance);
   bool research = MQLInfoInteger(MQL_TESTER) && InpTesterNoLimits;
   g_limDaily  = research ? 100.0 : InpDailyLossPct;
   g_limWeekly = research ? 100.0 : InpWeeklyLossPct;
   g_limKill   = research ? 100.0 : InpKillSwitchPct;
   if(research)
      Print("Research mode (tester): loss limits and kill switch off, to measure the strategy itself.");
   if(MQLInfoInteger(MQL_TESTER) && InpTesterStopAt > 0)
      Print("Out-of-sample lock: the test stops at " + TimeToString(InpTesterStopAt) + " server time.");
   if(InpSwingN < 1 || InpSwingLookback < 50)
     {
      Print("Swing size must be at least 1 and lookback at least 50 bars.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(PeriodSeconds(InpStructTF) <= PeriodSeconds(InpEntryTF))
     {
      Print("The structure timeframe must be higher than the entry timeframe.");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_sessStart = ParseHHMM(InpSessionStart);
   g_sessEnd   = ParseHHMM(InpSessionEnd);
   g_friClose  = ParseHHMM(InpFridayCloseNY);
   if(g_sessStart < 0 || g_sessEnd < 0 || g_friClose < 0 || g_sessEnd <= g_sessStart)
     {
      Print("Check the session times (HH:MM, end after start).");
      return INIT_PARAMETERS_INCORRECT;
     }

   bool isReal = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL);
   if(isReal && !InpAllowLive && !MQLInfoInteger(MQL_TESTER))
     {
      Alert("MS bot refused to start: this is a REAL-money account. Paper trade on demo first. "
            "To run live anyway, set AllowLive = true.");
      return INIT_FAILED;
     }

   g_atrStruct = iATR(_Symbol, InpStructTF, 14);
   g_atrEntry  = iATR(_Symbol, InpEntryTF, 14);
   if(g_atrStruct == INVALID_HANDLE || g_atrEntry == INVALID_HANDLE)
     {
      Print("Could not create ATR indicators.");
      return INIT_FAILED;
     }

   trade.SetExpertMagicNumber((ulong)InpMagic);
   trade.SetDeviationInPoints(50);
   trade.SetTypeFillingBySymbol(_Symbol);

   string base = StringFormat("MS_%I64d_%s_%I64d", AccountInfoInteger(ACCOUNT_LOGIN), _Symbol, InpMagic);
   g_gvPeak = base + "_peak";
   g_gvKill = base + "_kill";
   if(MQLInfoInteger(MQL_TESTER))
     {
      GlobalVariableDel(g_gvPeak);
      GlobalVariableDel(g_gvKill);
     }
   if(InpResetKillSwitch)
     {
      GlobalVariableDel(g_gvKill);
      GlobalVariableDel(g_gvPeak);
      Print("Kill switch reset. Peak equity restarts from current equity. Set ResetKillSwitch back to false.");
     }
   if(!GlobalVariableCheck(g_gvPeak))
      GlobalVariableSet(g_gvPeak, AccountInfoDouble(ACCOUNT_EQUITY));

   UpdateClock();
   ReportSymbol();
   if(InpPushNotify && !MQLInfoInteger(MQL_TESTER) && !TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED))
      Print("Phone alerts are OFF in MT5. Turn them on: Tools > Options > Notifications, enter your MetaQuotes ID.");
   Notify(StringFormat("Bot started on a %s account. Risk %.2f%% = %.2f per trade.",
                       isReal ? "REAL" : "demo", InpRiskPercent,
                       AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0));
   g_status = "watching 4H structure";
   ShowStatus();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(g_atrStruct != INVALID_HANDLE)
      IndicatorRelease(g_atrStruct);
   if(g_atrEntry != INVALID_HANDLE)
      IndicatorRelease(g_atrEntry);
   Comment("");
  }

void OnTick()
  {
   if(MQLInfoInteger(MQL_TESTER) && InpTesterStopAt > 0 && TimeCurrent() >= InpTesterStopAt)
     {
      if(!g_lockDone)
        {
         if(MyPositions() > 0)
            CloseAll("end of in-sample");
         Print("OUT-OF-SAMPLE LOCK: test stopped at " + TimeToString(TimeCurrent()) +
               ". Nothing after this date is used until the single out-of-sample run.");
         g_lockDone = true;
         TesterStop();
        }
      return;
     }
   datetime nyNow = ToNY(TimeCurrent());
   if(DayKey(nyNow) != g_dayKey)
     {
      UpdateClock();
      nyNow = ToNY(TimeCurrent());
      NewDay(nyNow);
     }
   int nowMin = MinuteOfDay(nyNow);
   int dow    = DayOfWeek(nyNow);

   // 1. Friday close - no positions held over the weekend
   if(InpCloseFriday && !InpMode24x7 && dow == 5 && nowMin >= g_friClose && MyPositions() > 0)
      CloseAll("Friday close");

   // 2. Kill switch, then the prop-firm guard
   if(KillSwitch())
     {
      ShowStatus();
      return;
     }
   if(PropGuard())
     {
      ShowStatus();
      return;
     }

   // 3. End-of-session summary (weekdays)
   if(InpDailySummary && !g_summarySent && nowMin >= 17 * 60 && dow >= 1 && dow <= 5)
     {
      double dayPnl, weekPnl;
      int    dayTrades, weekTrades;
      ClosedStats(g_dayStartSrv, dayPnl, dayTrades);
      ClosedStats(g_weekStartSrv, weekPnl, weekTrades);
      Notify(StringFormat("Session done: %d trade(s), %+.2f today | week %+.2f over %d trade(s) | open: %d | balance %.2f",
                          dayTrades, dayPnl, weekPnl, weekTrades, MyPositions(),
                          AccountInfoDouble(ACCOUNT_BALANCE)));
      g_summarySent = true;
     }

   // 4. Everything else once per new entry-timeframe bar
   datetime eb = iTime(_Symbol, InpEntryTF, 0);
   if(eb == 0 || eb == g_lastEntryBar)
      return;
   g_lastEntryBar = eb;

   if(MyPositions() > 0)
     {
      TimeStop();
      ShowStatus();
      return;
     }

   if(g_setupDir == 0)
      CheckForSetup();          // a new setup starts being managed from the next bar
   else
      ManageSetup(nyNow);
   ShowStatus();
  }
//+------------------------------------------------------------------+
