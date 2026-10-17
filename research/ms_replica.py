#!/usr/bin/env python3
"""
H-002 independent replica of mt5/MS_Gold.mq5 (v1.10)
====================================================

A second, separately written implementation of the same trading rules. If it produces
the same trade list as the MT5 Strategy Tester (see compare_trades.py), both are very
likely correct. It then runs the identical rules on every market in
research/h002_markets.csv, using the raw bars exported by mt5/ExportData.mq5.

Faithful to the EA:
  - server clock = New York + 7 h (FP Markets, fixed, as in the tester)
  - H1 and H4 bars built from the exported base bars, aligned to server midnight
  - ATR(14) = simple average of true range (MT5 iATR)
  - all decisions happen at the first tick of each new H1 bar, using closed bars only
  - ticks inside each base bar follow MT5 "1 minute OHLC": open, then low and high
    (bullish bar: low first, bearish bar: high first), then close; prices are bid,
    ask = bid + the bar's spread
  - stops and targets fill at their price, or at the open if price gapped through
  - swaps charged at server midnight, triple on the broker's 3-day weekday
  - position size from balance x risk%, rounded down to the volume step, skipped if
    the minimum lot would risk too much
Not modelled (research mode only): kill switch and daily/weekly loss limits (the tester
is run with these at 100% for research), execution delay.

Usage:
  python research/ms_replica.py --data data/export --label XAUUSD --tf M1 \
      --from 2023-01-01 --to 2025-06-30 --deposit 5000
  python research/ms_replica.py --data data/export --label ALL --from 2023-01-01 --to 2025-06-30
Options: --variant NAME (logged), --no-higher-low / --no-pullback / --no-session (ablations),
         --pessimistic (stop assumed first whenever stop and target share a bar),
         --commission USD_PER_LOT_PER_SIDE (default: research/h002_costs.csv), --swing-n, --zone-atr

Not financial advice. A backtest is evidence, not a promise.
"""

from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
MARKETS_CSV = os.path.join(HERE, "h002_markets.csv")
COSTS_CSV = os.path.join(HERE, "h002_costs.csv")
RUN_LOG = os.path.join(HERE, "h002_runs.csv")
RESULTS_DIR = os.path.join(HERE, "results", "h002")
SERVER_MINUS_NY = 7


# --------------------------------------------------------------------------- parameters
@dataclass
class Params:
    swing_n: int = 2
    swing_lookback: int = 300
    zone_atr: float = 0.3
    fail_atr: float = 0.5
    setup_expiry: int = 30
    stop_buf_atr: float = 0.1
    min_rr: float = 1.0
    default_r: float = 2.0
    max_hold_bars: int = 120
    close_friday: bool = True
    friday_close_ny: int = 16 * 60 + 30
    allow_long: bool = True
    allow_short: bool = True
    risk_pct: float = 1.0
    max_spread_frac: float = 0.15
    # ablations (all True = the registered rules)
    require_higher_low: bool = True
    require_pullback: bool = True
    use_session: bool = True
    pessimistic: bool = False


@dataclass
class Market:
    label: str
    sector: str
    zone: str
    start_min: int
    end_min: int
    mode_24x7: bool


@dataclass
class Spec:
    symbol: str
    digits: int
    point: float
    tick_size: float
    tick_value: float
    contract_size: float
    vol_min: float
    vol_step: float
    vol_max: float
    stops_level: int
    swap_mode: int
    swap_long: float
    swap_short: float
    swap_3day: int
    currency_profit: str


# --------------------------------------------------------------------------- loading
def hhmm(s: str) -> int:
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def load_markets(path: str = MARKETS_CSV) -> dict[str, Market]:
    df = pd.read_csv(path)
    out = {}
    for _, r in df.iterrows():
        out[r["label"]] = Market(r["label"], r["sector"], r["session_zone"], hhmm(r["session_start"]),
                                 hhmm(r["session_end"]), bool(int(r["mode_24x7"])))
    return out


def load_specs(path: str) -> dict[str, Spec]:
    df = pd.read_csv(path)
    out = {}
    for _, r in df.iterrows():
        out[r["label"]] = Spec(str(r["symbol"]), int(r["digits"]), float(r["point"]), float(r["tick_size"]),
                               float(r["tick_value"]), float(r["contract_size"]), float(r["volume_min"]),
                               float(r["volume_step"]), float(r["volume_max"]), int(r["stops_level"]),
                               int(r["swap_mode"]), float(r["swap_long"]), float(r["swap_short"]),
                               int(r["swap_3day"]), str(r["currency_profit"]).upper())
    return out


def load_commissions(path: str = COSTS_CSV) -> dict[str, float]:
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    return dict(zip(df["label"], df["commission_usd_per_lot_side"].astype(float)))


def load_spread_mults(path: str = COSTS_CSV) -> dict[str, float]:
    """Calibrated real-spread / bar-spread multipliers (amendment 14c). 1.0 = bar spreads as stored."""
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    if "spread_mult" not in df.columns:
        return {}
    return dict(zip(df["label"], df["spread_mult"].astype(float)))


def load_bars(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M")
    df = df.set_index("time").sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df[["open", "high", "low", "close", "spread"]].astype(float)


def resample(bars: pd.DataFrame, rule: str) -> pd.DataFrame:
    agg = bars.resample(rule, origin="epoch", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last"})
    return agg.dropna()


def atr_sma(df: pd.DataFrame, n: int = 14) -> np.ndarray:
    """MT5 iATR: simple moving average of true range."""
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    prev_c = np.concatenate([[np.nan], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    tr[0] = h[0] - l[0]
    return pd.Series(tr).rolling(n).mean().values


def fractal_flags(h: np.ndarray, l: np.ndarray, n: int):
    """Swing high: strictly above the n older bars, at least as high as the n newer bars
    (EA: h[i] <= older -> no, h[i] < newer -> no). Swing lows mirror this."""
    size = len(h)
    is_h = np.zeros(size, bool)
    is_l = np.zeros(size, bool)
    if size < 2 * n + 1:
        return is_h, is_l
    ok_h = np.ones(size - 2 * n, bool)
    ok_l = np.ones(size - 2 * n, bool)
    mid = slice(n, size - n)
    for k in range(1, n + 1):
        ok_h &= h[mid] > h[n - k:size - n - k]
        ok_h &= h[mid] >= h[n + k:size - n + k]
        ok_l &= l[mid] < l[n - k:size - n - k]
        ok_l &= l[mid] <= l[n + k:size - n + k]
    is_h[mid] = ok_h
    is_l[mid] = ok_l
    return is_h, is_l


# --------------------------------------------------------------------------- clocks
def nth_sunday(y: int, m: int, n: int) -> datetime:
    d = datetime(y, m, 1)
    first = 1 + (6 - d.weekday()) % 7          # Python: Monday=0 ... Sunday=6
    return datetime(y, m, first + 7 * (n - 1))


def last_sunday(y: int, m: int) -> datetime:
    d = datetime(y, m, 31)
    return d - timedelta(days=(d.weekday() + 1) % 7)


def us_dst(gmt: datetime) -> bool:
    start = nth_sunday(gmt.year, 3, 2) + timedelta(hours=7)
    end = nth_sunday(gmt.year, 11, 1) + timedelta(hours=6)
    return start <= gmt < end


def eu_dst(gmt: datetime) -> bool:
    return last_sunday(gmt.year, 3) + timedelta(hours=1) <= gmt < last_sunday(gmt.year, 10) + timedelta(hours=1)


def zone_time(ny: datetime, zone: str) -> datetime:
    if zone == "NEW_YORK":
        return ny
    gmt = ny + timedelta(hours=4 if us_dst(ny + timedelta(hours=5)) else 5)
    if zone == "LONDON":
        return gmt + timedelta(hours=1 if eu_dst(gmt) else 0)
    if zone == "FRANKFURT":
        return gmt + timedelta(hours=2 if eu_dst(gmt) else 1)
    if zone == "TOKYO":
        return gmt + timedelta(hours=9)
    raise ValueError(zone)


# --------------------------------------------------------------------------- engine
@dataclass
class Position:
    dir: int
    entry_time: datetime
    entry: float
    sl: float
    tp: float
    lots: float
    risk_money: float
    risk_price: float
    level: float
    swap: float = 0.0
    worst: float = 0.0          # adverse excursion in price
    best: float = 0.0           # favourable excursion in price
    last_day: object = None


class Replica:
    def __init__(self, bars: pd.DataFrame, spec: Spec, mkt: Market, prm: Params,
                 deposit: float, commission: float = 0.0, fx: dict | None = None, spread_mult: float = 1.0):
        self.b = bars
        self.spec, self.mkt, self.p = spec, mkt, prm
        self.balance = deposit
        self.commission = commission
        self.spread_mult = spread_mult
        self.fx = fx or {}
        self.h1 = resample(bars, "1h")
        self.h4 = resample(bars, "4h")
        self.atr1 = atr_sma(self.h1)
        self.atr4 = atr_sma(self.h4)
        self.h4_hi = self.h4["high"].values
        self.h4_lo = self.h4["low"].values
        self.h4_cl = self.h4["close"].values
        self.h4_t = self.h4.index.values
        self.h1_t = self.h1.index.values
        self.fh, self.fl = fractal_flags(self.h4_hi, self.h4_lo, prm.swing_n)
        # state
        self.pos: Position | None = None
        self.setup_dir = 0
        self.level = 0.0
        self.setup_bars = 0
        self.touched = False
        self.pb = 0.0
        self.last_struct = None
        self.trades: list[dict] = []
        self.events = {"setups": 0, "cancel_failed": 0, "cancel_expired": 0, "skip_min_lot": 0,
                       "skip_spread": 0, "entries": 0}

    # ---- helpers
    def norm(self, p: float) -> float:
        ts = self.spec.tick_size
        if ts > 0:
            p = round(p / ts) * ts
        return round(p, self.spec.digits)

    def vpp(self, t) -> float:
        """Account currency (USD) per 1.0 price move per 1 lot at time t."""
        cs, ccy = self.spec.contract_size, self.spec.currency_profit
        if ccy == "USD":
            return cs
        conv = self.fx.get(ccy)
        if conv is not None:
            s, invert = conv
            i = s.index.searchsorted(t, side="right") - 1
            if i >= 0:
                px = float(s.iloc[i])
                return cs / px if invert else cs * px
        return self.spec.tick_value / self.spec.tick_size if self.spec.tick_size > 0 else 0.0

    def h4_k1(self, t) -> int:
        """Index of the last CLOSED 4H bar at tick time t (EA: shift 1)."""
        return int(np.searchsorted(self.h4_t, np.datetime64(pd.Timestamp(t).floor("4h")), side="left")) - 1

    def h1_j1(self, t) -> int:
        return int(np.searchsorted(self.h1_t, np.datetime64(pd.Timestamp(t).floor("1h")), side="left")) - 1

    def swings(self, k1: int):
        got = min(self.p.swing_lookback, k1 + 1)
        lo = k1 - got + 1 + self.p.swing_n
        hi = k1 - self.p.swing_n
        if hi < lo:
            return [], []
        idx = np.arange(lo, hi + 1)
        hs = [(int(i), float(self.h4_hi[i])) for i in idx[self.fh[lo:hi + 1]]]
        ls = [(int(i), float(self.h4_lo[i])) for i in idx[self.fl[lo:hi + 1]]]
        return hs, ls

    def in_session(self, t) -> bool:
        p, m = self.p, self.mkt
        if m.mode_24x7:
            return True
        ny = pd.Timestamp(t).to_pydatetime() - timedelta(hours=SERVER_MINUS_NY)
        if p.close_friday and ny.weekday() == 4 and ny.hour * 60 + ny.minute >= p.friday_close_ny:
            return False
        if not p.use_session:
            return ny.weekday() < 5
        loc = zone_time(ny, m.zone)
        if loc.weekday() > 4:
            return False
        mm = loc.hour * 60 + loc.minute
        return m.start_min <= mm < m.end_min

    # ---- EA: CheckForSetup
    def check_for_setup(self, t):
        k1 = self.h4_k1(t)
        if k1 < 2:
            return
        sb = self.h4_t[k1]
        if self.last_struct is not None and sb == self.last_struct:
            return
        self.last_struct = sb
        hs, ls = self.swings(k1)
        if len(hs) < 2 or len(ls) < 2:
            return
        last_h, prev_h = hs[-1][1], hs[-2][1]
        last_l, prev_l = ls[-1][1], ls[-2][1]
        c1, c2 = self.h4_cl[k1], self.h4_cl[k1 - 1]
        hl_ok = (last_l > prev_l) or not self.p.require_higher_low
        lh_ok = (last_h < prev_h) or not self.p.require_higher_low
        if self.p.allow_long and hl_ok and c1 > last_h and c2 <= last_h:
            self.setup_dir, self.level = 1, last_h
        elif self.p.allow_short and lh_ok and c1 < last_l and c2 >= last_l:
            self.setup_dir, self.level = -1, last_l
        if self.setup_dir != 0:
            self.setup_bars, self.touched, self.pb = 0, False, 0.0
            self.events["setups"] += 1

    def cancel(self, why: str):
        if self.setup_dir == 0:
            return
        if why in ("failed", "expired"):
            self.events["cancel_" + why] += 1
        self.setup_dir, self.touched = 0, False

    # ---- EA: FindTarget
    def find_target(self, d: int, entry: float, risk: float, k1: int) -> float:
        hs, ls = self.swings(k1)
        best = 0.0
        if d > 0:
            for _, px in hs:
                if px >= entry + self.p.min_rr * risk and (best == 0.0 or px < best):
                    best = px
        else:
            for _, px in ls:
                if px <= entry - self.p.min_rr * risk and (best == 0.0 or px > best):
                    best = px
        return best if best > 0.0 else entry + d * self.p.default_r * risk

    # ---- EA: TryEnter (at the first tick of an H1 bar: bid = bar open)
    def try_enter(self, d: int, t, bid: float, spread: float, atr_e: float, k1: int):
        ask = bid + spread
        entry = ask if d > 0 else bid
        stop = self.pb - self.p.stop_buf_atr * atr_e if d > 0 else self.pb + self.p.stop_buf_atr * atr_e
        risk = (entry - stop) * d
        if risk <= 0:
            self.cancel("through_stop")
            return
        if spread > self.p.max_spread_frac * risk:
            self.events["skip_spread"] += 1
            return
        if risk < self.spec.stops_level * self.spec.point:
            self.cancel("stops_level")
            return
        vpp = self.vpp(t)
        step, vmin, vmax = self.spec.vol_step, self.spec.vol_min, self.spec.vol_max
        if vpp <= 0 or step <= 0:
            return
        risk_money = self.balance * self.p.risk_pct / 100.0
        lots = math.floor(risk_money / (risk * vpp) / step + 1e-9) * step
        lots = min(lots, vmax)
        if lots < vmin - 1e-9:
            self.events["skip_min_lot"] += 1
            self.cancel("min_lot")
            return
        lots = round(lots, max(0, int(math.ceil(-math.log10(step) - 1e-9))))
        target = self.find_target(d, entry, risk, k1)
        sl, tp = self.norm(stop), self.norm(target)
        self.pos = Position(d, pd.Timestamp(t).to_pydatetime(), entry, sl, tp, lots, lots * risk * vpp,
                            risk, self.level, last_day=pd.Timestamp(t).date())
        self.events["entries"] += 1
        self.setup_dir, self.touched = 0, False

    # ---- EA: ManageSetup
    def manage_setup(self, t, bid: float, spread: float):
        self.setup_bars += 1
        k1, j1 = self.h4_k1(t), self.h1_j1(t)
        if k1 < 1 or j1 < 1:
            return
        atr_s, atr_e = self.atr4[k1], self.atr1[j1]
        if not (atr_s > 0 and atr_e > 0):
            return
        sc1 = self.h4_cl[k1]
        d = self.setup_dir
        if d > 0 and sc1 < self.level - self.p.fail_atr * atr_s:
            self.cancel("failed")
            return
        if d < 0 and sc1 > self.level + self.p.fail_atr * atr_s:
            self.cancel("failed")
            return
        if self.setup_bars > self.p.setup_expiry:
            self.cancel("expired")
            return
        eh, el, ec = self.h1["high"].iat[j1], self.h1["low"].iat[j1], self.h1["close"].iat[j1]
        ph, pl = self.h1["high"].iat[j1 - 1], self.h1["low"].iat[j1 - 1]
        zone = self.p.zone_atr * atr_s
        if d > 0:
            hit = (el <= self.level + zone) or not self.p.require_pullback
            if not self.touched and hit:
                self.touched, self.pb = True, el
            elif self.touched:
                self.pb = min(self.pb, el)
            if self.touched and ec > ph and ec > self.level and self.in_session(t):
                self.try_enter(1, t, bid, spread, atr_e, k1)
        else:
            hit = (eh >= self.level - zone) or not self.p.require_pullback
            if not self.touched and hit:
                self.touched, self.pb = True, eh
            elif self.touched:
                self.pb = max(self.pb, eh)
            if self.touched and ec < pl and ec < self.level and self.in_session(t):
                self.try_enter(-1, t, bid, spread, atr_e, k1)

    # ---- position handling
    def close(self, t, price: float, reason: str):
        ps = self.pos
        vpp = self.vpp(t)
        gross = (price - ps.entry) * ps.dir * ps.lots * vpp
        comm = 2 * self.commission * ps.lots
        net = gross + ps.swap - comm
        self.balance += net
        self.trades.append({
            "symbol": self.spec.symbol, "label": self.mkt.label, "sector": self.mkt.sector,
            "side": "LONG" if ps.dir > 0 else "SHORT", "level": round(ps.level, 6),
            "entry_time": ps.entry_time, "entry": round(ps.entry, 6), "sl": ps.sl, "tp": ps.tp,
            "lots": ps.lots, "risk_money": round(ps.risk_money, 4),
            "exit_time": pd.Timestamp(t).to_pydatetime(), "exit": round(price, 6), "reason": reason,
            "gross": round(gross, 4), "swap": round(ps.swap, 4), "commission": round(comm, 4),
            "net": round(net, 4), "R": round(net / ps.risk_money, 4) if ps.risk_money > 0 else np.nan,
            "mae_R": round(ps.worst / ps.risk_price, 4), "mfe_R": round(ps.best / ps.risk_price, 4),
            "hours": round((pd.Timestamp(t).to_pydatetime() - ps.entry_time).total_seconds() / 3600, 2),
            "balance": round(self.balance, 4),
        })
        self.pos = None

    def charge_swap(self, t):
        ps, sp = self.pos, self.spec
        day = pd.Timestamp(t).date()
        while ps.last_day < day:
            wd = (ps.last_day.weekday() + 1) % 7            # MT5: Sunday=0
            mult = 3 if wd == sp.swap_3day else 1
            rate = sp.swap_long if ps.dir > 0 else sp.swap_short
            if sp.swap_mode == 1:                            # points
                ps.swap += rate * sp.point * self.vpp(t) * ps.lots * mult
            elif sp.swap_mode in (2, 4):                     # money per lot (profit or deposit currency)
                ps.swap += rate * ps.lots * mult * (self.vpp(t) / sp.contract_size if sp.swap_mode == 2 else 1.0)
            elif sp.swap_mode == 5:                          # annual interest on current price
                ps.swap += ps.entry * ps.lots * self.vpp(t) * rate / 100.0 / 360.0 * mult
            ps.last_day = ps.last_day + timedelta(days=1)

    def check_exit(self, t, bid: float, spread: float, is_open: bool) -> bool:
        ps = self.pos
        px = bid if ps.dir > 0 else bid + spread
        move = (px - ps.entry) * ps.dir
        ps.best = max(ps.best, move)
        ps.worst = max(ps.worst, -move)
        if ps.dir > 0:
            if px <= ps.sl:
                self.close(t, px if (is_open and px < ps.sl) else ps.sl, "stop")
                return True
            if px >= ps.tp:
                self.close(t, px if (is_open and px > ps.tp) else ps.tp, "target")
                return True
        else:
            if px >= ps.sl:
                self.close(t, px if (is_open and px > ps.sl) else ps.sl, "stop")
                return True
            if px <= ps.tp:
                self.close(t, px if (is_open and px < ps.tp) else ps.tp, "target")
                return True
        return False

    def ticks(self, o, h, l, c):
        if self.p.pessimistic and self.pos is not None:
            mid = [l, h] if self.pos.dir > 0 else [h, l]       # adverse extreme first
        else:
            mid = [l, h] if c >= o else [h, l]
        return [o] + mid + [c]

    # ---- main loop
    def run(self, start, end) -> pd.DataFrame:
        b = self.b
        times = b.index
        o, h, l, c = (b[x].values for x in ("open", "high", "low", "close"))
        raw = b["spread"].values
        if self.spread_mult != 1.0:          # calibrated costs: floor at 1 point, then scale (amendment 14c)
            raw = np.maximum(raw, 1.0) * self.spread_mult
        spr = raw * self.spec.point
        h1_of = times.floor("1h")
        cur_h1 = None
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        p = self.p
        for i in range(len(times)):
            t = times[i]
            new_bar = h1_of[i] != cur_h1
            cur_h1 = h1_of[i]
            if t > end:                      # tester closes anything still open at the end date
                if self.pos is not None:
                    px = o[i] if self.pos.dir > 0 else o[i] + spr[i]
                    self.close(t, px, "end_of_test")
                break
            # rollover swaps, then the open tick
            if self.pos is not None:
                if pd.Timestamp(t).date() > self.pos.last_day:
                    self.charge_swap(t)
                if self.check_exit(t, o[i], spr[i], True):
                    pass
            # Friday close
            if self.pos is not None and p.close_friday and not self.mkt.mode_24x7:
                ny = t.to_pydatetime() - timedelta(hours=SERVER_MINUS_NY)
                if ny.weekday() == 4 and ny.hour * 60 + ny.minute >= p.friday_close_ny:
                    px = o[i] if self.pos.dir > 0 else o[i] + spr[i]
                    self.close(t, px, "friday")
            # EA logic on the first tick of a new H1 bar
            if new_bar and start <= t <= end:
                if self.pos is not None:
                    held = (t.to_pydatetime() - self.pos.entry_time).total_seconds()
                    if held >= p.max_hold_bars * 3600:
                        px = o[i] if self.pos.dir > 0 else o[i] + spr[i]
                        self.close(t, px, "time")
                elif self.setup_dir == 0:
                    self.check_for_setup(t)
                else:
                    self.manage_setup(t, o[i], spr[i])
            # remaining ticks of this bar
            if self.pos is not None:
                for k, px in enumerate(self.ticks(o[i], h[i], l[i], c[i])):
                    if k == 0:
                        continue
                    if self.check_exit(t, px, spr[i], False):
                        break
        if self.pos is not None:
            self.close(times[-1], c[-1], "end_of_data")
        return pd.DataFrame(self.trades)


# --------------------------------------------------------------------------- metrics
def metrics(tr: pd.DataFrame) -> dict:
    if tr.empty:
        return {"trades": 0}
    r = tr["R"].dropna()
    wins, losses = r[r > 0], r[r <= 0]
    eq = tr["balance"].values
    start_bal = eq[0] - tr["net"].values[0]
    curve = np.concatenate([[start_bal], eq])
    dd = (np.maximum.accumulate(curve) - curve) / np.maximum.accumulate(curve)
    out = {
        "trades": int(len(r)),
        "win_rate_%": round(100 * len(wins) / len(r), 1),
        "profit_factor": round(wins.sum() / abs(losses.sum()), 2) if losses.sum() != 0 else float("inf"),
        "expectancy_R": round(r.mean(), 3),
        "total_R": round(r.sum(), 2),
        "max_dd_%": round(100 * dd.max(), 1),
        "avg_hours": round(tr["hours"].mean(), 1),
    }
    for side in ("LONG", "SHORT"):
        s = tr.loc[tr["side"] == side, "R"]
        sw, sl = s[s > 0].sum(), abs(s[s <= 0].sum())
        out[f"{side.lower()}_trades"] = int(len(s))
        out[f"{side.lower()}_pf"] = round(sw / sl, 2) if sl > 0 else (float("inf") if sw > 0 else 0.0)
    return out


def by_year(tr: pd.DataFrame) -> pd.DataFrame:
    if tr.empty:
        return pd.DataFrame()
    g = tr.assign(year=pd.to_datetime(tr["entry_time"]).dt.year).groupby("year")["R"]
    return pd.DataFrame({"trades": g.size(), "total_R": g.sum().round(2), "expectancy_R": g.mean().round(3)})


# --------------------------------------------------------------------------- CLI
def code_version() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                             check=True, cwd=HERE).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "ms_replica.py"], capture_output=True,
                               text=True, cwd=HERE).stdout.strip()
        return sha + ("-modified" if dirty else "")
    except Exception:
        return "unknown"


def fx_table(data_dir: str, tf: str) -> dict:
    """Profit-currency -> (close series, invert) for converting P&L to USD."""
    out = {}
    for ccy, (label, invert) in {"EUR": ("EURUSD", False), "GBP": ("GBPUSD", False),
                                 "AUD": ("AUDUSD", False), "JPY": ("USDJPY", True)}.items():
        path = os.path.join(data_dir, f"{label}_{tf}.csv")
        if os.path.exists(path):
            out[ccy] = (load_bars(path)["close"], invert)
    return out


def main():
    ap = argparse.ArgumentParser(description="H-002 independent replica of MS_Gold.mq5")
    ap.add_argument("--data", required=True, help="folder with ExportData.mq5 output")
    ap.add_argument("--label", default="XAUUSD", help="market label, or ALL")
    ap.add_argument("--tf", default="M5", help="base bars to use: M1 or M5")
    ap.add_argument("--from", dest="start", required=True)
    ap.add_argument("--to", dest="end", required=True)
    ap.add_argument("--deposit", type=float, default=5000.0)
    ap.add_argument("--commission", type=float, default=None,
                    help="USD per lot per side for every market (default: per market from h002_costs.csv)")
    ap.add_argument("--variant", default="V0-registered", help="name logged in h002_runs.csv")
    ap.add_argument("--note", default="")
    ap.add_argument("--swing-n", type=int)
    ap.add_argument("--zone-atr", type=float)
    ap.add_argument("--no-higher-low", action="store_true")
    ap.add_argument("--no-pullback", action="store_true")
    ap.add_argument("--no-session", action="store_true")
    ap.add_argument("--pessimistic", action="store_true")
    ap.add_argument("--no-log", action="store_true")
    ap.add_argument("--bar-spreads", action="store_true",
                    help="use the stored bar spreads as-is (Gate 0: matches the MT5 tester)")
    ap.add_argument("--spread-x", type=float, default=1.0, help="extra spread multiplier (R5 uses 2)")
    a = ap.parse_args()

    prm = Params(require_higher_low=not a.no_higher_low, require_pullback=not a.no_pullback,
                 use_session=not a.no_session, pessimistic=a.pessimistic)
    if a.swing_n:
        prm.swing_n = a.swing_n
    if a.zone_atr is not None:
        prm.zone_atr = a.zone_atr

    markets = load_markets()
    specs = load_specs(os.path.join(a.data, "specs.csv"))
    labels = [m for m in markets if m in specs] if a.label.upper() == "ALL" else [a.label]
    fx = fx_table(a.data, a.tf)
    comm = load_commissions()
    smult = load_spread_mults()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    rows = []
    for lab in labels:
        path = os.path.join(a.data, f"{lab}_{a.tf}.csv")
        if lab not in specs or not os.path.exists(path):
            print(f"  {lab}: no data ({path}) - skipped")
            continue
        bars = load_bars(path)
        c = a.commission if a.commission is not None else comm.get(lab, 0.0)
        sm = (1.0 if a.bar_spreads else smult.get(lab, 1.0)) * a.spread_x
        rep = Replica(bars, specs[lab], markets[lab], prm, a.deposit, c, fx, sm)
        tr = rep.run(a.start, a.end)
        out = os.path.join(RESULTS_DIR, f"{a.variant}_{lab}_{a.tf}_{a.start}_{a.end}.csv")
        tr.to_csv(out, index=False)
        m = metrics(tr)
        print(f"\n  {lab} ({specs[lab].symbol}, {markets[lab].sector}) {a.start} -> {a.end}  [{a.variant}]")
        for k, v in m.items():
            print(f"    {k:<16}{v}")
        print(f"    events          {rep.events}")
        yb = by_year(tr)
        if not yb.empty:
            print("    by year:\n" + "\n".join("      " + line for line in yb.to_string().splitlines()))
        rows.append({"run_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "variant": a.variant, "note": a.note,
                     "code_version": code_version(), "label": lab, "sector": markets[lab].sector,
                     "base_tf": a.tf, "from": a.start, "to": a.end, "params": str(asdict(prm)), "spread_mult": sm, "commission": c,
                     **m, "trades_file": os.path.relpath(out, HERE)})
    if rows and not a.no_log:
        df = pd.DataFrame(rows)
        df.to_csv(RUN_LOG, mode="a", header=not os.path.exists(RUN_LOG), index=False)
        n_var = pd.read_csv(RUN_LOG)["variant"].nunique()
        print(f"\n  Logged to research/h002_runs.csv. Distinct variants tried so far: {n_var}")


if __name__ == "__main__":
    main()
