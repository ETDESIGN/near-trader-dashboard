#!/usr/bin/env python3
"""
NEAR Trader — Historical Simulation (5 Trade Test)
Runs the v6.1 strategy against recent Binance 5m data to generate test trades.
"""
import json
import sys
import urllib.request
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

# Strategy params (same as live trader)
SRSI_PERIOD = 14
SRSI_K_BUY = 20
SRSI_K_SELL = 80
EMA_FAST = 9
EMA_SLOW = 21
RSI_PERIOD = 14
VOLUME_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5
HARD_STOP_PCT = 0.5
TP1_PCT = 0.5
TP2_PCT = 1.2
ENTRY_SCORE_MIN = 60
CIRCUIT_BREAKER_LOSSES = 2
CIRCUIT_BREAKER_PAUSE = 900
DAILY_LOSS_LIMIT_PCT = 3.0
TRADING_FEE = 0.001

BINANCE_BASE = "https://api.binance.com/api/v3"
SYMBOL = "NEARUSDT"
STAKE_USDT = 1000

def ema_numpy(arr, period):
    k = 2.0 / (period + 1)
    result = np.empty_like(arr)
    result[0] = arr[0]
    for i in range(1, len(arr)):
        result[i] = arr[i] * k + result[i-1] * (1 - k)
    return result

def rsi_numpy(close, period=14):
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.empty_like(close)
    avg_loss = np.empty_like(close)
    avg_gain[:period] = np.nan
    avg_loss[:period] = np.nan
    avg_gain[period] = np.mean(gain[1:period+1])
    avg_loss[period] = np.mean(loss[1:period+1])
    for i in range(period+1, len(close)):
        avg_gain[i] = (avg_gain[i-1] * (period-1) + gain[i]) / period
        avg_loss[i] = (avg_loss[i-1] * (period-1) + loss[i]) / period
    rs = np.where(avg_loss != 0, avg_gain / avg_loss, 100.0)
    return 100.0 - (100.0 / (1.0 + rs))

def stoch_rsi_numpy(close, period=14, k_smooth=3):
    rsi = rsi_numpy(close, period)
    n = len(close)
    stoch = np.full(n, np.nan)
    for i in range(period, n):
        rsi_slice = rsi[i-period+1:i+1]
        rsi_min = np.nanmin(rsi_slice)
        rsi_max = np.nanmax(rsi_slice)
        if rsi_max != rsi_min:
            stoch[i] = (rsi[i] - rsi_min) / (rsi_max - rsi_min) * 100
        else:
            stoch[i] = 50.0
    k = np.full(n, np.nan)
    for i in range(period+k_smooth-1, n):
        k[i] = np.nanmean(stoch[i-k_smooth+1:i+1])
    return k, rsi

def compute_macd(close, fast=12, slow=26, signal=9):
    ema_f = ema_numpy(close, fast)
    ema_s = ema_numpy(close, slow)
    macd_line = ema_f - ema_s
    sig_line = ema_numpy(macd_line, signal)
    return macd_line - sig_line

def compute_bb(close, period=20, std_dev=2.0):
    n = len(close)
    mid = np.full(n, np.nan)
    for i in range(period-1, n):
        sl = close[i-period+1:i+1]
        mid[i] = np.mean(sl)
    return mid

def volume_avg(volume, window=20):
    n = len(volume)
    result = np.full(n, np.nan)
    for i in range(window-1, n):
        result[i] = np.mean(volume[i-window+1:i+1])
    return result

def score_entry(price, srsi_k, rsi_val, macd_hist, ema_f, ema_s, vol, vol_avg, bb_mid, side):
    score = 0
    breakdown = {}
    if not np.isnan(srsi_k):
        if side == "long" and srsi_k < SRSI_K_BUY: pts = 25
        elif side == "short" and srsi_k > SRSI_K_SELL: pts = 25
        elif side == "long" and srsi_k < 40: pts = 15
        elif side == "short" and srsi_k > 60: pts = 15
        else: pts = 0
        score += pts; breakdown["stochrsi"] = pts
    if not np.isnan(macd_hist):
        if side == "long" and macd_hist > 0: pts = 20
        elif side == "short" and macd_hist < 0: pts = 20
        else: pts = 0
        score += pts; breakdown["macd"] = pts
    if not np.isnan(ema_f) and not np.isnan(ema_s):
        if side == "long" and ema_f > ema_s: pts = 20
        elif side == "short" and ema_f < ema_s: pts = 20
        else: pts = 0
        score += pts; breakdown["ema"] = pts
    if not np.isnan(rsi_val):
        if side == "long" and 35 <= rsi_val <= 55: pts = 15
        elif side == "short" and 45 <= rsi_val <= 65: pts = 15
        else: pts = 0
        score += pts; breakdown["rsi"] = pts
    if not np.isnan(vol_avg) and vol_avg > 0:
        if vol > vol_avg * VOLUME_MULTIPLIER: pts = 10
        elif vol > vol_avg: pts = 5
        else: pts = 0
        score += pts; breakdown["volume"] = pts
    if not np.isnan(bb_mid):
        if side == "long" and price <= bb_mid: pts = 10
        elif side == "short" and price >= bb_mid: pts = 10
        else: pts = 0
        score += pts; breakdown["bb"] = pts
    return score, breakdown

# Fetch data
print("📡 Fetching 5m candles from Binance...")
url = f"{BINANCE_BASE}/klines?symbol={SYMBOL}&interval=5m&limit=500"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
resp = urllib.request.urlopen(req, timeout=15)
klines = json.loads(resp.read())

opens = np.array([float(k[1]) for k in klines])
highs = np.array([float(k[2]) for k in klines])
lows = np.array([float(k[3]) for k in klines])
closes = np.array([float(k[4]) for k in klines])
volumes = np.array([float(k[5]) for k in klines])
timestamps = [k[0] for k in klines]

print(f"   Got {len(closes)} candles")
print(f"   Price range: ${closes.min():.4f} - ${closes.max():.4f}")
print(f"   Current: ${closes[-1]:.4f}")

# Compute indicators
ema_f = ema_numpy(closes, EMA_FAST)
ema_s = ema_numpy(closes, EMA_SLOW)
srsi_k, rsi_val = stoch_rsi_numpy(closes, SRSI_PERIOD)
macd_hist = compute_macd(closes)
bb_mid = compute_bb(closes)
vol_avg = volume_avg(volumes)

# Simulate trading
balance = STAKE_USDT
position = None
trades = []
consecutive_losses = 0
circuit_breaker_until = None
candle_pause = 0

for i in range(30, len(closes)):  # Start after warmup
    price = closes[i]
    ts = datetime.fromtimestamp(timestamps[i]/1000, tz=timezone.utc).isoformat()

    # Skip if in circuit breaker pause
    if candle_pause > 0:
        candle_pause -= 1
        # Still check exits
        if position:
            entry = position["entry_price"]
            side = position["side"]
            pnl_pct = (price - entry) / entry * 100 if side == "long" else (entry - price) / entry * 100
            
            exit_reason = None
            exit_detail = ""
            
            if pnl_pct <= -HARD_STOP_PCT:
                exit_reason = "hard_stop"
                exit_detail = f"P/L {pnl_pct:.2f}% hit -{HARD_STOP_PCT}% stop"
            elif side == "long" and not np.isnan(rsi_val[i]) and rsi_val[i] > 70:
                exit_reason = "rsi_extreme"
                exit_detail = f"RSI {rsi_val[i]:.1f} > 70"
            elif side == "short" and not np.isnan(rsi_val[i]) and rsi_val[i] < 30:
                exit_reason = "rsi_extreme"
                exit_detail = f"RSI {rsi_val[i]:.1f} < 30"
            elif side == "long" and not np.isnan(srsi_k[i]) and srsi_k[i] > SRSI_K_SELL:
                exit_reason = "signal_reversal"
                exit_detail = f"K {srsi_k[i]:.1f} > {SRSI_K_SELL}"
            elif side == "short" and not np.isnan(srsi_k[i]) and srsi_k[i] < SRSI_K_BUY:
                exit_reason = "signal_reversal"
                exit_detail = f"K {srsi_k[i]:.1f} < {SRSI_K_BUY}"
            elif not np.isnan(ema_f[i]) and not np.isnan(ema_s[i]):
                if side == "long" and ema_f[i] < ema_s[i]:
                    exit_reason = "ema_reversal"
                    exit_detail = f"EMA9({ema_f[i]:.4f}) < EMA21({ema_s[i]:.4f})"
                elif side == "short" and ema_f[i] > ema_s[i]:
                    exit_reason = "ema_reversal"
                    exit_detail = f"EMA9({ema_f[i]:.4f}) > EMA21({ema_s[i]:.4f})"
            
            if exit_reason:
                if side == "long":
                    pnl = (price - entry) * position["size"]
                else:
                    pnl = (entry - price) * position["size"]
                exit_fee = position["size"] * price * TRADING_FEE
                pnl -= exit_fee
                total_pnl = pnl + position.get("partial_closed", 0)
                balance = round(position["size"] * price - exit_fee + balance, 2)
                
                trade = {
                    "time": ts, "side": side,
                    "entry_price": entry, "exit_price": round(price, 6),
                    "size": position["size"], "pnl_usdt": round(pnl, 4),
                    "pnl_pct": round(pnl / (entry * position["size"]) * 100, 2),
                    "exit_reason": exit_reason, "exit_detail": exit_detail,
                    "entry_time": position["entry_time"], "score": position.get("score", 0),
                    "total_pnl_incl_partial": round(total_pnl, 4),
                }
                trades.append(trade)
                
                emoji = "🟢" if total_pnl > 0 else "🔴"
                print(f"  {emoji} CLOSED {side.upper()} @ ${price:.4f} | PnL: ${total_pnl:.2f} | Reason: {exit_reason}")
                
                if total_pnl < 0:
                    consecutive_losses += 1
                else:
                    consecutive_losses = 0
                
                position = None
        
        if len(trades) >= 5:
            break
        continue

    # Check exits first
    if position:
        entry = position["entry_price"]
        side = position["side"]
        pnl_pct = (price - entry) / entry * 100 if side == "long" else (entry - price) / entry * 100
        
        exit_reason = None
        exit_detail = ""
        
        if pnl_pct <= -HARD_STOP_PCT:
            exit_reason = "hard_stop"
            exit_detail = f"P/L {pnl_pct:.2f}% hit -{HARD_STOP_PCT}% stop"
        elif pnl_pct >= TP1_PCT and not position.get("tp1_hit"):
            # Partial close at TP1
            close_size = position["size"] * 0.5
            if side == "long":
                partial_pnl = (price - entry) * close_size
            else:
                partial_pnl = (entry - price) * close_size
            exit_fee = close_size * price * TRADING_FEE
            partial_pnl -= exit_fee
            balance = round(close_size * price - exit_fee, 2)
            position["tp1_hit"] = True
            position["size"] = round(position["size"] - close_size, 4)
            position["partial_closed"] = round(position.get("partial_closed", 0) + partial_pnl, 4)
            
            trade = {
                "time": ts, "side": side,
                "entry_price": entry, "exit_price": round(price, 6),
                "size": round(close_size, 4), "pnl_usdt": round(partial_pnl, 4),
                "pnl_pct": round(partial_pnl / (entry * close_size) * 100, 2),
                "exit_reason": "tp1_partial", "exit_detail": f"P/L {pnl_pct:.2f}% hit +{TP1_PCT}% TP1",
                "entry_time": position["entry_time"], "score": position.get("score", 0),
            }
            trades.append(trade)
            print(f"  🟡 TP1 PARTIAL {side.upper()} @ ${price:.4f} | PnL: ${partial_pnl:.2f} | Remaining: {position['size']:.2f} NEAR")
            continue
        elif pnl_pct >= TP2_PCT:
            exit_reason = "tp2_hit"
            exit_detail = f"P/L {pnl_pct:.2f}% hit +{TP2_PCT}% TP2"
        elif side == "long" and not np.isnan(rsi_val[i]) and rsi_val[i] > 70:
            exit_reason = "rsi_extreme"
            exit_detail = f"RSI {rsi_val[i]:.1f} > 70"
        elif side == "short" and not np.isnan(rsi_val[i]) and rsi_val[i] < 30:
            exit_reason = "rsi_extreme"
            exit_detail = f"RSI {rsi_val[i]:.1f} < 30"
        elif side == "long" and not np.isnan(srsi_k[i]) and srsi_k[i] > SRSI_K_SELL:
            exit_reason = "signal_reversal"
            exit_detail = f"K {srsi_k[i]:.1f} > {SRSI_K_SELL}"
        elif side == "short" and not np.isnan(srsi_k[i]) and srsi_k[i] < SRSI_K_BUY:
            exit_reason = "signal_reversal"
            exit_detail = f"K {srsi_k[i]:.1f} < {SRSI_K_BUY}"
        elif not np.isnan(ema_f[i]) and not np.isnan(ema_s[i]):
            if side == "long" and ema_f[i] < ema_s[i]:
                exit_reason = "ema_reversal"
                exit_detail = f"EMA9({ema_f[i]:.4f}) < EMA21({ema_s[i]:.4f})"
            elif side == "short" and ema_f[i] > ema_s[i]:
                exit_reason = "ema_reversal"
                exit_detail = f"EMA9({ema_f[i]:.4f}) > EMA21({ema_s[i]:.4f})"
        
        if exit_reason and exit_reason != "tp1_partial":
            if side == "long":
                pnl = (price - entry) * position["size"]
            else:
                pnl = (entry - price) * position["size"]
            exit_fee = position["size"] * price * TRADING_FEE
            pnl -= exit_fee
            total_pnl = pnl + position.get("partial_closed", 0)
            balance = round(position["size"] * price - exit_fee + balance, 2)
            
            trade = {
                "time": ts, "side": side,
                "entry_price": entry, "exit_price": round(price, 6),
                "size": position["size"], "pnl_usdt": round(pnl, 4),
                "pnl_pct": round(pnl / (entry * position["size"]) * 100, 2),
                "exit_reason": exit_reason, "exit_detail": exit_detail,
                "entry_time": position["entry_time"], "score": position.get("score", 0),
                "total_pnl_incl_partial": round(total_pnl, 4),
            }
            trades.append(trade)
            
            emoji = "🟢" if total_pnl > 0 else "🔴"
            print(f"  {emoji} CLOSED {side.upper()} @ ${price:.4f} | PnL: ${total_pnl:.2f} | Reason: {exit_reason}")
            
            if total_pnl < 0:
                consecutive_losses += 1
            else:
                consecutive_losses = 0
            
            position = None
            
            if len(trades) >= 5:
                break

    # Check entries
    if not position and balance > 0:
        if consecutive_losses >= CIRCUIT_BREAKER_LOSSES:
            candle_pause = CIRCUIT_BREAKER_PAUSE // 300  # Convert to 5m candles
            consecutive_losses = 0
            print(f"  🔴 CIRCUIT BREAKER: {candle_pause} candle pause")
            continue

        # Determine sides to check
        sides_to_check = []
        if not np.isnan(srsi_k[i]):
            if srsi_k[i] < SRSI_K_BUY:
                sides_to_check.append("long")
            elif srsi_k[i] > SRSI_K_SELL:
                sides_to_check.append("short")
            else:
                # Check both sides
                sides_to_check = ["long", "short"]
        else:
            sides_to_check = ["long", "short"]

        best_signal = None
        best_score = 0
        best_breakdown = {}

        for side in sides_to_check:
            sc, bd = score_entry(
                price, srsi_k[i], rsi_val[i], macd_hist[i],
                ema_f[i], ema_s[i], volumes[i], vol_avg[i], bb_mid[i], side
            )
            if sc >= ENTRY_SCORE_MIN and sc > best_score:
                best_signal = side
                best_score = sc
                best_breakdown = bd

        if best_signal:
            entry_fee = balance * TRADING_FEE
            net_balance = balance - entry_fee
            size = net_balance / price
            position = {
                "side": best_signal,
                "entry_price": round(price, 6),
                "size": round(size, 4),
                "entry_time": ts,
                "tp1_hit": False,
                "partial_closed": 0.0,
                "score": best_score,
                "entry_fee": round(entry_fee, 4),
            }
            balance = 0
            print(f"  🔵 OPENED {best_signal.upper()} @ ${price:.4f} | Score: {best_score}/100 | {best_breakdown}")

# Summary
print()
print("=" * 60)
print("  SIMULATION RESULTS")
print("=" * 60)

total_pnl = sum(t["pnl_usdt"] for t in trades)
wins = sum(1 for t in trades if t["pnl_usdt"] > 0)
losses = sum(1 for t in trades if t["pnl_usdt"] < 0)
breakeven = sum(1 for t in trades if t["pnl_usdt"] == 0)
wr = f"{wins/len(trades)*100:.1f}%" if trades else "N/A"

print(f"  Trades:      {len(trades)}")
print(f"  Wins:        {wins}")
print(f"  Losses:      {losses}")
print(f"  Breakeven:   {breakeven}")
print(f"  Win Rate:    {wr}")
print(f"  Net P&L:     {'+' if total_pnl >= 0 else ''}${total_pnl:.2f} ({'+' if total_pnl >= 0 else ''}{total_pnl/STAKE_USDT*100:.2f}%)")
print(f"  Final Bal:   ${balance:.2f}")

if trades:
    best = max(trades, key=lambda t: t["pnl_usdt"])
    worst = min(trades, key=lambda t: t["pnl_usdt"])
    print(f"  Best Trade:  {best['side'].upper()} +${best['pnl_usdt']:.2f}")
    print(f"  Worst Trade: {worst['side'].upper()} ${worst['pnl_usdt']:.2f}")

print()
print("  Trade Details:")
for i, t in enumerate(trades, 1):
    emoji = "🟢" if t["pnl_usdt"] > 0 else "🔴" if t["pnl_usdt"] < 0 else "⚪"
    print(f"  {i}. {emoji} {t['side'].upper():5} ${t['entry_price']:.4f} → ${t['exit_price']:.4f} | "
          f"{'+' if t['pnl_usdt'] >= 0 else ''}${t['pnl_usdt']:.2f} | {t['exit_reason']} | Score: {t.get('score',0)}")

# Save trades to state file
state_file = Path("/home/e/.openclaw/workspace/paper_trader_state.json")
state = {
    "pair": "NEAR/USDT",
    "stake_usdt": STAKE_USDT,
    "balance_usdt": balance,
    "position": position,
    "trades": trades,
    "started_at": datetime.now(timezone.utc).isoformat(),
    "version": "v6.1-sim",
    "consecutive_losses": consecutive_losses,
    "circuit_breaker_until": None,
    "daily_pnl": total_pnl,
}
state_file.write_text(json.dumps(state, indent=2))

# Append to trade log
log_file = Path("/home/e/.openclaw/workspace/paper_trader_log.jsonl")
with open(log_file, "a") as f:
    for t in trades:
        f.write(json.dumps(t) + "\n")

print()
print(f"✅ State saved to {state_file}")
print(f"✅ Trades logged to {log_file}")
