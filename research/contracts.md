# Contract terms (FP Markets, account 85928909, server FPMarketsSC-Live)

Filled from `specs.csv` produced by `mt5/ExportData.mq5`. Recorded **before** any strategy results,
because costs and lot sizes decide which markets are realistic.

| Label | Broker symbol | Min lot | Step | Value per point per lot | Typical spread | Swap long / short | 3-day swap | Commission (Raw) | Main session used | 1% risk at $100 possible? |
|---|---|---|---|---|---|---|---|---|---|---|
| *(to fill from export)* | | | | | | | | | | |

**Commission:** check FP Markets' Raw account page for each asset class and enter it here
(USD per lot per side). The replica takes it with `--commission`.

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

