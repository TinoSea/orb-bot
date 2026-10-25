"""Offline checks of the Tradovate runner helpers (no network)."""
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import lk_tradovate as R  # noqa: E402


def test_env_example_parses_with_inline_comments():
    cfg = R.Cfg(R.load_env(os.path.join(os.path.dirname(__file__), "..", "lk.env.example")))
    assert cfg.env == "demo" and cfg.symbol == "MNQZ6" and cfg.point_value == 2.0
    assert cfg.dry is True and cfg.rules.windows == "Asia=18:00-03:00,London=03:00-08:00,NY=08:00-14:00"
    assert cfg.rules.flat == "14:30" and cfg.guard.floor() == 24000
    assert cfg.no_trade_dates == set() and cfg.user == ""


def test_old_single_window_setting_still_works():
    cfg = R.Cfg({"LK_SIG_FROM": "09:30", "LK_SIG_TO": "09:57", "LK_FLAT": "11:45"})
    assert cfg.rules.windows == "09:30-09:57" and cfg.rules.session_of(9 * 60 + 40) == "W1"


def test_journal_adds_trading_day_and_session(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "HERE", str(tmp_path))
    from lk_core import NY
    t = datetime(2026, 10, 25, 19, 0, tzinfo=NY).timestamp()          # Sunday evening -> Monday
    R.journal(dict(ts=t, session="Asia", event="entry"))
    rows = open(tmp_path / "journal" / "LK_futures_journal_v110.csv").read().splitlines()
    assert rows[0].startswith("time_ny,trading_day,session,event")
    assert rows[1].startswith("2026-10-25 19:00:00,2026-10-26,Asia,entry")


class FakeMD:
    def __init__(self, stamps_end):
        self.stamps_end = stamps_end

    def bars(self, symbol, minutes, since):
        sec = minutes * 60
        now = time.time()
        start = int(now // sec) * sec - 3 * sec          # three closed bars and one forming
        out = []
        for i in range(4):
            t = start + i * sec + (sec if self.stamps_end else 0)
            iso = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            out.append(dict(timestamp=iso, open=1, high=2, low=0.5, close=1.5))
        return out


def test_provider_drops_forming_bar_either_stamping():
    for end in (False, True):
        bars = R.make_provider(FakeMD(end), "MNQZ6")("5m", 0)
        assert len(bars) == 3, end
        assert all(b.t_close <= time.time() for b in bars)


def test_paper_stop_checked_first():
    p = R.Paper()
    p.open(1, 100, 4, 87.5, 116.25)
    assert p.hit(100) is None and p.hit(87.0) == 87.5 and p.hit(117) == 116.25
    p.open(-1, 100, 4, 112.5, 83.75)
    assert p.hit(113) == 112.5 and p.hit(83) == 83.75
