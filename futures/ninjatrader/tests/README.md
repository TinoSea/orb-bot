# Parity check: NinjaScript vs the Python engine

Not needed to run the bot. A developer check that `LKForward.cs` makes exactly the same entries as `lk_core.py`.
`NtStubs.cs` and `DA.cs` are tiny stand-ins for NinjaTrader's classes, so the strategy compiles outside NinjaTrader.

```
cd futures/ninjatrader/tests
mcs -out:parity.exe DA.cs NtStubs.cs ../LKForward.cs Harness.cs
python3 gen_and_run.py 1 && mono parity.exe     # then compare py_entries.csv with cs_entries.csv
```
2026-10-22: seeds 1-5 (three weeks of random ticks each, 73 entries in all) gave identical entries.
2026-10-25 (v1.10, Asia/London/NY windows): seeds 1-5, 155 entries in all, identical.
