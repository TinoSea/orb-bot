"""LK_Forward rules as a pure engine (no broker code), for futures (MNQ / NQ).

Same rules as mt5/LK_Forward.mq5 v1.00, except the signal window and flat time, which are inputs
(futures default: signals 08:00-14:00 New York, flat 14:30). Differences from the MT5 bot, by design:
  - prices are the futures LAST trade price (MT5 used CFD bid for candles and mid for the trigger);
  - size is a fixed dollar risk capped by a contract limit (MT5: 1% of balance), plus a prop-firm guard
    that never lets a stop-out reach the account's Maximum Loss Limit floor.

Time is epoch seconds (UTC). New York days, Fridays and the window use America/New_York (DST-aware).
The engine never talks to a broker: the runner feeds it trade prices and tells it about fills and exits.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Callable, List, Optional
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


# ---------------------------------------------------------------- rules
@dataclass
class Rules:
    min_gap: float = 5.0          # smallest fair value gap, points
    lookback: int = 5             # gaps from the last N trading days before today
    stop_pts: float = 12.5        # stop distance, points
    target_pts: float = 16.25     # target distance, points (1.3R)
    trigger_off: float = 0.25     # stop-entry offset beyond the rejection candle
    arm_sec: int = 45             # trigger valid for this many seconds
    sig_from: str = "08:00"       # signals from (New York), candle close time
    sig_to: str = "14:00"         # signals until (New York), exclusive
    cap_min: int = 15             # close a trade after this many minutes
    flat: str = "14:30"           # close anything open at this New York time
    max_trades: int = 3           # max trades a day
    max_losses: int = 2           # stop for the day after this many losing trades
    no_friday: bool = True        # her rule: no trading on Fridays

    def check(self) -> None:
        if hhmm(self.flat) <= hhmm(self.sig_to):
            raise ValueError(f"flat time {self.flat} must be after the signal window end {self.sig_to}")
        if hhmm(self.sig_from) >= hhmm(self.sig_to):
            raise ValueError("sig_from must be before sig_to")


def hhmm(v: str) -> int:
    h, m = v.split(":")
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------- New York calendar helpers
def ny_date(ts: float) -> date:
    return datetime.fromtimestamp(ts, NY).date()


def ny_midnight(d: date) -> float:
    return datetime.combine(d, time(0, 0), NY).timestamp()


def ny_minute(ts: float) -> int:
    t = datetime.fromtimestamp(ts, NY)
    return t.hour * 60 + t.minute


def days_back(d: date, n: int) -> date:
    """The date n weekdays before d (same as the MT5 DaysBack: skips Saturdays and Sundays only)."""
    k = 0
    while k < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            k += 1
    return d


# ---------------------------------------------------------------- bars and zones
@dataclass
class Bar:
    t_open: float     # epoch seconds, bar start
    sec: int          # bar length in seconds
    open: float
    high: float
    low: float
    close: float

    @property
    def t_close(self) -> float:
        return self.t_open + self.sec


@dataclass
class Zone:
    supply: bool
    lo: float
    hi: float
    tf: str           # "5m" or "15m"
    formed: float     # epoch seconds: close time of the third candle
    used: bool = False


def find_zones(bars: List[Bar], tf: str, since: float, today: float, min_gap: float) -> List[Zone]:
    """Fair value gaps on CLOSED bars (oldest first), formed in [since, today], not yet closed through.
    Mirrors BuildZones() in LK_Forward.mq5 (bar i vs bar i-2; dead if a later close goes beyond the far edge)."""
    out = []
    n = len(bars)
    for i in range(2, n):
        a, c = bars[i - 2], bars[i]
        sup = c.high < a.low
        dem = c.low > a.high
        if not sup and not dem:
            continue
        lo = c.high if sup else a.high
        hi = a.low if sup else c.low
        formed = c.t_close
        if hi - lo < min_gap or formed < since or formed > today:
            continue
        dead = any((sup and bars[j].close > hi) or (dem and bars[j].close < lo) for j in range(i + 1, n))
        if dead:
            continue
        out.append(Zone(sup, lo, hi, tf, formed))
    return out


class BarBuilder:
    """Builds fixed-length bars from trade prices. on_price returns the bar that just CLOSED, if any
    (a bar closes when the first price of a later bar arrives, as in MT5)."""

    def __init__(self, sec: int):
        self.sec = sec
        self.k: Optional[int] = None
        self.bar: Optional[Bar] = None

    def reset(self) -> None:
        self.k, self.bar = None, None

    def on_price(self, ts: float, p: float) -> Optional[Bar]:
        k = int(ts // self.sec)
        if k != self.k:
            done = self.bar
            self.k = k
            self.bar = Bar(k * self.sec, self.sec, p, p, p, p)
            return done
        b = self.bar
        b.high = max(b.high, p)
        b.low = min(b.low, p)
        b.close = p
        return None


# ---------------------------------------------------------------- the engine
@dataclass
class Enter:
    side: int          # +1 long, -1 short
    price: float       # trade price that hit the trigger
    zone: Zone
    ts: float


@dataclass
class Exit:
    reason: str        # "cap" or "flat"
    ts: float


@dataclass
class Engine:
    rules: Rules
    bars_provider: Callable[[str, float], List[Bar]]   # (tf, since_epoch) -> CLOSED bars, oldest first
    log: Callable[[str], None] = print

    zones: List[Zone] = field(default_factory=list)
    day: Optional[date] = None
    trades: int = 0
    losses: int = 0
    arm_dir: int = 0
    arm_trig: float = 0.0
    arm_exp: float = 0.0
    arm_zone: Optional[Zone] = None
    entry_time: Optional[float] = None

    def __post_init__(self):
        self.rules.check()
        self.c15 = BarBuilder(15)
        self.b5 = BarBuilder(300)
        self.b15 = BarBuilder(900)

    # ---- day start
    def _new_day(self, d: date) -> None:
        self.day = d
        self.trades = self.losses = 0
        self.arm_dir, self.arm_zone = 0, None
        self.c15.reset()
        self.b5.reset()                    # no stale bar from an earlier day may kill a fresh zone
        self.b15.reset()
        today = ny_midnight(d)
        since = ny_midnight(days_back(d, self.rules.lookback))
        self.zones = []
        for tf, sec in (("5m", 300), ("15m", 900)):
            bars = self.bars_provider(tf, since - 2 * sec)
            self.zones += find_zones(bars, tf, since, today, self.rules.min_gap)
        self.log(f"{d}: {len(self.zones)} earlier-day zones live")

    # ---- zones broken by newly closed 5m / 15m bars
    def _kill(self, tf: str, close: float) -> None:
        keep = []
        for z in self.zones:
            if z.tf == tf and ((z.supply and close > z.hi) or (not z.supply and close < z.lo)):
                if self.arm_zone is z:
                    self.arm_dir, self.arm_zone = 0, None
                continue
            keep.append(z)
        self.zones = keep

    # ---- 15-second candle closed
    def _on_closed15(self, c: Bar, in_position: bool) -> None:
        r = self.rules
        mm = ny_minute(c.t_close)
        if mm < hhmm(r.sig_from) or mm >= hhmm(r.sig_to):
            return
        if in_position or self.trades >= r.max_trades or self.losses >= r.max_losses:
            return
        for d in (-1, 1):
            body = (c.open - c.close) * -d
            wick = c.high - max(c.open, c.close) if d < 0 else min(c.open, c.close) - c.low
            tip = c.high if d < 0 else c.low
            if body <= 0 or wick < body:
                continue
            for z in self.zones:
                if z.used or z.supply != (d < 0):
                    continue
                if tip < z.lo or tip > z.hi:
                    continue
                self.arm_dir, self.arm_zone = d, z
                self.arm_exp = c.t_close + r.arm_sec
                self.arm_trig = c.low - r.trigger_off if d < 0 else c.high + r.trigger_off
                return

    # ---- main entry point: one trade price
    def on_tick(self, ts: float, price: float, in_position: bool) -> list:
        r = self.rules
        actions: list = []
        d = ny_date(ts)
        if d != self.day:
            self._new_day(d)
        # manage the open trade (time cap and flat time)
        x = self.manage(ts, in_position)
        if x is not None:
            actions.append(x)
        wd = d.weekday()
        if wd >= 5 or (r.no_friday and wd == 4):
            return actions
        for b, tf in ((self.b5, "5m"), (self.b15, "15m")):
            done = b.on_price(ts, price)
            if done is not None:
                self._kill(tf, done.close)
        done = self.c15.on_price(ts, price)
        if done is not None:
            self._on_closed15(done, in_position)
        if not in_position and self.trades < r.max_trades and self.losses < r.max_losses:
            e = self._try_fill(ts, price)
            if e is not None:
                actions.append(e)
        return actions

    def manage(self, ts: float, in_position: bool) -> Optional[Exit]:
        """Time cap and flat time. Also called by the runner once a second when no price arrives."""
        if not in_position:
            return None
        r = self.rules
        cap = self.entry_time is not None and ts - self.entry_time >= r.cap_min * 60
        if cap or ny_minute(ts) >= hhmm(r.flat):
            return Exit("cap" if cap else "flat", ts)
        return None

    def _try_fill(self, ts: float, price: float) -> Optional[Enter]:
        if self.arm_dir == 0:
            return None
        if ts > self.arm_exp or self.arm_zone is None or self.arm_zone not in self.zones:
            self.arm_dir, self.arm_zone = 0, None
            return None
        d = self.arm_dir
        if not (price <= self.arm_trig if d < 0 else price >= self.arm_trig):
            return None
        z = self.arm_zone
        z.used = True                      # first try only, win or lose (even if the order is skipped)
        self.arm_dir, self.arm_zone = 0, None
        return Enter(d, price, z, ts)

    # ---- the runner reports what really happened
    def on_entry(self, ts: float) -> None:
        self.trades += 1
        self.entry_time = ts

    def on_exit(self, pnl: float) -> None:
        if pnl < 0:
            self.losses += 1
        self.entry_time = None


# ---------------------------------------------------------------- sizing and the prop-firm guard
@dataclass
class Guard:
    """Keeps every trade's stop-out above the Maximum Loss Limit floor.

    floor = start balance if a payout has been taken (FundedNext resets the MLL to the initial balance), otherwise
    min(start, highest end-of-day balance - mll): it trails up with end-of-day highs and locks at the start balance.
    floor_override > 0 replaces the calculation (copy it from the FundedNext dashboard if they ever disagree).
    """
    start_balance: float = 25000.0
    mll: float = 1000.0
    eod_high: float = 25000.0
    payout_taken: bool = False
    floor_override: float = 0.0
    buffer: float = 50.0              # extra room for slippage on the stop

    def floor(self) -> float:
        if self.floor_override > 0:
            return self.floor_override
        if self.payout_taken:
            return self.start_balance
        return min(self.start_balance, self.eod_high - self.mll)

    def record_eod(self, balance: float) -> None:
        self.eod_high = max(self.eod_high, balance)


def size(risk_dollars: float, stop_pts: float, point_value: float, max_contracts: int,
         balance: float, guard: Optional[Guard] = None, commission_rt: float = 0.0) -> int:
    """Contracts for one trade: fixed dollar risk, contract cap, and (if given) the guard."""
    per = stop_pts * point_value + commission_rt
    if per <= 0:
        return 0
    q = min(int(math.floor(risk_dollars / per + 1e-9)), max_contracts)
    if guard is not None:
        room = balance - guard.floor() - guard.buffer
        q = min(q, int(math.floor(room / per + 1e-9)))
    return max(q, 0)
