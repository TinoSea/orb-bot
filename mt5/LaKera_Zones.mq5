//+------------------------------------------------------------------+
//|                                               LaKera_Zones.mq5 |
//|  CHART HELPER (indicator, places no trades). Marks the chart the  |
//|  way La'Kera's 23 Oct 2025 charts do (research/hypotheses.md,    |
//|  H-011): Asia and London session boxes, London high / 50% / low, |
//|  and 5- and 15-minute fair value gaps, kept until price closes   |
//|  through them. Alerts when price enters a gap from an EARLIER     |
//|  day during 09:30-11:30 New York time. You make every decision.   |
//|  Part of github.com/TinoSea/orb-bot                               |
//+------------------------------------------------------------------+
//
//  Fair value gap: three candles where candle 3 does not overlap candle 1.
//    supply (red):  candle 3 high  < candle 1 low   -> zone = candle 3 high .. candle 1 low
//    demand (green): candle 3 low  > candle 1 high  -> zone = candle 1 high .. candle 3 low
//  A gap stays live until a later candle of the SAME time frame closes beyond its far edge.
//  Strong colours = gaps from earlier days (the ones H-012/H-013 kept); pale = formed today.
//
#property copyright   "orb-bot"
#property version     "1.00"
#property indicator_chart_window
#property indicator_plots 0

input group "Zones (fair value gaps)"
input bool   InpShowM5        = true;     // Show 5-minute gaps
input bool   InpShowM15       = true;     // Show 15-minute gaps
input double InpMinGap        = 5.0;      // Smallest gap shown, in PRICE units (US100: 5 points; gold: ~1.0)
input int    InpLookbackDays  = 5;        // Gaps formed in the last N trading days
input bool   InpShowTodayGaps = true;     // Also show gaps formed today (pale)
input bool   InpShowMidline   = true;     // Dashed 50% line inside each gap

input group "Sessions (New York time)"
input bool   InpShowSessions  = true;     // Asia 20:00-03:00 and London 03:00-09:00 boxes
input int    InpSessionDays   = 3;        // How many days of session boxes
input bool   InpShowLondonFib = true;     // Today's London high / 50% / low lines

input group "Alerts"
input bool   InpAlerts        = true;     // Alert when price enters an earlier-day gap
input string InpAlertFrom     = "09:30";  // Alert window start (New York)
input string InpAlertTo       = "11:30";  // Alert window end (New York)
input bool   InpPush          = true;     // Also send to the MetaTrader app on your phone

input group "Clock"
input int    InpServerMinusNY = 7;        // Server time minus New York time, hours (FP Markets = 7)

input group "Colours"
input color  InpSupplyOld = C'205,92,92';   // Supply, earlier days
input color  InpSupplyNew = C'255,205,210'; // Supply, today
input color  InpDemandOld = C'60,160,110';  // Demand, earlier days
input color  InpDemandNew = C'200,235,210'; // Demand, today
input color  InpAsiaCol   = C'252,228,236'; // Asia box
input color  InpLondonCol = C'225,225,235'; // London box

const string PFX = "LKZ_";

struct Gap
  {
   bool     supply;
   double   lo, hi;
   datetime start;     // candle 2 open (box left edge)
   datetime formed;    // close of candle 3
   bool     old;       // formed before today's New York midnight
   string   tf;
   string   name;
  };

Gap      g_live[];
datetime g_lastM1 = 0;
string   g_alerted = "";
datetime g_alertDay = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   ObjectsDeleteAll(0, PFX);
   EventSetTimer(30);
   Redraw();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ObjectsDeleteAll(0, PFX);
  }

void OnTimer() { MaybeRedraw(); }

int OnCalculate(const int rates_total, const int prev_calculated, const datetime &time[],
                const double &open[], const double &high[], const double &low[], const double &close[],
                const long &tick_volume[], const long &volume[], const int &spread[])
  {
   MaybeRedraw();
   CheckAlerts();
   return(rates_total);
  }

//+------------------------------------------------------------------+
//| time helpers                                                      |
//+------------------------------------------------------------------+
int Off() { return InpServerMinusNY * 3600; }

datetime NYMidnightServer(datetime serverTime)      // server time of the NY midnight that starts this NY day
  {
   long ny = (long)serverTime - Off();
   long mid = ny - (ny % 86400);
   return (datetime)(mid + Off());
  }

int NYDayOfWeek(datetime nyMidServer)
  {
   MqlDateTime s;
   TimeToStruct((datetime)((long)nyMidServer - Off()), s);
   return s.day_of_week;
  }

int ParseHHMM(const string v)
  {
   string p[];
   if(StringSplit(v, ':', p) != 2) return -1;
   return (int)StringToInteger(p[0]) * 60 + (int)StringToInteger(p[1]);
  }

datetime TradingDaysBack(datetime todayMid, int n)  // NY midnight (server time) n trading days before today
  {
   datetime d = todayMid;
   int k = 0;
   while(k < n)
     {
      d -= 86400;
      int w = NYDayOfWeek(d);
      if(w != 0 && w != 6) k++;
     }
   return d;
  }

//+------------------------------------------------------------------+
void MaybeRedraw()
  {
   datetime m1[];
   if(CopyTime(_Symbol, PERIOD_M1, 0, 1, m1) != 1) return;
   if(m1[0] == g_lastM1) return;
   g_lastM1 = m1[0];
   Redraw();
  }

void Redraw()
  {
   ObjectsDeleteAll(0, PFX);
   ArrayResize(g_live, 0);
   datetime now = TimeCurrent();
   datetime today = NYMidnightServer(now);
   if(InpShowSessions) DrawSessions(today);
   datetime since = TradingDaysBack(today, InpLookbackDays);
   if(InpShowM15) ScanGaps(PERIOD_M15, "15m", since, today);
   if(InpShowM5)  ScanGaps(PERIOD_M5,  "5m",  since, today);
   ChartRedraw();
  }

//+------------------------------------------------------------------+
//| sessions                                                          |
//+------------------------------------------------------------------+
bool RangeHL(datetime a, datetime b, double &hi, double &lo)
  {
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M5, a, b - 1, r);
   if(n <= 0) return false;
   hi = r[0].high; lo = r[0].low;
   for(int i = 1; i < n; i++) { hi = MathMax(hi, r[i].high); lo = MathMin(lo, r[i].low); }
   return true;
  }

void Box(const string name, datetime t1, double p1, datetime t2, double p2, color c, const string tip)
  {
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

void HLine(const string name, datetime t1, datetime t2, double p, color c, ENUM_LINE_STYLE st, const string tip)
  {
   ObjectCreate(0, name, OBJ_TREND, 0, t1, p, t2, p);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_STYLE, st);
   ObjectSetInteger(0, name, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetString(0, name, OBJPROP_TOOLTIP, tip);
  }

void Label(const string name, datetime t, double p, const string txt, color c)
  {
   ObjectCreate(0, name, OBJ_TEXT, 0, t, p);
   ObjectSetString(0, name, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, name, OBJPROP_COLOR, c);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 7);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
  }

void DrawSessions(datetime today)
  {
   datetime d = today;
   int shown = 0;
   for(int guard = 0; shown < InpSessionDays && guard < 14; guard++, d -= 86400)
     {
      int w = NYDayOfWeek(d);
      if(w == 0 || w == 6) continue;
      shown++;
      double hi, lo;
      datetime a0 = d - 4 * 3600, a1 = d + 3 * 3600;       // Asia 20:00 (previous evening) - 03:00 NY
      if(RangeHL(a0, a1, hi, lo))
        {
         string n = PFX + "asia_" + TimeToString(d, TIME_DATE);
         Box(n, a0, hi, a1, lo, InpAsiaCol, StringFormat("Asia %s-%s", DoubleToString(lo, _Digits), DoubleToString(hi, _Digits)));
         Label(n + "_t", a0, hi, "Asia", clrDimGray);
        }
      datetime l0 = d + 3 * 3600, l1 = d + 9 * 3600;       // London 03:00 - 09:00 NY
      datetime lEnd = (TimeCurrent() + 60 < l1) ? TimeCurrent() + 60 : l1;
      if(TimeCurrent() > l0 && RangeHL(l0, lEnd, hi, lo))
        {
         string n = PFX + "london_" + TimeToString(d, TIME_DATE);
         Box(n, l0, hi, l1, lo, InpLondonCol, StringFormat("London %s-%s", DoubleToString(lo, _Digits), DoubleToString(hi, _Digits)));
         Label(n + "_t", l0, hi, "London", clrDimGray);
         if(InpShowLondonFib && d == today)
           {
            datetime e = d + 17 * 3600;
            double mid = (hi + lo) / 2.0;
            HLine(n + "_h", l0, e, hi, clrDimGray, STYLE_SOLID, "London high");
            HLine(n + "_m", l0, e, mid, clrDimGray, STYLE_DOT, "London 50%");
            HLine(n + "_l", l0, e, lo, clrDimGray, STYLE_SOLID, "London low");
            Label(n + "_ht", e, hi, "0 (" + DoubleToString(hi, _Digits) + ")", clrDimGray);
            Label(n + "_mt", e, mid, "0.5 (" + DoubleToString(mid, _Digits) + ")", clrDimGray);
            Label(n + "_lt", e, lo, "1 (" + DoubleToString(lo, _Digits) + ")", clrDimGray);
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| fair value gaps                                                   |
//+------------------------------------------------------------------+
void ScanGaps(ENUM_TIMEFRAMES tf, const string tfName, datetime since, datetime today)
  {
   MqlRates r[];
   int n = CopyRates(_Symbol, tf, since - 2 * PeriodSeconds(tf), TimeCurrent(), r);   // chronological
   if(n < 4) return;
   int last = n - 2;                      // r[n-1] is still forming; only closed candles count
   int sec = PeriodSeconds(tf);
   datetime right = TimeCurrent() + 6 * 3600;
   for(int i = 2; i <= last; i++)
     {
      bool sup, dem;
      sup = r[i].high < r[i - 2].low;
      dem = r[i].low > r[i - 2].high;
      if(!sup && !dem) continue;
      double lo = sup ? r[i].high : r[i - 2].high;
      double hi = sup ? r[i - 2].low : r[i].low;
      if(hi - lo < InpMinGap) continue;
      datetime formed = r[i].time + sec;
      if(formed < since) continue;
      bool old = formed <= today;
      if(!old && !InpShowTodayGaps) continue;
      // still live? a later CLOSED candle of this time frame closing beyond the far edge kills it
      bool dead = false;
      for(int j = i + 1; j <= last; j++)
         if((sup && r[j].close > hi) || (dem && r[j].close < lo)) { dead = true; break; }
      if(dead) continue;
      Gap g;
      g.supply = sup; g.lo = lo; g.hi = hi; g.start = r[i - 1].time; g.formed = formed; g.old = old; g.tf = tfName;
      g.name = PFX + tfName + "_" + (sup ? "S_" : "D_") + IntegerToString((long)g.start);
      color c = sup ? (old ? InpSupplyOld : InpSupplyNew) : (old ? InpDemandOld : InpDemandNew);
      string day = TimeToString((datetime)((long)formed - Off()), TIME_DATE | TIME_MINUTES);
      string tip = StringFormat("%s %s gap %s-%s, formed %s NY%s", sup ? "Supply" : "Demand", tfName,
                                DoubleToString(lo, _Digits), DoubleToString(hi, _Digits), day, old ? "" : " (today)");
      Box(g.name, g.start, hi, right, lo, c, tip);
      if(InpShowMidline)
         HLine(g.name + "_m", g.start, right, (hi + lo) / 2.0, c, STYLE_DASH, "50% of gap");
      int k = ArraySize(g_live);
      ArrayResize(g_live, k + 1);
      g_live[k] = g;
     }
  }

//+------------------------------------------------------------------+
//| alerts: price enters an earlier-day gap in the NY window          |
//+------------------------------------------------------------------+
void CheckAlerts()
  {
   if(!InpAlerts) return;
   datetime now = TimeCurrent();
   datetime today = NYMidnightServer(now);
   if(today != g_alertDay) { g_alertDay = today; g_alerted = ""; }
   int w = NYDayOfWeek(today);
   if(w == 0 || w == 6) return;
   int mm = (int)(((long)now - (long)today) / 60);
   int a = ParseHHMM(InpAlertFrom), b = ParseHHMM(InpAlertTo);
   if(mm < a || mm >= b) return;
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   for(int i = 0; i < ArraySize(g_live); i++)
     {
      if(!g_live[i].old) continue;
      if(bid < g_live[i].lo || bid > g_live[i].hi) continue;
      if(StringFind(g_alerted, g_live[i].name + ";") >= 0) continue;
      g_alerted += g_live[i].name + ";";
      string msg = StringFormat("%s: price %s entered %s %s gap %s-%s. Watch for a rejection candle.",
                                _Symbol, DoubleToString(bid, _Digits), g_live[i].supply ? "SUPPLY" : "DEMAND", g_live[i].tf,
                                DoubleToString(g_live[i].lo, _Digits), DoubleToString(g_live[i].hi, _Digits));
      Alert(msg);
      if(InpPush) SendNotification(msg);
     }
  }
//+------------------------------------------------------------------+
