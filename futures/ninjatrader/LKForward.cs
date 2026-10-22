// LKForward.cs - NinjaTrader 8 strategy. La'Kera's zone method as a fixed rule, on futures (MNQ / NQ).
// Port of mt5/LK_Forward.mq5 v1.00 (H-017) with the same zone, candle, trigger and bracket rules, plus:
//   - signal window and flat time are inputs (defaults 08:00-14:00 and 14:30 New York);
//   - prices are the futures LAST trade (MT5 used CFD bid candles and a mid trigger);
//   - size = fixed dollar risk, capped by a contract limit and by a prop-firm guard that keeps every stop-out
//     above the Maximum Loss Limit floor (MT5: 1% of balance).
// Same rules as futures/tradovate/lk_core.py (tested there). Setup: futures/README.md.
// Part of github.com/TinoSea/orb-bot

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Strategies
{
    public class LKForward : Strategy
    {
        private class Zone
        {
            public bool Supply;
            public double Lo, Hi;
            public string Tf;
            public DateTime FormedUtc;
            public bool Used;
        }

        private const string Version = "1.00-futures";
        private const string Sig = "LK";

        private readonly List<Zone> zones = new List<Zone>();
        private TimeZoneInfo nyTz;
        private DateTime day = DateTime.MinValue;          // current New York date
        private int trades, losses;
        private long c15 = -1;                             // current 15-second candle index
        private double o, h, l, c;                         // current 15-second candle (last trade)
        private int armDir;
        private double armTrig;
        private DateTime armExpUtc;
        private Zone armZone;
        private DateTime entryUtc = DateTime.MinValue;
        private bool blocked;
        private double eodHigh;
        private string eodDate = "";
        private string statePath, journalPath;
        private HashSet<string> noTrade = new HashSet<string>();
        private string lastSide = "";
        private bool exitSent;
        private DateTime pendingUtc = DateTime.MinValue;   // entry sent, fill not yet reported
        private long k5 = -1, k15 = -1;                    // current 5m / 15m bar index (from ticks)
        private double close5, close15;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "LK_Forward (H-017 rules) on futures: earlier-day fair value gaps + 15-second rejection candle.";
                Name = "LKForward";
                Calculate = Calculate.OnEachTick;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                StartBehavior = StartBehavior.WaitUntilFlat;
                TimeInForce = TimeInForce.Gtc;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                BarsRequiredToTrade = 0;
                TraceOrders = false;

                MinGap = 5.0; Lookback = 5; StopPts = 12.5; TargetPts = 16.25; TriggerOff = 0.25; ArmSec = 45;
                SignalFrom = "08:00"; SignalTo = "14:00"; CapMin = 15; FlatAt = "14:30";
                MaxTrades = 3; MaxLosses = 2; NoFriday = true;
                RiskDollars = 100; MaxContracts = 10; CommissionRoundTrip = 1.0;
                StartBalance = 25000; MaxLossLimit = 1000; PayoutTaken = false; FloorOverride = 0; Buffer = 50;
                NoTradeDates = "";
                AllowNonSimAccount = false;
            }
            else if (State == State.Configure)
            {
                AddDataSeries(BarsPeriodType.Minute, 5);    // BarsArray[1]
                AddDataSeries(BarsPeriodType.Minute, 15);   // BarsArray[2]
            }
            else if (State == State.DataLoaded)
            {
                try { nyTz = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
                catch (TimeZoneNotFoundException) { nyTz = TimeZoneInfo.FindSystemTimeZoneById("America/New_York"); }
                if (HM(FlatAt) <= HM(SignalTo))
                    throw new ArgumentException("FlatAt must be later than SignalTo");
                string acct = Account != null ? Account.Name : "none";
                statePath = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "LKForward_" + Safe(acct) + "_state.txt");
                journalPath = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "LK_futures_journal.csv");
                noTrade = new HashSet<string>((NoTradeDates ?? "").Split(new[] { ',', ' ' },
                    StringSplitOptions.RemoveEmptyEntries));
                LoadState();
            }
            else if (State == State.Realtime)
            {
                string acct = Account != null ? Account.Name : "";
                bool sim = acct.StartsWith("Sim") || acct.StartsWith("Playback");
                if (!sim && !AllowNonSimAccount)
                {
                    blocked = true;
                    Log("LKForward: account " + acct + " is not a Sim account and AllowNonSimAccount is off. Not trading.",
                        LogLevel.Alert);
                }
                Print(string.Format("LKForward {0} on {1}, account {2}, window {3}-{4} NY, flat {5}{6}", Version,
                    Instrument.FullName, acct, SignalFrom, SignalTo, FlatAt, blocked ? " - BLOCKED" : ""));
            }
        }

        // ------------------------------------------------------------ time helpers
        private static int HM(string v)
        {
            string[] p = v.Split(':');
            return int.Parse(p[0], CultureInfo.InvariantCulture) * 60 + int.Parse(p[1], CultureInfo.InvariantCulture);
        }

        private static string Safe(string s)
        {
            foreach (char ch in Path.GetInvalidFileNameChars()) s = s.Replace(ch, '_');
            return s;
        }

        private DateTime ToUtc(DateTime local)
        {
            return TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(local, DateTimeKind.Unspecified),
                NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo);
        }

        private DateTime ToNy(DateTime utc) { return TimeZoneInfo.ConvertTimeFromUtc(utc, nyTz); }

        private DateTime NyMidnightUtc(DateTime nyDate)
        {
            return TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(nyDate.Date, DateTimeKind.Unspecified), nyTz);
        }

        private static int Minute(DateTime ny) { return ny.Hour * 60 + ny.Minute; }

        private static DateTime DaysBack(DateTime d, int n)
        {
            int k = 0;
            while (k < n)
            {
                d = d.AddDays(-1);
                if (d.DayOfWeek != DayOfWeek.Saturday && d.DayOfWeek != DayOfWeek.Sunday) k++;
            }
            return d;
        }

        // ------------------------------------------------------------ zones
        private void BuildZones(DateTime nyToday, DateTime nowUtc)
        {
            zones.Clear();
            DateTime sinceUtc = NyMidnightUtc(DaysBack(nyToday, Lookback));
            DateTime todayUtc = NyMidnightUtc(nyToday);
            for (int k = 1; k <= 2; k++)
            {
                Bars b = BarsArray[k];
                string tf = k == 1 ? "5m" : "15m";
                // closed bars only: NinjaTrader stamps bars with their END time
                var idx = new List<int>();
                for (int i = 0; i < b.Count; i++)
                    if (ToUtc(b.GetTime(i)) <= nowUtc) idx.Add(i);
                int n = idx.Count;
                for (int x = 2; x < n; x++)
                {
                    int i = idx[x], a = idx[x - 2];
                    bool sup = b.GetHigh(i) < b.GetLow(a), dem = b.GetLow(i) > b.GetHigh(a);
                    if (!sup && !dem) continue;
                    double lo = sup ? b.GetHigh(i) : b.GetHigh(a), hi = sup ? b.GetLow(a) : b.GetLow(i);
                    DateTime formed = ToUtc(b.GetTime(i));
                    if (hi - lo < MinGap || formed < sinceUtc || formed > todayUtc) continue;
                    bool dead = false;
                    for (int y = x + 1; y < n; y++)
                    {
                        double cl = b.GetClose(idx[y]);
                        if ((sup && cl > hi) || (dem && cl < lo)) { dead = true; break; }
                    }
                    if (dead) continue;
                    zones.Add(new Zone { Supply = sup, Lo = lo, Hi = hi, Tf = tf, FormedUtc = formed });
                }
            }
            Print(string.Format("LKForward {0:yyyy-MM-dd}: {1} earlier-day zones live (5m bars loaded: {2}, 15m: {3})",
                nyToday, zones.Count, BarsArray[1].Count, BarsArray[2].Count));
        }

        private void KillBroken(string tf, double close)
        {
            for (int i = zones.Count - 1; i >= 0; i--)
            {
                Zone z = zones[i];
                if (z.Tf != tf) continue;
                if ((z.Supply && close > z.Hi) || (!z.Supply && close < z.Lo))
                {
                    if (armZone == z) { armDir = 0; armZone = null; }
                    zones.RemoveAt(i);
                }
            }
        }

        protected override void OnBarUpdate()
        {
            // Everything runs on trade ticks in OnMarketData. The 5m / 15m series are only the history for the zones.
        }

        // ------------------------------------------------------------ ticks
        protected override void OnMarketData(MarketDataEventArgs e)
        {
            if (State != State.Realtime || e.MarketDataType != MarketDataType.Last || blocked) return;
            DateTime nowUtc = ToUtc(e.Time);
            DateTime ny = ToNy(nowUtc);
            double price = e.Price;

            if (ny.Date != day)
            {
                day = ny.Date; trades = 0; losses = 0; armDir = 0; armZone = null; c15 = -1; k5 = -1; k15 = -1;
                BuildZones(day, nowUtc);
            }

            // an entry that is sent but not yet filled counts as a position (no second signal meanwhile)
            if (pendingUtc != DateTime.MinValue && (nowUtc - pendingUtc).TotalSeconds > 10
                && Position.MarketPosition == MarketPosition.Flat)
            {
                pendingUtc = DateTime.MinValue;
                Journal(ny, "error", lastSide, price, 0, 0, null, 0, "", Account.Get(AccountItem.CashValue, Currency.UsDollar),
                    "entry not filled within 10 s");
            }
            bool inPos = Position.MarketPosition != MarketPosition.Flat || pendingUtc != DateTime.MinValue;
            // time cap and flat time
            if (inPos)
            {
                bool cap = entryUtc != DateTime.MinValue && (nowUtc - entryUtc).TotalSeconds >= CapMin * 60;
                if ((cap || Minute(ny) >= HM(FlatAt)) && !exitSent)
                {
                    exitSent = true;                       // one exit order, not one per tick
                    if (Position.MarketPosition == MarketPosition.Long) ExitLong(cap ? "cap" : "flat", Sig);
                    else ExitShort(cap ? "cap" : "flat", Sig);
                }
            }
            else if (Minute(ny) >= HM(FlatAt) + 1 && eodDate != ny.ToString("yyyy-MM-dd"))
                RecordEod(ny);

            DayOfWeek w = ny.DayOfWeek;
            if (w == DayOfWeek.Saturday || w == DayOfWeek.Sunday || (NoFriday && w == DayOfWeek.Friday)) return;

            double epoch = (nowUtc - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
            // zones broken by a newly closed 5m / 15m bar (bars built from the same trade prices)
            long n5 = (long)Math.Floor(epoch / 300.0), n15 = (long)Math.Floor(epoch / 900.0);
            if (n5 != k5) { if (k5 >= 0) KillBroken("5m", close5); k5 = n5; }
            close5 = price;
            if (n15 != k15) { if (k15 >= 0) KillBroken("15m", close15); k15 = n15; }
            close15 = price;

            // 15-second candles from trade prices
            long k = (long)Math.Floor(epoch / 15.0);
            if (k != c15)
            {
                if (c15 >= 0) OnClosed15(new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc).AddSeconds((c15 + 1) * 15), inPos);
                c15 = k; o = price; h = price; l = price; c = price;
            }
            else { h = Math.Max(h, price); l = Math.Min(l, price); c = price; }

            if (!inPos && trades < MaxTrades && losses < MaxLosses && !noTrade.Contains(ny.ToString("yyyy-MM-dd")))
                TryFill(nowUtc, ny, price);
        }

        private void OnClosed15(DateTime closeUtc, bool inPos)
        {
            int mm = Minute(ToNy(closeUtc));
            if (mm < HM(SignalFrom) || mm >= HM(SignalTo)) return;
            if (inPos || trades >= MaxTrades || losses >= MaxLosses) return;
            for (int d = -1; d <= 1; d += 2)
            {
                double body = (o - c) * -d;
                double wick = d < 0 ? h - Math.Max(o, c) : Math.Min(o, c) - l;
                double tip = d < 0 ? h : l;
                if (body <= 0 || wick < body) continue;
                foreach (Zone z in zones)
                {
                    if (z.Used || z.Supply != (d < 0)) continue;
                    if (tip < z.Lo || tip > z.Hi) continue;
                    armDir = d; armZone = z; armExpUtc = closeUtc.AddSeconds(ArmSec);
                    armTrig = d < 0 ? l - TriggerOff : h + TriggerOff;
                    return;
                }
            }
        }

        private void TryFill(DateTime nowUtc, DateTime ny, double price)
        {
            if (armDir == 0) return;
            if (nowUtc > armExpUtc || armZone == null || !zones.Contains(armZone)) { armDir = 0; armZone = null; return; }
            int d = armDir;
            if (!(d < 0 ? price <= armTrig : price >= armTrig)) return;
            Zone z = armZone;
            z.Used = true;                                 // first try only, win or lose
            armDir = 0; armZone = null;

            double cash = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            int qty = Size(cash);
            string side = d < 0 ? "short" : "long";
            double sl = price - d * StopPts, tp = price + d * TargetPts;
            if (qty <= 0)
            {
                Journal(ny, "skipped", side, price, sl, tp, z, 0, "", cash, "size 0: risk, contract cap or MLL guard");
                Print("LKForward: signal skipped, size 0 (cash " + cash.ToString("F2") + ", floor " + Floor().ToString("F2") + ")");
                return;
            }
            int stopTicks = (int)Math.Round(StopPts / TickSize), tgtTicks = (int)Math.Round(TargetPts / TickSize);
            SetStopLoss(Sig, CalculationMode.Ticks, stopTicks, false);
            SetProfitTarget(Sig, CalculationMode.Ticks, tgtTicks);
            if (d < 0) EnterShort(qty, Sig); else EnterLong(qty, Sig);
            trades++;
            entryUtc = nowUtc;
            pendingUtc = nowUtc;
            lastSide = side;
            Journal(ny, "entry", side, price, sl, tp, z, qty, "", cash, "");
        }

        protected override void OnPositionUpdate(Position position, double averagePrice, int quantity,
            MarketPosition marketPosition)
        {
            if (State != State.Realtime) return;
            pendingUtc = DateTime.MinValue;                // filled (or closed): no longer pending
            if (marketPosition != MarketPosition.Flat) return;
            double pnl = 0, exitPx = 0;
            if (SystemPerformance.AllTrades.Count > 0)
            {
                Trade t = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
                pnl = t.ProfitCurrency;
                exitPx = t.Exit.Price;
            }
            if (pnl < 0) losses++;
            entryUtc = DateTime.MinValue;
            exitSent = false;
            DateTime ny = ToNy(DateTime.UtcNow);
            double cash = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            Journal(ny, "exit", lastSide, exitPx, 0, 0, null, 0, pnl.ToString("F2", CultureInfo.InvariantCulture), cash, "");
        }

        // ------------------------------------------------------------ size and the prop-firm guard
        private double Floor()
        {
            if (FloorOverride > 0) return FloorOverride;
            if (PayoutTaken) return StartBalance;
            return Math.Min(StartBalance, eodHigh - MaxLossLimit);
        }

        private int Size(double cash)
        {
            double per = StopPts * Instrument.MasterInstrument.PointValue + CommissionRoundTrip;
            if (per <= 0) return 0;
            int q = Math.Min((int)Math.Floor(RiskDollars / per + 1e-9), MaxContracts);
            double room = cash - Floor() - Buffer;
            q = Math.Min(q, (int)Math.Floor(room / per + 1e-9));
            return Math.Max(q, 0);
        }

        private void RecordEod(DateTime ny)
        {
            double cash = Account.Get(AccountItem.CashValue, Currency.UsDollar);
            eodHigh = Math.Max(eodHigh, cash);
            eodDate = ny.ToString("yyyy-MM-dd");
            SaveState();
            Journal(ny, "eod", "", 0, 0, 0, null, 0, "", cash, "floor " + Floor().ToString("F2", CultureInfo.InvariantCulture));
        }

        private void LoadState()
        {
            eodHigh = StartBalance;
            try
            {
                if (File.Exists(statePath))
                {
                    string[] p = File.ReadAllText(statePath).Trim().Split(';');
                    eodHigh = Math.Max(StartBalance, double.Parse(p[0], CultureInfo.InvariantCulture));
                    if (p.Length > 1) eodDate = p[1];
                }
            }
            catch (Exception ex) { Print("LKForward: could not read state: " + ex.Message); }
        }

        private void SaveState()
        {
            try { File.WriteAllText(statePath, eodHigh.ToString(CultureInfo.InvariantCulture) + ";" + eodDate); }
            catch (Exception ex) { Print("LKForward: could not save state: " + ex.Message); }
        }

        private void Journal(DateTime ny, string ev, string side, double price, double sl, double tp, Zone z, int qty,
            string profit, double cash, string note)
        {
            try
            {
                bool exists = File.Exists(journalPath);
                using (var w = new StreamWriter(journalPath, true))
                {
                    if (!exists)
                        w.WriteLine("time_ny,event,side,price,sl,tp,zone_tf,zone_lo,zone_hi,contracts,profit,balance,floor,note");
                    var ci = CultureInfo.InvariantCulture;
                    w.WriteLine(string.Join(",", new[] {
                        ny.ToString("yyyy-MM-dd HH:mm:ss", ci), ev, side,
                        price != 0 ? price.ToString(ci) : "", sl != 0 ? sl.ToString(ci) : "", tp != 0 ? tp.ToString(ci) : "",
                        z != null ? z.Tf : "", z != null ? z.Lo.ToString(ci) : "", z != null ? z.Hi.ToString(ci) : "",
                        qty != 0 ? qty.ToString(ci) : "", profit, cash.ToString("F2", ci), Floor().ToString("F2", ci),
                        note.Replace(",", ";") }));
                }
            }
            catch (Exception ex) { Print("LKForward: journal: " + ex.Message); }
        }

        #region Properties
        [NinjaScriptProperty, Range(0.25, double.MaxValue)]
        [Display(Name = "Min gap (points)", Order = 1, GroupName = "1. Rule")]
        public double MinGap { get; set; }

        [NinjaScriptProperty, Range(1, 20)]
        [Display(Name = "Lookback (trading days)", Order = 2, GroupName = "1. Rule")]
        public int Lookback { get; set; }

        [NinjaScriptProperty, Range(0.25, double.MaxValue)]
        [Display(Name = "Stop (points)", Order = 3, GroupName = "1. Rule")]
        public double StopPts { get; set; }

        [NinjaScriptProperty, Range(0.25, double.MaxValue)]
        [Display(Name = "Target (points)", Order = 4, GroupName = "1. Rule")]
        public double TargetPts { get; set; }

        [NinjaScriptProperty, Range(0, double.MaxValue)]
        [Display(Name = "Trigger offset (points)", Order = 5, GroupName = "1. Rule")]
        public double TriggerOff { get; set; }

        [NinjaScriptProperty, Range(15, 600)]
        [Display(Name = "Trigger valid (seconds)", Order = 6, GroupName = "1. Rule")]
        public int ArmSec { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Signals from (NY, HH:MM)", Order = 7, GroupName = "1. Rule")]
        public string SignalFrom { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Signals until (NY, HH:MM)", Order = 8, GroupName = "1. Rule")]
        public string SignalTo { get; set; }

        [NinjaScriptProperty, Range(1, 240)]
        [Display(Name = "Time cap (minutes)", Order = 9, GroupName = "1. Rule")]
        public int CapMin { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Flat at (NY, HH:MM)", Order = 10, GroupName = "1. Rule")]
        public string FlatAt { get; set; }

        [NinjaScriptProperty, Range(1, 20)]
        [Display(Name = "Max trades a day", Order = 11, GroupName = "1. Rule")]
        public int MaxTrades { get; set; }

        [NinjaScriptProperty, Range(1, 20)]
        [Display(Name = "Max losses a day", Order = 12, GroupName = "1. Rule")]
        public int MaxLosses { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "No Fridays", Order = 13, GroupName = "1. Rule")]
        public bool NoFriday { get; set; }

        [NinjaScriptProperty, Range(1, double.MaxValue)]
        [Display(Name = "Risk per trade ($)", Order = 1, GroupName = "2. Size and prop-firm guard")]
        public double RiskDollars { get; set; }

        [NinjaScriptProperty, Range(1, 100)]
        [Display(Name = "Max contracts", Order = 2, GroupName = "2. Size and prop-firm guard")]
        public int MaxContracts { get; set; }

        [NinjaScriptProperty, Range(0, double.MaxValue)]
        [Display(Name = "Commission per contract, round trip ($)", Order = 3, GroupName = "2. Size and prop-firm guard")]
        public double CommissionRoundTrip { get; set; }

        [NinjaScriptProperty, Range(1, double.MaxValue)]
        [Display(Name = "Start balance ($)", Order = 4, GroupName = "2. Size and prop-firm guard")]
        public double StartBalance { get; set; }

        [NinjaScriptProperty, Range(1, double.MaxValue)]
        [Display(Name = "Maximum Loss Limit ($)", Order = 5, GroupName = "2. Size and prop-firm guard")]
        public double MaxLossLimit { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Payout taken (floor = start balance)", Order = 6, GroupName = "2. Size and prop-firm guard")]
        public bool PayoutTaken { get; set; }

        [NinjaScriptProperty, Range(0, double.MaxValue)]
        [Display(Name = "Floor override ($, 0 = calculate)", Order = 7, GroupName = "2. Size and prop-firm guard")]
        public double FloorOverride { get; set; }

        [NinjaScriptProperty, Range(0, double.MaxValue)]
        [Display(Name = "Buffer above floor ($)", Order = 8, GroupName = "2. Size and prop-firm guard")]
        public double Buffer { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "No-trade dates (yyyy-MM-dd, comma separated)", Order = 1, GroupName = "3. Safety")]
        public string NoTradeDates { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Allow non-Sim account", Order = 2, GroupName = "3. Safety")]
        public bool AllowNonSimAccount { get; set; }
        #endregion
    }
}
