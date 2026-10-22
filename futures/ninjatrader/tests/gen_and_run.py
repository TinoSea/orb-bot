"""Parity: same random tick stream through lk_core (Python) and LKForward.cs (C#, via stubs). Entries must match."""
import random, sys, csv
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tradovate'))
from lk_core import Engine, Rules, Bar, Enter, ny_date, NY
from datetime import datetime

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
rnd = random.Random(seed)
t = datetime(2026, 9, 27, 18, 0, tzinfo=NY).timestamp()    # Sunday evening
end = datetime(2026, 10, 17, 17, 0, tzinfo=NY).timestamp()
ticks, p = [], 20000.0
while t < end:
    d = datetime.fromtimestamp(t, NY)
    if d.weekday() == 5 or (d.weekday() == 4 and d.hour >= 17) or (d.weekday() == 6 and d.hour < 18):
        t += 600; continue
    p = round((p + rnd.choice([-1, 1]) * rnd.choice([0.25, 0.25, 0.5, 0.75, 1.0, 1.5])) * 4) / 4
    ticks.append((round(t, 3), p))
    t += rnd.choice([0.2, 0.5, 1, 1, 2, 3, 6])
print("ticks", len(ticks), file=sys.stderr)

def bars_from(sec):
    out, k, b = [], None, None
    for ts, pr in ticks:
        kk = int(ts // sec)
        if kk != k:
            if b: out.append(b)
            k = kk; b = [kk * sec, pr, pr, pr, pr]
        else:
            b[2] = max(b[2], pr); b[3] = min(b[3], pr); b[4] = pr
    out.append(b)
    return out

B = {"5m": bars_from(300), "15m": bars_from(900)}
for tf in B:
    with open(f"bars{tf}.csv", "w") as f:
        for r in B[tf]: f.write(",".join(map(str, r)) + "\n")
with open("ticks.csv", "w") as f:
    for ts, pr in ticks: f.write(f"{ts},{pr}\n")

now = [0.0]
sec = {"5m": 300, "15m": 900}
def provider(tf, since):
    return [Bar(r[0], sec[tf], *r[1:]) for r in B[tf] if r[0] >= since and r[0] + sec[tf] <= now[0]]

e = Engine(Rules(), provider, log=lambda m: None)
n = 0
with open("py_entries.csv", "w") as f:
    for ts, pr in ticks:
        now[0] = ts
        for a in e.on_tick(ts, pr, False):
            if isinstance(a, Enter):
                e.on_entry(ts); e.on_exit(-1.0 if n % 2 == 0 else 1.0); n += 1
                f.write(f"{ts:.3f},{a.side},{a.price},{a.zone.tf},{a.zone.lo},{a.zone.hi}\n")
print("python entries", n, file=sys.stderr)
