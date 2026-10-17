//+------------------------------------------------------------------+
//|                                                  ExportData.mq5 |
//|  SCRIPT (not an Expert Advisor). Exports raw price history and   |
//|  contract terms from your broker for the H-002 market universe.  |
//|  Part of github.com/TinoSea/orb-bot.                             |
//+------------------------------------------------------------------+
//
//  What it writes (all under MQL5/Files/orb_export/):
//    all_symbols.csv        every symbol the broker offers (name, path, description)
//    specs.csv              contract terms for each market found (lot sizes, tick value,
//                           swaps, trading sessions, currencies)
//    <LABEL>_M5.csv         5-minute bars with spread for every market found
//    <LABEL>_M1.csv         1-minute bars for the validation market(s) (default: gold)
//    export_log.txt         what was found, what was not, and row counts
//
//  Before running: Tools > Options > Charts > "Max bars in chart" = Unlimited,
//  then restart MT5. Otherwise the broker may only hand over recent history.
//
#property copyright   "orb-bot"
#property version     "1.00"
#property script_show_inputs

input datetime        InpFrom      = D'2022.12.01 00:00'; // Export from (server time)
input datetime        InpTo        = D'2026.10.17 00:00'; // Export to (server time)
input ENUM_TIMEFRAMES InpTF        = PERIOD_M5;           // Bars for all markets
input string          InpM1Labels  = "XAUUSD";            // Also export 1-minute bars for these labels (comma-separated)
input int             InpChunkDays = 20;                  // Days per request (smaller = gentler on the terminal)

// The pre-registered H-002 universe (same as research/h002_markets.csv)
string g_labels[] =
  {
   "US500", "US100", "US30", "US2000",
   "UK100", "GER40", "JP225",
   "BOND",
   "EURUSD", "USDJPY", "GBPUSD", "AUDUSD",
   "XAUUSD", "XAGUSD",
   "WTI",
   "BTCUSD",
   "AGRI"
  };
string g_aliases[] =
  {
   "US500|SPX500|US500.cash", "US100|NAS100|USTEC|NDX100", "US30|DJ30|WS30|DOW30", "US2000|RUSSELL2000|RUS2000|RTY|US2K",
   "UK100|FTSE100|FTSE", "GER40|DE40|GER30|DAX40|DE30", "JP225|JPN225|NIKKEI225|NIK225",
   "UST10Y|US10Y|USTN10Y|TNOTE|T-NOTE|BUND|EUBUND|BUND10Y",
   "EURUSD.r|EURUSD", "USDJPY.r|USDJPY", "GBPUSD.r|GBPUSD", "AUDUSD.r|AUDUSD",
   "XAUUSD.r|XAUUSD|GOLD", "XAGUSD.r|XAGUSD|SILVER",
   "XTIUSD|USOIL|WTI|CRUDE|CL",
   "BTCUSD|BITCOIN|BTCUSD.r",
   "COFFEE|SUGAR|WHEAT|CORN|SOYBEAN|COCOA|COTTON"
  };

const string DIR = "orb_export\\";
int g_log = INVALID_HANDLE;

void Log(const string msg)
  {
   Print(msg);
   if(g_log != INVALID_HANDLE)
      FileWriteString(g_log, msg + "\r\n");
  }

string Upper(string s)
  {
   StringToUpper(s);
   return s;
  }

// Exact name first (case-insensitive), then "starts with" (e.g. XAUUSD -> XAUUSD.r).
string ResolveSymbol(const string aliasList)
  {
   string aliases[];
   int na = StringSplit(aliasList, StringGetCharacter("|", 0), aliases);
   int total = SymbolsTotal(false);
   for(int pass = 0; pass < 2; pass++)
      for(int a = 0; a < na; a++)
        {
         string want = Upper(aliases[a]);
         for(int i = 0; i < total; i++)
           {
            string name = SymbolName(i, false);
            string up = Upper(name);
            bool hit = (pass == 0) ? (up == want) : (StringFind(up, want) == 0);
            if(hit)
              {
               SymbolSelect(name, true);
               return name;
              }
           }
        }
   return "";
  }

string TfName(const ENUM_TIMEFRAMES tf)
  {
   string s = EnumToString(tf);          // e.g. PERIOD_M5
   return StringSubstr(s, 7);
  }

// Writes bars in chunks; retries while the terminal downloads history.
long ExportBars(const string sym, const string label, const ENUM_TIMEFRAMES tf)
  {
   string fname = DIR + label + "_" + TfName(tf) + ".csv";
   int h = FileOpen(fname, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(h == INVALID_HANDLE)
     {
      Log("  could not create " + fname + " (error " + IntegerToString(GetLastError()) + ")");
      return -1;
     }
   FileWrite(h, "time", "open", "high", "low", "close", "tick_volume", "spread");
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   long rows = 0;
   datetime cur = InpFrom;
   datetime firstBar = 0, lastBar = 0;
   while(cur < InpTo && !IsStopped())
     {
      datetime nxt = (datetime)((long)cur + (long)InpChunkDays * 86400);
      if(nxt > InpTo)
         nxt = InpTo;
      MqlRates r[];
      int got = -1;
      for(int attempt = 0; attempt < 30 && got < 0; attempt++)
        {
         got = CopyRates(sym, tf, cur, (datetime)((long)nxt - 1), r);
         if(got < 0)
            Sleep(500);
        }
      if(got < 0)
         Log(StringFormat("  %s: no data for %s - %s (error %d)", label,
                          TimeToString(cur, TIME_DATE), TimeToString(nxt, TIME_DATE), GetLastError()));
      for(int i = 0; i < got; i++)
        {
         FileWrite(h,
                   TimeToString(r[i].time, TIME_DATE | TIME_MINUTES),
                   DoubleToString(r[i].open, digits),
                   DoubleToString(r[i].high, digits),
                   DoubleToString(r[i].low, digits),
                   DoubleToString(r[i].close, digits),
                   IntegerToString(r[i].tick_volume),
                   IntegerToString(r[i].spread));
         if(firstBar == 0)
            firstBar = r[i].time;
         lastBar = r[i].time;
        }
      if(got > 0)
         rows += got;
      cur = nxt;
     }
   FileClose(h);
   Log(StringFormat("  %s %s: %I64d bars, %s -> %s", label, TfName(tf), rows,
                    TimeToString(firstBar, TIME_DATE | TIME_MINUTES), TimeToString(lastBar, TIME_DATE | TIME_MINUTES)));
   return rows;
  }

string Sessions(const string sym)
  {
   string days[] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
   string out = "";
   for(int d = 0; d < 7; d++)
     {
      datetime f, t;
      for(uint k = 0; k < 4; k++)
        {
         if(!SymbolInfoSessionTrade(sym, (ENUM_DAY_OF_WEEK)d, k, f, t))
            break;
         out += days[d] + " " + TimeToString(f, TIME_MINUTES) + "-" + TimeToString(t, TIME_MINUTES) + " ";
        }
     }
   return out;
  }

void WriteSpecs(const int h, const string label, const string sym)
  {
   FileWrite(h, label, sym,
             SymbolInfoString(sym, SYMBOL_DESCRIPTION),
             SymbolInfoString(sym, SYMBOL_PATH),
             IntegerToString(SymbolInfoInteger(sym, SYMBOL_DIGITS)),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_POINT), 10),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_SIZE), 10),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_TRADE_TICK_VALUE), 10),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_TRADE_CONTRACT_SIZE), 4),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN), 4),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP), 4),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX), 4),
             IntegerToString(SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL)),
             IntegerToString(SymbolInfoInteger(sym, SYMBOL_SPREAD)),
             IntegerToString(SymbolInfoInteger(sym, SYMBOL_SPREAD_FLOAT)),
             IntegerToString(SymbolInfoInteger(sym, SYMBOL_SWAP_MODE)),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_SWAP_LONG), 6),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_SWAP_SHORT), 6),
             IntegerToString(SymbolInfoInteger(sym, SYMBOL_SWAP_ROLLOVER3DAYS)),
             IntegerToString(SymbolInfoInteger(sym, SYMBOL_TRADE_CALC_MODE)),
             SymbolInfoString(sym, SYMBOL_CURRENCY_PROFIT),
             SymbolInfoString(sym, SYMBOL_CURRENCY_MARGIN),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_MARGIN_INITIAL), 4),
             DoubleToString(SymbolInfoDouble(sym, SYMBOL_BID), 6),
             Sessions(sym));
  }

void OnStart()
  {
   FolderCreate("orb_export");
   g_log = FileOpen(DIR + "export_log.txt", FILE_WRITE | FILE_TXT | FILE_ANSI);
   Log(StringFormat("Export started %s | account %I64d on %s | %s to %s",
                    TimeToString(TimeCurrent()), AccountInfoInteger(ACCOUNT_LOGIN),
                    AccountInfoString(ACCOUNT_SERVER), TimeToString(InpFrom), TimeToString(InpTo)));
   Log(StringFormat("Terminal max bars in chart: %d (set to Unlimited for full history)",
                    TerminalInfoInteger(TERMINAL_MAXBARS)));

   // 1. Everything the broker offers
   int ha = FileOpen(DIR + "all_symbols.csv", FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(ha != INVALID_HANDLE)
     {
      FileWrite(ha, "name", "path", "description", "calc_mode", "digits");
      int total = SymbolsTotal(false);
      for(int i = 0; i < total; i++)
        {
         string n = SymbolName(i, false);
         FileWrite(ha, n, SymbolInfoString(n, SYMBOL_PATH), SymbolInfoString(n, SYMBOL_DESCRIPTION),
                   IntegerToString(SymbolInfoInteger(n, SYMBOL_TRADE_CALC_MODE)),
                   IntegerToString(SymbolInfoInteger(n, SYMBOL_DIGITS)));
        }
      FileClose(ha);
      Log(StringFormat("all_symbols.csv: %d symbols listed", total));
     }

   // 2. Contract terms + bars for each market in the universe
   int hs = FileOpen(DIR + "specs.csv", FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(hs != INVALID_HANDLE)
      FileWrite(hs, "label", "symbol", "description", "path", "digits", "point", "tick_size", "tick_value",
                "contract_size", "volume_min", "volume_step", "volume_max", "stops_level", "spread_now",
                "spread_float", "swap_mode", "swap_long", "swap_short", "swap_3day", "calc_mode",
                "currency_profit", "currency_margin", "margin_initial", "bid_now", "sessions");

   string m1[];
   int nm1 = StringSplit(InpM1Labels, StringGetCharacter(",", 0), m1);
   int found = 0;
   for(int k = 0; k < ArraySize(g_labels) && !IsStopped(); k++)
     {
      string sym = ResolveSymbol(g_aliases[k]);
      if(sym == "")
        {
         Log(g_labels[k] + ": NOT FOUND at this broker (tried " + g_aliases[k] + ")");
         continue;
        }
      found++;
      Log(g_labels[k] + " -> " + sym);
      if(hs != INVALID_HANDLE)
         WriteSpecs(hs, g_labels[k], sym);
      ExportBars(sym, g_labels[k], InpTF);
      for(int j = 0; j < nm1; j++)
        {
         string lab = m1[j];
         StringTrimLeft(lab);
         StringTrimRight(lab);
         if(Upper(lab) == Upper(g_labels[k]) && InpTF != PERIOD_M1)
            ExportBars(sym, g_labels[k], PERIOD_M1);
        }
     }
   if(hs != INVALID_HANDLE)
      FileClose(hs);

   Log(StringFormat("Done: %d of %d markets found. Files are in MQL5/Files/orb_export (File > Open Data Folder).",
                    found, ArraySize(g_labels)));
   if(g_log != INVALID_HANDLE)
      FileClose(g_log);
   Alert(StringFormat("Export finished: %d of %d markets. Open File > Open Data Folder > MQL5 > Files > orb_export.",
                      found, ArraySize(g_labels)));
  }
//+------------------------------------------------------------------+
