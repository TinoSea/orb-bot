//+------------------------------------------------------------------+
//| LK_Signals.mq5 - chart helper (draws only, never trades)         |
//| github.com/TinoSea/orb-bot                                       |
//|                                                                  |
//| Rejection candle at an earlier-day 5/15-minute fair value gap:   |
//|  - arrow on the signal candle (only after it has CLOSED: no      |
//|    repainting)                                                   |
//|  - stop-entry just beyond the candle, valid for N bars           |
//|  - red box  = entry to stop (2-3 pts past the wick)              |
//|  - green box = entry to TP3; dotted lines at TP1 and TP2         |
//|  - score panel: for each target, how often it was hit before the |
//|    stop, and the average R after costs                          |
//| Buys only at demand (green) zones, sells only at supply (red).   |
//+------------------------------------------------------------------+
#property copyright "TinoSea"
#property version   "1.00"
#property indicator_chart_window
#property indicator_buffers 0
#property indicator_plots   0

input group "Zones"
input double InpMinGap        = 5.0;     // Smallest gap (US100 5, US500 2, gold 1)
input int    InpZoneDays      = 7;       // Use gaps formed in the last N calendar days (before today)
input bool   InpFirstTouch    = true;    // One signal per zone only (first try)
input bool   InpShowZones     = true;    // Draw the live zones

input group "Signal"
input double InpWickBody      = 1.0;     // Wick must be at least this x the body
input string InpFrom          = "09:30"; // Signals from (New York time)
input string InpTo            = "11:30"; // Signals until (New York time)
input string InpFlat          = "15:55"; // Trades still open are closed at this NY time
input bool   InpNoFriday      = false;   // Skip Fridays
input int    InpMaxPerDay     = 3;       // Max signals a day

input group "Order"
input double InpEntryOff      = 0.25;    // Stop-entry this far beyond the candle
input double InpStopBuf       = 2.5;     // Stop this far past the wick
input int    InpValidBars     = 2;       // Entry order valid for this many bars
input double InpTP1           = 1.0;     // TP1 (R)
input double InpTP2           = 1.3;     // TP2 (R) - the one drawn as the result
input double InpTP3           = 2.0;     // TP3 (R)
input double InpCostPts       = 1.0;     // Spread + costs per trade, points (scoring only)

input group "Display"
input int    InpDaysBack      = 20;      // Days of history to show and score
input double InpRiskPct       = 1.0;     // Risk % for the suggested lot size
input int    InpServerMinusNY = 7;       // Server time minus New York time, hours (FTMO/FP = 7; 6 from 26-30 Oct)
input bool   InpAlert         = true;    // Pop-up alert on a new signal
input bool   InpPush          = false;   // Also send to the MT5 phone app
input color  InpStopColor     = C'110,35,35';
input color  InpTgtColor      = C'25,95,60';
input color  InpPanelColor    = clrDodgerBlue;

#define PFX "LKS_"

struct Zone { double lo, hi; bool sup; datetime formed, killed; int tfmin; bool used; };
Zone g_z[];
datetime g_lastBar = 0, g_lastAlert = 0;

//--- time helpers (New York)
datetime NY(datetime t)        { return t - InpServerMinusNY * 3600; }
int      NYDay(datetime t)     { return (int)(NY(t) / 86400); }
int      NYMin(datetime t)     { return (int)((NY(t) % 86400) / 60); }
int      HM(string s)          { return (int)StringToInteger(StringSubstr(s, 0, 2)) * 60 + (int)StringToInteger(StringSubstr(s, 3, 2)); }
int      NYDow(datetime t)     { MqlDateTime s; TimeToStruct(NY(t), s); return s.day_of_week; }

//+------------------------------------------------------------------+
void AddZones(ENUM_TIMEFRAMES tf, datetime from, datetime to)
  {
   MqlRates r[];
   int n = CopyRates(_Symbol, tf, from, to, r);
   if(n < 4) return;
   int ps = PeriodSeconds(tf);
   for(int k = 2; k < n - 1; k++)              // n-1 is still forming: ignore
     {
      bool sup = r[k].high < r[k - 2].low, dem = r[k].low > r[k - 2].high;
      if(!sup && !dem) continue;
      double lo = sup ? r[k].high : r[k - 2].high, hi = sup ? r[k - 2].low : r[k].low;
      if(hi - lo < InpMinGap) continue;
      datetime killed = D'2100.01.01';
      for(int m = k + 1; m < n - 1; m++)
         if((sup && r[m].close > hi) || (dem && r[m].close < lo)) { killed = r[m].time + ps; break; }
      int s = ArraySize(g_z); ArrayResize(g_z, s + 1);
      g_z[s].lo = lo; g_z[s].hi = hi; g_z[s].sup = sup; g_z[s].formed = r[k].time + ps;
      g_z[s].killed = killed; g_z[s].tfmin = ps / 60; g_z[s].used = false;
     }
  }

//--- drawing helpers
void Rect(string name, datetime t1, double p1, datetime t2, double p2, color c)
  {
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }
void Seg(string name, datetime t1, datetime t2, double p, color c, ENUM_LINE_STYLE st)
  {
   ObjectCreate(0, name, OBJ_TREND, 0, t1, p, t2, p);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_STYLE, st);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }
void Txt(string name, datetime t, double p, string s, color c)
  {
   ObjectCreate(0, name, OBJ_TEXT, 0, t, p);
   ObjectSetString(0, name, OBJPROP_TEXT, s);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }
void Arrow(string name, datetime t, double p, bool buy)
  {
   ObjectCreate(0, name, buy ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, t, p);
   ObjectSetInteger(0, name, OBJPROP_COLOR, buy ? clrLimeGreen : clrRed);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
  }
void Line(int row, string s)
  {
   string name = PFX + "panel" + IntegerToString(row);
   ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
   ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 10);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 30 + row * 16);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
   ObjectSetInteger(0, name, OBJPROP_COLOR, InpPanelColor);
   ObjectSetString(0, name, OBJPROP_TEXT, s);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
  }

double Lots(double riskPts)
  {
   double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE), ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(tv <= 0 || ts <= 0 || riskPts <= 0 || step <= 0) return 0;
   double lots = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPct / 100.0 / (riskPts * tv / ts);
   return MathFloor(lots / step) * step;
  }

//--- walk forward from the fill bar; returns R and sets exit index (-1 = still open)
double Sim(const MqlRates &b[], int n, int j, int dir, double fill, double stop, double L, int flatMin, int &exitIdx)
  {
   double risk = dir * (fill - stop), tp = fill + dir * L * risk;
   int d0 = NYDay(b[j].time), ps = PeriodSeconds();
   for(int k = j; k < n - 1; k++)
     {
      if(NYDay(b[k].time) != d0) { exitIdx = k - 1; return dir * (b[k - 1].close - fill) / risk; }
      bool hs = dir > 0 ? b[k].low <= stop : b[k].high >= stop;
      bool ht = k > j && (dir > 0 ? b[k].high >= tp : b[k].low <= tp);   // fill bar: stop only (cautious)
      if(hs) { exitIdx = k; return -1.0; }
      if(ht) { exitIdx = k; return L; }
      if(NYMin(b[k].time + ps) >= flatMin) { exitIdx = k; return dir * (b[k].close - fill) / risk; }
     }
   exitIdx = -1;
   return 0;
  }

//+------------------------------------------------------------------+
void Recalc()
  {
   ObjectsDeleteAll(0, PFX);
   ArrayResize(g_z, 0);
   datetime now = TimeCurrent();
   datetime from = now - (datetime)(InpDaysBack + InpZoneDays + 3) * 86400;
   AddZones(PERIOD_M5, from, now);
   AddZones(PERIOD_M15, from, now);

   MqlRates b[];
   int n = CopyRates(_Symbol, _Period, now - (datetime)InpDaysBack * 86400, now, b);
   if(n < 10) return;
   int ps = PeriodSeconds(), t0 = HM(InpFrom), t1 = HM(InpTo), tFlat = HM(InpFlat);
   double L[3]; L[0] = InpTP1; L[1] = InpTP2; L[2] = InpTP3;
   int win[3] = {0, 0, 0}, loss[3] = {0, 0, 0}, other[3] = {0, 0, 0};
   double sumR[3] = {0, 0, 0};
   int signals = 0, nofill = 0, open = 0, busyUntil = -1, curDay = -1, dayCount = 0;

   if(InpShowZones)
      for(int z = 0; z < ArraySize(g_z); z++)
        {
         if(g_z[z].killed <= b[0].time) continue;
         datetime e = g_z[z].killed > now ? now + 3600 : g_z[z].killed;
         Rect(PFX + "z" + IntegerToString(z), g_z[z].formed, g_z[z].lo, e, g_z[z].hi,
              g_z[z].sup ? C'60,30,40' : C'25,55,45');
        }

   for(int i = 1; i < n - 1; i++)                 // closed bars only
     {
      if(i <= busyUntil) continue;
      int d = NYDay(b[i].time), mc = NYMin(b[i].time + ps);
      if(mc < t0 || mc > t1) continue;
      if(InpNoFriday && NYDow(b[i].time) == 5) continue;
      if(d != curDay) { curDay = d; dayCount = 0; }
      if(dayCount >= InpMaxPerDay) continue;

      double body = MathAbs(b[i].close - b[i].open);
      double lw = MathMin(b[i].open, b[i].close) - b[i].low, uw = b[i].high - MathMax(b[i].open, b[i].close);
      int dir = 0, zi = -1;
      for(int z = 0; z < ArraySize(g_z) && dir == 0; z++)
        {
         if(InpFirstTouch && g_z[z].used) continue;
         if(g_z[z].formed > b[i].time || g_z[z].killed <= b[i].time) continue;
         if(NYDay(g_z[z].formed) >= d) continue;                                   // earlier days only
         if(g_z[z].formed < b[i].time - (datetime)InpZoneDays * 86400) continue;
         if(!g_z[z].sup && b[i].low <= g_z[z].hi && b[i].close >= g_z[z].lo && lw > 0 && lw >= InpWickBody * body && lw >= uw)
           { dir = 1; zi = z; }
         else if(g_z[z].sup && b[i].high >= g_z[z].lo && b[i].close <= g_z[z].hi && uw > 0 && uw >= InpWickBody * body && uw >= lw)
           { dir = -1; zi = z; }
        }
      if(dir == 0) continue;
      g_z[zi].used = true; dayCount++; signals++;
      string id = PFX + IntegerToString(i) + "_";
      double trig = dir > 0 ? b[i].high + InpEntryOff : b[i].low - InpEntryOff;
      double stop = dir > 0 ? b[i].low - InpStopBuf : b[i].high + InpStopBuf;
      Arrow(id + "a", b[i].time, dir > 0 ? b[i].low : b[i].high, dir > 0);

      // fill?
      int j = -1; bool pending = false;
      for(int k = i + 1; k <= i + InpValidBars; k++)
        {
         if(k >= n - 1) { pending = true; break; }
         if(dir > 0 ? b[k].high >= trig : b[k].low <= trig) { j = k; break; }
        }
      if(j < 0)
        {
         if(pending)
           {
            double rp = MathAbs(trig - stop);
            datetime e = b[n - 1].time + 10 * ps;
            Seg(id + "pe", b[i].time, e, trig, clrSilver, STYLE_DASH);
            Seg(id + "ps", b[i].time, e, stop, clrRed, STYLE_DASH);
            Seg(id + "pt", b[i].time, e, trig + dir * InpTP2 * rp, clrLimeGreen, STYLE_DASH);
            string msg = StringFormat("LK_Signals %s %s: %s STOP at %s, SL %s, TP1 %s TP2 %s TP3 %s, risk %.1f pts = %.2f lots at %.1f%%",
                         _Symbol, TimeToString(b[i].time, TIME_MINUTES), dir > 0 ? "BUY" : "SELL",
                         DoubleToString(trig, _Digits), DoubleToString(stop, _Digits),
                         DoubleToString(trig + dir * InpTP1 * rp, _Digits), DoubleToString(trig + dir * InpTP2 * rp, _Digits),
                         DoubleToString(trig + dir * InpTP3 * rp, _Digits), rp, Lots(rp), InpRiskPct);
            if(b[i].time > g_lastAlert)
              {
               g_lastAlert = b[i].time;
               if(InpAlert) Alert(msg);
               if(InpPush) SendNotification(msg);
              }
           }
         else { nofill++; Txt(id + "nf", b[i].time, dir > 0 ? b[i].low : b[i].high, "  no fill", clrGray); }
         continue;
        }

      double fill = dir > 0 ? MathMax(trig, b[j].open) : MathMin(trig, b[j].open);
      double risk = dir * (fill - stop);
      if(risk <= 0) continue;
      double costR = InpCostPts / risk;
      int exitMain = -1;
      for(int l = 0; l < 3; l++)
        {
         int ex;
         double R = Sim(b, n, j, dir, fill, stop, L[l], tFlat, ex);
         if(l == 1) exitMain = ex;
         if(ex < 0) { if(l == 1) open++; continue; }
         if(R >= L[l] - 1e-9) win[l]++; else if(R <= -1 + 1e-9) loss[l]++; else other[l]++;
         sumR[l] += R - costR;
        }
      datetime te = exitMain < 0 ? b[n - 1].time + 5 * ps : b[exitMain].time + ps;
      Rect(id + "s", b[j].time, fill, te, stop, InpStopColor);
      Rect(id + "t", b[j].time, fill, te, fill + dir * InpTP3 * risk, InpTgtColor);
      Seg(id + "t1", b[j].time, te, fill + dir * InpTP1 * risk, clrSilver, STYLE_DOT);
      Seg(id + "t2", b[j].time, te, fill + dir * InpTP2 * risk, clrWhite, STYLE_DOT);
      if(exitMain >= 0)
        {
         int ex2; double R2 = Sim(b, n, j, dir, fill, stop, InpTP2, tFlat, ex2);
         Txt(id + "r", te, dir > 0 ? fill + dir * InpTP3 * risk : fill + dir * InpTP3 * risk,
             StringFormat("%+.2fR", R2), R2 > 0 ? clrLimeGreen : clrTomato);
         busyUntil = exitMain;
        }
      else busyUntil = n;
     }

   // panel
   int filled = signals - nofill;
   Line(0, StringFormat("LK_Signals  %s  last %d days  (costs %.2f pts/trade)", _Symbol, InpDaysBack, InpCostPts));
   Line(1, StringFormat("Signals %d   filled %d   no fill %d   open %d", signals, filled, nofill, open));
   for(int l = 0; l < 3; l++)
     {
      int done = win[l] + loss[l] + other[l];
      Line(2 + l, StringFormat("TP%d %.1fR: hit %d  stop %d  time %d  win %4.0f%%  avg %+.2fR",
                                l + 1, L[l], win[l], loss[l], other[l],
                                done > 0 ? 100.0 * win[l] / done : 0.0, done > 0 ? sumR[l] / done : 0.0));
     }
   Line(5, filled < 30 ? "Fewer than 30 trades: too few to judge." : "Judge on avg R after costs, not win %.");
   ChartRedraw();
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   IndicatorSetString(INDICATOR_SHORTNAME, "LK_Signals");
   g_lastAlert = TimeCurrent();      // no alerts for history on load
   return(INIT_SUCCEEDED);
  }
void OnDeinit(const int reason) { ObjectsDeleteAll(0, PFX); }

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
  {
   if(rates_total < 2) return(rates_total);
   if(time[rates_total - 1] != g_lastBar)   // once per new bar
     {
      g_lastBar = time[rates_total - 1];
      Recalc();
     }
   return(rates_total);
  }
//+------------------------------------------------------------------+
