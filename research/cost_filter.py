#!/usr/bin/env python3
"""
H-002 cost filter and $100-tradability check, run BLIND to strategy results.

  python research/cost_filter.py --data data/export

For every market it runs the registered rules on in-sample data (2023-01-01 -> 2025-06-30)
with the spread-skip turned off, so every signal counts, and keeps only:
  - the stop distance of each signal (entry to stop, in price)
  - the broker spread at entry, and the commission converted to price
It never reads exits, P&L or R. Output: research/cost_filter.md

Pre-registered rule (hypotheses.md, H-002 item 5): a market is excluded if its median
spread at entry is more than 10% of its median stop distance.
The $100 question (item 15) is separate and never affects the research verdict.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ms_replica as R  # noqa: E402

IS_FROM, IS_TO = "2023-01-01", "2025-06-30"
LIMIT = 0.10


class Blind(R.Replica):
    """Records signal geometry at entry; exits are simulated (to keep one trade at a time,
    as in the EA) but never recorded."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.sig = []
        self._spread_now = 0.0

    def try_enter(self, d, t, bid, spread, atr_e, k1):
        self._spread_now = spread
        before = self.pos
        super().try_enter(d, t, bid, spread, atr_e, k1)
        if self.pos is not None and before is None:
            self.sig.append({"time": t, "stop_dist": self.pos.risk_price, "spread": spread,
                             "vpp": self.vpp(t)})

    def close(self, t, price, reason):
        self.balance_before = self.balance
        super().close(t, price, reason)
        self.trades.clear()                  # results are discarded unread
        self.balance = self.balance_before   # keep sizing independent of results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    a = ap.parse_args()
    markets = R.load_markets()
    specs = R.load_specs(os.path.join(a.data, "specs.csv"))
    comm = R.load_commissions()
    smult = R.load_spread_mults()
    fx = R.fx_table(a.data, "M5")
    rows = []
    for lab, mkt in markets.items():
        path = os.path.join(a.data, f"{lab}_M5.csv")
        if lab not in specs or not os.path.exists(path):
            rows.append({"label": lab, "symbol": "-", "signals": 0, "verdict": "missing at broker"})
            continue
        sp = specs[lab]
        prm = R.Params(max_spread_frac=1e9)
        rep = Blind(R.load_bars(path), sp, mkt, prm, deposit=1e7, commission=0.0, fx=fx,
                    spread_mult=smult.get(lab, 1.0))
        rep.run(IS_FROM, IS_TO)
        s = pd.DataFrame(rep.sig)
        if s.empty:
            rows.append({"label": lab, "symbol": sp.symbol, "signals": 0, "verdict": "no signals"})
            continue
        c_price = 2 * comm.get(lab, 0.0) / s["vpp"]          # round-trip commission per lot, in price
        med_stop = s["stop_dist"].median()
        med_spread = s["spread"].median()
        ratio = med_spread / med_stop
        all_in = (s["spread"] + c_price).median() / med_stop
        vpp_med = s["vpp"].median()
        min_lot_risk = sp.vol_min * med_stop * vpp_med
        rows.append({
            "label": lab, "symbol": sp.symbol, "sector": mkt.sector, "signals": len(s),
            "spread_mult": smult.get(lab, 1.0),
            "median_stop": round(med_stop, sp.digits), "median_spread": round(med_spread, sp.digits),
            "spread_%_of_stop": round(100 * ratio, 1), "spread+commission_%_of_stop": round(100 * all_in, 1),
            "verdict": "keep" if ratio <= LIMIT else "EXCLUDE (cost filter)",
            "min_lot": sp.vol_min, "usd_per_point_per_lot": round(vpp_med, 4),
            "min_lot_risk_usd_at_median_stop": round(min_lot_risk, 2),
            "1%_on_$100_possible": "yes" if min_lot_risk <= 1.0 else ("close" if min_lot_risk <= 2.0 else "no"),
            "account_needed_for_1%_usd": int(np.ceil(min_lot_risk * 100 / 100.0) * 100),
        })
        print(f"  {lab:<7} signals {len(s):>4}  spread {100 * ratio:5.1f}% of stop  -> {rows[-1]['verdict']}")
    df = pd.DataFrame(rows)
    md = ["# H-002 cost filter and $100 tradability (in-sample, blind to results)", "",
          f"Signals from the registered rules, {IS_FROM} to {IS_TO}, spread-skip off so every signal counts. "
          "Exits, profits and R were not recorded. Produced by `research/cost_filter.py`. "
          "spread_mult = real/bar spread calibration from `research/h002_costs.csv` (1.0 = not yet calibrated).", "",
          "**Rule (pre-registered):** exclude a market if median spread at entry > 10% of median stop distance. "
          "The spread+commission column is shown for information; the rule uses spread, as registered.", "",
          "**$100 columns:** risk of the smallest allowed trade at the median stop. 1% of $100 is $1. "
          "These never affect the research verdict.", "",
          df.to_markdown(index=False), ""]
    with open(os.path.join(HERE, "cost_filter.md"), "w") as fh:
        fh.write("\n".join(md))
    print("\nWritten research/cost_filter.md")


if __name__ == "__main__":
    main()
