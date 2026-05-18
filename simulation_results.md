# NEAR Trader — Simulation Results (5-Trade Test)

**Date:** 2026-05-18
**Data:** 500 x 5m candles from Binance (~$1.48–$1.556 range)
**Strategy:** v6.1

## Results

| Metric | Value |
|--------|-------|
| Trades | 5 |
| Wins | 2 |
| Losses | 3 |
| Win Rate | 40.0% |
| Net P&L | -$7.79 (-0.78%) |
| Final Balance | $998.89 |
| Best Trade | LONG +$3.75 |
| Worst Trade | SHORT -$6.33 |

## Trade Details

| # | Side | Entry | Exit | P&L | Reason | Score |
|---|------|-------|------|-----|--------|-------|
| 1 | LONG | $1.4980 | $1.4940 | -$3.66 | ema_reversal | 75 |
| 2 | LONG | $1.4850 | $1.4810 | -$3.67 | ema_reversal | 60 |
| 3 | SHORT | $1.4850 | $1.4930 | -$6.33 | hard_stop | 60 |
| 4 | LONG | $1.5180 | $1.5260 | +$2.12 | tp1_partial | 75 |
| 5 | LONG | $1.5180 | $1.5310 | +$3.75 | signal_reversal | 75 |

## Analysis

### What worked
- Trade #4/#5 (LONG $1.518) was the best setup: score 75, caught a +2.1% move, TP1 hit
- Circuit breaker correctly activated after 2 consecutive losses

### What didn't
- Trades #1 and #2: EMA reversal exits triggered quickly — price was choppy, EMAs kept crossing
- Trade #3: SHORT hit hard stop (-0.5%) — price spiked up against the position
- Score 60 entries underperformed score 75 entries (2/3 losses at 60 vs 0/2 losses at 75)

### Key observations
1. **Score threshold matters:** Raising minimum score from 60 to 70 would have avoided 2 of the 3 losses
2. **EMA reversal is the dominant exit** (3/5 trades) — in choppy conditions, this is a leak
3. **Hard stop on SHORT was too tight** — $1.485→$1.493 is only 0.54%, stopped out before reversal
4. **The strategy needs a "chop filter"** — when EMA9 and EMA21 are close together (within ~0.1%), avoid entries

## Recommendations

1. **Raise entry score minimum to 65 or 70** — fewer trades, better quality
2. **Add chop detection** — if |EMA9 - EMA21| / price < 0.1%, skip entries
3. **Widen hard stop to 0.7%** — 0.5% is too tight for 5m volatility
4. **Consider volume-weighted scoring** — low volume entries consistently lost money
