#!/usr/bin/env python3
"""
NEAR Trader — Instant Status Check
Run this to get a quick snapshot of the trading system.
Usage: python3 status_check.py [--json]
"""
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

STATE_FILE = Path("/home/e/.openclaw/workspace/paper_trader_state.json")
LOG_FILE = Path("/home/e/.openclaw/workspace/paper_trader_log.jsonl")
LIVE_LOG = Path("/home/e/.openclaw/workspace/paper_trader_live.log")
STATUS_FILE = Path(__file__).parent / "STATUS.md"
JOURNAL_FILE = Path(__file__).parent / "trading_journal.md"

def check_process():
    """Check if trader process is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "paper_trader_near.py"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False

def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return None

def load_trades():
    trades = []
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            for line in f:
                line = line.strip()
                if line:
                    trades.append(json.loads(line))
    return trades

def get_recent_log_lines(n=15):
    if not LIVE_LOG.exists():
        return []
    with open(LIVE_LOG) as f:
        lines = f.readlines()
    return lines[-n:]

def format_status_json(state, trades, is_running):
    total = len(trades)
    pnl = sum(t.get("pnl_usdt", 0) for t in trades)
    wins = sum(1 for t in trades if t.get("pnl_usdt", 0) > 0)
    losses = total - wins
    wr = round(wins / total * 100, 1) if total > 0 else 0

    pos = state.get("position") if state else None
    balance = state.get("balance_usdt", 0) if state else 0

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "process_running": is_running,
        "pair": "NEAR/USDT",
        "strategy": "v6.1",
        "balance_usdt": balance,
        "position": {
            "side": pos["side"] if pos else None,
            "entry_price": pos["entry_price"] if pos else None,
            "size": pos["size"] if pos else None,
            "score": pos.get("score", 0) if pos else None,
        } if pos else None,
        "stats": {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": wr,
            "net_pnl": round(pnl, 2),
            "net_pnl_pct": round(pnl / 1000 * 100, 2),
        },
        "risk": {
            "consecutive_losses": state.get("consecutive_losses", 0) if state else 0,
            "circuit_breaker_active": state.get("circuit_breaker_until") is not None if state else False,
            "daily_pnl": state.get("daily_pnl", 0) if state else 0,
        },
        "recent_trades": trades[-5:] if trades else [],
    }

def format_status_text(state, trades, is_running):
    total = len(trades)
    pnl = sum(t.get("pnl_usdt", 0) for t in trades)
    wins = sum(1 for t in trades if t.get("pnl_usdt", 0) > 0)
    losses = total - wins
    wr = f"{wins/total*100:.1f}%" if total > 0 else "N/A"

    pos = state.get("position") if state else None
    balance = state.get("balance_usdt", 0) if state else 0

    lines = []
    lines.append("=" * 60)
    lines.append("  NEAR/USDT Paper Trader — Status")
    lines.append("=" * 60)
    lines.append(f"  Process:     {'🟢 RUNNING' if is_running else '🔴 NOT RUNNING'}")
    lines.append(f"  Position:    {pos['side'].upper() + ' @ $' + str(pos['entry_price']) + ' (score: ' + str(pos.get('score', 0)) + ')' if pos else 'FLAT'}")
    lines.append(f"  Balance:     ${balance:.2f}")
    lines.append(f"  Trades:      {total} ({wins}W / {losses}L)")
    lines.append(f"  Win Rate:    {wr}")
    lines.append(f"  Net P&L:     {'+' if pnl >= 0 else ''}${pnl:.2f} ({'+' if pnl >= 0 else ''}{pnl/1000*100:.2f}%)")
    lines.append(f"  Daily P&L:   ${state.get('daily_pnl', 0):.2f}" if state else "  Daily P&L: N/A")

    if state and state.get("circuit_breaker_until"):
        lines.append(f"  ⚠️  CIRCUIT BREAKER ACTIVE")

    lines.append("-" * 60)

    if trades:
        lines.append("  Recent Trades (last 5):")
        for t in trades[-5:]:
            emoji = "🟢" if t.get("pnl_usdt", 0) > 0 else "🔴" if t.get("pnl_usdt", 0) < 0 else "⚪"
            lines.append(
                f"    {emoji} {t['side'].upper():5} ${t['entry_price']:.4f} → ${t['exit_price']:.4f} | "
                f"{'+' if t.get('pnl_usdt',0) >= 0 else ''}${t.get('pnl_usdt',0):.2f} | {t.get('exit_reason','')}"
            )
    else:
        lines.append("  No trades yet.")

    lines.append("-" * 60)

    recent = get_recent_log_lines(5)
    if recent:
        lines.append("  Recent Log:")
        for line in recent:
            lines.append(f"    {line.rstrip()}")

    lines.append("=" * 60)
    return "\n".join(lines)

def update_status_file(text):
    """Update STATUS.md with current status."""
    STATUS_FILE.write_text(
        f"# NEAR Trader — Live Status\n\n"
        f"> Auto-generated | Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n"
        f"```\n{text}\n```\n"
    )

def update_journal(state, trades):
    """Update trading journal with current data."""
    total = len(trades)
    pnl = sum(t.get("pnl_usdt", 0) for t in trades)
    wins = sum(1 for t in trades if t.get("pnl_usdt", 0) > 0)
    losses = total - wins
    wr = f"{wins/total*100:.1f}%" if total > 0 else "N/A"
    balance = state.get("balance_usdt", 1000) if state else 1000
    pos = state.get("position") if state else None

    trade_rows = ""
    for i, t in enumerate(trades, 1):
        time_str = t.get("time", "")[:16].replace("T", " ") if t.get("time") else "—"
        trade_rows += (
            f"| {i} | {time_str} | {t.get('side','').upper()} | "
            f"${t.get('entry_price',0):.4f} | ${t.get('exit_price',0):.4f} | "
            f"{'+' if t.get('pnl_usdt',0) >= 0 else ''}${t.get('pnl_usdt',0):.2f} | "
            f"{'+' if t.get('pnl_pct',0) >= 0 else ''}{t.get('pnl_pct',0):.2f}% | "
            f"{t.get('exit_reason','')} | {t.get('score',0)} |\n"
        )

    if not trade_rows:
        trade_rows = "| — | — | — | — | — | — | — | — | — |\n"

    pos_str = f"{pos['side'].upper()} @ ${pos['entry_price']}" if pos else "FLAT"

    content = f"""# NEAR Trading Journal

**Pair:** NEAR/USDT | **Strategy:** v6.1
**Session:** Test Run (2026-05-18)
**Last Updated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

---

## Session Summary

| Metric | Value |
|--------|-------|
| Starting Balance | $1,000.00 |
| Current Balance | ${balance:.2f} |
| Open Position | {pos_str} |
| Total Trades | {total} |
| Win Rate | {wr} |
| Net P&L | {'+' if pnl >= 0 else ''}${pnl:.2f} ({'+' if pnl >= 0 else ''}{pnl/1000*100:.2f}%) |
| Status | {'🟢 Active' if total > 0 else '🟡 Waiting for signals'} |

---

## Trade Log

| # | Time | Side | Entry | Exit | P&L $ | P&L % | Exit Reason | Score |
|---|------|------|-------|------|--------|-------|-------------|-------|
{trade_rows}
---

## Notes

- 2026-05-18: Session started. Clean state reset. Waiting for first signal.
"""
    JOURNAL_FILE.write_text(content)

def main():
    as_json = "--json" in sys.argv
    is_running = check_process()
    state = load_state()
    trades = load_trades()

    if as_json:
        print(json.dumps(format_status_json(state, trades, is_running), indent=2))
    else:
        text = format_status_text(state, trades, is_running)
        print(text)
        update_status_file(text)
        update_journal(state, trades)
        print(f"\n✅ STATUS.md and trading_journal.md updated")

if __name__ == "__main__":
    main()
