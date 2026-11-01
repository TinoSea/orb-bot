"""How much should a good result be discounted for the number of ideas already tried?

  python3 research/trials.py                              # count trials in research/trials.csv, show the luck bar
  python3 research/trials.py --trades results.csv --col R # deflated Sharpe ratio of one trade list (R per trade)

Method: Bailey & Lopez de Prado (2014), "The Deflated Sharpe Ratio". With N independent tries, the best one's
Sharpe ratio is expected to reach SR0 = sd_SR * [(1-g)*Z(1-1/N) + g*Z(1-1/(N e))] by luck alone (g = Euler's
constant). The deflated Sharpe ratio is the probability that a result's true Sharpe ratio is above SR0, allowing
for its sample size, skew and fat tails. 0.95 or more is the usual bar.

Sharpe ratios here are per trade (mean R / sd of R). sd_SR, how much the tries' Sharpe ratios differ from each
other, is rarely known; by default it is estimated from the expectancies in trials.csv, treating sd(R) as about 1,
which is a rough approximation. Override it with --sd-sr. Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import statistics
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
GAMMA = 0.5772156649
Z = NormalDist().inv_cdf


def ledger(path: str = os.path.join(HERE, 'trials.csv')) -> list[dict]:
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def expected_max_sr(n: int, sd_sr: float) -> float:
    if n < 2:
        return 0.0
    return sd_sr * ((1 - GAMMA) * Z(1 - 1 / n) + GAMMA * Z(1 - 1 / (n * math.e)))


def deflated_sharpe(r: list[float], n_trials: int, sd_sr: float) -> dict:
    t = len(r)
    mu, sd = statistics.fmean(r), statistics.pstdev(r)
    sr = mu / sd if sd > 0 else 0.0
    m3 = sum((x - mu) ** 3 for x in r) / t / sd ** 3 if sd > 0 else 0.0
    m4 = sum((x - mu) ** 4 for x in r) / t / sd ** 4 if sd > 0 else 3.0
    sr0 = expected_max_sr(n_trials, sd_sr)
    denom = math.sqrt(max(1 - m3 * sr + (m4 - 1) / 4 * sr ** 2, 1e-12))
    dsr = NormalDist().cdf((sr - sr0) * math.sqrt(t - 1) / denom)
    psr0 = NormalDist().cdf(sr * math.sqrt(t - 1) / denom)
    return dict(trades=t, mean_R=round(mu, 4), sharpe_per_trade=round(sr, 4), skew=round(m3, 2), kurtosis=round(m4, 2),
                luck_bar_SR0=round(sr0, 4), prob_sr_above_zero=round(psr0, 3), deflated_sharpe=round(dsr, 3),
                passes_0_95=dsr >= 0.95)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--trades', help='CSV with one row per trade')
    ap.add_argument('--col', default='R', help='column holding R per trade (after costs)')
    ap.add_argument('--sd-sr', type=float, help='spread of Sharpe ratios across tries (default: estimated from trials.csv)')
    ap.add_argument('--extra', type=int, default=0, help='tries not in the ledger (unregistered variants, settings sweeps)')
    a = ap.parse_args()
    rows = ledger()
    n = sum(r['looked_at_data'] == 'yes' for r in rows) + a.extra
    ex = [float(r['expectancy_R_after_costs']) for r in rows if r['expectancy_R_after_costs']]
    sd_sr = a.sd_sr if a.sd_sr else (statistics.stdev(ex) if len(ex) > 2 else 0.1)
    print(f'Trials that looked at data: {n} (ledger {n - a.extra} + extra {a.extra})')
    print(f'Spread of per-trade Sharpe across tries: {sd_sr:.3f} '
          f'({"given" if a.sd_sr else f"estimated from {len(ex)} expectancies, sd(R)≈1 assumed"})')
    print(f'Luck bar: the best of {n} tries with no edge would show a per-trade Sharpe of about {expected_max_sr(n, sd_sr):.3f}')
    if a.trades:
        with open(a.trades, newline='') as f:
            r = [float(x[a.col]) for x in csv.DictReader(f) if x.get(a.col) not in (None, '')]
        res = deflated_sharpe(r, n, sd_sr)
        for k, v in res.items():
            print(f'  {k}: {v}')
        print('  Verdict:', 'clears the luck bar' if res['passes_0_95'] else 'does NOT clear the luck bar (deflated Sharpe < 0.95)')


if __name__ == '__main__':
    main()
