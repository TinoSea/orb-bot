#!/usr/bin/env python3
"""
ORB Bot - Backtester v1
=======================
Opening-range breakout (ORB) on micro E-mini futures (MES / MNQ),
with hard-coded risk rules and honest costs.

Strategy (one setup, traded mechanically):
  1. Opening range (OR) = high/low of the first N minutes after 09:30 New York time.
  2. A bar CLOSES above the OR high -> buy at the NEXT bar's open (+ slippage).
     A bar CLOSES below the OR low  -> sell at the NEXT bar's open (- slippage).
  3. Stop  = other side of the range (or the range midpoint).
     Target = entry +/- target_r x risk.
  4. Anything still open at flat_time is closed. Max 1 trade per day by default.
  5. Days with a range that is too small or too wide are skipped.

Risk engine (the bot cannot override these):
  - max $ risk per trade (trade skipped if the stop is too wide)
  - daily loss limit, weekly loss limit
  - kill switch: stop trading completely after a set drawdown from peak

Honesty rules built in:
  - commissions + slippage on every trade
  - if stop and target are hit in the same bar, we assume the STOP hit first
  - results split into in-sample (first 70%) and out-of-sample (last 30%)

Usage:
  python orb_backtest.py --demo                     # fake data, checks your install works
  python orb_backtest.py --source yf --symbol MES   # ~60 days of real 5-min data from Yahoo
  python orb_backtest.py --csv mydata.csv           # your own data (best)
  python orb_backtest.py --source yf --sweep        # test parameter combos on in-sample only

Not financial advice. A backtest is evidence, not a promise.
"""

import argparse
import itertools
import math
import sys
from dataclasses import dataclass, asdict, replace
from datetime import datetime, time

import numpy as np
import pandas as pd

TZ = "America/New_York"

CONTRACTS = {
    # tick size in points, $ value of one tick, Yahoo ticker
    "MES": {"tick": 0.25, "tick_value": 1.25, "yf": "MES=F"},  # $5 per point
    "MNQ": {"tick": 0.25, "tick_value": 0.50, "yf": "MNQ=F"},  # $2 per point
}


# --------------------------------------------------------------------------- config
@dataclass
class Config:
    symbol: str = "MES"
    # strategy
    or_minutes: int = 15
    session_start: str = "09:30"
    last_entry: str = "11:30"       # no new entries after this time
    flat_time: str = "15:55"        # close anything still open
    target_r: float = 1.5           # target = 1.5 x risk
    stop_mode: str = "range"        # "range" = other side of OR, "mid" = OR midpoint
    min_range_pts: float = 2.0      # skip dead, tiny ranges
    max_range_pts: float = 15.0     # skip huge ranges (stop too wide)
    direction: str = "both"         # both | long | short
    # costs - CHECK YOUR REAL TRADOVATE FEES and update these
    commission_per_side: float = 1.00   # $ per contract per side, all-in (commission + exchange fees)
    slippage_ticks: int = 1             # on entry and on stop / time exits
    # risk engine
    account: float = 50000.0
    sizing: str = "fixed"           # fixed | percent
    contracts: int = 1              # used when sizing = fixed
    risk_pct: float = 1.0           # used when sizing = percent
    max_contracts: int = 5
    max_risk_per_trade: float = 100.0   # $ - trade skipped if risk is bigger
    daily_loss_limit: float = 150.0     # $ - no more trades that day
    weekly_loss_limit: float = 400.0    # $ - no more trades that week
    max_trades_per_day: int = 1
    kill_switch_dd: float = 1500.0      # $ drawdown from peak -> bot stops for good


def _t(s: str) -> time:
    return datetime.strptime(s, "%H:%M").time()


# --------------------------------------------------------------------------- data
def _clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns=str.lower)
    need = ["open", "high", "low", "close"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        sys.exit(f"Data is missing columns: {missing}")
    if "volume" not in df.columns:
        df["volume"] = 0
    df = df[need + ["volume"]].astype(float).dropna()
    df = df[~df.index.duplicated()].sort_index()
    return df


def load_csv(path: str, csv_tz: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    lower = {c.lower().strip(): c for c in raw.columns}
    dtcol = next((lower[c] for c in ("datetime", "timestamp", "date", "time") if c in lower), None)
    if dtcol is None:
        sys.exit("CSV needs a datetime column (named datetime, timestamp, date or time).")
    idx = pd.to_datetime(raw[dtcol])
    idx = idx.dt.tz_localize(csv_tz) if idx.dt.tz is None else idx
    raw.index = pd.DatetimeIndex(idx).tz_convert(TZ)
    raw.columns = [c.lower().strip() for c in raw.columns]
    return _clean(raw)


def load_yf(symbol: str, interval: str, days: int) -> pd.DataFrame:
    try:
        import yfinance as yf
    except ImportError:
        sys.exit("yfinance not installed. Run: pip install yfinance")
    ticker = CONTRACTS[symbol]["yf"]
    df = yf.Ticker(ticker).history(period=f"{days}d", interval=interval, auto_adjust=False)
    if df.empty:
        sys.exit("Yahoo returned no data. Check your internet, or try --days 30.")
    df.index = pd.DatetimeIndex(df.index).tz_convert(TZ)
    return _clean(df)


def make_synthetic(days: int = 250, seed: int = 7, trend: float = 0.0) -> pd.DataFrame:
    """Random-walk 5-min bars. Results on this are MEANINGLESS - it only tests the code.
    With trend=0 there is no edge to find, so an honest backtester should show ~zero
    or negative results after costs. If it shows big profits here, something is wrong."""
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=days)
    rows, price = [], 5000.0
    for d in dates:
        drift = rng.normal(0, trend)
        times = pd.date_range(f"{d.date()} 09:30", f"{d.date()} 15:55", freq="5min", tz=TZ)
        for ts in times:
            o = price
            c = o + drift + rng.normal(0, 2.0)
            h = max(o, c) + abs(rng.normal(0, 1.0))
            l = min(o, c) - abs(rng.normal(0, 1.0))
            r = lambda x: round(x * 4) / 4
            rows.append((ts, r(o), r(h), r(l), r(c), 1000))
            price = c
    df = pd.DataFrame(rows, columns=["dt", "open", "high", "low", "close", "volume"]).set_index("dt")
    return df


# --------------------------------------------------------------------------- engine
def backtest(df: pd.DataFrame, cfg: Config):
    spec = CONTRACTS[cfg.symbol]
    tick = spec["tick"]
    pv = spec["tick_value"] / tick              # $ per point per contract
    slip = cfg.slippage_ticks * tick

    bar_min = int(round(pd.Series(df.index).diff().dropna().dt.total_seconds().median() / 60))
    if cfg.or_minutes % bar_min != 0:
        sys.exit(f"or_minutes ({cfg.or_minutes}) must be a multiple of the bar size ({bar_min} min).")
    s_start, last_entry, flat = _t(cfg.session_start), _t(cfg.last_entry), _t(cfg.flat_time)
    or_end = (datetime.combine(datetime.today(), s_start) + pd.Timedelta(minutes=cfg.or_minutes)).time()
    or_bars_needed = cfg.or_minutes // bar_min

    trades, skips = [], []
    equity = peak = cfg.account
    week_pnl, killed = {}, None
    rth = df.between_time(cfg.session_start, cfg.flat_time)
    all_days = sorted(set(rth.index.date))

    for day in all_days:
        if killed:
            break
        g = rth[rth.index.date == day]
        wk = tuple(pd.Timestamp(day).isocalendar()[:2])
        week_pnl.setdefault(wk, 0.0)
        if week_pnl[wk] <= -cfg.weekly_loss_limit:
            skips.append((day, "weekly loss limit"))
            continue

        or_df = g[g.index.time < or_end]
        if len(or_df) < or_bars_needed or or_df.index[0].time() != s_start:
            skips.append((day, "incomplete opening range"))
            continue
        hi, lo = or_df["high"].max(), or_df["low"].min()
        rng_pts = hi - lo
        if rng_pts < cfg.min_range_pts:
            skips.append((day, "range too small"))
            continue
        if rng_pts > cfg.max_range_pts:
            skips.append((day, "range too wide"))
            continue

        rest = g[g.index.time >= or_end]
        day_pnl, n_today, i = 0.0, 0, 0
        while (i < len(rest) - 1 and n_today < cfg.max_trades_per_day
               and day_pnl > -cfg.daily_loss_limit):
            if rest.index[i].time() >= last_entry:
                break
            bar = rest.iloc[i]
            side = 0
            if bar.close > hi and cfg.direction in ("both", "long"):
                side = 1
            elif bar.close < lo and cfg.direction in ("both", "short"):
                side = -1
            if side == 0:
                i += 1
                continue

            entry_ts = rest.index[i + 1]
            if entry_ts.time() >= flat:
                break
            entry = rest.iloc[i + 1].open + side * slip
            stop = (lo if side == 1 else hi) if cfg.stop_mode == "range" else (hi + lo) / 2
            risk_pts = (entry - stop) * side
            if risk_pts <= 0:                       # price already through the stop
                i += 1
                continue
            target = entry + side * cfg.target_r * risk_pts

            risk_per_ct = risk_pts * pv + slip * pv + 2 * cfg.commission_per_side
            qty = cfg.contracts if cfg.sizing == "fixed" else math.floor(
                equity * cfg.risk_pct / 100 / risk_per_ct)
            qty = min(qty, cfg.max_contracts)
            if qty * risk_per_ct > cfg.max_risk_per_trade:
                qty = math.floor(cfg.max_risk_per_trade / risk_per_ct)
            if qty < 1:
                skips.append((day, "risk too big for limits"))
                break

            exit_px = reason = exit_ts = None
            exit_j = len(rest)
            for j in range(i + 1, len(rest)):
                b, tj = rest.iloc[j], rest.index[j]
                if tj.time() >= flat:
                    exit_px, reason, exit_ts, exit_j = b.open - side * slip, "time", tj, j
                    break
                hit_stop = b.low <= stop if side == 1 else b.high >= stop
                hit_tgt = b.high > target if side == 1 else b.low < target
                if hit_stop:  # stop checked first = conservative
                    gapped = (b.open < stop) if side == 1 else (b.open > stop)
                    exit_px = (b.open if gapped else stop) - side * slip
                    reason, exit_ts, exit_j = "stop", tj, j
                    break
                if hit_tgt:
                    gapped = (b.open > target) if side == 1 else (b.open < target)
                    exit_px = b.open if gapped else target
                    reason, exit_ts, exit_j = "target", tj, j
                    break
            if exit_px is None:
                exit_px, reason, exit_ts = rest.iloc[-1].close - side * slip, "session end", rest.index[-1]

            pts = (exit_px - entry) * side
            net = pts * pv * qty - 2 * cfg.commission_per_side * qty
            equity += net
            day_pnl += net
            week_pnl[wk] += net
            peak = max(peak, equity)
            trades.append({
                "date": day, "side": "LONG" if side == 1 else "SHORT", "qty": qty,
                "entry_time": entry_ts.strftime("%H:%M"), "entry": round(entry, 2),
                "stop": round(stop, 2), "target": round(target, 2),
                "exit_time": exit_ts.strftime("%H:%M"), "exit": round(exit_px, 2),
                "exit_reason": reason, "range_pts": round(rng_pts, 2),
                "pnl_pts": round(pts, 2), "net_pnl": round(net, 2),
                "r_multiple": round(net / (qty * risk_per_ct), 2), "equity": round(equity, 2),
            })
            n_today += 1
            if peak - equity >= cfg.kill_switch_dd:
                killed = day
                break
            i = exit_j + 1

    return pd.DataFrame(trades), skips, killed, all_days


# --------------------------------------------------------------------------- metrics
def metrics(tr: pd.DataFrame, days, start_equity: float) -> dict:
    if tr.empty:
        return {"trades": 0}
    pnl = tr["net_pnl"]
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    eq = pd.concat([pd.Series([start_equity]), start_equity + pnl.cumsum()], ignore_index=True)
    daily = tr.groupby("date")["net_pnl"].sum().reindex(days, fill_value=0.0)
    sd = daily.std()
    streak = best = 0
    for p in pnl:
        streak = streak + 1 if p <= 0 else 0
        best = max(best, streak)
    return {
        "trades": len(tr),
        "win_rate_%": round(100 * len(wins) / len(tr), 1),
        "avg_win_$": round(wins.mean(), 2) if len(wins) else 0.0,
        "avg_loss_$": round(losses.mean(), 2) if len(losses) else 0.0,
        "profit_factor": round(wins.sum() / abs(losses.sum()), 2) if losses.sum() else float("inf"),
        "expectancy_$": round(pnl.mean(), 2),
        "expectancy_R": round(tr["r_multiple"].mean(), 3),
        "net_pnl_$": round(pnl.sum(), 2),
        "max_drawdown_$": round((eq.cummax() - eq).max(), 2),
        "sharpe_daily_ann": round(daily.mean() / sd * math.sqrt(252), 2) if sd > 0 else 0.0,
        "longest_losing_streak": best,
    }


def verdict(m_in: dict, m_out: dict) -> str:
    n = m_in.get("trades", 0) + m_out.get("trades", 0)
    if n < 50:
        return (f"NOT ENOUGH TRADES ({n}). You need 100+ trades over a year or more "
                "before trusting any number here. Get longer data.")
    pf_in, pf_out = m_in.get("profit_factor", 0), m_out.get("profit_factor", 0)
    if pf_out >= 1.2 and pf_in >= 1.2:
        return "PROMISING. Holds up on unseen data. Next step: paper trade it for 6-8 weeks."
    if pf_in >= 1.2 and pf_out < 1.05:
        return "LIKELY OVERFIT. Works on the data it was tuned on, fails on unseen data. Do not trade."
    if pf_out >= 1.05:
        return "MARGINAL. Small edge at best. Needs more data and testing before paper trading."
    return "NO EDGE YET. Do not trade this version. That's a useful result - it cost you nothing."


# --------------------------------------------------------------------------- reporting
def print_block(title: str, m: dict):
    print(f"\n  {title}")
    print("  " + "-" * 44)
    if m.get("trades", 0) == 0:
        print("  no trades")
        return
    for k, v in m.items():
        print(f"  {k:<24}{v:>18}")


def split(df: pd.DataFrame, frac: float = 0.7):
    days = sorted(set(df.index.date))
    cut = days[int(len(days) * frac)]
    return df[df.index.date < cut], df[df.index.date >= cut], cut


def run_sweep(df_in: pd.DataFrame, cfg: Config, bar_min: int) -> Config:
    grid = {
        "or_minutes": [m for m in (5, 15, 30) if m % bar_min == 0],
        "target_r": [1.0, 1.5, 2.0],
        "stop_mode": ["range", "mid"],
    }
    rows = []
    for vals in itertools.product(*grid.values()):
        c = replace(cfg, **dict(zip(grid.keys(), vals)))
        tr, _, _, days = backtest(df_in, c)
        m = metrics(tr, days, c.account)
        rows.append({**dict(zip(grid.keys(), vals)), **m})
    res = pd.DataFrame(rows)
    res = res[res["trades"] >= 15] if (res["trades"] >= 15).any() else res
    res = res.sort_values("expectancy_R", ascending=False)
    print("\n  PARAMETER SWEEP (in-sample only - out-of-sample stays untouched)")
    print(res[["or_minutes", "target_r", "stop_mode", "trades", "win_rate_%",
               "profit_factor", "expectancy_R", "net_pnl_$"]].head(8).to_string(index=False))
    best = res.iloc[0]
    return replace(cfg, or_minutes=int(best.or_minutes), target_r=float(best.target_r),
                   stop_mode=str(best.stop_mode))


def save_chart(tr: pd.DataFrame, cut, path: str, start_equity: float):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    if tr.empty:
        return
    x = pd.to_datetime(tr["date"])
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(x, tr["equity"], lw=1.6, color="#1f6feb")
    ax.axhline(start_equity, color="#888", lw=0.8, ls=":")
    ax.axvline(pd.Timestamp(cut), color="#d29922", ls="--", lw=1.2, label="out-of-sample starts")
    ax.set_title("ORB backtest - account equity after each trade")
    ax.set_ylabel("$")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------------- research log
LOG_PATH = "research/experiments.csv"
LOG_COLS = [
    "run_at", "hypothesis", "note", "code_version", "data_source", "symbol", "data_from", "data_to",
    "days", "bar_min", "or_minutes", "target_r", "stop_mode", "min_range_pts", "max_range_pts",
    "commission_per_side", "slippage_ticks", "swept",
    "is_trades", "is_win_rate", "is_profit_factor", "is_expectancy_R", "is_max_dd",
    "oos_trades", "oos_win_rate", "oos_profit_factor", "oos_expectancy_R", "oos_max_dd",
    "verdict",
]


def code_version() -> str:
    """Git commit of the code that produced this result (+ '-modified' if uncommitted edits)."""
    import subprocess
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                             text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "orb_backtest.py"],
                               capture_output=True, text=True).stdout.strip()
        return sha + ("-modified" if dirty else "")
    except Exception:
        return "unknown"


def log_experiment(row: dict) -> int:
    """Append one run to the research log. Returns how many runs this hypothesis now has."""
    import csv
    import os
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    new = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LOG_COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow(row)
    prior = pd.read_csv(LOG_PATH)
    return int((prior["hypothesis"].astype(str) == str(row["hypothesis"])).sum())


# --------------------------------------------------------------------------- main
def main():
    p = argparse.ArgumentParser(description="ORB futures backtester")
    p.add_argument("--demo", action="store_true", help="use random fake data (tests the code only)")
    p.add_argument("--source", choices=["yf"], help="download from Yahoo Finance")
    p.add_argument("--csv", help="path to your own OHLC csv")
    p.add_argument("--csv-tz", default=TZ, help="timezone of naive CSV timestamps")
    p.add_argument("--symbol", default="MES", choices=list(CONTRACTS))
    p.add_argument("--interval", default="5m", help="Yahoo bar size (5m gives ~60 days)")
    p.add_argument("--days", type=int, default=59)
    p.add_argument("--sweep", action="store_true", help="tune parameters on in-sample data")
    p.add_argument("--or-minutes", type=int)
    p.add_argument("--target-r", type=float)
    p.add_argument("--stop-mode", choices=["range", "mid"])
    p.add_argument("--account", type=float)
    p.add_argument("--commission", type=float, help="$ per contract per side")
    p.add_argument("--out", default="trades.csv")
    p.add_argument("--hyp", default="H-001", help="hypothesis id this run tests (see research/hypotheses.md)")
    p.add_argument("--note", default="", help="one line: what you changed or why you ran this")
    p.add_argument("--no-log", action="store_true", help="don't write to research/experiments.csv")
    a = p.parse_args()

    cfg = Config(symbol=a.symbol)
    for arg, field_ in (("or_minutes", "or_minutes"), ("target_r", "target_r"),
                        ("stop_mode", "stop_mode"), ("account", "account"),
                        ("commission", "commission_per_side")):
        if getattr(a, arg) is not None:
            cfg = replace(cfg, **{field_: getattr(a, arg)})

    if a.demo:
        df = make_synthetic()
        print("\n  *** DEMO MODE: random fake data with no edge in it. ***")
        print("  *** Expect break-even or a loss after costs. That proves the backtester is honest. ***")
    elif a.csv:
        df = load_csv(a.csv, a.csv_tz)
    elif a.source == "yf":
        df = load_yf(a.symbol, a.interval, a.days)
    else:
        p.error("choose --demo, --source yf, or --csv FILE")

    bar_min = int(round(pd.Series(df.index).diff().dropna().dt.total_seconds().median() / 60))
    first, last = df.index[0].date(), df.index[-1].date()
    print(f"\n  Data: {a.symbol}  {first} -> {last}  ({len(set(df.index.date))} days, {bar_min}-min bars)")

    df_in, df_out, cut = split(df)
    if a.sweep:
        cfg = run_sweep(df_in, cfg, bar_min)

    print("\n  SETTINGS")
    for k in ("or_minutes", "target_r", "stop_mode", "min_range_pts", "max_range_pts",
              "commission_per_side", "slippage_ticks", "contracts", "max_risk_per_trade",
              "daily_loss_limit", "weekly_loss_limit", "kill_switch_dd"):
        print(f"  {k:<24}{str(asdict(cfg)[k]):>18}")

    tr, skips, killed, days = backtest(df, cfg)
    tr_in = tr[pd.to_datetime(tr["date"]) < pd.Timestamp(cut)] if not tr.empty else tr
    tr_out = tr[pd.to_datetime(tr["date"]) >= pd.Timestamp(cut)] if not tr.empty else tr
    d_in = [d for d in days if d < cut]
    d_out = [d for d in days if d >= cut]

    m_all = metrics(tr, days, cfg.account)
    m_in = metrics(tr_in, d_in, cfg.account)
    m_out = metrics(tr_out, d_out, cfg.account)
    print_block("ALL DATA", m_all)
    print_block(f"IN-SAMPLE  (before {cut})", m_in)
    print_block(f"OUT-OF-SAMPLE  (from {cut})  <- the number that matters", m_out)

    if skips:
        s = pd.Series([r for _, r in skips]).value_counts()
        print("\n  Days skipped by rules:")
        for reason, n in s.items():
            print(f"    {reason:<28}{n:>5}")
    if killed:
        print(f"\n  !!! KILL SWITCH hit on {killed}. Live, the bot would have stopped here.")

    v = verdict(m_in, m_out)
    print(f"\n  VERDICT: {v}\n")

    if a.demo or a.no_log:
        print("  (Not logged: demo data or --no-log.)\n")
    else:
        source = "csv:" + a.csv if a.csv else f"yahoo:{a.interval}"
        row = {
            "run_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "hypothesis": a.hyp, "note": a.note,
            "code_version": code_version(), "data_source": source, "symbol": a.symbol,
            "data_from": first, "data_to": last, "days": len(set(df.index.date)), "bar_min": bar_min,
            **{k: asdict(cfg)[k] for k in ("or_minutes", "target_r", "stop_mode", "min_range_pts",
                                           "max_range_pts", "commission_per_side", "slippage_ticks")},
            "swept": a.sweep, "verdict": v.split(".")[0],
        }
        for tag, m in (("is", m_in), ("oos", m_out)):
            row[f"{tag}_trades"] = m.get("trades", 0)
            row[f"{tag}_win_rate"] = m.get("win_rate_%", "")
            row[f"{tag}_profit_factor"] = m.get("profit_factor", "")
            row[f"{tag}_expectancy_R"] = m.get("expectancy_R", "")
            row[f"{tag}_max_dd"] = m.get("max_drawdown_$", "")
        n = log_experiment(row)
        print(f"  Logged to {LOG_PATH} as run #{n} for {a.hyp}.")
        if n >= 10:
            print(f"  Caution: {n} tests on {a.hyp}. The more variations you try, the more likely")
            print("  a good result is luck. Raise the bar, or write a new hypothesis.")
        print()

    if not tr.empty:
        tr.to_csv(a.out, index=False)
        save_chart(tr, cut, "equity.png", cfg.account)
        print(f"  Saved: {a.out} (every trade) and equity.png (equity curve)\n")


if __name__ == "__main__":
    main()
