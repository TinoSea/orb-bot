# Contract terms (FP Markets, account 85928909, server FPMarketsSC-Live)

Filled from `specs.csv` produced by `mt5/ExportData.mq5`. Recorded **before** any strategy results,
because costs and lot sizes decide which markets are realistic.

| Label | Broker symbol | Min lot | Step | Value per point per lot | Typical spread | Swap long / short | 3-day swap | Commission (Raw) | Main session used | 1% risk at $100 possible? |
|---|---|---|---|---|---|---|---|---|---|---|
| US500 | US500 | 0.01 | 0.01 | 1 | 0.44   (bar data, see note) | -1.18 / 0.52 (mode 2) | Fri | 0 | New York 09:30–16:00 | yes (min-lot risk $0.25) |
| US100 | US100 | 0.01 | 0.01 | 1 | 1.25   (bar data, see note) | -4.58 / 2.03 (mode 2) | Fri | 0 | New York 09:30–16:00 | close (min-lot risk $1.36) |
| US30 | US30 | 0.01 | 0.01 | 1 | 1.2    (bar data, see note) | -7.98 / 3.57 (mode 2) | Fri | 0 | New York 09:30–16:00 | close (min-lot risk $1.95) |
| US2000 | — | | | | | | | | | not offered |
| UK100 | UK100 | 0.01 | 0.01 | 1.2668 | 1.1    (bar data, see note) | -1.59 / 0.64 (mode 2) | Fri | 0 | London 08:00–16:30 | yes (min-lot risk $0.42) |
| GER40 | GER40 | 0.01 | 0.01 | 1.0843 | 0.8    (bar data, see note) | -2.85 / 0.66 (mode 2) | Fri | 0 | Frankfurt 09:00–17:30 | yes (min-lot risk $0.78) |
| JP225 | JP225 | 0.01 | 0.01 | 0.0679 | 4.6    (bar data, see note) | -47.72 / -7.44 (mode 2) | Fri | 0 | Tokyo 09:00–15:00 | yes (min-lot risk $0.18) |
| BOND | US10YR | 1 | 1 | 1 | 0.08   (bar data, see note) | 0 / 0 (none) | n/a | 0 | New York 08:00–15:00 | yes (min-lot risk $0.32) |
| EURUSD | EURUSD.r | 0.01 | 0.01 | 100000 | 0      (bar data, see note) | -6.23 / 2.68 (mode 1, points) | Wed | 3 | London 08:00–22:00 | no (min-lot risk $2.15) |
| USDJPY | USDJPY.r | 0.01 | 0.01 | 681.849 | 0      (bar data, see note) | 9.58 / -14.82 (mode 1, points) | Wed | 3 | London 08:00–22:00 | no (min-lot risk $2.79) |
| GBPUSD | GBPUSD.r | 0.01 | 0.01 | 100000 | 0      (bar data, see note) | -3.09 / -1.09 (mode 1, points) | Wed | 3 | London 08:00–22:00 | no (min-lot risk $2.69) |
| AUDUSD | AUDUSD.r | 0.01 | 0.01 | 100000 | 0      (bar data, see note) | -0.37 / -2.68 (mode 1, points) | Wed | 3 | London 08:00–22:00 | no (min-lot risk $2.06) |
| XAUUSD | XAUUSD.r | 0.01 | 0.01 | 100 | 0.02   (bar data, see note) | -62.89 / 37.52 (mode 1, points) | Wed | 3 | New York 08:00–17:00 | no (min-lot risk $11.88) |
| XAGUSD | XAGUSD.r | 0.01 | 0.01 | 5000 | 0.009  (bar data, see note) | -10.3 / 4.7 (mode 1, points) | Wed | 3 | New York 08:00–17:00 | no (min-lot risk $13.73) |
| WTI | XTIUSD | 0.01 | 0.01 | 1000 | 0.004  (bar data, see note) | 30.7 / -127.5 (mode 1, points) | Wed | 0 | New York 09:00–14:30 | no (min-lot risk $9.35) |
| BTCUSD | BTCUSD | 0.01 | 0.01 | 1 | 12.51   (bar data, see note) | -20 / -2 (mode 5) | Fri | 0 | New York 00:00–24:00 | no (min-lot risk $6.17) |
| AGRI | COFFEE | 1 | 1 | 10 | 0.7    (bar data, see note) | 0 / 0 (none) | n/a | 0 | New York 09:30–14:00 | no (min-lot risk $39.52) |

Filled 2026-10-17 from `specs.csv`. "Value per point" is USD per 1.0 price move per 1 lot (converted at the
median in-sample FX rate for GBP/EUR/JPY markets). "Typical spread" is the median **bar** spread at signal times,
which MT5 tends to record as the lowest spread in the bar; real spreads are being measured with
`mt5/ExportSpreads.mq5` (amendment 14c). Min-lot risk is at the median in-sample stop (`research/cost_filter.md`).

Swap modes are MT5's codes (1 = points per lot per night; others are confirmed against the tester journal at Gate 0).

**Commission** (`research/h002_costs.csv`, read by the replica): FX USD 3.00 per lot per side on the Raw account;
metals assumed the same until the Gate 0 tester journal shows the real figure; indices, oil, BTC and softs
spread-only (to confirm).

**Symbol mapping** (from `all_symbols.csv`, 2026-10-17, before any H-002 data was examined)

| Label | FP Markets symbol | Note |
|---|---|---|
| US500 / US100 / US30 | US500 / US100 / US30 | Index cash CFDs |
| UK100 / GER40 / JP225 | UK100 / GER40 / JP225 | Index cash CFDs |
| BOND | US10YR | T-Note **futures** CFD (rolls); data-coverage rule applies |
| EURUSD / USDJPY / GBPUSD / AUDUSD | `.r` versions | Raw pricing (spread + commission) |
| XAUUSD / XAGUSD | XAUUSD.r / XAGUSD.r | Only Raw versions exist |
| WTI | XTIUSD | Cash (the `WTI` symbol is a dated futures contract) |
| BTCUSD | BTCUSD | |
| AGRI | COFFEE, SUGAR (futures); WHEAT, CORN, COCOA (cash); COTTON (futures) | All exported; selection by the data-coverage rule |

**Missing markets** (not offered by the broker): **US2000** (Russell 2000). Not substituted: the IWM ETF
CFD exists, but US equity already has three markets that move together, so a fourth adds little.

