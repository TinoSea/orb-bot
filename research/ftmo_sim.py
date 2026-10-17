#!/usr/bin/env python3
"""
H-002 amendment 17: the gold bot on an FTMO $10,000 2-Step Challenge.

Replays the in-sample gold trade list (from ms_replica.py) under FTMO's rules:
  Phase 1 +10%, Phase 2 +5%; equity above (CE(S)T-midnight balance - 5% of initial) and above 90% of
  initial; at least 4 trading days per phase; no time limit; no new entries after 15:00 New York on
  Fridays (gap-trading rule: gold closes for the weekend at 17:00 New York).

  python research/ftmo_sim.py --trades research/results/h002/gate0/replica_XAUUSD_M1_IS.csv \
      --out research/ftmo_10k.md

Runs: A historical rolling starts (one challenge per month), B Monte Carlo resampling whole trading days
under three edge scenarios, C a funded year with monthly payouts. Decision rule as pre-registered.
Not financial advice. In-sample evidence only.
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from small_account import per_ounce  # noqa: E402

SERVER_MINUS_NY = 7
SERVER_MINUS_CET = 1          # FP Markets server (NY+7) is one hour ahead of CE(S)T all year
INITIAL = 10_000.0
DAILY = 0.05
MAXLOSS = 0.10
TARGETS = (0.10, 0.05)
MIN_DAYS = 4
SPLIT = 0.80
RISKS = (0.005, 0.010, 0.015, 0.020)


def prepare(tr: pd.DataFrame, stress: float) -> pd.DataFrame:
    po = per_ounce(tr)
    po["exit_time"] = pd.to_datetime(tr["exit_time"])
    ny = po["entry_time"] - pd.Timedelta(hours=SERVER_MINUS_NY)
    po["friday_late"] = (ny.dt.dayofweek == 4) & (ny.dt.hour >= 15)
    po["day"] = (po["entry_time"] - pd.Timedelta(hours=SERVER_MINUS_CET)).dt.date
    po["net"] = po["move"] + po["swap"] - po["comm"] - stress          # $ per oz, after costs
    po["R"] = po["net"] / po["risk"]
    return po


class Account:
    """One FTMO account phase. Trades are dicts with risk, net, mae (all $ per oz) and day."""

    def __init__(self, start: float, risk_pct: float):
        self.bal = start
        self.risk_pct = risk_pct
        self.cur_day = None
        self.day_start = start
        self.days: set = set()
        self.n = 0

    def trade(self, t) -> str | None:
        if t["day"] != self.cur_day:
            self.cur_day, self.day_start = t["day"], self.bal
        oz = max(1.0, np.floor(self.bal * self.risk_pct / t["risk"]))        # 0.01 lot = 1 oz, minimum 1
        ref = max(self.day_start, self.bal)                                   # conservative daily reference
        worst = self.bal - oz * t["mae"]
        self.bal += oz * t["net"]
        self.days.add(t["day"])
        self.n += 1
        low = min(worst, self.bal)
        if low < ref - DAILY * INITIAL:
            return "daily"
        if low < INITIAL * (1 - MAXLOSS):
            return "max"
        return None


def run_phase(trades, risk_pct: float, target: float, cap: int | None = None):
    """Returns (outcome, trades used). outcome: pass / daily / max / unfinished.
    `trades` may be a list or an iterator (Monte Carlo); `cap` limits iterator length."""
    acc = Account(INITIAL, risk_pct)
    k = 0
    for t in trades:
        k += 1
        bad = acc.trade(t)
        if bad:
            return bad, k
        if acc.bal >= INITIAL * (1 + target) and len(acc.days) >= MIN_DAYS:
            return "pass", k
        if cap and k >= cap:
            break
    return "unfinished", k


def historical(po: pd.DataFrame, risk_pct: float) -> pd.DataFrame:
    rows = po.to_dict("records")
    rows = [r for r in rows if not r["friday_late"]]
    times = [r["entry_time"] for r in rows]
    months = pd.date_range(po["entry_time"].min().to_period("M").to_timestamp(),
                           po["entry_time"].max(), freq="MS")
    out = []
    for m in months:
        i = next((k for k, t in enumerate(times) if t >= m), None)
        if i is None:
            continue
        o1, n1 = run_phase(rows[i:], risk_pct, TARGETS[0])
        res = {"start": m.strftime("%Y-%m"), "phase1": o1, "p1_trades": n1}
        if o1 == "pass":
            j = i + n1
            o2, n2 = run_phase(rows[j:], risk_pct, TARGETS[1])
            res.update(phase2=o2, p2_trades=n2)
            end = rows[min(j + n2, len(rows)) - 1]["exit_time"]
            res["months"] = round((end - rows[i]["entry_time"]).days / 30.44, 1) if o2 == "pass" else np.nan
        else:
            res.update(phase2="-", p2_trades=0, months=np.nan)
        res["result"] = "PASS" if res.get("phase2") == "pass" else (
            "unfinished" if "unfinished" in (o1, res.get("phase2")) else "FAIL")
        out.append(res)
    return pd.DataFrame(out)


def day_blocks(po: pd.DataFrame, shift_R: float) -> list[list[dict]]:
    d = po[~po["friday_late"]].copy()
    d["net"] = d["net"] - shift_R * d["risk"]
    return [g.to_dict("records") for _, g in d.groupby("day", sort=True)]


def sample_stream(blocks, rng):
    """Endless stream of trades, drawing whole trading days at random. Each drawn day gets a fresh
    day key so that same-day trades share one daily-loss reference and different draws don't."""
    n = 0
    while True:
        n += 1
        for t in blocks[rng.integers(len(blocks))]:
            yield {**t, "day": n}


def monte_carlo(blocks, risk_pct: float, rate_per_month: float, sims: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    passed, fails, months = 0, {"daily": 0, "max": 0}, []
    for _ in range(sims):
        stream = sample_stream(blocks, rng)
        o1, n1 = run_phase(stream, risk_pct, TARGETS[0], cap=5000)
        if o1 != "pass":
            fails[o1] = fails.get(o1, 0) + 1
            continue
        o2, n2 = run_phase(stream, risk_pct, TARGETS[1], cap=5000)
        if o2 != "pass":
            fails[o2] = fails.get(o2, 0) + 1
            continue
        passed += 1
        months.append((n1 + n2) / rate_per_month)
    m = np.array(months) if months else np.array([np.nan])
    return {"pass_%": round(100 * passed / sims, 1),
            "fail_daily_%": round(100 * fails.get("daily", 0) / sims, 1),
            "fail_max_%": round(100 * fails.get("max", 0) / sims, 1),
            "months_median": round(float(np.nanmedian(m)), 1),
            "months_p90": round(float(np.nanpercentile(m, 90)), 1)}


def funded_year(blocks, risk_pct: float, rate_per_month: float, sims: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    per_month = max(1, int(round(rate_per_month)))
    breached, payouts = 0, []
    for _ in range(sims):
        acc = Account(INITIAL, risk_pct)
        paid = 0.0
        stream = sample_stream(blocks, rng)
        dead = False
        for _m in range(12):
            for _ in range(per_month):
                if acc.trade(next(stream)):
                    dead = True
                    break
            if dead:
                break
            if acc.bal > INITIAL:                       # monthly payout, account back to $10,000
                paid += SPLIT * (acc.bal - INITIAL)
                acc.bal = INITIAL
                acc.day_start = min(acc.day_start, INITIAL)
        breached += dead
        payouts.append(paid)
    p = np.array(payouts)
    return {"breach_in_year_%": round(100 * breached / sims, 1),
            "payout_mean_$": round(p.mean(), 0), "payout_median_$": round(np.median(p), 0),
            "payout_p10_$": round(np.percentile(p, 10), 0), "payout_p90_$": round(np.percentile(p, 90), 0)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades", required=True)
    ap.add_argument("--stress", type=float, default=0.30)
    ap.add_argument("--sims", type=int, default=10000)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    po = prepare(pd.read_csv(a.trades), a.stress)
    kept = po[~po["friday_late"]]
    span_months = (po["entry_time"].max() - po["entry_time"].min()).days / 30.44
    rate = len(kept) / span_months
    mean_R = kept["R"].mean()

    L = ["# FTMO $10,000 2-Step Challenge — gold bot, in-sample (H-002 amendment 17)", "",
         f"Trades: `{a.trades}`: {len(po)} signals, {int(po['friday_late'].sum())} removed by the Friday 15:00 New York "
         f"cutoff, {len(kept)} kept = **{rate:.1f} trades a month**. Cost stress +${a.stress:.2f}/oz. "
         f"Mean result after costs **{mean_R:+.3f}R** per trade.",
         "Rules: +10% then +5%; equity above CE(S)T-midnight balance − $500 and above $9,000; ≥4 trading days; "
         "no time limit. Produced by `research/ftmo_sim.py`.", ""]

    # A. historical rolling starts
    L += ["## A. Historical: one challenge started each month (real trade order)", ""]
    summ = []
    for r in RISKS:
        h = historical(po, r)
        fin = h[h["result"] != "unfinished"]
        summ.append({"risk_%": r * 100, "starts": len(h), "passed": int((h["result"] == "PASS").sum()),
                     "failed": int((h["result"] == "FAIL").sum()), "unfinished": int((h["result"] == "unfinished").sum()),
                     "pass_%_of_finished": round(100 * (fin["result"] == "PASS").mean(), 0) if len(fin) else np.nan,
                     "median_months_to_pass": h["months"].median()})
        if r == 0.01:
            detail = h
    L += [pd.DataFrame(summ).to_markdown(index=False), "",
          "<details><summary>Every start at 1% risk</summary>", "", detail.to_markdown(index=False), "", "</details>", ""]

    # B. Monte Carlo
    L += [f"## B. Monte Carlo: {a.sims:,} challenges, whole trading days resampled", ""]
    mc_rows = []
    scen = {"as measured": 0.0, "edge halved": 0.5 * mean_R, "no edge": mean_R}
    for name, shift in scen.items():
        blocks = day_blocks(po, shift)
        for i, r in enumerate(RISKS):
            mc_rows.append({"scenario": name, "risk_%": r * 100,
                            **monte_carlo(blocks, r, rate, a.sims, 100 + i)})
    mc = pd.DataFrame(mc_rows)
    L += [mc.to_markdown(index=False), "",
          "pass_% = both phases passed. fail_daily / fail_max = which FTMO limit ended the attempt. "
          "Months from the first trade to passing Phase 2, at the in-sample trade rate.", ""]

    # decision rule
    h = mc[mc["scenario"] == "edge halved"]
    eligible = h[h["months_median"] <= 18]
    L += ["## Decision rule (amendment 17, scenario \"edge halved\")", ""]
    if eligible.empty:
        chosen = None
        L += ["No risk level passes within a median of 18 months.", ""]
    else:
        best = eligible.sort_values(["pass_%", "risk_%"], ascending=[False, True]).iloc[0]
        chosen = best["risk_%"] / 100
        verdict = "meets" if best["pass_%"] >= 50 else "is BELOW"
        L += [f"- Eligible levels (median ≤ 18 months): {', '.join(f'{x:g}%' for x in eligible['risk_%'])}.",
              f"- Highest pass probability: **{best['risk_%']:g}% risk → {best['pass_%']}%**, median "
              f"{best['months_median']} months (90th percentile {best['months_p90']}).",
              f"- This {verdict} the 50% bar.", ""]

    # C. funded year
    if chosen is not None:
        L += [f"## C. Funded year at {chosen * 100:g}% risk (monthly payouts, 80% split)", ""]
        fy = []
        for name, shift in scen.items():
            fy.append({"scenario": name, **funded_year(day_blocks(po, shift), chosen, rate, a.sims, 7)})
        L += [pd.DataFrame(fy).to_markdown(index=False), "",
              "A breach ends the account; payouts already taken are kept. FTMO also refunds the fee with the first reward.", ""]

    rep = "\n".join(L)
    print(rep)
    if a.out:
        with open(a.out, "w") as f:
            f.write(rep + "\n")


if __name__ == "__main__":
    main()
