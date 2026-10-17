#!/usr/bin/env python3
"""
Trade-by-trade check: MT5 Strategy Tester vs the independent Python replica.

Two separately written implementations of the same rules should produce the same trades.
Where they differ, one of them has a bug (or the data differ), and we find out which before
trusting either.

Inputs
  --mt5      MS_journal.csv written by MS_Gold.mq5 during the tester run. On a Mac it is in:
             ~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/
             MetaTrader 5/Tester/Agent-127.0.0.1-3000/MQL5/Files/MS_journal.csv
             (delete it before each tester run - the EA appends)
  --replica  trades CSV written by ms_replica.py (research/results/h002/...)
  --tick     the symbol's tick size, to express price differences in ticks

Pass rule (decided before comparing): at least 95% of trades match on entry time (same minute)
and direction, and the median entry-price difference is at most 2 ticks.
"""

import argparse
import sys

import numpy as np
import pandas as pd


def mt5_trades(path: str) -> pd.DataFrame:
    j = pd.read_csv(path)
    j["time"] = pd.to_datetime(j["server_time"], format="%Y.%m.%d %H:%M")
    rows, open_ = [], None
    for _, r in j.iterrows():
        if r["entry"] == "IN":
            open_ = r
        elif r["entry"] == "OUT" and open_ is not None:
            rows.append({"entry_time": open_["time"], "side": "LONG" if open_["side"] == "BUY" else "SHORT",
                         "entry": float(open_["price"]), "lots": float(open_["lots"]),
                         "exit_time": r["time"], "exit": float(r["price"]), "reason": r["reason"],
                         "net": float(r["profit"]) + float(r["commission"]) + float(r["swap"])
                         + float(open_["commission"])})
            open_ = None
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mt5", required=True)
    ap.add_argument("--replica", required=True)
    ap.add_argument("--tick", type=float, required=True)
    a = ap.parse_args()

    m = mt5_trades(a.mt5)
    r = pd.read_csv(a.replica, parse_dates=["entry_time", "exit_time"])
    r["entry_time"] = r["entry_time"].dt.floor("min")
    m["entry_time"] = m["entry_time"].dt.floor("min")

    key = ["entry_time", "side"]
    both = m.merge(r, on=key, how="outer", suffixes=("_mt5", "_py"), indicator=True)
    matched = both[both["_merge"] == "both"].copy()
    only_m = both[both["_merge"] == "left_only"]
    only_r = both[both["_merge"] == "right_only"]

    n = max(len(m), len(r))
    rate = len(matched) / n if n else 0.0
    matched["entry_diff_ticks"] = (matched["entry_mt5"] - matched["entry_py"]).abs() / a.tick
    matched["exit_diff_ticks"] = (matched["exit_mt5"] - matched["exit_py"]).abs() / a.tick
    matched["same_exit"] = matched["exit_time_mt5"].dt.floor("min") == matched["exit_time_py"].dt.floor("min")

    print(f"\n  MT5 trades: {len(m)}   replica trades: {len(r)}   matched: {len(matched)}  ({100 * rate:.1f}%)")
    if len(matched):
        print(f"  entry price diff (ticks): median {matched['entry_diff_ticks'].median():.1f}, "
              f"max {matched['entry_diff_ticks'].max():.1f}")
        print(f"  same exit minute: {100 * matched['same_exit'].mean():.1f}%   "
              f"exit price diff median {matched['exit_diff_ticks'].median():.1f} ticks")
        print(f"  net P&L: MT5 {matched['net_mt5'].sum():.2f} vs replica {matched['net_py'].sum():.2f}")
    if len(only_m):
        print("\n  In MT5 only (first 10):")
        print(only_m[key].head(10).to_string(index=False))
    if len(only_r):
        print("\n  In replica only (first 10):")
        print(only_r[key].head(10).to_string(index=False))

    ok = rate >= 0.95 and (len(matched) == 0 or matched["entry_diff_ticks"].median() <= 2)
    print(f"\n  VERDICT: {'PASS - implementations agree' if ok else 'FAIL - investigate the differences above'}\n")
    out = a.replica.replace(".csv", "_vs_mt5.csv")
    both.to_csv(out, index=False)
    print(f"  Full comparison saved to {out}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
