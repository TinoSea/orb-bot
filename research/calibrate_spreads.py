#!/usr/bin/env python3
"""
Spread calibration (H-002 amendment 14c).

  python research/calibrate_spreads.py --samples data/export/spread_samples.csv

Reads the first real ticks at each hour open (mt5/ExportSpreads.mq5) and compares them with
the spread stored in the bar history. Writes the median ratio (tick spread / max(bar spread, 1))
per market into research/h002_costs.csv (spread_mult) and a summary to research/spread_calibration.md.
Uses only in-session hours of each market (as in research/h002_markets.csv).
"""
import argparse
import os
import sys
from datetime import timedelta

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ms_replica as R  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    a = ap.parse_args()
    s = pd.read_csv(a.samples)
    s["hour_open"] = pd.to_datetime(s["hour_open"], format="%Y.%m.%d %H:%M")
    markets = R.load_markets()
    rows = []
    for lab, g in s.groupby("label"):
        m = markets.get(lab)
        if m is not None and not m.mode_24x7:
            keep = []
            for t in g["hour_open"]:
                ny = t.to_pydatetime() - timedelta(hours=R.SERVER_MINUS_NY)
                loc = R.zone_time(ny, m.zone)
                mm = loc.hour * 60 + loc.minute
                keep.append(loc.weekday() < 5 and m.start_min <= mm < m.end_min)
            g = g[np.array(keep)]
        if g.empty:
            continue
        ratio = g["tick_spread_points"] / np.maximum(g["bar_spread_points"], 1.0)
        rows.append({"label": lab, "symbol": g["symbol"].iloc[0], "hours_sampled": len(g),
                     "median_bar_spread_pts": g["bar_spread_points"].median(),
                     "median_tick_spread_pts": g["tick_spread_points"].median(),
                     "p90_tick_spread_pts": g["tick_spread_points"].quantile(0.9),
                     "spread_mult": round(float(max(ratio.median(), 1.0)), 2)})
    out = pd.DataFrame(rows)
    costs = pd.read_csv(os.path.join(HERE, "h002_costs.csv"))
    for _, r in out.iterrows():
        sel = costs["label"] == r["label"]
        costs.loc[sel, "spread_mult"] = r["spread_mult"]
        costs.loc[sel, "spread_mult_basis"] = f"median tick/bar spread at in-session hour opens, {int(r['hours_sampled'])} hours"
    costs.to_csv(os.path.join(HERE, "h002_costs.csv"), index=False)
    with open(os.path.join(HERE, "spread_calibration.md"), "w") as fh:
        fh.write("# Spread calibration (real tick spreads vs stored bar spreads)\n\n"
                 "From `mt5/ExportSpreads.mq5`; multipliers written to `research/h002_costs.csv`. "
                 "A multiplier below 1 is set to 1 (costs are never reduced).\n\n" + out.to_markdown(index=False) + "\n")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
