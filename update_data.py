#!/usr/bin/env python3
"""
Updates data.json for the dashboard from paper trader state.
Run this alongside the paper trader (or on cron).
"""
import json
import requests
from pathlib import Path
from datetime import datetime, timezone

STATE_FILE = Path("/home/e/.openclaw/workspace/paper_trader_state.json")
TRADE_LOG = Path("/home/e/.openclaw/workspace/paper_trader_log.jsonl")
DATA_FILE = Path(__file__).parent / "data.json"
TRADING_FEE = 0.001

def fetch_price():
    """Get current NEAR price from CoinGecko"""
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "near", "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=10,
        )
        r.raise_for_status()
        d = r.json()["near"]
        return {"price": d["usd"], "change_24h": d.get("usd_24h_change", 0)}
    except Exception as e:
        print(f"Price fetch error: {e}")
        return None

def load_trades():
    """Load trades from jsonl log"""
    trades = []
    if TRADE_LOG.exists():
        with open(TRADE_LOG) as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))
    return trades

def _position_equity(pos, current_price):
    """Calculate current equity for an open position (what you'd get if you closed now)."""
    size = pos["size"]
    fee = size * current_price * TRADING_FEE
    if pos["side"] == "long":
        return size * current_price - fee
    else:
        # Short: you received size*entry from the short sale, buy back at current_price
        return size * pos["entry_price"] - size * current_price - fee

def main():
    if not STATE_FILE.exists():
        print("No state file yet")
        return

    state = json.loads(STATE_FILE.read_text())
    price_data = fetch_price()

    # Merge trades from log + state (log first, so log's richer data wins dedup)
    all_trades = load_trades() + state.get("trades", [])
    # Deduplicate by time
    seen = set()
    unique_trades = []
    for t in all_trades:
        key = t.get("time", "") + t.get("side", "")
        if key not in seen:
            seen.add(key)
            unique_trades.append(t)
    unique_trades.sort(key=lambda t: t.get("time", ""))

    # Compute stats (use net PnL if available)
    total_pnl = sum(t.get("pnl_usdt_net", t.get("pnl_usdt", 0)) for t in unique_trades)
    wins = sum(1 for t in unique_trades if t.get("pnl_usdt_net", t.get("pnl_usdt", 0)) > 0)
    total = len(unique_trades)
    current_price = price_data["price"] if price_data else (
        state["position"]["entry_price"] if state.get("position") else 0
    )

    # Equity curve data (start → each trade) — use net PnL
    equity_points = [state["stake_usdt"]]
    running = state["stake_usdt"]
    for t in unique_trades:
        running += t.get("pnl_usdt_net", t.get("pnl_usdt", 0))
        equity_points.append(round(running, 2))

    data = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "pair": state.get("pair", "NEAR/USDT"),
        "stake": state.get("stake_usdt", 1000),
        "current_price": current_price,
        "price_change_24h": round(price_data["change_24h"], 2) if price_data else None,
        "balance_usdt": state.get("balance_usdt", 0),
        "position": state.get("position"),
        "trades": unique_trades,
        "stats": {
            "total_trades": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": round(wins / total * 100, 1) if total > 0 else 0,
            "total_pnl": round(total_pnl, 2),
            "total_pnl_pct": round(total_pnl / state.get("stake_usdt", 1000) * 100, 2),
            "equity": round(
                state.get("balance_usdt", 0) + (
                    _position_equity(state["position"], current_price)
                    if state.get("position") else 0
                ), 2
            ),
        },
        "equity_curve": equity_points,
        "exit_reasons": {},
    }

    # Count exit reasons
    for t in unique_trades:
        reason = t.get("exit_reason", "unknown")
        data["exit_reasons"][reason] = data["exit_reasons"].get(reason, 0) + 1

    # If no trades yet, use the backtest stats
    if total == 0:
        data["exit_reasons"] = {"median_recross": 65, "rpmar": 25, "signal_reversal": 5, "rsi": 5}

    DATA_FILE.write_text(json.dumps(data, indent=2))
    print(f"✅ Updated data.json | Price: ${current_price:.4f} | Trades: {total} | Equity: ${data['stats']['equity']}")

if __name__ == "__main__":
    main()
