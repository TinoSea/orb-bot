"""H-018: the BOS model (H-007/1 variant V2) tested on its own (research/hypotheses.md, H-018).

  python3 h018.py dev   <M1 2025-26 csv>     # 2025-07-01..2026-03-31, seen once
  python3 h018.py final <M1 2022-25 csv>     # ONCE, 2023-01-01..2025-06-30, only if dev futures expectancy > 0
Rules and engine: h007.py variant V2, unchanged.
"""
import sys, os, json
import h007 as H

OUT = 'results/h018'
if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(OUT, exist_ok=True)
    mode, path = sys.argv[1], sys.argv[2]
    f = f'{OUT}/{mode}.json'
    if mode == 'final':
        if os.path.exists(f):
            sys.exit('Final already run once: ' + f)
        d = json.load(open(f'{OUT}/dev.json'))
        if not d['fut_R'] > 0:
            sys.exit('Development expectancy not above zero: final not spent (as registered).')
    D = H.Data(H.load_m1(path))
    a, b = H.DEV if mode == 'dev' else H.FINAL
    tr = H.run(D, a, b, 'V2')
    tr.to_csv(f'{OUT}/{mode}_trades.csv', index=False)
    s = H.stats(tr, D, 'V2', with_null=True)
    s['verdict'] = H.verdict(s); s['period'] = [a, b]
    print(json.dumps(s, indent=1, default=str)); json.dump(s, open(f, 'w'), indent=1, default=str)
