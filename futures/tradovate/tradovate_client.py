"""Small Tradovate API client: login, REST calls, and the market-data websocket.

Written from Tradovate's public API documentation. It has NOT been run against a live Tradovate server
yet, so the first runs must be on the Tradovate DEMO environment with LK_DRY_RUN=1 (signals only, no orders).
Anything that looks different from what this file expects is logged in full so it can be fixed.

API access: Tradovate's API needs an API key (cid + secret) from Tradovate. A prop-firm account such as
FundedNext's may not give you one; ask FundedNext support before relying on this route. The NinjaTrader
version (futures/ninjatrader/LKForward.cs) does not need an API key.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import requests
import websocket

log = logging.getLogger("tradovate")

URLS = {
    "demo": ("https://demo.tradovateapi.com/v1", "wss://md.tradovateapi.com/v1/websocket"),
    "live": ("https://live.tradovateapi.com/v1", "wss://md.tradovateapi.com/v1/websocket"),
}


class TradovateError(RuntimeError):
    pass


class Tradovate:
    def __init__(self, env: str, name: str, password: str, app_id: str, app_version: str, cid: str, sec: str,
                 device_id: str, md_url: str = ""):
        if env not in URLS:
            raise ValueError("env must be 'demo' or 'live'")
        self.env = env
        self.rest, self.md_url = URLS[env]
        if md_url:
            self.md_url = md_url
        self.creds = dict(name=name, password=password, appId=app_id, appVersion=app_version, cid=cid, sec=sec,
                          deviceId=device_id)
        self.token: Optional[str] = None
        self.md_token: Optional[str] = None
        self.expires = 0.0
        self.s = requests.Session()

    # ---------------------------------------------------------------- auth
    def login(self) -> None:
        body = dict(self.creds)
        for _ in range(3):
            r = self.s.post(f"{self.rest}/auth/accesstokenrequest", json=body, timeout=20)
            d = r.json()
            if "p-ticket" in d:                       # Tradovate asks you to wait before retrying
                wait = int(d.get("p-time", 15))
                log.warning("login: Tradovate asked to wait %s s", wait)
                time.sleep(wait)
                body["p-ticket"] = d["p-ticket"]
                continue
            if "accessToken" not in d:
                raise TradovateError(f"login failed: {d.get('errorText', d)}")
            self._set_tokens(d)
            log.info("logged in to Tradovate %s as %s", self.env, self.creds["name"])
            return
        raise TradovateError("login: too many retries")

    def _set_tokens(self, d: dict) -> None:
        self.token = d["accessToken"]
        self.md_token = d.get("mdAccessToken", self.md_token)
        exp = d.get("expirationTime")
        self.expires = (datetime.fromisoformat(exp.replace("Z", "+00:00")).timestamp() if exp
                        else time.time() + 80 * 60)
        self.s.headers["Authorization"] = f"Bearer {self.token}"

    def renew_if_needed(self) -> None:
        if time.time() < self.expires - 15 * 60:
            return
        r = self.s.get(f"{self.rest}/auth/renewaccesstoken", timeout=20)
        d = r.json()
        if "accessToken" in d:
            self._set_tokens(d)
            log.info("access token renewed")
        else:
            log.warning("token renewal failed (%s); logging in again", d)
            self.login()

    # ---------------------------------------------------------------- REST
    def get(self, path: str, **params):
        self.renew_if_needed()
        r = self.s.get(f"{self.rest}/{path}", params=params, timeout=20)
        if r.status_code != 200:
            raise TradovateError(f"GET {path}: {r.status_code} {r.text[:300]}")
        return r.json()

    def post(self, path: str, body: dict):
        self.renew_if_needed()
        r = self.s.post(f"{self.rest}/{path}", json=body, timeout=20)
        if r.status_code != 200:
            raise TradovateError(f"POST {path}: {r.status_code} {r.text[:300]}")
        return r.json()

    def account(self, name: str = "") -> dict:
        accts = self.get("account/list")
        if not accts:
            raise TradovateError("no accounts on this login")
        if name:
            for a in accts:
                if a.get("name") == name:
                    return a
            raise TradovateError(f"account {name!r} not found; have {[a.get('name') for a in accts]}")
        if len(accts) > 1:
            raise TradovateError(f"several accounts {[a.get('name') for a in accts]}: set LK_ACCOUNT")
        return accts[0]

    def contract(self, symbol: str) -> dict:
        return self.get("contract/find", name=symbol)

    def balance(self, account_id: int) -> float:
        d = self.post("cashBalance/getcashbalancesnapshot", {"accountId": account_id})
        for k in ("totalCashValue", "netLiq", "amount"):
            if k in d and d[k] is not None:
                return float(d[k])
        raise TradovateError(f"cash balance snapshot without a balance field: {d}")

    def net_position(self, account_id: int, contract_id: int) -> int:
        for p in self.get("position/list"):
            if p.get("accountId") == account_id and p.get("contractId") == contract_id:
                return int(p.get("netPos", 0))
        return 0

    def place_bracket(self, account: dict, symbol: str, side: int, qty: int, stop: float, target: float) -> dict:
        """Market entry with a stop and a target that cancel each other (Tradovate order-sends-OCO)."""
        act, opp = ("Buy", "Sell") if side > 0 else ("Sell", "Buy")
        body = {
            "accountSpec": account["name"], "accountId": account["id"], "action": act, "symbol": symbol,
            "orderQty": qty, "orderType": "Market", "isAutomated": True,
            "bracket1": {"action": opp, "orderType": "Stop", "stopPrice": stop},
            "bracket2": {"action": opp, "orderType": "Limit", "price": target},
        }
        d = self.post("order/placeOSO", body)
        if d.get("failureReason") or "orderId" not in d:
            raise TradovateError(f"order rejected: {d}")
        return d

    def flatten(self, account_id: int, contract_id: int) -> None:
        """Cancel this contract's working orders and close the position."""
        self.post("order/liquidateposition", {"accountId": account_id, "contractId": contract_id, "admin": False})


class MarketData:
    """Market-data websocket: trade prices for one symbol, plus historical bars on request.

    Tradovate frames: 'o' = open, 'h' = heartbeat, 'a[...]' = messages, 'c' = closed.
    Requests are 'endpoint\\nid\\n\\nJSON'. The client must send '[]' every 2.5 s or the server drops it.
    """

    def __init__(self, url: str, token_getter: Callable[[], str], on_trade: Callable[[float, float], None]):
        self.url = url
        self.token_getter = token_getter
        self.on_trade = on_trade
        self.ws: Optional[websocket.WebSocketApp] = None
        self.next_id = 1
        self.pending: Dict[int, dict] = {}
        self.events: Dict[int, threading.Event] = {}
        self.charts: Dict[int, List[dict]] = {}
        self.chart_done: Dict[int, threading.Event] = {}
        self.chart_ended: set = set()            # end-of-history markers that arrived before anyone waited
        self.ready = threading.Event()
        self.lock = threading.Lock()
        self.symbol: Optional[str] = None
        self.last_msg = time.time()

    # ---------------------------------------------------------------- connection
    def start(self) -> None:
        self.ws = websocket.WebSocketApp(self.url, on_message=self._on_msg, on_error=self._on_err,
                                         on_close=self._on_close)
        threading.Thread(target=self.ws.run_forever, kwargs={"ping_interval": 0}, daemon=True).start()
        threading.Thread(target=self._heartbeat, daemon=True).start()
        if not self.ready.wait(20):
            raise TradovateError("market data: no authorised connection within 20 s")

    def _heartbeat(self) -> None:
        while True:
            time.sleep(2.5)
            try:
                if self.ws and self.ws.sock and self.ws.sock.connected:
                    self.ws.send("[]")
            except Exception as ex:  # noqa: BLE001
                log.warning("heartbeat: %s", ex)

    def _send(self, endpoint: str, body: Optional[dict] = None) -> int:
        with self.lock:
            i = self.next_id
            self.next_id += 1
            self.events[i] = threading.Event()
        payload = f"{endpoint}\n{i}\n\n{json.dumps(body) if body is not None else ''}"
        self.ws.send(payload)
        return i

    def _request(self, endpoint: str, body: Optional[dict] = None, timeout: float = 20) -> dict:
        i = self._send(endpoint, body)
        if not self.events[i].wait(timeout):
            raise TradovateError(f"{endpoint}: no reply in {timeout} s")
        d = self.pending.pop(i)
        if d.get("s") != 200:
            raise TradovateError(f"{endpoint}: {d}")
        return d.get("d", {})

    def _on_msg(self, _ws, raw: str) -> None:
        self.last_msg = time.time()
        if not raw:
            return
        kind = raw[0]
        if kind == "o":
            with self.lock:
                i = self.next_id
                self.next_id += 1
            self._auth_id = i
            # 'authorize' takes the token as the raw body, not JSON
            self.ws.send(f"authorize\n{i}\n\n{self.token_getter()}")
            return
        if kind != "a":
            return
        try:
            msgs = json.loads(raw[1:])
        except json.JSONDecodeError:
            log.warning("market data: unreadable frame %r", raw[:200])
            return
        for m in msgs:
            if "i" in m:                                   # reply to a request
                if getattr(self, "_auth_id", None) == m["i"]:
                    if m.get("s") == 200:
                        self.ready.set()
                        if self.symbol:                    # reconnect: resubscribe
                            self._send("md/subscribeQuote", {"symbol": self.symbol})
                    else:
                        log.error("market data authorisation failed: %s", m)
                    continue
                self.pending[m["i"]] = m
                ev = self.events.get(m["i"])
                if ev:
                    ev.set()
            elif m.get("e") == "md":
                for q in m.get("d", {}).get("quotes", []):
                    tr = q.get("entries", {}).get("Trade")
                    if tr and "price" in tr:
                        ts = _ts(q.get("timestamp"))
                        self.on_trade(ts, float(tr["price"]))
            elif m.get("e") == "chart":
                for c in m.get("d", {}).get("charts", []):
                    cid = c.get("id")
                    if c.get("eoh"):
                        with self.lock:
                            self.chart_ended.add(cid)
                            ev = self.chart_done.get(cid)
                        if ev:
                            ev.set()
                        continue
                    self.charts.setdefault(cid, []).extend(c.get("bars", []))

    def _on_err(self, _ws, err) -> None:
        log.error("market data error: %s", err)

    def _on_close(self, _ws, code, msg) -> None:
        log.warning("market data closed (%s %s); reconnecting in 5 s", code, msg)
        self.ready.clear()
        time.sleep(5)
        threading.Thread(target=self.ws.run_forever, kwargs={"ping_interval": 0}, daemon=True).start()

    # ---------------------------------------------------------------- requests
    def subscribe(self, symbol: str) -> None:
        self.symbol = symbol
        self._request("md/subscribeQuote", {"symbol": symbol})

    def bars(self, symbol: str, minutes: int, since: float, timeout: float = 30) -> List[dict]:
        """Historical minute bars from `since` (epoch s) to now. Returns Tradovate bar dicts
        (timestamp, open, high, low, close, ...). The last, still-forming bar is dropped by the caller."""
        d = self._request("md/getChart", {
            "symbol": symbol,
            "chartDescription": {"underlyingType": "MinuteBar", "elementSize": minutes,
                                 "elementSizeUnit": "UnderlyingUnits", "withHistogram": False},
            "timeRange": {"asFarAsTimestamp": datetime.fromtimestamp(since, timezone.utc)
                          .strftime("%Y-%m-%dT%H:%M:%S.000Z")},
        })
        hid = d.get("historicalId") or d.get("realtimeId")
        rid = d.get("realtimeId")
        with self.lock:
            ev = self.chart_done.setdefault(hid, threading.Event())
            if hid in self.chart_ended:          # the marker came before this line ran
                ev.set()
        if not ev.wait(timeout):
            log.warning("getChart %sm: no end-of-history marker in %s s; using what arrived", minutes, timeout)
        bars = list(self.charts.pop(hid, []))
        if rid is not None and rid != hid:
            bars += self.charts.pop(rid, [])
        for sid in {hid, rid} - {None}:          # stop both the history and the live part of the chart
            try:
                self._send("md/cancelChart", {"subscriptionId": sid})
            except Exception:  # noqa: BLE001
                pass
        with self.lock:
            self.chart_done.pop(hid, None)
            self.chart_ended.discard(hid)
        self.charts.pop(rid, None)
        uniq = {b["timestamp"]: b for b in bars}
        return [uniq[k] for k in sorted(uniq)]


def _ts(s: Optional[str]) -> float:
    if not s:
        return time.time()
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
