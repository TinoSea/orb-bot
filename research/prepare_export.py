#!/usr/bin/env python3
"""
Prepare the raw MT5 export for research and write a data-quality report.

  python research/prepare_export.py --raw data/export_raw/orb_export --out data/export

- copies the bar files and specs.csv into --out
- applies the pre-registered data-coverage rule (hypotheses.md, H-002 item 14a) to the
  rolling-futures markets and picks the AGRI market (first passing candidate in registered order)
- writes research/data_quality.md: coverage, gaps, weekend bars, spreads, bad bars, roll jumps

It reports nothing about strategy results.
"""

import argparse
import glob
import os
import shutil

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
AGRI_ORDER = ["COFFEE", "SUGAR", "WHEAT", "CORN", "SOYBEAN", "COCOA", "COTTON"]
COVER_BY = pd.Timestamp("2023-01-31 23:59")
MAX_MISSING_WEEKDAYS = 5
SERVER_MINUS_NY = 7


def load(path):
    df = pd.read_csv(path)
    df.index = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M")
    return df


def missing_weekdays(idx):
    d = pd.Series(idx.normalize().unique())
    gaps = [np.busday_count((a + pd.Timedelta(days=1)).date(), b.date()) for a, b in zip(d[:-1], d[1:])]
    return pd.Series(gaps, index=d[1:]) if gaps else pd.Series(dtype=int)


def coverage_ok(df):
    mw = missing_weekdays(df.index)
    return df.index[0] <= COVER_BY and (mw.max() if len(mw) else 0) <= MAX_MISSING_WEEKDAYS, mw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    specs = pd.read_csv(os.path.join(a.raw, "specs.csv"))
    rows, notes = [], []
    for f in sorted(glob.glob(os.path.join(a.raw, "*_M[15].csv"))):
        name = os.path.basename(f)
        label, tf = name[:-4].rsplit("_", 1)
        df = load(f)
        ny = df.index - pd.Timedelta(hours=SERVER_MINUS_NY)
        step = df.index.to_series().diff().dt.total_seconds() / 3600
        bad = ((df.high < df[["open", "close"]].max(axis=1)) | (df.low > df[["open", "close"]].min(axis=1))).sum()
        ok, mw = coverage_ok(df)
        rel = (df.open - df.close.shift()).abs() / df.close.shift()
        sym = specs.loc[specs.label == label, "symbol"]
        rows.append({
            "label": label, "tf": tf, "symbol": sym.iloc[0] if len(sym) else "", "bars": len(df),
            "first": df.index[0].strftime("%Y-%m-%d"), "last": df.index[-1].strftime("%Y-%m-%d"),
            "server_sat_sun_bars": int((df.index.dayofweek >= 5).sum()),
            "max_missing_weekdays": int(mw.max()) if len(mw) else 0,
            "max_gap_hours": round(step.max(), 1), "bad_ohlc": int(bad), "duplicates": int(df.index.duplicated().sum()),
            "zero_spread_pct": round(100 * (df.spread == 0).mean(), 1), "median_spread_points": df.spread.median(),
            "largest_jump_pct": round(100 * rel.max(), 2),
            "largest_jump_at": rel.idxmax().strftime("%Y-%m-%d %H:%M") if rel.notna().any() else "",
            "coverage_rule": "pass" if ok else "FAIL",
        })
        shutil.copy(f, os.path.join(a.out, name))
    q = pd.DataFrame(rows)

    # AGRI selection: first candidate, in registered order, passing the coverage rule
    agri = None
    for c in AGRI_ORDER:
        r = q[(q.label == f"AGRI_{c}") & (q.tf == "M5")]
        if len(r) and r.iloc[0]["coverage_rule"] == "pass":
            agri = c
            break
    out_specs = specs.copy()
    if agri:
        shutil.copy(os.path.join(a.out, f"AGRI_{agri}_M5.csv"), os.path.join(a.out, "AGRI_M5.csv"))
        row = specs[specs.label == f"AGRI_{agri}"].copy()
        row["label"] = "AGRI"
        out_specs = pd.concat([out_specs, row], ignore_index=True)
        notes.append(f"AGRI = **{agri}** (first candidate in the registered order that passes the coverage rule).")
    else:
        notes.append("AGRI: no candidate passes the coverage rule - recorded missing.")
    bond = q[(q.label == "BOND") & (q.tf == "M5")]
    if len(bond) and bond.iloc[0]["coverage_rule"] != "pass":
        out_specs = out_specs[out_specs.label != "BOND"]
        os.remove(os.path.join(a.out, "BOND_M5.csv"))
        notes.append("BOND (US10YR) fails the coverage rule - recorded missing.")
    else:
        notes.append("BOND = US10YR passes the coverage rule.")
    out_specs.to_csv(os.path.join(a.out, "specs.csv"), index=False)

    btc = q[(q.label == "BTCUSD") & (q.tf == "M5")]
    if len(btc) and btc.iloc[0]["server_sat_sun_bars"] < 100:
        notes.append(f"BTCUSD: only {btc.iloc[0]['server_sat_sun_bars']} weekend bars in the whole history - "
                     "FP Markets' Bitcoin CFD is closed at weekends.")

    md = ["# Data quality: FP Markets export (2026-10-17)", "",
          "Produced by `research/prepare_export.py` from the `mt5/ExportData.mq5` export. "
          "Server time = New York + 7 h. No strategy results are used or shown here.", "",
          "## Decisions from pre-registered rules", ""] + [f"- {n}" for n in notes] + [
          "", "## Per file", "", q.to_markdown(index=False), "",
          "## How to read it", "",
          "- **zero_spread_pct / median_spread_points:** MT5 stores one spread value per bar (in points). "
          "FX on the Raw account is often 0.0 pips; its cost is the commission instead. "
          "Bar spreads understate costs at busy moments, hence the spreads x 2 robustness run (R5).",
          "- **largest_jump:** biggest move between one bar's close and the next bar's open. "
          "For futures-based CFDs (COFFEE, US10YR) some of these are contract rolls, not market moves.",
          "- **max_missing_weekdays:** longest run of weekdays with no bars at all (holidays give 1-2).", ""]
    with open(os.path.join(HERE, "data_quality.md"), "w") as fh:
        fh.write("\n".join(md))
    print("\n".join(notes))
    print(q.to_string(index=False))


if __name__ == "__main__":
    main()
