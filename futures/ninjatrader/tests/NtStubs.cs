// Minimal stand-ins for the NinjaTrader 8 API surface LKForward.cs uses: lets mcs type-check our own code.
using System;
using System.Collections.Generic;
namespace NinjaTrader.Gui { } namespace NinjaTrader.Gui.Tools { } namespace NinjaTrader.Core.FloatingPoint { }
namespace NinjaTrader.NinjaScript.Indicators { } namespace NinjaTrader.NinjaScript.DrawingTools { }
namespace NinjaTrader.Core { public static class Globals { public static string UserDataDir = "/tmp";
  public static class GeneralOptions { public static TimeZoneInfo TimeZoneInfo = TimeZoneInfo.Utc; } } }
namespace NinjaTrader.Cbi {
  public enum AccountItem { CashValue } public enum Currency { UsDollar } public enum MarketPosition { Flat, Long, Short }
  public enum TimeInForce { Gtc, Day } public enum LogLevel { Information, Warning, Alert, Error }
  public class Account { public string Name = "Sim101"; public double Get(AccountItem i, Currency c) { return 25000; } }
  public class Position { public MarketPosition MarketPosition = MarketPosition.Flat; }
  public class MasterInstrument { public double PointValue = 2; public double TickSize = 0.25; }
  public class Instrument { public string FullName = "MNQ 12-26"; public MasterInstrument MasterInstrument = new MasterInstrument(); }
  public class Execution { public double Price; }
  public class Trade { public double ProfitCurrency; public Execution Exit = new Execution(); }
  public class TradeCollection { List<Trade> t = new List<Trade>(); public void Add(Trade x) { t.Add(x); } public int Count { get { return t.Count; } } public Trade this[int i] { get { return t[i]; } } }
  public class SystemPerformance { public TradeCollection AllTrades = new TradeCollection(); }
}
namespace NinjaTrader.Data {
  public enum BarsPeriodType { Minute, Second, Tick } public enum MarketDataType { Last, Bid, Ask }
  public class Bars { public List<double[]> Rows = new List<double[]>(); public int Sec; public Func<double> NowFn = () => 0;
    static readonly DateTime Ep = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
    public int Count { get { int c = 0; double now = NowFn(); while (c < Rows.Count && Rows[c][0] <= now) c++; return c; } }
    public DateTime GetTime(int i) { return DateTime.SpecifyKind(Ep.AddSeconds(Rows[i][0] + Sec), DateTimeKind.Unspecified); }
    public double GetHigh(int i) { return Rows[i][2]; } public double GetLow(int i) { return Rows[i][3]; } public double GetClose(int i) { return Rows[i][4]; } }
  public class MarketDataEventArgs { public MarketDataType MarketDataType; public DateTime Time; public double Price; }
}
namespace NinjaTrader.NinjaScript {
  public enum State { SetDefaults, Configure, DataLoaded, Historical, Transition, Realtime, Terminated }
  public enum Calculate { OnBarClose, OnEachTick, OnPriceChange } public enum EntryHandling { AllEntries, UniqueEntries }
  public enum StartBehavior { WaitUntilFlat, ImmediatelySubmit } public enum RealtimeErrorHandling { StopCancelClose, IgnoreAllErrors }
  public enum StopTargetHandling { PerEntryExecution, ByStrategyPosition } public enum CalculationMode { Ticks, Price, Currency, Percent }
  [AttributeUsage(AttributeTargets.Property)] public class NinjaScriptPropertyAttribute : Attribute { }
  public class Series<T> { public T this[int barsAgo] { get { return default(T); } } }
}
namespace NinjaTrader.NinjaScript.Strategies {
  using NinjaTrader.Cbi; using NinjaTrader.Data;
  public abstract class Strategy {
    public State State; public string Description, Name; public Calculate Calculate; public int EntriesPerDirection;
    public EntryHandling EntryHandling; public bool IsExitOnSessionCloseStrategy; public int ExitOnSessionCloseSeconds;
    public StartBehavior StartBehavior; public TimeInForce TimeInForce; public RealtimeErrorHandling RealtimeErrorHandling;
    public StopTargetHandling StopTargetHandling; public int BarsRequiredToTrade; public bool TraceOrders;
    public Account Account; public Instrument Instrument; public Bars[] BarsArray; public int BarsInProgress;
    public bool IsFirstTickOfBar; public int[] CurrentBars; public Series<double>[] Closes; public Position Position;
    public double TickSize; public NinjaTrader.Cbi.SystemPerformance SystemPerformance;
    public void AddDataSeries(BarsPeriodType t, int v) { } public void Print(string s) { } public void Log(string s, LogLevel l) { }
    public void ExitLong(string a, string b) { } public void ExitShort(string a, string b) { }
    public virtual void EnterLong(int q, string s) { } public virtual void EnterShort(int q, string s) { }
    public void SetStopLoss(string s, CalculationMode m, double v, bool sim) { } public void SetProfitTarget(string s, CalculationMode m, double v) { }
    protected virtual void OnStateChange() { } protected virtual void OnBarUpdate() { }
    protected virtual void OnMarketData(MarketDataEventArgs e) { }
    protected virtual void OnPositionUpdate(Position position, double averagePrice, int quantity, MarketPosition marketPosition) { }
  }
}
