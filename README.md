# NEAR/USDT Paper Trading System

**Status:** Active — Paper Trading
**Pair:** NEAR/USDT | **Timeframe:** 2–20min scalping
**Strategy:** v6.1 — StochRSI + MACD + BB + Volume + Regime Filter + Scaled TP
**Dashboard:** https://near-trader-dashboard.netlify.app

---

## Architecture

```
Binance API (5m/15m klines)
        │
        ▼
paper_trader_near.py          ← Main trading engine (runs in background)
        │
        ├──→ paper_trader_state.json    ← Current balance, position, trade list (JSON)
        ├──→ paper_trader_log.jsonl     ← Append-only trade log (JSONL)
        └──→ paper_trader_live.log      ← Human-readable live log
                │
                ▼
        update_data.py                  ← Merges state + log → data.json
                │
                ▼
        near-trader-dashboard/data.json ← Dashboard data source
                │
                ▼
        index.html (Netlify)            ← Public dashboard
```

## Quick Reference

| Action | Command |
|--------|---------|
| **Start trader** | `cd /home/e/.openclaw/workspace && /home/e/.hermes/hermes-agent/venv/bin/python3 paper_trader_near.py > paper_trader_live.log 2>&1 &` |
| **Check if running** | `pgrep -f paper_trader_near.py` |
| **Live log** | `tail -30 /home/e/.openclaw/workspace/paper_trader_live.log` |
| **Trade log** | `tail -20 /home/e/.openclaw/workspace/paper_trader_log.jsonl` |
| **Current state** | `python3 -c "import json; d=json.load(open('/home/e/.openclaw/workspace/paper_trader_state.json')); print(json.dumps(d, indent=2))"` |
| **Update dashboard** | `python3 /home/e/.openclaw/workspace/near-trader-dashboard/update_data.py` |
| **Deploy dashboard** | `cd /home/e/.openclaw/workspace/near-trader-dashboard && NETLIFY_AUTH_TOKEN=nfp_MpdmBZc485soqUAg7weXnEA68B1NxxX1e83 netlify deploy --prod --dir=.` |
| **Kill trader** | `pkill -f paper_trader_near.py` |
| **Reset trades** | See "Resetting State" below |

## Key Files

| File | Path | Purpose |
|------|------|---------|
| Trader engine | `/home/e/.openclaw/workspace/paper_trader_near.py` | Main loop, connects to Binance API |
| Live state | `/home/e/.openclaw/workspace/paper_trader_state.json` | Balance, position, trades array |
| Trade log | `/home/e/.openclaw/workspace/paper_trader_log.jsonl` | Append-only JSONL of completed trades |
| Live log | `/home/e/.openclaw/workspace/paper_trader_live.log` | Human-readable activity log |
| Dashboard updater | `near-trader-dashboard/update_data.py` | Merges state+log → data.json |
| Dashboard HTML | `near-trader-dashboard/index.html` | Static HTML/JS dashboard |
| Dashboard data | `near-trader-dashboard/data.json` | Generated data for dashboard |
| Credentials | `/home/e/.openclaw/workspace/memory/active/near-trader-dashboard-credentials.md` | API keys, tokens |
| Wiki docs | `~/wiki/entities/near-trading-project.md` | Full project documentation |
| Trading journal | `/home/e/.openclaw/workspace/near-trader-dashboard/trading_journal.md` | Human-readable trade journal |
| Status file | `/home/e/.openclaw/workspace/near-trader-dashboard/STATUS.md` | Quick status snapshot |

## Strategy v6.1

### Entry Scoring (≥60/100 required)

| Factor | Points | Condition |
|--------|--------|-----------|
| StochRSI | 25 | K < 20 (long) or K > 80 (short) |
| MACD | 20 | Histogram > 0 (long) or < 0 (short) |
| EMA Regime | 20 | EMA9 > EMA21 (long) or EMA9 < EMA21 (short) |
| RSI Zone | 15 | RSI 35-55 (long) or 45-65 (short) |
| Volume | 10 | Volume > 1.5x average |
| Bollinger | 10 | Price ≤ BB mid (long) or ≥ BB mid (short) |

### Exit Conditions (first to trigger)
1. **Hard stop:** -0.5%
2. **TP1:** +0.5% → close 50%, move stop to entry
3. **TP2:** +1.2% → close remainder
4. **RSI extreme:** RSI > 70 (longs) or < 30 (shorts)
5. **Signal reversal:** StochRSI K > 80 (longs) or K < 20 (shorts)
6. **EMA reversal:** EMA9 crosses EMA21 against position

### Risk Management
- **Circuit breaker:** 2 consecutive losses → 15-minute pause
- **Daily loss limit:** 3% of starting balance
- **Trading fees:** 0.1% taker fee per side (0.2% round trip)
- **Position sizing:** 100% of balance per trade (paper trading)

### Data Source
- **Primary:** Binance klines API (`/api/v3/klines`)
- **5m candles:** 200 limit (for indicators)
- **15m candles:** 100 limit (for trend direction)
- **Loop interval:** 90 seconds

## Operating Procedures

### Starting a Live Session
```bash
# 1. Check current state
python3 -c "import json; print(json.dumps(json.load(open('/home/e/.openclaw/workspace/paper_trader_state.json')), indent=2))"

# 2. Start trader in background
cd /home/e/.openclaw/workspace
/home/e/.hermes/hermes-agent/venv/bin/python3 paper_trader_near.py > paper_trader_live.log 2>&1 &

# 3. Verify it's running
pgrep -f paper_trader_near.py

# 4. Watch first few cycles
tail -f paper_trader_live.log
```

### Resetting State (Clean Slate)
```bash
# 1. Stop trader if running
pkill -f paper_trader_near.py

# 2. Reset state file
python3 -c "
import json
from pathlib import Path
from datetime import datetime, timezone

state = {
    'pair': 'NEAR/USDT',
    'stake_usdt': 1000,
    'balance_usdt': 1000.0,
    'position': None,
    'trades': [],
    'started_at': datetime.now(timezone.utc).isoformat(),
    'version': 'v6.1',
    'consecutive_losses': 0,
    'circuit_breaker_until': None,
    'daily_pnl': 0.0,
}
Path('/home/e/.openclaw/workspace/paper_trader_state.json').write_text(json.dumps(state, indent=2))
print('✅ State reset: FLAT, \$1000.00')
"

# 3. Clear trade log
> /home/e/.openclaw/workspace/paper_trader_log.jsonl

# 4. Update dashboard data
python3 /home/e/.openclaw/workspace/near-trader-dashboard/update_data.py

# 5. Deploy dashboard
cd /home/e/.openclaw/workspace/near-trader-dashboard
NETLIFY_AUTH_TOKEN=nfp_MpdmBZc485soqUAg7weXnEA68B1NxxX1e83 netlify deploy --prod --dir=.
```

### Deploying Dashboard
```bash
export PATH="$HOME/.npm-global/bin:$PATH"
cd /home/e/.openclaw/workspace/near-trader-dashboard
NETLIFY_AUTH_TOKEN=nfp_MpdmBZc485soqUAg7weXnEA68B1NxxX1e83 netlify deploy --prod --dir=.
```
Alternative: `git push origin master` (Netlify auto-deploys from GitHub).

## User Rules (MANDATORY)

1. **High probability only** — if setup isn't clear, stay flat
2. **No trading in low volume** — volume must be reasonable
3. **No trading in chop** — EMA(9/21) must be aligned with trend
4. **Max 2 losses in a row** — then mandatory 15-min break
5. **"Play the high probability"** — user's standing instruction

## Environment Notes

- **Python:** `/home/e/.hermes/hermes-agent/venv/bin/python3`
- **No pandas** — trader uses numpy only
- **No requests lib** — trader uses `urllib.request`
- **CoinGecko free API** returns only ~49 data points — use Binance klines instead
- **Netlify CLI** can timeout — git push is more reliable fallback

## Credentials

See: `/home/e/.openclaw/workspace/memory/active/near-trader-dashboard-credentials.md`

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v5 | 2026-05-15 | Initial strategy: StochRSI + Regime Filter + RSI Exit |
| v6 | 2026-05-16 | Score entry + MACD + BB + Volume + Scaled TP + Circuit Breaker |
| v6.1 | 2026-05-16 | numpy-only rewrite, Binance data source, trading fees |
