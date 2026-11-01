"""FundedNext futures account simulator: how often a trade record passes, busts, and pays out under the account's rules.

  # from a trade list (one row per trade: a date column and an R-per-trade column, after costs)
  python3 research/prop_sim.py --trades my_trades.csv --date-col date --r-col R --risk 100
  # from a profile: 40% winners averaging 3.4R, losers -1R, 2 trades a day, 20% of trades scratched at break-even
  python3 research/prop_sim.py --profile 0.40 3.4 --per-day 2 --be-rate 0.2 --risk 100

Defaults are the Rapid Pro $25K rules as FundedNext's page showed them on 2026-11-01
(https://fundednext.com/api-doc/futures/rapid): profit target $1,500; maximum loss $1,000, end-of-day trailing;
no daily loss limit; consistency 40% (funded; the page contradicts itself on the challenge, so it is ON here and can be
switched off); max 20 micros; rewards every 3 days, $800 cap, 90% share; challenge fee $79.99.
ASSUMPTIONS the page does not settle, all adjustable: the trailing floor stops rising once it reaches the starting
balance (--lock); the floor is checked after every trade (intra-trade dips are ignored, which flatters results);
consistency = best day's profit no more than 40% of total profit when passing or withdrawing.
Monte Carlo resamples whole trading days, keeping each day's trades together. Not financial advice.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd


def day_blocks(a) -> list[np.ndarray]:
    if a.trades:
        t = pd.read_csv(a.trades)
        t['d'] = pd.to_datetime(t[a.date_col]).dt.normalize()
        return [g[a.r_col].to_numpy(float) - a.cost_r for _, g in t.groupby('d')]
    p, win = a.profile
    rng = np.random.default_rng(a.seed)
    blocks = []
    for _ in range(5000):
        n = rng.poisson(a.per_day) if a.poisson else int(a.per_day)
        u = rng.random(n)
        r = np.where(u < a.be_rate, 0.0, np.where(rng.random(n) < p / (1 - a.be_rate) if a.be_rate < 1 else 0, win, -a.avg_loss))
        blocks.append(r - a.cost_r)
    return blocks


class Account:
    def __init__(self, a):
        self.a = a
        self.bal = self.start = a.start
        self.peak_eod = a.start
        self.floor = a.start - a.mll
        self.days = []                        # daily P&L

    def trade_day(self, rs: np.ndarray) -> str | None:
        pnl = 0.0
        for r in rs:
            self.bal += r * self.a.risk
            pnl += r * self.a.risk
            if self.bal <= self.floor:
                self.days.append(pnl)
                return 'bust'
        self.days.append(pnl)
        self.peak_eod = max(self.peak_eod, self.bal)
        f = self.peak_eod - self.a.mll
        self.floor = min(f, self.a.lock) if self.a.lock else f
        return None

    def consistent(self, since: int = 0) -> bool:
        d = np.array(self.days[since:])
        prof = d.sum()
        return prof > 0 and (not self.a.consistency or d.max() <= self.a.consistency * prof)


def challenge(blocks, a, rng) -> tuple[str, int]:
    acc = Account(a)
    for day in range(1, a.max_days + 1):
        if acc.trade_day(blocks[rng.integers(len(blocks))]) == 'bust':
            return 'bust', day
        if acc.bal - acc.start >= a.target and (not a.eval_consistency or acc.consistent()):
            return 'pass', day
    return 'open', a.max_days


def funded(blocks, a, rng) -> tuple[bool, float]:
    acc, paid, last, since = Account(a), 0.0, 0, 0
    for day in range(1, a.funded_days + 1):
        if acc.trade_day(blocks[rng.integers(len(blocks))]) == 'bust':
            return True, paid
        since += 1
        gain = acc.bal - acc.start
        if since >= a.cycle and gain > 0 and acc.consistent(last):
            w = min(gain, a.cap)
            paid += w * a.share
            acc.bal -= w
            last, since = len(acc.days), 0
    return False, paid


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--trades')
    src.add_argument('--profile', nargs=2, type=float, metavar=('WIN_RATE', 'AVG_WIN_R'))
    ap.add_argument('--date-col', default='date'); ap.add_argument('--r-col', default='R')
    ap.add_argument('--per-day', type=float, default=1.0); ap.add_argument('--poisson', action='store_true')
    ap.add_argument('--avg-loss', type=float, default=1.0); ap.add_argument('--be-rate', type=float, default=0.0)
    ap.add_argument('--cost-r', type=float, default=0.0, help='extra cost per trade in R, if the R column is before costs')
    ap.add_argument('--risk', type=float, default=100.0, help='dollars per 1R')
    ap.add_argument('--start', type=float, default=25_000); ap.add_argument('--target', type=float, default=1_500)
    ap.add_argument('--mll', type=float, default=1_000); ap.add_argument('--lock', type=float, default=25_000,
                    help='floor stops trailing at this balance (0 = never stops)')
    ap.add_argument('--consistency', type=float, default=0.40)
    ap.add_argument('--no-eval-consistency', dest='eval_consistency', action='store_false')
    ap.add_argument('--max-days', type=int, default=60); ap.add_argument('--funded-days', type=int, default=60)
    ap.add_argument('--cycle', type=int, default=3); ap.add_argument('--cap', type=float, default=800)
    ap.add_argument('--share', type=float, default=0.90); ap.add_argument('--fee', type=float, default=79.99)
    ap.add_argument('--sims', type=int, default=10_000); ap.add_argument('--seed', type=int, default=7)
    a = ap.parse_args()
    blocks = day_blocks(a)
    rng = np.random.default_rng(a.seed)
    allr = np.concatenate(blocks) if blocks else np.array([])
    print(f'Trade record: {len(allr)} trades over {len(blocks)} days, mean {allr.mean():+.3f}R, '
          f'win {np.mean(allr > 0):.1%}, ${a.risk:.0f} per R')
    ch = [challenge(blocks, a, rng) for _ in range(a.sims)]
    res = pd.Series([c[0] for c in ch]).value_counts(normalize=True)
    p_pass = res.get('pass', 0.0)
    days = [d for o, d in ch if o == 'pass']
    print(f'\nChallenge (${a.target:,.0f} target, ${a.mll:,.0f} trailing max loss, '
          f'{"40% consistency" if a.eval_consistency else "no consistency"}, {a.max_days} trading days):')
    print(f'  pass {p_pass:.1%}   bust {res.get("bust", 0):.1%}   still open {res.get("open", 0):.1%}')
    if days:
        print(f'  days to pass: median {np.median(days):.0f}, 90th pct {np.percentile(days, 90):.0f}')
    print(f'  expected fees per funded account: ${a.fee / p_pass:,.0f}' if p_pass > 0 else '  never passes')
    fd = [funded(blocks, a, rng) for _ in range(a.sims)]
    bust = np.mean([b for b, _ in fd]); paid = np.array([p for _, p in fd])
    print(f'\nFunded, {a.funded_days} trading days (payout every {a.cycle} days, ${a.cap:,.0f} cap, {a.share:.0%} share):')
    print(f'  account lost {bust:.1%}   paid out: mean ${paid.mean():,.0f}, median ${np.median(paid):,.0f}, '
          f'zero {np.mean(paid == 0):.1%}')
    print('\nAssumptions are listed in the header of this file. Check the rules against FundedNext\'s current terms.')


if __name__ == '__main__':
    main()
