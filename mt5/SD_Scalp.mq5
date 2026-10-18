//+------------------------------------------------------------------+
//|                                                   SD_Scalp.mq5 |
//|  H-004: supply/demand rejection scalp at the New York open.      |
//|  Mechanical version of a discretionary Nasdaq futures scalp:     |
//|  zones marked before 09:30 NY on 15-minute bars, 1-minute        |
//|  rejection candle at a zone, entry on the break of that candle,  |
//|  fixed 25-tick (6.25 point) stop and target.                     |
//|  Built for US100 (FP Markets). Part of github.com/TinoSea/orb-bot|
//|  Not financial advice. TEST WITH "Every tick based on real ticks"|
//+------------------------------------------------------------------+
//
//  Rules (research/hypotheses.md, H-004):
//    Zones (fixed at 09:30 NY): on InpZoneTF bars from 18:00 NY the previous evening to 09:30,
//      an impulse candle has body >= InpImpulseATR x ATR(14) and >= InpImpulseBody of its range.
//      The candle before it is the zone (low..high): demand if the impulse is up, supply if down.
//      Dropped if a later zone-TF close goes through its far side before 09:30. Keep the newest
//      InpMaxZones of each kind.
//    Signal (closed 1-minute bar, 09:30-11:00 NY): SELL when the bar's high reaches a supply
//      zone, the bar is bearish, and it closes below the zone low; trigger = bar low - 1 tick.
//      BUY mirrors at demand; trigger = bar high + 1 tick. Armed for InpArmBars bars.
//    Entry: market order when price crosses the trigger. Stop = target = InpStopPts (1:1).
//    Each zone trades once; a 1-minute close through a zone's far side removes it.
//    Limits: one position; max InpMaxTrades a day; stop after InpMaxLosses losses; no entries
//      after 11:00; flat at 11:30 or after InpMaxHoldMin minutes; no Friday trading.
//    Skip an entry if spread > InpMaxSpreadFrac x stop. Risk % per trade sizing.
//
//  Variants (H-004 amendment 1), all off by default = V0:
//    V1 InpEntrySec = 15       entry candles of 15 seconds built from ticks (bid)
//    V2 InpTrendEMA = 20       buys only above EMA(20) of zone-TF closes, sells only below
//    V3 InpLondonBias = true   London (03:00-08:00 NY) high taken and low not -> sells only; mirror
//    V4 InpChopATR = 1.0       no new signal if the last 30 one-minute bars span < 1.0 x ATR(14, zone TF)
//    V5 all of the above
//
#property copyright   "orb-bot"
#property version     "1.10"
#property description "H-004: supply/demand rejection scalp at the NY open (built for US100)."
#property description "Test only with 'Every tick based on real ticks'."

#include <Trade\Trade.mqh>

//--- inputs ---------------------------------------------------------
input group "Zones (marked before the open)"
input ENUM_TIMEFRAMES InpZoneTF = PERIOD_M15; // Zone timeframe
input double InpImpulseATR     = 1.5;      // Impulse candle body >= this x ATR(14) of the zone timeframe
input double InpImpulseBody    = 0.6;      // Impulse candle body >= this share of its range
input string InpZoneFromNY     = "18:00";  // Zones built from this NY time the previous evening...
input int    InpMaxZones       = 6;        // Keep this many newest zones of each kind

input group "Entries (1-minute bars)"
input string InpSessionStartNY = "09:30";  // Signals from (NY) - zones are fixed at this time
input string InpEntryEndNY     = "11:00";  // No new entries from (NY)
input string InpFlatNY         = "11:30";  // Close everything at (NY)
input int    InpEntrySec       = 60;       // Entry candle length in seconds (60 = 1-minute; V1 = 15)
input int    InpArmBars        = 3;        // A trigger stays armed for this many entry candles
input double InpStopPts        = 6.25;     // Stop distance in index points (25 NQ ticks)
input double InpTargetPts      = 6.25;     // Target distance in index points (25 NQ ticks)
input int    InpMaxHoldMin     = 15;       // Close a trade after this many minutes
input bool   InpSkipFriday     = true;     // No trading on Fridays

input group "Filters (H-004 amendment 1) - all off = V0"
input int    InpTrendEMA       = 0;        // V2: EMA period on zone-TF closes (0 = off; 20 for V2)
input bool   InpLondonBias     = false;    // V3: London sweep bias
input string InpLondonStartNY  = "03:00";  // V3: London range from (NY)
input string InpLondonEndNY    = "08:00";  // V3: London range until (NY)
input double InpChopATR        = 0.0;      // V4: skip if the last InpChopMinutes span < this x ATR(14, zone TF) (0 = off; 1.0 for V4)
input int    InpChopMinutes    = 30;       // V4: look-back in minutes

input group "Risk (hard limits)"
input double InpRiskPercent    = 1.0;      // Risk per trade, % of balance
input int    InpMaxTrades      = 4;        // Max trades per day
input int    InpMaxLosses      = 2;        // Stop for the day after this many losses
input double InpMaxSpreadFrac  = 0.30;     // Skip entry if spread > this fraction of the stop
input double InpKillSwitchPct  = 15.0;     // Live/demo: stop for good after this % drawdown from peak equity
input bool   InpResetKillSwitch = false;   // Set true ONCE to clear a tripped kill switch
input bool   InpAllowLive      = false;    // Must be true to run on a real-money account

input group "Research (Strategy Tester only - ignored on demo/live)"
input datetime InpTesterStopAt = D'2025.07.01 00:00'; // Tester: stop here (out-of-sample lock). 1970.01.01 = off, for the ONE out-of-sample run

input group "Clock"
input int    InpServerMinusNY  = 7;        // Server time minus New York time, hours (FP Markets = 7)
input bool   InpAutoDetectClock = true;    // Live/demo only: detect from the broker clock

input group "Other"
input long   InpMagic          = 202614;   // Magic number
input bool   InpWriteJournal   = true;     // Write every fill to MQL5/Files/SD_journal.csv
input bool   InpPushNotify     = true;     // Phone alerts (live/demo only)
input bool   InpLogZones       = true;     // Print every zone and signal (for the trade audit)

//--- state ----------------------------------------------------------
struct Zone
  {
   double            lo;
   double            hi;
   int               type;     // +1 demand, -1 supply
   datetime          formed;   // server time of the impulse candle
   bool              active;
  };

CTrade   trade;
Zone     g_z[];
int      g_offsetHrs   = 7;
int      g_nyDay       = -1;
bool     g_zonesBuilt  = false;
// entry candles built from ticks
long     g_barKey      = -1;
double   g_bo = 0.0, g_bh = 0.0, g_bl = 0.0, g_bc = 0.0;
// filters
int      g_emaHandle   = INVALID_HANDLE;
int      g_atrHandle   = INVALID_HANDLE;
int      g_lonStart    = 0;
int      g_lonEnd      = 0;
bool     g_lonValid    = false;
double   g_lonHi       = 0.0;
double   g_lonLo       = 0.0;
bool     g_sweptHi     = false;
bool     g_sweptLo     = false;
int      g_sessStart   = 0;
int      g_entryEnd    = 0;
int      g_flat        = 0;
int      g_zoneFrom    = 0;
int      g_dayTrades   = 0;
int      g_dayLosses   = 0;
bool     g_lockDone    = false;
string   g_gvPeak      = "";
string   g_gvKill      = "";
// armed trigger
int      g_armDir      = 0;
double   g_armPrice    = 0.0;
datetime g_armExpiry   = 0;
int      g_armZone     = -1;
bool     g_armSpreadLogged = false;
// journal extras
double   g_entryRisk   = 0.0;
double   g_entrySpread = 0.0;
int      g_entryZone   = -1;

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
void Notify(const string msg)
  {
   Print(msg);
   if(!InpPushNotify || MQLInfoInteger(MQL_TESTER) || MQLInfoInteger(MQL_OPTIMIZATION))
      return;
   if(!TerminalInfoInteger(TERMINAL_NOTIFICATIONS_ENABLED))
      return;
   string text = "SD " + _Symbol + ": " + msg;
   if(StringLen(text) > 255)
      text = StringSubstr(text, 0, 255);
   SendNotification(text);
  }

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
   if(det >= 0 && det <= 14)
      g_offsetHrs = det;
  }

double NormPrice(double p)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts > 0)
      p = MathRound(p / ts) * ts;
   return NormalizeDouble(p, _Digits);
  }

double TickSize()
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   return (ts > 0) ? ts : _Point;
  }

double ValuePerPoint()
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(ts <= 0 || tv <= 0)
      return 0.0;
   return tv / ts;
  }

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

void CloseAll(const string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !IsMine())
         continue;
      if(trade.PositionClose(t))
         PrintFormat("Closed position #%I64u (%s)", t, reason);
     }
  }

void Disarm()
  {
   g_armDir  = 0;
   g_armZone = -1;
   g_armSpreadLogged = false;
  }

//+------------------------------------------------------------------+
//| Zones                                                             |
//+------------------------------------------------------------------+
// Builds the day's zones from closed zone-TF bars between InpZoneFromNY (previous evening)
// and the session start. Called once per NY day, at the first tick at or after the start.
void BuildZones(const datetime nyNow)
  {
   ArrayResize(g_z, 0);
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int got = CopyRates(_Symbol, InpZoneTF, 1, 300, r);      // oldest first, last CLOSED bar at the end
   if(got < 30)
     {
      Print("Zones: not enough history.");
      return;
     }
   // NY window: previous calendar day at InpZoneFromNY .. today at session start
   MqlDateTime s;
   TimeToStruct(nyNow, s);
   long todayMid = (long)nyNow - (s.hour * 3600 + s.min * 60 + s.sec);
   long winStart = todayMid - 86400 + (long)g_zoneFrom * 60;
   long winEnd   = todayMid + (long)g_sessStart * 60;
   long barSecs  = PeriodSeconds(InpZoneTF);

   // true range and ATR(14), simple average (as MT5 iATR)
   double tr[];
   ArrayResize(tr, got);
   for(int i = 0; i < got; i++)
     {
      double hl = r[i].high - r[i].low;
      if(i == 0)
         tr[i] = hl;
      else
         tr[i] = MathMax(hl, MathMax(MathAbs(r[i].high - r[i - 1].close), MathAbs(r[i].low - r[i - 1].close)));
     }

   Zone tmp[];
   ArrayResize(tmp, 0);
   for(int j = 15; j < got; j++)
     {
      long nyOpen = (long)ToNY(r[j].time);
      if(nyOpen < winStart || nyOpen + barSecs > winEnd)   // impulse bar must close inside the window
         continue;
      double atr = 0.0;
      for(int k = j - 14; k < j; k++)
         atr += tr[k];
      atr /= 14.0;
      double body  = MathAbs(r[j].close - r[j].open);
      double range = r[j].high - r[j].low;
      if(atr <= 0 || range <= 0 || body < InpImpulseATR * atr || body < InpImpulseBody * range)
         continue;
      Zone z;
      z.lo     = r[j - 1].low;
      z.hi     = r[j - 1].high;
      z.type   = (r[j].close > r[j].open) ? 1 : -1;
      z.formed = r[j].time;
      z.active = true;
      // invalidation by any later closed bar before the session start
      for(int m = j + 1; m < got; m++)
        {
         long nyM = (long)ToNY(r[m].time);
         if(nyM + barSecs > winEnd)
            break;
         if((z.type > 0 && r[m].close < z.lo) || (z.type < 0 && r[m].close > z.hi))
           {
            z.active = false;
            break;
           }
        }
      if(!z.active)
         continue;
      int n = ArraySize(tmp);
      ArrayResize(tmp, n + 1);
      tmp[n] = z;
     }
   // keep the newest InpMaxZones of each kind
   int keptD = 0, keptS = 0;
   for(int i = ArraySize(tmp) - 1; i >= 0; i--)
     {
      if(tmp[i].type > 0 && keptD >= InpMaxZones)
         continue;
      if(tmp[i].type < 0 && keptS >= InpMaxZones)
         continue;
      if(tmp[i].type > 0)
         keptD++;
      else
         keptS++;
      int n = ArraySize(g_z);
      ArrayResize(g_z, n + 1);
      g_z[n] = tmp[i];
     }
   if(InpLogZones)
     {
      PrintFormat("Zones for %s: %d demand, %d supply", TimeToString(nyNow, TIME_DATE), keptD, keptS);
      for(int i = 0; i < ArraySize(g_z); i++)
         PrintFormat("  zone %d %s %.2f-%.2f (impulse bar %s server)", i, (g_z[i].type > 0) ? "DEMAND" : "SUPPLY",
                     g_z[i].lo, g_z[i].hi, TimeToString(g_z[i].formed, TIME_DATE | TIME_MINUTES));
     }
  }

// V3: London range (InpLondonStartNY..InpLondonEndNY NY) and whether it was taken out before the session.
void BuildLondon(const datetime nyNow)
  {
   g_lonValid = false;
   g_sweptHi  = false;
   g_sweptLo  = false;
   if(!InpLondonBias)
      return;
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int got = CopyRates(_Symbol, PERIOD_M1, 0, 900, r);
   if(got < 60)
      return;
   MqlDateTime s;
   TimeToStruct(nyNow, s);
   long todayMid = (long)nyNow - (s.hour * 3600 + s.min * 60 + s.sec);
   long lonA = todayMid + (long)g_lonStart * 60, lonB = todayMid + (long)g_lonEnd * 60;
   long sess = todayMid + (long)g_sessStart * 60;
   double hi = 0.0, lo = 0.0;
   bool any = false;
   for(int i = 0; i < got; i++)
     {
      long ny = (long)ToNY(r[i].time);
      if(ny >= lonA && ny < lonB)
        {
         if(!any)
           {
            hi = r[i].high;
            lo = r[i].low;
            any = true;
           }
         hi = MathMax(hi, r[i].high);
         lo = MathMin(lo, r[i].low);
        }
     }
   if(!any)
      return;
   g_lonHi = hi;
   g_lonLo = lo;
   g_lonValid = true;
   for(int i = 0; i < got; i++)
     {
      long ny = (long)ToNY(r[i].time);
      if(ny >= lonB && ny < sess)
        {
         if(r[i].high > g_lonHi)
            g_sweptHi = true;
         if(r[i].low < g_lonLo)
            g_sweptLo = true;
        }
     }
   if(InpLogZones)
      PrintFormat("London range %.2f-%.2f; before the open: high taken %s, low taken %s",
                  g_lonLo, g_lonHi, g_sweptHi ? "yes" : "no", g_sweptLo ? "yes" : "no");
  }

// V2 + V3: may a signal in direction d be taken?
bool Allowed(const int d, string &why)
  {
   if(InpTrendEMA > 0 && g_emaHandle != INVALID_HANDLE)
     {
      double e[];
      if(CopyBuffer(g_emaHandle, 0, 1, 1, e) == 1)
        {
         double c1 = iClose(_Symbol, InpZoneTF, 1);
         if((d > 0 && c1 <= e[0]) || (d < 0 && c1 >= e[0]))
           {
            why = StringFormat("EMA filter (close %.2f vs EMA %.2f)", c1, e[0]);
            return false;
           }
        }
     }
   if(InpLondonBias && g_lonValid)
     {
      int b = 0;
      if(g_sweptHi && !g_sweptLo)
         b = -1;
      else
         if(g_sweptLo && !g_sweptHi)
            b = 1;
      if(b != 0 && b != d)
        {
         why = (b < 0) ? "London bias: sells only" : "London bias: buys only";
         return false;
        }
     }
   return true;
  }

// V4: is the market consolidating?
bool Choppy()
  {
   if(InpChopATR <= 0.0 || g_atrHandle == INVALID_HANDLE)
      return false;
   MqlRates r[];
   if(CopyRates(_Symbol, PERIOD_M1, 1, InpChopMinutes, r) != InpChopMinutes)
      return false;
   double hi = r[0].high, lo = r[0].low;
   for(int i = 1; i < InpChopMinutes; i++)
     {
      hi = MathMax(hi, r[i].high);
      lo = MathMin(lo, r[i].low);
     }
   double a[];
   if(CopyBuffer(g_atrHandle, 0, 1, 1, a) != 1 || a[0] <= 0)
      return false;
   return (hi - lo) < InpChopATR * a[0];
  }

// Called on each closed entry candle (InpEntrySec seconds) inside the signal window.
void OnClosedBar(const double o, const double h, const double l, const double c, const datetime start)
  {
   if(g_lonValid)
     {
      if(h > g_lonHi)
         g_sweptHi = true;
      if(l < g_lonLo)
         g_sweptLo = true;
     }
   // 1. zones broken by this close are removed
   for(int i = 0; i < ArraySize(g_z); i++)
     {
      if(!g_z[i].active)
         continue;
      if((g_z[i].type > 0 && c < g_z[i].lo) || (g_z[i].type < 0 && c > g_z[i].hi))
        {
         g_z[i].active = false;
         if(g_armZone == i)
            Disarm();
         if(InpLogZones)
            PrintFormat("  zone %d broken by the candle close %.2f", i, c);
        }
     }
   // 2. a new rejection arms a trigger (newest zone first); an existing armed trigger is kept
   if(g_armDir != 0 || MyPositions() > 0)
      return;
   bool chop = Choppy();
   double tick = TickSize();
   for(int i = 0; i < ArraySize(g_z); i++)
     {
      if(!g_z[i].active)
         continue;
      int d = 0;
      if(g_z[i].type < 0 && h >= g_z[i].lo && c < o && c < g_z[i].lo)
         d = -1;
      else
         if(g_z[i].type > 0 && l <= g_z[i].hi && c > o && c > g_z[i].hi)
            d = 1;
      if(d == 0)
         continue;
      string why = "";
      if(chop)
         why = "consolidation filter";
      if(chop || !Allowed(d, why))
        {
         if(InpLogZones)
            PrintFormat("  signal %s at zone %d blocked: %s", (d > 0) ? "BUY" : "SELL", i, why);
         continue;
        }
      g_armDir   = d;
      g_armPrice = NormPrice((d > 0) ? h + tick : l - tick);
      if(g_armDir != 0)
        {
         g_armZone   = i;
         g_armExpiry = (datetime)((long)start + (long)(InpArmBars + 1) * InpEntrySec);
         if(InpLogZones)
            PrintFormat("  SIGNAL %s at zone %d (%.2f-%.2f): rejection bar o%.2f h%.2f l%.2f c%.2f, trigger %.2f",
                        (g_armDir > 0) ? "BUY" : "SELL", i, g_z[i].lo, g_z[i].hi, o, h, l, c, g_armPrice);
         return;
        }
     }
  }

void TryTrigger(const datetime nyNow)
  {
   if(g_armDir == 0)
      return;
   if(TimeCurrent() >= g_armExpiry)
     {
      if(InpLogZones)
         Print("  trigger expired");
      Disarm();
      return;
     }
   if(MinuteOfDay(nyNow) >= g_entryEnd || g_dayTrades >= InpMaxTrades || g_dayLosses >= InpMaxLosses)
     {
      Disarm();
      return;
     }
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk))
      return;
   bool hit = (g_armDir > 0) ? (tk.ask >= g_armPrice) : (tk.bid <= g_armPrice);
   if(!hit)
      return;
   double spread = tk.ask - tk.bid;
   if(spread > InpMaxSpreadFrac * InpStopPts)
     {
      if(!g_armSpreadLogged)
         PrintFormat("  entry held back: spread %.2f is above %.0f%% of the %.2f stop", spread,
                     100 * InpMaxSpreadFrac, InpStopPts);
      g_armSpreadLogged = true;
      return;
     }
   double vpp    = ValuePerPoint();
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(vpp <= 0 || step <= 0)
      return;
   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0;
   double lots = MathFloor(riskMoney / (InpStopPts * vpp) / step + 1e-9) * step;
   lots = MathMin(lots, maxLot);
   if(lots < minLot - 1e-9)
     {
      Notify(StringFormat("Entry skipped: the smallest trade would risk %.2f, above %.2f%% of balance.",
                          minLot * InpStopPts * vpp, InpRiskPercent));
      Disarm();
      return;
     }
   int volDigits = (int)MathMax(0.0, MathCeil(-MathLog10(step) - 1e-9));
   lots = NormalizeDouble(lots, volDigits);
   double entry = (g_armDir > 0) ? tk.ask : tk.bid;
   double sl = NormPrice(entry - g_armDir * InpStopPts);
   double tp = NormPrice(entry + g_armDir * InpTargetPts);
   bool ok = (g_armDir > 0) ? trade.Buy(lots, _Symbol, 0.0, sl, tp, "SD buy")
                            : trade.Sell(lots, _Symbol, 0.0, sl, tp, "SD sell");
   uint rc = trade.ResultRetcode();
   if(ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED))
     {
      g_entryRisk   = lots * InpStopPts * vpp;
      g_entrySpread = spread;
      g_entryZone   = g_armZone;
      g_dayTrades++;
      if(g_armZone >= 0 && g_armZone < ArraySize(g_z))
         g_z[g_armZone].active = false;                         // each zone trades once
      Notify(StringFormat("ENTERED %s %.2f lots @ %.2f | stop %.2f | target %.2f | risk %.2f | spread %.2f | zone %d",
                          (g_armDir > 0) ? "LONG" : "SHORT", lots, trade.ResultPrice(), sl, tp,
                          g_entryRisk, spread, g_armZone));
      Disarm();
     }
   else
      PrintFormat("Entry FAILED: %u %s", rc, trade.ResultRetcodeDescription());
  }

void ManagePosition(const datetime nyNow)
  {
   if(MyPositions() == 0)
      return;
   if(MinuteOfDay(nyNow) >= g_flat)
     {
      CloseAll("flat time");
      return;
     }
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !IsMine())
         continue;
      long held = (long)TimeCurrent() - (long)PositionGetInteger(POSITION_TIME);
      if(held >= (long)InpMaxHoldMin * 60 && trade.PositionClose(t))
         PrintFormat("Closed position #%I64u (time stop %d min)", t, InpMaxHoldMin);
     }
  }

//+------------------------------------------------------------------+
//| Kill switch (live/demo only)                                     |
//+------------------------------------------------------------------+
bool KillSwitch()
  {
   if(MQLInfoInteger(MQL_TESTER))
      return false;                       // research mode: measure the strategy itself
   if(GlobalVariableCheck(g_gvKill))
     {
      if(MyPositions() > 0)
         CloseAll("kill switch");
      return true;
     }
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);
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
      Notify(StringFormat("KILL SWITCH: equity %.2f is %.1f%% below peak %.2f. Stopped until reset.",
                          eq, 100.0 * (1.0 - eq / peak), peak));
      return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Exits: day counters, alerts, journal                             |
//+------------------------------------------------------------------+
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
   if(HistoryDealGetInteger(d, DEAL_MAGIC) != InpMagic)
     {
      // exits by stop/target carry the position's magic in most builds; check the position history too
      bool ours = false;
      if(HistorySelectByPosition(pid))
         for(int i = 0; i < HistoryDealsTotal(); i++)
           {
            ulong x = HistoryDealGetTicket(i);
            if(x != 0 && HistoryDealGetInteger(x, DEAL_MAGIC) == InpMagic)
               ours = true;
           }
      if(!ours)
         return;
     }
   MqlTick tk;
   double spreadNow = SymbolInfoTick(_Symbol, tk) ? tk.ask - tk.bid : 0.0;
   if(entry == DEAL_ENTRY_OUT || entry == DEAL_ENTRY_OUT_BY)
     {
      double total = 0.0;
      if(HistorySelectByPosition(pid))
         for(int i = 0; i < HistoryDealsTotal(); i++)
           {
            ulong x = HistoryDealGetTicket(i);
            if(x != 0)
               total += HistoryDealGetDouble(x, DEAL_PROFIT) + HistoryDealGetDouble(x, DEAL_COMMISSION)
                        + HistoryDealGetDouble(x, DEAL_SWAP);
           }
      if(total < 0)
         g_dayLosses++;
      string why = (reason == DEAL_REASON_SL) ? "STOP" : (reason == DEAL_REASON_TP) ? "TARGET" : "TIME/FLAT";
      Notify(StringFormat("EXIT %s: %+.2fR (%+.2f) | spread at exit %.2f", why,
                          (g_entryRisk > 0) ? total / g_entryRisk : 0.0, total, spreadNow));
     }
   if(!InpWriteJournal)
      return;
   int h = FileOpen("SD_journal.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE)
      return;
   if(FileSize(h) == 0)
      FileWrite(h, "server_time", "ny_time", "entry", "side", "lots", "price", "profit", "commission", "swap",
                "reason", "balance", "risk_money", "spread", "zone");
   FileSeek(h, 0, SEEK_END);
   bool isIn = (entry == DEAL_ENTRY_IN);
   FileWrite(h, TimeToString(t, TIME_DATE | TIME_SECONDS), TimeToString(ToNY(t), TIME_DATE | TIME_SECONDS),
             isIn ? "IN" : "OUT", (type == DEAL_TYPE_BUY) ? "BUY" : "SELL", DoubleToString(vol, 2),
             DoubleToString(price, _Digits), DoubleToString(profit, 2), DoubleToString(comm, 2),
             DoubleToString(swap, 2),
             (reason == DEAL_REASON_SL) ? "stop" : (reason == DEAL_REASON_TP) ? "target" : "bot",
             DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2),
             DoubleToString(g_entryRisk, 2), DoubleToString(isIn ? g_entrySpread : spreadNow, _Digits),
             IntegerToString(g_entryZone));
   FileClose(h);
  }

//+------------------------------------------------------------------+
//| Lifecycle                                                        |
//+------------------------------------------------------------------+
int OnInit()
  {
   Print("SD_Scalp version 1.10 (H-004 + amendment 1). Use 'Every tick based on real ticks' in the tester.");
   if(InpRiskPercent <= 0.0 || InpRiskPercent > 3.0)
     {
      Print("RiskPercent must be between 0.01 and 3.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpStopPts <= 0 || InpTargetPts <= 0 || InpArmBars < 1 || InpMaxZones < 1 || InpMaxHoldMin < 1)
     {
      Print("Check stop/target, armed bars, zones and hold time (all must be positive).");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(PeriodSeconds(InpZoneTF) <= 60)
     {
      Print("The zone timeframe must be above 1 minute.");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpEntrySec < 5 || InpEntrySec > 60 || 60 % InpEntrySec != 0)
     {
      Print("EntrySec must divide 60 (5, 10, 15, 20, 30 or 60).");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpTrendEMA < 0 || InpChopATR < 0 || InpChopMinutes < 2)
     {
      Print("Check the filter inputs.");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_lonStart = ParseHHMM(InpLondonStartNY);
   g_lonEnd   = ParseHHMM(InpLondonEndNY);
   if(InpLondonBias && (g_lonStart < 0 || g_lonEnd <= g_lonStart))
     {
      Print("Check the London times (HH:MM, end after start).");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpTrendEMA > 0)
      g_emaHandle = iMA(_Symbol, InpZoneTF, InpTrendEMA, 0, MODE_EMA, PRICE_CLOSE);
   if(InpChopATR > 0)
      g_atrHandle = iATR(_Symbol, InpZoneTF, 14);
   if((InpTrendEMA > 0 && g_emaHandle == INVALID_HANDLE) || (InpChopATR > 0 && g_atrHandle == INVALID_HANDLE))
     {
      Print("Could not create the filter indicators.");
      return INIT_FAILED;
     }
   PrintFormat("Variant: entry candles %d s | EMA %d | London bias %s | consolidation filter %.2f x ATR over %d min",
               InpEntrySec, InpTrendEMA, InpLondonBias ? "on" : "off", InpChopATR, InpChopMinutes);
   g_sessStart = ParseHHMM(InpSessionStartNY);
   g_entryEnd  = ParseHHMM(InpEntryEndNY);
   g_flat      = ParseHHMM(InpFlatNY);
   g_zoneFrom  = ParseHHMM(InpZoneFromNY);
   if(g_sessStart < 0 || g_entryEnd <= g_sessStart || g_flat < g_entryEnd || g_zoneFrom < 0)
     {
      Print("Check the session times (HH:MM; entry end after start; flat after entry end).");
      return INIT_PARAMETERS_INCORRECT;
     }
   bool isReal = (AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL);
   if(isReal && !InpAllowLive && !MQLInfoInteger(MQL_TESTER))
     {
      Alert("SD_Scalp refused to start: REAL-money account. Demo first, or set AllowLive = true.");
      return INIT_FAILED;
     }
   trade.SetExpertMagicNumber((ulong)InpMagic);
   trade.SetDeviationInPoints(30);
   trade.SetTypeFillingBySymbol(_Symbol);
   string base = StringFormat("SD_%I64d_%s_%I64d", AccountInfoInteger(ACCOUNT_LOGIN), _Symbol, InpMagic);
   g_gvPeak = base + "_peak";
   g_gvKill = base + "_kill";
   if(InpResetKillSwitch)
     {
      GlobalVariableDel(g_gvKill);
      GlobalVariableDel(g_gvPeak);
     }
   if(!MQLInfoInteger(MQL_TESTER) && !GlobalVariableCheck(g_gvPeak))
      GlobalVariableSet(g_gvPeak, AccountInfoDouble(ACCOUNT_EQUITY));
   UpdateClock();
   double vpp = ValuePerPoint();
   PrintFormat("SD_Scalp on %s | %.4f per point per lot | min lot %.2f | stop %.2f pts = %.2f per lot | clock NY+%d",
               _Symbol, vpp, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), InpStopPts, InpStopPts * vpp, g_offsetHrs);
   if(MQLInfoInteger(MQL_TESTER) && InpTesterStopAt > 0)
      Print("Out-of-sample lock: the test stops at " + TimeToString(InpTesterStopAt) + " server time.");
   return INIT_SUCCEEDED;
  }

// Builds entry candles of InpEntrySec seconds from bid ticks; a candle closes when the first
// tick of the next one arrives.
void FeedTick()
  {
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk))
      return;
   long key = (long)tk.time / InpEntrySec;
   if(key != g_barKey)
     {
      if(g_barKey >= 0)
         OnClosedBar(g_bo, g_bh, g_bl, g_bc, (datetime)(g_barKey * InpEntrySec));
      g_barKey = key;
      g_bo = tk.bid;
      g_bh = tk.bid;
      g_bl = tk.bid;
      g_bc = tk.bid;
     }
   else
     {
      g_bh = MathMax(g_bh, tk.bid);
      g_bl = MathMin(g_bl, tk.bid);
      g_bc = tk.bid;
     }
  }

void OnDeinit(const int reason)
  {
   if(g_emaHandle != INVALID_HANDLE)
      IndicatorRelease(g_emaHandle);
   if(g_atrHandle != INVALID_HANDLE)
      IndicatorRelease(g_atrHandle);
  }

void OnTick()
  {
   if(MQLInfoInteger(MQL_TESTER) && InpTesterStopAt > 0 && TimeCurrent() >= InpTesterStopAt)
     {
      if(!g_lockDone)
        {
         CloseAll("end of in-sample");
         Print("OUT-OF-SAMPLE LOCK: test stopped at " + TimeToString(TimeCurrent()) + ".");
         g_lockDone = true;
         TesterStop();
        }
      return;
     }
   datetime nyNow = ToNY(TimeCurrent());
   int day = DayKey(nyNow);
   if(day != g_nyDay)
     {
      UpdateClock();
      nyNow = ToNY(TimeCurrent());
      g_nyDay = DayKey(nyNow);
      g_zonesBuilt = false;
      g_dayTrades  = 0;
      g_dayLosses  = 0;
      ArrayResize(g_z, 0);
      Disarm();
     }
   ManagePosition(nyNow);
   if(KillSwitch())
      return;

   int dow = DayOfWeek(nyNow);
   int m   = MinuteOfDay(nyNow);
   if(dow < 1 || dow > 5 || (InpSkipFriday && dow == 5))
      return;
   if(m < g_sessStart || m >= g_entryEnd)
     {
      if(g_armDir != 0)
         Disarm();
      g_barKey = -1;
      return;
     }
   if(!g_zonesBuilt)
     {
      BuildZones(nyNow);
      BuildLondon(nyNow);
      g_zonesBuilt = true;
      g_barKey = -1;                              // first candle starts at the first tick after the start
     }
   FeedTick();
   if(MyPositions() == 0)
      TryTrigger(nyNow);
  }
//+------------------------------------------------------------------+
