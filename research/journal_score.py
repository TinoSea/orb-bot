"""Does your judgement add anything? Scores research/journal/predictions_log.csv.

  python3 research/journal_score.py [path/to/predictions_log.csv]

How to fill the log (one row per setup you notice, taken or not):
  BEFORE the entry: logged_at_ny (YYYY-MM-DD HH:MM), date, symbol, level (asia_high, asia_low, london_high, london_low,
  asia_mid, london_mid, gap_5min, gap_15min or other), side (long/short), entry, stop, target, confidence_pct (your
  probability, 0-100, that the target is hit before the stop), screenshot (file name), taken (yes/no).
  AFTER: exit, hit_target (1 = target first, 0 = stop first; for skipped setups, what price did), result_R, followed_plan.

What it reports
  - Win rate, average R and total R for trades taken, split by whether the plan was followed.
  - Brier score: mean of (confidence - outcome)^2. Lower is better. The skill score compares it with always guessing
    your own average hit rate: above 0 means your confidence carries information; at or below 0 means it does not.
  - Calibration: when you said 60-70%, how often did it happen?
  - Taken vs skipped: did the setups you chose beat the ones you passed on?
  - With H-026 results present, your hit rate per level next to the market's own reversal rate at that level.
Needs about 50 rows before any of this means much. Not financial advice.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def main(path: str):
    j = pd.read_csv(path)
    if j.empty:
        sys.exit('The log is empty: add a row before each setup, then run this again.')
    j['p'] = pd.to_numeric(j.confidence_pct, errors='coerce') / 100
    j['hit'] = pd.to_numeric(j.hit_target, errors='coerce')
    j['R'] = pd.to_numeric(j.result_R, errors='coerce')
    taken = j[j.taken.astype(str).str.lower().eq('yes')]
    print(f'{len(j)} setups logged, {len(taken)} taken.')
    if len(taken):
        print(f'Taken: win {taken.hit.mean():.1%}, average {taken.R.mean():+.2f}R, total {taken.R.sum():+.1f}R')
        for v, g in taken.groupby(taken.followed_plan.astype(str).str.lower()):
            print(f'  followed plan = {v}: {len(g)} trades, average {g.R.mean():+.2f}R')
    s = j.dropna(subset=['p', 'hit'])
    if len(s) >= 5:
        brier = np.mean((s.p - s.hit) ** 2)
        base = np.mean((s.hit.mean() - s.hit) ** 2)
        skill = 1 - brier / base if base > 0 else np.nan
        print(f'\nBrier score {brier:.3f}; guessing your average every time scores {base:.3f}; skill {skill:+.2f} '
              f'({"your confidence carries information" if skill > 0 else "your confidence adds nothing yet"})')
        s = s.assign(bucket=pd.cut(s.p, [0, .4, .5, .6, .7, 1.0], include_lowest=True))
        print('\nCalibration (what you said vs what happened):')
        for b, g in s.groupby('bucket', observed=True):
            print(f'  said {b}: {len(g)} setups, happened {g.hit.mean():.0%}')
    sk = j[j.taken.astype(str).str.lower().eq('no')].dropna(subset=['hit'])
    if len(sk) and len(taken.dropna(subset=['hit'])):
        print(f'\nTaken hit {taken.hit.mean():.0%} vs skipped hit {sk.hit.mean():.0%} '
              f'({"your selection helps" if taken.hit.mean() > sk.hit.mean() else "your selection does not help yet"})')
    h = os.path.join(HERE, 'results', 'h026', 'dev_events.csv')
    if os.path.exists(h):
        ev = pd.read_csv(h)
        base = ev.groupby('name').outcome.apply(lambda o: (o == 'rev').mean())
        print('\nYour hit rate vs the market\'s reversal rate at the same level (H-026 development data):')
        for lv, g in j.dropna(subset=['hit']).groupby('level'):
            b = f'{base[lv]:.0%}' if lv in base else 'n/a'
            print(f'  {lv}: you {g.hit.mean():.0%} over {len(g)}, market {b}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, 'journal', 'predictions_log.csv'))
