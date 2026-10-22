using System; using System.Collections.Generic; using System.IO; using System.Globalization;
using NinjaTrader.Cbi; using NinjaTrader.Data; using NinjaTrader.NinjaScript;
namespace NinjaTrader.NinjaScript.Strategies {
  public class Harness : LKForward {
    public static double Now;
    int n = 0; StreamWriter outw;
    public override void EnterLong(int q, string s) { Rec(1); }
    public override void EnterShort(int q, string s) { Rec(-1); }
    void Rec(int side) {
      double pnl = n % 2 == 0 ? -1.0 : 1.0; n++;
      SystemPerformance.AllTrades.Add(new Trade { ProfitCurrency = pnl });
      pendingSide = side;
    }
    int pendingSide = 0;
    public static void Main(string[] a) {
      var ci = CultureInfo.InvariantCulture;
      var h = new Harness();
      h.State = State.SetDefaults; h.OnStateChange();
      h.Account = new Account(); h.Instrument = new Instrument(); h.TickSize = 0.25; h.Position = new Position();
      h.SystemPerformance = new SystemPerformance();
      h.BarsArray = new Bars[] { new Bars(), LoadBars("bars5m.csv", 300), LoadBars("bars15m.csv", 900) };
      h.State = State.DataLoaded; h.OnStateChange();
      h.State = State.Realtime; h.OnStateChange();
      h.outw = new StreamWriter("cs_entries.csv");
      var ep = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);
      foreach (var line in File.ReadLines("ticks.csv")) {
        var p = line.Split(','); double ts = double.Parse(p[0], ci), pr = double.Parse(p[1], ci);
        Now = ts;
        var e = new MarketDataEventArgs { MarketDataType = MarketDataType.Last, Time = DateTime.SpecifyKind(ep.AddSeconds(ts), DateTimeKind.Unspecified), Price = pr };
        h.OnMarketData(e);
        if (h.pendingSide != 0) {
          h.outw.WriteLine(string.Format(ci, "{0:F3},{1},{2}", ts, h.pendingSide, pr));
          h.pendingSide = 0;
          h.OnPositionUpdate(null, 0, 0, MarketPosition.Flat);
        }
      }
      h.outw.Close();
      Console.Error.WriteLine("cs entries " + h.n);
    }
    static Bars LoadBars(string f, int sec) {
      var b = new Bars(); var ci = CultureInfo.InvariantCulture;
      foreach (var line in File.ReadLines(f)) { var p = line.Split(',');
        b.Rows.Add(new double[] { double.Parse(p[0], ci), double.Parse(p[1], ci), double.Parse(p[2], ci), double.Parse(p[3], ci), double.Parse(p[4], ci) }); }
      b.Sec = sec; b.NowFn = () => Now; return b;
    }
  }
}
