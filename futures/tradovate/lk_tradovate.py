"""LK_Forward on Tradovate futures (MNQ by default). Run from the orb-bot folder:

    python futures/tradovate/lk_tradovate.py              # uses futures/tradovate/lk.env

Signal windows (v1.10): Asia 18:00-03:00, London 03:00-08:00, New York 08:00-14:00 (New York time), flat 14:30.
Starts in DRY RUN (LK_DRY_RUN=1): it reads live prices, finds signals and paper-trades them itself
(stop, target, 15-minute cap, flat time), writing every step to the journal. No orders are sent.
Set LK_DRY_RUN=0 only after a few dry-run days look right, and only on the Tradovate DEMO first.
Settings: futures/tradovate/lk.env (copy lk.env.example). Setup: futures/README.md.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import queue
import sys
import time
from datetime import datetime
from typing import List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lk_core import (NY, Bar, Engine, Enter, Exit, Guard, Rules, in_flat_period, size,  # noqa: E402
                     trading_day)
from tradovate_client import MarketData, Tradovate, TradovateError  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
VERSION = "1.10-futures"
log = logging.getLogger("lk")


# ---------------------------------------------------------------- settings
def load_env(path: str) -> dict:
    cfg = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.split(" #")[0].split("\t#")[0]          # allow comments after a value
                cfg[k.strip()] = v.strip().strip('"').strip("'")
    for k, v in os.environ.items():
        if k.startswith("LK_"):
            cfg[k] = v
    return cfg


class Cfg:
    def __init__(self, d: dict):
        g = lambda k, default="": d.get(k, default)  # noqa: E731
        self.env = g("LK_ENV", "demo")
        self.user, self.password = g("LK_USER"), g("LK_PASSWORD")
        self.app_id, self.app_version = g("LK_APP_ID", "orb-bot"), g("LK_APP_VERSION", "1.0")
        self.cid, self.sec, self.device_id = g("LK_CID"), g("LK_SEC"), g("LK_DEVICE_ID", "orb-bot-mac")
        self.md_url = g("LK_MD_URL")
        self.account = g("LK_ACCOUNT")
        self.symbol = g("LK_SYMBOL", "MNQZ6")
        self.point_value = float(g("LK_POINT_VALUE", "2"))
        self.tick = float(g("LK_TICK_SIZE", "0.25"))
        self.risk = float(g("LK_RISK_DOLLARS", "100"))
        self.max_contracts = int(g("LK_MAX_CONTRACTS", "10"))
        self.commission_rt = float(g("LK_COMMISSION_RT", "1.00"))
        self.dry = g("LK_DRY_RUN", "1") != "0"
        self.allow_live = g("LK_ALLOW_LIVE_ENV", "0") == "1"
        self.no_trade_dates = {x.strip() for x in g("LK_NO_TRADE_DATES").split(",") if x.strip()}
        self.guard = Guard(start_balance=float(g("LK_START_BALANCE", "25000")), mll=float(g("LK_MLL", "1000")),
                           payout_taken=g("LK_PAYOUT_TAKEN", "0") == "1",
                           floor_override=float(g("LK_FLOOR_OVERRIDE", "0")), buffer=float(g("LK_BUFFER", "50")))
        self.guard.eod_high = self.guard.start_balance
        windows = g("LK_WINDOWS")
        if not windows and g("LK_SIG_FROM"):                  # old single-window settings still work
            windows = f'{g("LK_SIG_FROM")}-{g("LK_SIG_TO", "14:00")}'
        self.rules = Rules(windows=windows or Rules.windows, flat=g("LK_FLAT", "14:30"))


# ---------------------------------------------------------------- journal and state
JOURNAL_COLS = ["time_ny", "trading_day", "session", "event", "side", "price", "sl", "tp", "zone_tf", "zone_lo",
                "zone_hi", "contracts", "profit", "balance", "floor", "note"]


def journal(row: dict) -> None:
    if "ts" in row:
        row = dict(row, time_ny=now_ny(row["ts"]), trading_day=trading_day(row["ts"]).isoformat())
    os.makedirs(os.path.join(HERE, "journal"), exist_ok=True)
    path = os.path.join(HERE, "journal", "LK_futures_journal_v110.csv")
    new = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=JOURNAL_COLS, extrasaction="ignore")
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in JOURNAL_COLS})


def now_ny(ts: float) -> str:
    return datetime.fromtimestamp(ts, NY).strftime("%Y-%m-%d %H:%M:%S")


def load_state(guard: Guard) -> dict:
    path = os.path.join(HERE, "journal", "lk_state.json")
    if os.path.exists(path):
        st = json.load(open(path))
        guard.eod_high = max(guard.eod_high, float(st.get("eod_high", guard.eod_high)))
        return st
    return {}


def save_state(st: dict) -> None:
    os.makedirs(os.path.join(HERE, "journal"), exist_ok=True)
    json.dump(st, open(os.path.join(HERE, "journal", "lk_state.json"), "w"), indent=1)


def rnd(p: float, tick: float) -> float:
    return round(round(p / tick) * tick, 10)


# ---------------------------------------------------------------- bars for the zones
def make_provider(md: MarketData, symbol: str):
    def provider(tf: str, since: float) -> List[Bar]:
        minutes = 5 if tf == "5m" else 15
        sec = minutes * 60
        raw = md.bars(symbol, minutes, since)
        if not raw:
            log.warning("no %s bars from Tradovate", tf)
            return []
        now = time.time()
        stamps = [datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00")).timestamp() for b in raw]
        end_stamped = max(stamps) > now + 1          # a timestamp in the future means bars are stamped at their end
        out = []
        for t, b in zip(stamps, raw):
            t_open = t - sec if end_stamped else t
            if t_open + sec > now:                   # still forming: not a closed bar
                continue
            out.append(Bar(t_open, sec, float(b["open"]), float(b["high"]), float(b["low"]), float(b["close"])))
        log.info("%s: %d closed bars from %s (stamped at bar %s)", tf, len(out), now_ny(since),
                 "end" if end_stamped else "start")
        return out
    return provider


# ---------------------------------------------------------------- paper position (dry run)
class Paper:
    def __init__(self):
        self.side = 0

    def open(self, side, price, qty, sl, tp):
        self.side, self.entry, self.qty, self.sl, self.tp = side, price, qty, sl, tp

    def hit(self, price):
        """Exit price if the stop or target traded, else None (stop checked first, as the worse case)."""
        if self.side > 0:
            if price <= self.sl:
                return self.sl
            if price >= self.tp:
                return self.tp
        elif self.side < 0:
            if price >= self.sl:
                return self.sl
            if price <= self.tp:
                return self.tp
        return None


# ---------------------------------------------------------------- main loop
def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cfg = Cfg(load_env(os.path.join(HERE, "lk.env")))
    cfg.rules.check()
    if cfg.env == "live" and not cfg.allow_live and not cfg.dry:
        sys.exit("LK_ENV=live with orders on needs LK_ALLOW_LIVE_ENV=1. Test on the demo environment first.")
    if not (cfg.user and cfg.password and cfg.cid and cfg.sec):
        sys.exit("Fill LK_USER, LK_PASSWORD, LK_CID and LK_SEC in futures/tradovate/lk.env")

    tv = Tradovate(cfg.env, cfg.user, cfg.password, cfg.app_id, cfg.app_version, cfg.cid, cfg.sec, cfg.device_id,
                   cfg.md_url)
    tv.login()
    acct = tv.account(cfg.account)
    contract = tv.contract(cfg.symbol)
    log.info("LK_Forward %s | %s | account %s | %s | %s", VERSION, cfg.env, acct.get("name"), cfg.symbol,
             "DRY RUN (no orders)" if cfg.dry else "ORDERS ON")
    log.info("signal windows (New York): %s | flat %s", cfg.rules.windows, cfg.rules.flat)
    state = load_state(cfg.guard)

    ticks: "queue.Queue[tuple]" = queue.Queue()
    md = MarketData(tv.md_url, lambda: tv.md_token or tv.token, lambda ts, p: ticks.put((ts, p)))
    md.start()
    eng = Engine(cfg.rules, make_provider(md, cfg.symbol), log=lambda m: log.info(m))
    md.subscribe(cfg.symbol)

    paper = Paper()
    in_pos = False
    bal_before = 0.0
    last_check = 0.0
    last_price = None
    eod_done = state.get("eod_date", "")
    pos: dict = {}                               # the open trade: side, entry, qty, session

    def balance() -> float:
        if cfg.dry:
            return float(state.get("paper_balance", cfg.guard.start_balance))
        return tv.balance(acct["id"])

    def close_trade(ts: float, pnl: float, price, how: str, note: str = "") -> None:
        nonlocal in_pos
        in_pos = False
        eng.on_exit(pnl)
        if cfg.dry:
            state["paper_balance"] = round(balance() + pnl, 2)
            save_state(state)
        journal(dict(ts=ts, session=pos.get("session", ""), event="exit", side=pos.get("side_txt", ""), price=price,
                     profit=round(pnl, 2), balance=balance(), note=(how + " " + note).strip()))
        log.info("exit (%s) at %s: %+.2f", how, price, pnl)

    def realised(price) -> tuple:
        """Real account: P&L from the balance change. Tradovate can post the cash a moment after the position goes
        flat, so wait up to 5 s for it to move; if it never does, estimate from the last price (sign matters: it
        decides whether the trade counts towards the 2-loss limit)."""
        for _ in range(10):
            delta = balance() - bal_before
            if abs(delta) >= 0.01:
                return delta, ""
            time.sleep(0.5)
        if price is None or not pos:
            return 0.0, "balance unchanged"
        est = pos["side"] * (price - pos["entry"]) * cfg.point_value * pos["qty"] - cfg.commission_rt * pos["qty"]
        return est, "estimated from last price (balance had not updated)"

    while True:
        try:
            item = ticks.get(timeout=1.0)
        except queue.Empty:
            item = None
        ts = item[0] if item else time.time()
        actions = []
        if item:
            last_price = item[1]
            if trading_day(ts).isoformat() in cfg.no_trade_dates:
                actions = [a for a in eng.on_tick(ts, last_price, in_pos) if not isinstance(a, Enter)]
            else:
                actions = eng.on_tick(ts, last_price, in_pos)
        else:
            x = eng.manage(ts, in_pos)
            if x:
                actions = [x]

        # paper stop/target
        if cfg.dry and in_pos and last_price is not None:
            px = paper.hit(last_price)
            if px is not None:
                pnl = paper.side * (px - paper.entry) * cfg.point_value * paper.qty - cfg.commission_rt * paper.qty
                close_trade(ts, pnl, px, "stop" if px == paper.sl else "target")
                paper.side = 0

        # real position closed by its stop or target
        if not cfg.dry and in_pos and time.time() - last_check >= 2:
            last_check = time.time()
            try:
                if tv.net_position(acct["id"], contract["id"]) == 0:
                    pnl, note = realised(last_price)
                    close_trade(ts, pnl, "", "stop/target", note)
            except TradovateError as ex:
                log.warning("position check: %s", ex)

        for a in actions:
            if isinstance(a, Exit) and in_pos:
                if cfg.dry:
                    pnl = paper.side * (last_price - paper.entry) * cfg.point_value * paper.qty \
                        - cfg.commission_rt * paper.qty
                    close_trade(ts, pnl, last_price, a.reason)
                    paper.side = 0
                else:
                    tv.flatten(acct["id"], contract["id"])
                    for _ in range(20):
                        time.sleep(0.5)
                        if tv.net_position(acct["id"], contract["id"]) == 0:
                            break
                    pnl, note = realised(last_price)
                    close_trade(ts, pnl, last_price, a.reason, note)
            elif isinstance(a, Enter) and not in_pos:
                b = balance()
                q = size(cfg.risk, cfg.rules.stop_pts, cfg.point_value, cfg.max_contracts, b, cfg.guard,
                         cfg.commission_rt)
                side = "long" if a.side > 0 else "short"
                sl = rnd(a.price - a.side * cfg.rules.stop_pts, cfg.tick)
                tp = rnd(a.price + a.side * cfg.rules.target_pts, cfg.tick)
                row = dict(ts=ts, session=a.session, side=side, price=a.price, sl=sl, tp=tp, zone_tf=a.zone.tf,
                           zone_lo=a.zone.lo, zone_hi=a.zone.hi, contracts=q, balance=b,
                           floor=cfg.guard.floor())
                if q <= 0:
                    journal(dict(row, event="skipped", note="size 0: risk, contract cap or MLL guard"))
                    log.info("signal %s skipped: size 0 (balance %.2f, floor %.2f)", side, b, cfg.guard.floor())
                    continue
                pos = dict(side=a.side, side_txt=side, entry=a.price, qty=q, session=a.session)
                if cfg.dry:
                    paper.open(a.side, a.price, q, sl, tp)
                    in_pos = True
                    eng.on_entry(ts)
                    journal(dict(row, event="entry", note="paper"))
                    log.info("PAPER %s %d at %s (sl %s, tp %s)", side, q, a.price, sl, tp)
                    continue
                try:
                    bal_before = b
                    tv.place_bracket(acct, cfg.symbol, a.side, q, sl, tp)
                    filled = False
                    for _ in range(10):
                        time.sleep(0.5)
                        if tv.net_position(acct["id"], contract["id"]) != 0:
                            filled = True
                            break
                    if filled:
                        in_pos = True
                        eng.on_entry(ts)
                        journal(dict(row, event="entry"))
                        log.info("%s %d at ~%s (sl %s, tp %s)", side, q, a.price, sl, tp)
                    else:
                        tv.flatten(acct["id"], contract["id"])
                        journal(dict(row, event="error", note="no fill within 5 s; cancelled"))
                except TradovateError as ex:
                    journal(dict(row, event="error", note=str(ex)[:200]))
                    log.error("order failed: %s", ex)

        # end of day: record the balance for the trailing loss limit (once per trading day, between the flat time
        # and the 18:00 session open, a minute after flat so the last exit has settled)
        today = trading_day(ts).isoformat()
        if not in_pos and in_flat_period(ts - 60, cfg.rules) and in_flat_period(ts, cfg.rules) and eod_done != today:
            try:
                b = balance()
                cfg.guard.record_eod(b)
                eod_done = today
                state.update(eod_high=cfg.guard.eod_high, eod_date=today)
                save_state(state)
                journal(dict(ts=ts, event="eod", balance=b, floor=cfg.guard.floor()))
                log.info("end of day: balance %.2f, MLL floor now %.2f", b, cfg.guard.floor())
            except TradovateError as ex:
                log.warning("end-of-day balance: %s", ex)


if __name__ == "__main__":
    main()
