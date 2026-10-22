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
    assert cfg.dry is True and cfg.rules.sig_from == "08:00" and cfg.rules.sig_to == "14:00"
    assert cfg.rules.flat == "14:30" and cfg.guard.floor() == 24000
    assert cfg.no_trade_dates == set() and cfg.user == ""


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
