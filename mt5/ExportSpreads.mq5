//+------------------------------------------------------------------+
//|                                                ExportSpreads.mq5 |
//|  SCRIPT. Measures REAL spreads from tick history and compares    |
//|  them with the spread stored in the bar history.                 |
//|  Part of github.com/TinoSea/orb-bot (H-002 cost calibration).    |
//+------------------------------------------------------------------+
//
//  Why: MT5 bar history keeps one spread number per bar, and it is often the
//  smallest spread seen in that bar. Strategy entries happen at the start of an
//  hour, when spreads can be wider. This script reads the actual first ticks
//  (bid and ask) at the start of every hour over the last InpDays days, for each
//  market, and writes them next to the bar spread.
//
//  Output: MQL5/Files/orb_export/spread_samples.csv
//          label, symbol, hour_open (server), tick_time, bid, ask, tick_spread_points,
//          bar_spread_points (M5 bar of that hour), tick_spread_1min_max_points
//          and spread_log.txt
//
#property copyright   "orb-bot"
#property version     "1.00"
#property script_show_inputs

input int InpDays = 90;   // How many recent days to sample

string g_labels[]  = {"US500", "US100", "US30", "UK100", "GER40", "JP225", "BOND",
                      "EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "XAUUSD", "XAGUSD", "WTI", "BTCUSD", "AGRI"};
string g_symbols[] = {"US500", "US100", "US30", "UK100", "GER40", "JP225", "US10YR",
                      "EURUSD.r", "USDJPY.r", "GBPUSD.r", "AUDUSD.r", "XAUUSD.r", "XAGUSD.r", "XTIUSD", "BTCUSD", "COFFEE"};

const string DIR = "orb_export\\";
int g_log = INVALID_HANDLE;

void Log(const string msg)
  {
   Print(msg);
   if(g_log != INVALID_HANDLE)
      FileWriteString(g_log, msg + "\r\n");
  }

void OnStart()
  {
   FolderCreate("orb_export");
   g_log = FileOpen(DIR + "spread_log.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   int h = FileOpen(DIR + "spread_samples.csv", FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(h == INVALID_HANDLE)
     {
      Alert("Could not create spread_samples.csv");
      return;
     }
   FileWrite(h, "label", "symbol", "hour_open", "tick_time", "bid", "ask", "tick_spread_points",
             "bar_spread_points", "tick_spread_1min_max_points");

   datetime to = TimeCurrent();
   datetime from = to - (datetime)((long)InpDays * 86400);
   from = (datetime)((long)from - (long)from % 3600);
   int done = 0;
   for(int k = 0; k < ArraySize(g_labels) && !IsStopped(); k++)
     {
      string sym = g_symbols[k];
      if(!SymbolSelect(sym, true))
        {
         Log(g_labels[k] + ": symbol " + sym + " not available");
         continue;
        }
      double pt = SymbolInfoDouble(sym, SYMBOL_POINT);
      int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
      // M5 bars of the period (for the stored bar spread)
      MqlRates bars[];
      int nb = -1;
      for(int a = 0; a < 60 && nb < 0 && !IsStopped(); a++)
        {
         nb = CopyRates(sym, PERIOD_M5, from, to, bars);
         if(nb < 0)
            Sleep(500);
        }
      if(nb <= 0)
        {
         Log(g_labels[k] + ": no M5 bars");
         continue;
        }
      int samples = 0, noTicks = 0;
      for(int i = 0; i < nb && !IsStopped(); i++)
        {
         if((long)bars[i].time % 3600 != 0)
            continue;                       // only the first M5 bar of each hour
         MqlTick t[];
         ulong fromMsc = (ulong)bars[i].time * 1000;
         ulong toMsc = fromMsc + 60000;      // first minute of the hour
         int n = -1;
         for(int a = 0; a < 20 && n < 0 && !IsStopped(); a++)
           {
            n = CopyTicksRange(sym, t, COPY_TICKS_INFO, fromMsc, toMsc);
            if(n < 0)
               Sleep(250);
           }
         if(n <= 0)
           {
            noTicks++;
            continue;
           }
         double mx = 0;
         for(int j = 0; j < n; j++)
            if(t[j].ask > 0 && t[j].bid > 0)
               mx = MathMax(mx, (t[j].ask - t[j].bid) / pt);
         FileWrite(h, g_labels[k], sym,
                   TimeToString(bars[i].time, TIME_DATE | TIME_MINUTES),
                   TimeToString((datetime)(t[0].time_msc / 1000), TIME_DATE | TIME_SECONDS),
                   DoubleToString(t[0].bid, digits), DoubleToString(t[0].ask, digits),
                   DoubleToString((t[0].ask - t[0].bid) / pt, 1),
                   IntegerToString(bars[i].spread),
                   DoubleToString(mx, 1));
         samples++;
        }
      Log(StringFormat("%s (%s): %d hourly samples, %d hours without ticks", g_labels[k], sym, samples, noTicks));
      if(samples > 0)
         done++;
     }
   FileClose(h);
   string msg = IsStopped() ? "Spread export STOPPED early - run it again." :
                StringFormat("Spread export finished: %d of %d markets. File: MQL5/Files/orb_export/spread_samples.csv",
                             done, ArraySize(g_labels));
   Log(msg);
   if(g_log != INVALID_HANDLE)
      FileClose(g_log);
   Alert(msg);
  }
//+------------------------------------------------------------------+
