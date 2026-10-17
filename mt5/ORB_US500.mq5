//+------------------------------------------------------------------+
//|                                                    ORB_US500.mq5 |
//|  Opening-range breakout on the US500 index CFD (S&P 500).        |
//|  Same strategy and risk rules as orb_backtest.py.                 |
//|  Part of github.com/TinoSea/orb-bot.  Not financial advice.       |
//+------------------------------------------------------------------+
//
//  Strategy (one setup, traded mechanically):
//    1. Opening range (OR) = high/low of the first N minutes after 09:30 New York time.
//    2. A 5-minute bar CLOSES above the OR high -> buy.  Closes below the OR low -> sell.
//    3. Stop = other side of the range (or the midpoint).  Target = TargetR x risk.
//    4. Anything still open at the flat time is closed.  Max 1 trade per day by default.
//    5. Days with a range that is too small or too wide are skipped.
//
//  Risk engine (the bot cannot override these):
//    - risk per trade as % of balance; if even the smallest lot would risk more, the trade is skipped
//    - daily and weekly loss limits
//    - kill switch: stops for good after a set drawdown from peak equity, until you reset it
//    - refuses to run on a LIVE account unless you explicitly allow it
//
#property copyright   "orb-bot"
#property version     "1.10"
#property description "Opening-range breakout on US500 (S&P 500 CFD)."
#property description "Hard limits: % risk per trade, daily/weekly loss caps, kill switch."

#include <Trade\Trade.mqh>

//--- inputs ---------------------------------------------------------
input group "Strategy"
input int    InpORMinutes       = 15;      // Opening range length in minutes (multiple of 5)
input double InpTargetR         = 1.5;     // Target as a multiple of risk
input bool   InpStopAtMid       = false;   // Stop at range midpoint instead of far side
input double InpMinRangePts     = 3.0;     // Skip day if range is smaller (index points)
input double InpMaxRangePts     = 30.0;    // Skip day if range is wider (index points)
input string InpLastEntryNY     = "11:30"; // No new entries after this New York time
input string InpFlatNY          = "15:55"; // Close everything at this New York time
input int    InpMaxTradesPerDay = 1;       // Max trades per day
input bool   InpAllowLong       = true;    // Allow long trades
input bool   InpAllowShort      = true;    // Allow short trades

input group "Risk (hard limits)"
input double InpRiskPercent     = 1.0;     // Risk per trade, % of balance
input double InpDailyLossPct    = 2.0;     // Stop for the day after losing this % of balance
input double InpWeeklyLossPct   = 5.0;     // Stop for the week after losing this % of balance
input double InpKillSwitchPct   = 15.0;    // Stop for good after this % drawdown from peak equity
input double InpMaxSpreadPts    = 1.5;     // Ignore a signal if spread is wider (index points)
input bool   InpResetKillSwitch = false;   // Set true ONCE to clear a tripped kill switch
input bool   InpAllowLive       = false;   // Must be true to run on a real-money account

input group "Clock"
input int    InpServerMinusNY   = 7;       // Server time minus New York time, hours (FP Markets = 7)
input bool   InpAutoDetectClock = true;    // Live/demo only: detect from the broker clock

input group "Other"
input long   InpMagic           = 202610;  // Magic number (identifies this bot's trades)
input bool   InpWriteJournal    = true;    // Write every fill to MQL5/Files/ORB_journal.csv
input bool   InpPushNotify      = true;    // Send alerts to the MetaTrader app on your phone
input bool   InpDailySummary    = true;    // Send a short end-of-day summary on weekdays

//--- state ----------------------------------------------------------
CTrade   trade;
int      g_offsetHrs    = 7;
int      g_dayKey       = -1;
datetime g_dayStartSrv  = 0;
datetime g_weekStartSrv = 0;
bool     g_orReady      = false;
bool     g_daySkip      = false;
double   g_orHigh       = 0.0;
double   g_orLow        = 0.0;
datetime g_lastBarTime  = 0;
int      g_startMin     = 9 * 60 + 30;
int      g_orEndMin     = 0;
int      g_lastEntryMin = 0;
int      g_flatMin      = 0;
string   g_gvPeak       = "";
string   g_gvKill       = "";
bool     g_killLogged   = false;
string   g_status       = "";
double   g_entryRisk    = 0.0;     // money at risk on the open trade (for R-multiples)
bool     g_summarySent  = false;
bool     g_cutoffSent   = false;
bool     g_failSent     = false;

//+------------------------------------------------------------------+
//| Phone alerts                                                      |
//+------------------------------------------------------------------+
// Prints to the Experts log and, when enabled, pushes to the MetaTrader
// app on your phone (Tools > Options > Notifications > MetaQuotes ID).
void Notify(const string msg)
  {
   Print(msg);
   if(!InpPushNotify || MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      return;
   if(!TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED))
      return;
   string text = "ORB " + _Symbol + ": " + msg;
   if(StringLen(text) > 255)
      text = StringSubstr(text, 0, 255);
   if(!SendNotification(text))
      PrintFormat("Phone alert not sent (error %d)", GetLastError());
  }

//+------------------------------------------------------------------+
//| Time helpers                                                      |
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

// US daylight saving: 2nd Sunday of March 02:00 local -> 1st Sunday of November 02:00 local
bool IsUSDST(const datetime gmt)
  {
   MqlDateTime s;
   TimeToStruct(gmt, s);
   long start = (long)NthSunday(s.year, 3, 2) + 7 * 3600;   // 02:00 EST = 07:00 UTC
   long end   = (long)NthSunday(s.year, 11, 1) + 6 * 3600;  // 02:00 EDT = 06:00 UTC
   return ((long)gmt >= start && (long)gmt < end);
  }

// Works out how many hours the broker server is ahead of New York.
// In the Strategy Tester the broker clock can't be read, so the input is used.
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
   g_orReady    = false;
   g_daySkip    = false;
   g_orHigh     = 0.0;
   g_orLow      = 0.0;
   g_killLogged  = false;
   g_summarySent = false;
   g_cutoffSent  = false;
   g_failSent    = false;
   g_status      = "waiting for 09:30 New York";
  }

//+------------------------------------------------------------------+
//| Position and history helpers                                      |
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

// Closed P&L (incl. commission and swap) and number of entries since `from`.
// Exits by stop/target are matched to our entries by position id, so they count
// even if the broker does not stamp them with our magic number.
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
//| Risk engine                                                       |
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
   if(peak > 0 && eq <= peak * (1.0 - InpKillSwitchPct / 100.0))
     {
      GlobalVariableSet(g_gvKill, 1.0);
      CloseAll("kill switch");
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
   double bal = AccountInfoDouble(ACCOUNT_BALANCE);
   double fl  = FloatingPnL();
   double dayPnl, weekPnl;
   int    e;
   ClosedStats(g_dayStartSrv, dayPnl, e);
   if(dayPnl + fl <= -bal * InpDailyLossPct / 100.0)
     {
      Notify(StringFormat("Daily loss limit reached (%.2f). No more trades today.", dayPnl + fl));
      g_status = "daily loss limit - done for today";
      g_daySkip = true;
      return true;
     }
   ClosedStats(g_weekStartSrv, weekPnl, e);
   if(weekPnl + fl <= -bal * InpWeeklyLossPct / 100.0)
     {
      Notify(StringFormat("Weekly loss limit reached (%.2f). No more trades this week.", weekPnl + fl));
      g_status = "weekly loss limit - done for the week";
      g_daySkip = true;
      return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Strategy                                                          |
//+------------------------------------------------------------------+
bool BuildOR()
  {
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M5, 1, 150, r);   // oldest first
   if(n <= 0)
     {
      g_status = "skipped: no 5-minute data";
      return false;
     }
   int    need = InpORMinutes / 5, got = 0;
   bool   sawStart = false;
   double hi = -DBL_MAX, lo = DBL_MAX;
   for(int i = 0; i < n; i++)
     {
      datetime ny = ToNY(r[i].time);
      if(DayKey(ny) != g_dayKey)
         continue;
      int m = MinuteOfDay(ny);
      if(m < g_startMin || m >= g_orEndMin)
         continue;
      if(m == g_startMin)
         sawStart = true;
      hi = MathMax(hi, r[i].high);
      lo = MathMin(lo, r[i].low);
      got++;
     }
   if(!sawStart || got < need)
     {
      g_status = StringFormat("skipped: incomplete opening range (%d of %d bars)", got, need);
      return false;
     }
   g_orHigh = hi;
   g_orLow  = lo;
   double range = hi - lo;
   if(range < InpMinRangePts)
     {
      g_status = StringFormat("skipped: range too small (%.2f pts)", range);
      return false;
     }
   if(range > InpMaxRangePts)
     {
      g_status = StringFormat("skipped: range too wide (%.2f pts)", range);
      return false;
     }
   Notify(StringFormat("Range set %.2f - %.2f (%.2f pts). Watching for a breakout until %s NY.",
                       lo, hi, range, InpLastEntryNY));
   g_status = StringFormat("range %.2f - %.2f, waiting for breakout", lo, hi);
   return true;
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

void TryEnter(const int side)
  {
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk))
      return;
   double spread = tk.ask - tk.bid;
   if(spread > InpMaxSpreadPts)
     {
      PrintFormat("Signal ignored: spread %.2f is wider than %.2f", spread, InpMaxSpreadPts);
      return;
     }

   double entry   = (side > 0) ? tk.ask : tk.bid;
   double stop    = InpStopAtMid ? (g_orHigh + g_orLow) / 2.0 : ((side > 0) ? g_orLow : g_orHigh);
   double riskPts = (entry - stop) * side;
   if(riskPts <= 0)
      return;   // price already back through the stop

   double vpp    = ValuePerPoint();
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vpp <= 0 || step <= 0)
     {
      Print("Symbol data unavailable - no trade.");
      return;
     }

   double stopsLevel = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(riskPts < stopsLevel)
     {
      Notify(StringFormat("No trade today: stop distance %.2f is inside the broker's minimum %.2f", riskPts, stopsLevel));
      g_status  = "skipped: stop too close for broker";
      g_daySkip = true;
      return;
     }

   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0;
   double lots      = MathFloor(riskMoney / (riskPts * vpp) / step + 1e-9) * step;
   lots = MathMin(lots, maxLot);
   if(lots < minLot - 1e-9)
     {
      Notify(StringFormat("No trade today: the smallest trade (%.2f lots) would risk %.2f, above your %.2f%% limit (%.2f).",
                          minLot, minLot * riskPts * vpp, InpRiskPercent, riskMoney));
      g_status  = "skipped: risk too big for limits";
      g_daySkip = true;
      return;
     }
   int volDigits = (int)MathMax(0.0, MathCeil(-MathLog10(step) - 1e-9));
   lots = NormalizeDouble(lots, volDigits);

   double sl = NormPrice(stop);
   double tp = NormPrice(entry + side * InpTargetR * riskPts);

   bool ok = (side > 0) ? trade.Buy(lots, _Symbol, 0.0, sl, tp, "ORB long")
                        : trade.Sell(lots, _Symbol, 0.0, sl, tp, "ORB short");
   uint rc = trade.ResultRetcode();
   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED))
     {
      g_entryRisk = lots * riskPts * vpp;
      Notify(StringFormat("ENTERED %s %.2f lots @ %.2f | stop %.2f | target %.2f | risk %.2f",
                          (side > 0) ? "LONG" : "SHORT", lots, trade.ResultPrice(), sl, tp, g_entryRisk));
      g_status = StringFormat("in trade: %s %.2f lots", (side > 0) ? "LONG" : "SHORT", lots);
     }
   else
     {
      string fm = StringFormat("Entry FAILED: %u %s. Will retry on the next bar if the signal is still valid.",
                               rc, trade.ResultRetcodeDescription());
      if(g_failSent)
         Print(fm);
      else
        {
         Notify(fm);
         g_failSent = true;
        }
     }
  }

//+------------------------------------------------------------------+
//| Journal: one CSV line per fill                                    |
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

// Phone alert when a trade closes: result in R and $, and a reminder that a
// stop that followed the plan is still a good trade.
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
            head = "Closed by the bot (end of day or safety rule)";
            tail = "";
           }
         else
           {
            head = "Closed MANUALLY";
            tail = "Note it in your weekly review.";
           }
   Notify(StringFormat("%s: %s. %s", head, rText, tail));
   g_entryRisk = 0.0;
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
   int h = FileOpen("ORB_journal.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE)
      return;
   if(FileSize(h) == 0)
      FileWrite(h, "server_time", "ny_time", "entry", "side", "lots", "price",
                "profit", "commission", "swap", "reason", "balance");
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
             DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2));
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Start-up report: tells you what one trade will actually risk      |
//+------------------------------------------------------------------+
void ReportSymbol()
  {
   double vpp       = ValuePerPoint();
   double minLot    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double step      = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double contract  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0;
   double minRisk10 = minLot * vpp * 10.0;
   PrintFormat("ORB bot on %s | contract size %.2f | min lot %.2f, step %.2f | %.4f per point per lot | %.4f per point at min lot",
               _Symbol, contract, minLot, step, vpp, vpp * minLot);
   PrintFormat("Clock: server is %d h ahead of New York (09:30 NY = %02d:%02d server time)",
               g_offsetHrs, (570 / 60 + g_offsetHrs) % 24, 570 % 60);
   PrintFormat("Risk per trade: %.2f%% of balance = %.2f.  Smallest trade on a 10-point stop risks %.2f.",
               InpRiskPercent, riskMoney, minRisk10);
   if(minRisk10 > riskMoney)
      Print("WARNING: at this balance most trades will be SKIPPED, because even the smallest trade risks more than your limit.");
  }

void ShowStatus()
  {
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))
      return;
   Comment(StringFormat("ORB bot | %s\nNY time %s | server +%d h | risk %.2f%% | magic %I64d",
                        g_status, TimeToString(ToNY(TimeCurrent()), TIME_MINUTES),
                        g_offsetHrs, InpRiskPercent, InpMagic));
  }

//+------------------------------------------------------------------+
//| Expert lifecycle                                                  |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpORMinutes < 5 || InpORMinutes % 5 != 0)
     {
      Print("Opening range minutes must be a multiple of 5.");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_orEndMin     = g_startMin + InpORMinutes;
   g_lastEntryMin = ParseHHMM(InpLastEntryNY);
   g_flatMin      = ParseHHMM(InpFlatNY);
   if(g_lastEntryMin < 0 || g_flatMin < 0 || g_lastEntryMin <= g_orEndMin || g_flatMin <= g_lastEntryMin)
     {
      Print("Check the times: last entry must be after the range ends, and flat time after last entry (HH:MM).");
      return INIT_PARAMETERS_INCORRECT;
     }

   bool isReal = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL);
   if(isReal && !InpAllowLive && !MQLInfoInteger(MQL_TESTER))
     {
      Alert("ORB bot refused to start: this is a REAL-money account. Paper trade on demo first. "
            "To run live anyway, set AllowLive = true.");
      return INIT_FAILED;
     }

   trade.SetExpertMagicNumber((ulong)InpMagic);
   trade.SetDeviationInPoints(50);
   trade.SetTypeFillingBySymbol(_Symbol);

   string base = StringFormat("ORB_%I64d_%s_%I64d", AccountInfoInteger(ACCOUNT_LOGIN), _Symbol, InpMagic);
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
   g_status = "starting";
   ShowStatus();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   Comment("");
  }

void OnTick()
  {
   datetime nyNow = ToNY(TimeCurrent());
   if(DayKey(nyNow) != g_dayKey)
     {
      UpdateClock();
      nyNow = ToNY(TimeCurrent());
      NewDay(nyNow);
     }
   int nowMin = MinuteOfDay(nyNow);

   // 1. End-of-day exit - always runs first
   if(nowMin >= g_flatMin && MyPositions() > 0)
     {
      CloseAll("end-of-day exit");
      g_status = "flat for the day";
     }

   // 1b. End-of-day summary to the phone (weekdays only)
   if(InpDailySummary && !g_summarySent && nowMin >= g_flatMin && MyPositions() == 0)
     {
      MqlDateTime s;
      TimeToStruct(nyNow, s);
      if(s.day_of_week >= 1 && s.day_of_week <= 5)
        {
         double dayPnl, weekPnl;
         int    dayTrades, weekTrades;
         ClosedStats(g_dayStartSrv, dayPnl, dayTrades);
         ClosedStats(g_weekStartSrv, weekPnl, weekTrades);
         Notify(StringFormat("Day done: %d trade(s), %+.2f today | week %+.2f over %d trade(s) | balance %.2f",
                             dayTrades, dayPnl, weekPnl, weekTrades, AccountInfoDouble(ACCOUNT_BALANCE)));
        }
      g_summarySent = true;
     }

   // 2. Kill switch
   if(KillSwitch())
     {
      ShowStatus();
      return;
     }

   // 3. Only act once per new 5-minute bar
   datetime bar0 = iTime(_Symbol, PERIOD_M5, 0);
   if(bar0 == 0 || bar0 == g_lastBarTime)
      return;
   g_lastBarTime = bar0;

   if(MyPositions() == 0 && StringFind(g_status, "in trade") == 0)
      g_status = "trade closed - done for today";

   if(g_daySkip)
     {
      ShowStatus();
      return;
     }

   MqlRates r[];
   if(CopyRates(_Symbol, PERIOD_M5, 1, 1, r) != 1)
      return;
   datetime barNY = ToNY(r[0].time);
   if(DayKey(barNY) != g_dayKey)
     {
      ShowStatus();
      return;
     }
   int barMin = MinuteOfDay(barNY);
   if(barMin < g_orEndMin || barMin >= g_lastEntryMin)
     {
      if(barMin >= g_lastEntryMin && MyPositions() == 0 && g_orReady && StringFind(g_status, "range") == 0)
        {
         g_status = "no breakout before cut-off - done for today";
         if(!g_cutoffSent)
           {
            Notify(StringFormat("No breakout by %s NY. No trade today - that's the plan working.", InpLastEntryNY));
            g_cutoffSent = true;
           }
        }
      ShowStatus();
      return;
     }

   // 4. Build the opening range once it is complete
   if(!g_orReady)
     {
      if(!BuildOR())
        {
         g_daySkip = true;
         Notify("No trade today - " + g_status);
         ShowStatus();
         return;
        }
      g_orReady = true;
     }

   // 5. Entry checks
   if(MyPositions() > 0)
     {
      ShowStatus();
      return;
     }
   double dayPnl;
   int    entries;
   ClosedStats(g_dayStartSrv, dayPnl, entries);
   if(entries >= InpMaxTradesPerDay)
     {
      ShowStatus();
      return;
     }
   if(LossLimitHit())
     {
      ShowStatus();
      return;
     }

   int side = 0;
   if(r[0].close > g_orHigh && InpAllowLong)
      side = 1;
   else
      if(r[0].close < g_orLow && InpAllowShort)
         side = -1;
   if(side != 0)
      TryEnter(side);
   ShowStatus();
  }
//+------------------------------------------------------------------+
