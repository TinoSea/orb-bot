//+------------------------------------------------------------------+
//|                                                ExportTicks.mq5 |
//|  H-005: exports real bid/ask ticks for one symbol around the New |
//|  York open, plus 1-minute bars for the whole range, so the       |
//|  replication study can run outside MetaTrader.                   |
//|  Part of github.com/TinoSea/orb-bot                              |
//+------------------------------------------------------------------+
//  Writes under MQL5/Files/orb_export/:
//    <SYMBOL>_ticks_<YYYYMM>.csv   time_msc,bid,ask      (only InpFromNY..InpToNY each weekday)
//    <SYMBOL>_M1.csv               time,open,high,low,close,tick_volume,spread  (whole range, server time)
//    ticks_log.txt                 what was written, day by day
#property copyright "orb-bot"
#property version   "1.00"
#property script_show_inputs

input string   InpSymbol   = "US100";                // Symbol (as in Market Watch)
input datetime InpFrom     = D'2025.07.01 00:00';    // From (server date)
input datetime InpTo       = D'2026.10.17 00:00';    // To (server date)
input string   InpFromNY   = "09:00";                // Ticks from this New York time each weekday...
input string   InpToNY     = "11:45";                // ...until this New York time
input int      InpServerMinusNY = 7;                 // Server time minus New York time (FP Markets = 7)

const string DIR = "orb_export\\";

int ParseHHMM(const string s)
  {
   string p[];
   if(StringSplit(s, StringGetCharacter(":", 0), p) != 2)
      return -1;
   return (int)StringToInteger(p[0]) * 60 + (int)StringToInteger(p[1]);
  }

void OnStart()
  {
   int a = ParseHHMM(InpFromNY), b = ParseHHMM(InpToNY);
   if(a < 0 || b <= a)
     {
      Alert("Check the New York times (HH:MM).");
      return;
     }
   if(!SymbolSelect(InpSymbol, true))
     {
      Alert("Symbol not found: " + InpSymbol);
      return;
     }
   FolderCreate("orb_export");
   int lg = FileOpen(DIR + "ticks_log.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   int digits = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);

   // 1. one-minute bars for the whole range
   MqlRates r[];
   int nb = CopyRates(InpSymbol, PERIOD_M1, InpFrom - 3 * 86400, InpTo, r);
   if(nb > 0)
     {
      int h = FileOpen(DIR + InpSymbol + "_M1.csv", FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
      FileWrite(h, "time", "open", "high", "low", "close", "tick_volume", "spread");
      for(int i = 0; i < nb; i++)
         FileWrite(h, TimeToString(r[i].time, TIME_DATE | TIME_MINUTES), DoubleToString(r[i].open, digits),
                   DoubleToString(r[i].high, digits), DoubleToString(r[i].low, digits),
                   DoubleToString(r[i].close, digits), (string)r[i].tick_volume, (string)r[i].spread);
      FileClose(h);
     }
   FileWrite(lg, StringFormat("M1 bars: %d", nb));

   // 2. ticks around the open, day by day, one file per month
   int hf = INVALID_HANDLE, curMonth = -1, days = 0;
   long total = 0;
   for(datetime d = InpFrom; d < InpTo; d += 86400)
     {
      // server midnight d; NY window [a,b) on the NY calendar day that starts at server d + offset
      long nyMid = (long)d;                                   // treat d as the NY date
      MqlDateTime ns;
      TimeToStruct((datetime)nyMid, ns);
      if(ns.day_of_week == 0 || ns.day_of_week == 6)
         continue;
      long fromSrv = nyMid + (long)a * 60 + (long)InpServerMinusNY * 3600;
      long toSrv   = nyMid + (long)b * 60 + (long)InpServerMinusNY * 3600;
      MqlTick tk[];
      int n = CopyTicksRange(InpSymbol, tk, COPY_TICKS_ALL, (ulong)fromSrv * 1000, (ulong)toSrv * 1000);
      if(n <= 0)
        {
         FileWrite(lg, StringFormat("%s: no ticks (%d, error %d)", TimeToString(d, TIME_DATE), n, GetLastError()));
         continue;
        }
      int month = ns.year * 100 + ns.mon;
      if(month != curMonth)
        {
         if(hf != INVALID_HANDLE)
            FileClose(hf);
         hf = FileOpen(DIR + StringFormat("%s_ticks_%d.csv", InpSymbol, month), FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
         FileWrite(hf, "time_msc", "bid", "ask");
         curMonth = month;
        }
      for(int i = 0; i < n; i++)
         FileWrite(hf, (string)tk[i].time_msc, DoubleToString(tk[i].bid, digits), DoubleToString(tk[i].ask, digits));
      total += n;
      days++;
      FileWrite(lg, StringFormat("%s: %d ticks", TimeToString(d, TIME_DATE), n));
     }
   if(hf != INVALID_HANDLE)
      FileClose(hf);
   string msg = StringFormat("ExportTicks finished: %d days, %I64d ticks, %d one-minute bars. Files: File > Open Data Folder > MQL5 > Files > orb_export.",
                             days, total, nb);
   FileWrite(lg, msg);
   FileClose(lg);
   Alert(msg);
  }
//+------------------------------------------------------------------+
