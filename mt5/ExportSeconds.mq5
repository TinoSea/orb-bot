//+------------------------------------------------------------------+
//|                                              ExportSeconds.mq5 |
//|  H-005: turns real ticks around the New York open into 1-second |
//|  bid/ask bars (much smaller than raw ticks, same information at |
//|  the precision a 6.25-point bracket needs).                      |
//|  Part of github.com/TinoSea/orb-bot                              |
//+------------------------------------------------------------------+
//  Writes under MQL5/Files/orb_export/:
//    <SYMBOL>_S1_<YYYYMM>.csv  t,bo,bh,bl,bc,ao,ah,al,ac,n   (t = server time in seconds; one row per second that had ticks)
//    seconds_log.txt
#property copyright "orb-bot"
#property version   "1.00"
#property script_show_inputs

input string   InpSymbol   = "US100";                // Symbol (as in Market Watch)
input datetime InpFrom     = D'2025.07.01 00:00';    // From (date)
input datetime InpTo       = D'2026.10.17 00:00';    // To (date)
input string   InpFromNY   = "08:30";                // From this New York time each weekday...
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
   int lg = FileOpen(DIR + "seconds_log.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   int dg = (int)SymbolInfoInteger(InpSymbol, SYMBOL_DIGITS);
   int hf = INVALID_HANDLE, curMonth = -1, days = 0;
   long rows = 0;

   for(datetime d = InpFrom; d < InpTo; d += 86400)
     {
      MqlDateTime ns;
      TimeToStruct(d, ns);
      if(ns.day_of_week == 0 || ns.day_of_week == 6)
         continue;
      long fromSrv = (long)d + (long)a * 60 + (long)InpServerMinusNY * 3600;
      long toSrv   = (long)d + (long)b * 60 + (long)InpServerMinusNY * 3600;
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
         hf = FileOpen(DIR + StringFormat("%s_S1_%d.csv", InpSymbol, month), FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
         FileWrite(hf, "t", "bo", "bh", "bl", "bc", "ao", "ah", "al", "ac", "n");
         curMonth = month;
        }
      long sec = -1;
      double bo = 0, bh = 0, bl = 0, bc = 0, ao = 0, ah = 0, al = 0, ac = 0;
      int cnt = 0, dayRows = 0;
      for(int i = 0; i <= n; i++)
        {
         long s = (i < n) ? (long)(tk[i].time_msc / 1000) : -2;
         bool valid = (i < n) && tk[i].bid > 0 && tk[i].ask > 0;
         if(i < n && !valid)
            continue;
         if(s != sec)
           {
            if(sec >= 0 && cnt > 0)
              {
               FileWrite(hf, (string)sec,
                         DoubleToString(bo, dg), DoubleToString(bh, dg), DoubleToString(bl, dg), DoubleToString(bc, dg),
                         DoubleToString(ao, dg), DoubleToString(ah, dg), DoubleToString(al, dg), DoubleToString(ac, dg),
                         (string)cnt);
               dayRows++;
              }
            if(i == n)
               break;
            sec = s;
            bo = bh = bl = bc = tk[i].bid;
            ao = ah = al = ac = tk[i].ask;
            cnt = 1;
           }
         else
           {
            double bd = tk[i].bid, ak = tk[i].ask;
            if(bd > bh) bh = bd;
            if(bd < bl) bl = bd;
            if(ak > ah) ah = ak;
            if(ak < al) al = ak;
            bc = bd;
            ac = ak;
            cnt++;
           }
        }
      rows += dayRows;
      days++;
      FileWrite(lg, StringFormat("%s: %d ticks -> %d seconds", TimeToString(d, TIME_DATE), n, dayRows));
     }
   if(hf != INVALID_HANDLE)
      FileClose(hf);
   string msg = StringFormat("ExportSeconds finished: %d days, %I64d one-second rows. Files: MQL5 > Files > orb_export (US100_S1_*.csv).", days, rows);
   FileWrite(lg, msg);
   FileClose(lg);
   Alert(msg);
  }
//+------------------------------------------------------------------+
