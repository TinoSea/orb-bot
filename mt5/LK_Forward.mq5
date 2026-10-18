//+------------------------------------------------------------------+
//|                                                 LK_Forward.mq5 |
//|  H-017 forward test (research/hypotheses.md). Trades La'Kera's   |
//|  zone method as a fixed rule, ON DEMO, on new days only:         |
//|   - zones: 5/15-minute fair value gaps >= InpMinGap, formed on   |
//|     the last 5 trading days BEFORE today, still unbroken;         |
//|   - first try only: each zone trades once per day;               |
//|   - time: signals 09:30-09:57 New York;                          |
//|   - 15-second rejection candle (built from ticks): touches the   |
//|     gap, closes against it, wick >= body; stop order 0.25 beyond |
//|     its extreme, valid 45 s;                                     |
//|   - stop 12.5, target 16.25 points; 15-minute cap; flat 11:45 NY;|
//|   - one position at a time, max 3 trades and 2 losses a day,     |
//|     no Fridays, 1% risk. Writes MQL5/Files/LK_journal.csv.       |
//|  Part of github.com/TinoSea/orb-bot                               |
//+------------------------------------------------------------------+
#property copyright "orb-bot"
#property version   "1.00"
#include <Trade/Trade.mqh>

input group "Rule (H-017 - do not change during the test)"
input double InpMinGap      = 5.0;     // Smallest gap, price units (US100 points)
input int    InpLookback    = 5;       // Gaps from the last N trading days before today
input double InpStopPts     = 12.5;    // Stop distance, points
input double InpTargetPts   = 16.25;   // Target distance, points (1.3R)
input double InpTriggerOff  = 0.25;    // Stop-entry offset beyond the rejection candle
input int    InpArmSec      = 45;      // Trigger valid for this many seconds
input string InpFrom        = "09:30"; // Signals from (New York)
input string InpTo          = "09:57"; // Signals until (New York)
input int    InpCapMin      = 15;      // Close a trade after this many minutes
input string InpFlat        = "11:45"; // Close anything open at this NY time
input int    InpMaxTrades   = 3;       // Max trades a day
input int    InpMaxLosses   = 2;       // Stop for the day after this many losses
input bool   InpNoFriday    = true;    // No trading on Fridays (her rule)

input group "Risk and safety"
input double InpRiskPct     = 1.0;     // Risk per trade, % of balance
input bool   InpAllowLive   = false;   // Must be true to run on a real-money account
input int    InpServerMinusNY = 7;     // Server time minus New York time, hours (FP Markets = 7)
input long   InpMagic       = 202617;  // Magic number

struct Zone { bool supply; double lo, hi; string tf; datetime formed; bool used; };

CTrade   trade;
Zone     g_z[];
datetime g_day = 0;
int      g_trades = 0, g_losses = 0;
long     g_c15 = -1;                    // current 15-second candle index
double   g_o, g_h, g_l, g_c;            // current 15-second candle (bid)
int      g_armDir = 0; double g_armTrig = 0; datetime g_armExp = 0; int g_armZone = -1;
datetime g_entryTime = 0;
datetime g_lastM5 = 0;
ulong    g_ticket = 0;

int Off() { return InpServerMinusNY * 3600; }
datetime NYMid(datetime s) { long ny = (long)s - Off(); return (datetime)(ny - ny % 86400 + Off()); }
int NYDow(datetime mid) { MqlDateTime m; TimeToStruct((datetime)((long)mid - Off()), m); return m.day_of_week; }
int HHMM(const string v) { string p[]; if(StringSplit(v, ':', p) != 2) return -1; return (int)StringToInteger(p[0]) * 60 + (int)StringToInteger(p[1]); }
int NYMin(datetime s) { return (int)(((long)s - (long)NYMid(s)) / 60); }

datetime DaysBack(datetime mid, int n)
  {
   datetime d = mid; int k = 0;
   while(k < n) { d -= 86400; int w = NYDow(d); if(w != 0 && w != 6) k++; }
   return d;
  }

void Journal(const string line)
  {
   bool exists = FileIsExist("LK_journal.csv");
   int h = FileOpen("LK_journal.csv", FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI);
   if(h == INVALID_HANDLE) return;
   FileSeek(h, 0, SEEK_END);
   if(!exists) FileWriteString(h, "time_server,event,side,price,sl,tp,zone_tf,zone_lo,zone_hi,lots,profit\r\n");
   FileWriteString(h, line + "\r\n");
   FileClose(h);
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   bool real = AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_REAL;
   if(real && !InpAllowLive)
     {
      Alert("LK_Forward: real-money account and AllowLive = false. H-017 is a DEMO test. Not trading.");
      return(INIT_FAILED);
     }
   trade.SetExpertMagicNumber(InpMagic);
   PrintFormat("LK_Forward 1.00 (H-017) on %s. Server = NY + %d h.", _Symbol, InpServerMinusNY);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void BuildZones(datetime today)
  {
   ArrayResize(g_z, 0);
   datetime since = DaysBack(today, InpLookback);
   ENUM_TIMEFRAMES tfs[2] = {PERIOD_M5, PERIOD_M15};
   string names[2] = {"5m", "15m"};
   for(int k = 0; k < 2; k++)
     {
      MqlRates r[];
      int n = CopyRates(_Symbol, tfs[k], since - 2 * PeriodSeconds(tfs[k]), TimeCurrent(), r);
      if(n < 4) continue;
      int sec = PeriodSeconds(tfs[k]);
      int last = n - 2;
      for(int i = 2; i <= last; i++)
        {
         bool sup = r[i].high < r[i - 2].low, dem = r[i].low > r[i - 2].high;
         if(!sup && !dem) continue;
         double lo = sup ? r[i].high : r[i - 2].high, hi = sup ? r[i - 2].low : r[i].low;
         datetime formed = r[i].time + sec;
         if(hi - lo < InpMinGap || formed < since || formed > today) continue;   // earlier days only
         bool dead = false;
         for(int j = i + 1; j <= last; j++)
            if((sup && r[j].close > hi) || (dem && r[j].close < lo)) { dead = true; break; }
         if(dead) continue;
         int m = ArraySize(g_z); ArrayResize(g_z, m + 1);
         g_z[m].supply = sup; g_z[m].lo = lo; g_z[m].hi = hi; g_z[m].tf = names[k]; g_z[m].formed = formed; g_z[m].used = false;
        }
     }
   PrintFormat("H-017 %s: %d earlier-day zones live.", TimeToString(today, TIME_DATE), ArraySize(g_z));
  }

void KillBrokenZones()   // a newly closed M5/M15 candle beyond the far edge ends a zone (same time frame)
  {
   MqlRates a[], b[];
   bool ok5 = CopyRates(_Symbol, PERIOD_M5, 1, 1, a) == 1, ok15 = CopyRates(_Symbol, PERIOD_M15, 1, 1, b) == 1;
   for(int i = ArraySize(g_z) - 1; i >= 0; i--)
     {
      double c = 0; bool have = false;
      if(g_z[i].tf == "5m" && ok5) { c = a[0].close; have = true; }
      if(g_z[i].tf == "15m" && ok15) { c = b[0].close; have = true; }
      if(!have) continue;
      if((g_z[i].supply && c > g_z[i].hi) || (!g_z[i].supply && c < g_z[i].lo))
        {
         for(int j = i; j < ArraySize(g_z) - 1; j++) g_z[j] = g_z[j + 1];
         ArrayResize(g_z, ArraySize(g_z) - 1);
         if(g_armZone == i) g_armDir = 0; else if(g_armZone > i) g_armZone--;
        }
     }
  }

//+------------------------------------------------------------------+
void OnClosed15(datetime closeTime)
  {
   int mm = NYMin(closeTime);
   if(mm < HHMM(InpFrom) || mm >= HHMM(InpTo)) return;
   if(PositionSelectByMagic() || g_trades >= InpMaxTrades || g_losses >= InpMaxLosses) return;
   for(int d = -1; d <= 1; d += 2)
     {
      double body = (g_o - g_c) * -d;                       // sell (d=-1): o > c
      double wick = d < 0 ? g_h - MathMax(g_o, g_c) : MathMin(g_o, g_c) - g_l;
      double tip = d < 0 ? g_h : g_l;
      if(body <= 0 || wick < body) continue;
      for(int i = 0; i < ArraySize(g_z); i++)
        {
         if(g_z[i].used || g_z[i].supply != (d < 0)) continue;
         if(tip < g_z[i].lo || tip > g_z[i].hi) continue;
         g_armDir = d; g_armZone = i; g_armExp = closeTime + InpArmSec;
         g_armTrig = d < 0 ? g_l - InpTriggerOff : g_h + InpTriggerOff;
         return;
        }
     }
  }

bool PositionSelectByMagic()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(PositionSelectByTicket(t) && PositionGetInteger(POSITION_MAGIC) == InpMagic && PositionGetString(POSITION_SYMBOL) == _Symbol)
         return true;
     }
   return false;
  }

double Lots()
  {
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP), vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(tv <= 0 || ts <= 0 || step <= 0) return 0;
   double perLotRisk = InpStopPts / ts * tv;
   double lots = MathFloor(AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct / 100.0 / perLotRisk / step) * step;
   if(lots < vmin) return 0;
   return MathMin(lots, vmax);
  }

void TryFill()
  {
   if(g_armDir == 0) return;
   datetime now = TimeCurrent();
   if(now > g_armExp || g_armZone < 0 || g_armZone >= ArraySize(g_z)) { g_armDir = 0; return; }
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID), ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double mid = (bid + ask) / 2;
   if(!(g_armDir < 0 ? mid <= g_armTrig : mid >= g_armTrig)) return;
   double lots = Lots();
   Zone z = g_z[g_armZone];
   g_z[g_armZone].used = true;                                // first try only, win or lose
   int d = g_armDir; g_armDir = 0;
   if(lots <= 0) { Print("H-017: lot too small for 1% risk - trade skipped."); return; }
   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   bool ok;
   double px = d < 0 ? bid : ask;
   double sl = NormalizeDouble(px - d * InpStopPts, dg), tp = NormalizeDouble(px + d * InpTargetPts, dg);
   ok = d < 0 ? trade.Sell(lots, _Symbol, 0, sl, tp, "H-017") : trade.Buy(lots, _Symbol, 0, sl, tp, "H-017");
   if(ok)
     {
      g_trades++; g_entryTime = now;
      Journal(StringFormat("%s,entry,%s,%s,%s,%s,%s,%s,%s,%.2f,", TimeToString(now, TIME_DATE | TIME_SECONDS), d < 0 ? "short" : "long",
              DoubleToString(trade.ResultPrice(), dg), DoubleToString(sl, dg), DoubleToString(tp, dg), z.tf,
              DoubleToString(z.lo, dg), DoubleToString(z.hi, dg), lots));
     }
  }

void ManageOpen()
  {
   if(!PositionSelectByMagic()) return;
   datetime now = TimeCurrent();
   bool cap = g_entryTime > 0 && now - g_entryTime >= InpCapMin * 60;
   bool flat = NYMin(now) >= HHMM(InpFlat);
   if(cap || flat) trade.PositionClose(PositionGetInteger(POSITION_TICKET));
  }

void OnTradeTransaction(const MqlTradeTransaction &tr, const MqlTradeRequest &rq, const MqlTradeResult &rs)
  {
   if(tr.type != TRADE_TRANSACTION_DEAL_ADD) return;
   if(!HistoryDealSelect(tr.deal)) return;
   if(HistoryDealGetInteger(tr.deal, DEAL_MAGIC) != InpMagic) return;
   if(HistoryDealGetInteger(tr.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;
   double p = HistoryDealGetDouble(tr.deal, DEAL_PROFIT) + HistoryDealGetDouble(tr.deal, DEAL_COMMISSION) + HistoryDealGetDouble(tr.deal, DEAL_SWAP);
   if(p < 0) g_losses++;
   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   Journal(StringFormat("%s,exit,,%s,,,,,,,%.2f", TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
           DoubleToString(HistoryDealGetDouble(tr.deal, DEAL_PRICE), dg), p));
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   datetime now = TimeCurrent();
   datetime today = NYMid(now);
   if(today != g_day)
     {
      g_day = today; g_trades = 0; g_losses = 0; g_armDir = 0; g_c15 = -1;
      BuildZones(today);
     }
   ManageOpen();
   int w = NYDow(today);
   if(w == 0 || w == 6 || (InpNoFriday && w == 5)) return;
   // zones broken by newly closed candles
   datetime m5[]; if(CopyTime(_Symbol, PERIOD_M5, 0, 1, m5) == 1 && m5[0] != g_lastM5) { g_lastM5 = m5[0]; KillBrokenZones(); }
   // 15-second candles from ticks (bid)
   MqlTick t; if(!SymbolInfoTick(_Symbol, t)) return;
   long k = (long)(t.time_msc / 15000);
   double b = t.bid;
   if(k != g_c15)
     {
      if(g_c15 >= 0) OnClosed15((datetime)((g_c15 + 1) * 15));
      g_c15 = k; g_o = b; g_h = b; g_l = b; g_c = b;
     }
   else { g_h = MathMax(g_h, b); g_l = MathMin(g_l, b); g_c = b; }
   if(!PositionSelectByMagic() && g_trades < InpMaxTrades && g_losses < InpMaxLosses) TryFill();
  }
//+------------------------------------------------------------------+
