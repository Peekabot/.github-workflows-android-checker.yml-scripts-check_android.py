"""
Coinbase Advanced Trade API - Multi-Asset Strategy Script

Strategy overview:
  - Diversified: trades multiple products (BTC-USDC, ETH-USDC by default)
  - Day-of-week bias:
      Thursday          → BUY bias  (anticipated sell-off dip)
      Monday–Wednesday  → SELL bias (anticipated early-week strength)
      Fri–Sun           → NEUTRAL
  - Price signal (24-period SMA on hourly candles):
      price < SMA * (1 - BUY_THRESHOLD)   → BUY signal
      price > SMA * (1 + SELL_THRESHOLD)  → SELL signal
  - Rush guard: if 1-hour price move > RUSH_PCT, skip buying (avoid chasing)
  - Combined decision: day bias + price signal must both agree (or price signal
    is strong enough alone) to place an order.

Required env vars:
  COINBASE_API_KEY      Coinbase CDP API key name
  COINBASE_API_SECRET   Coinbase CDP EC private key (PEM) or HMAC secret

Optional env vars (all have defaults):
  TRADE_PRODUCTS    Comma-separated list of product IDs  (default: BTC-USDC,ETH-USDC)
  ORDER_SIZE        Quote currency amount per BUY order  (default: 10)
  SELL_FRACTION     Fraction of available balance to sell (default: 0.5)
  BUY_THRESHOLD     % below SMA to trigger buy           (default: 0.01 = 1%)
  SELL_THRESHOLD    % above SMA to trigger sell          (default: 0.015 = 1.5%)
  RUSH_PCT          1-hour gain that blocks buying       (default: 0.02 = 2%)
  SMA_PERIODS       Number of hourly candles for SMA     (default: 24)
  DRY_RUN           "true" to log without placing orders (default: false)
"""

import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("COINBASE_API_KEY", "")
API_SECRET = os.environ.get("COINBASE_API_SECRET", "")

TRADE_PRODUCTS = [p.strip() for p in os.environ.get("TRADE_PRODUCTS", "BTC-USDC,ETH-USDC").split(",") if p.strip()]
ORDER_SIZE = os.environ.get("ORDER_SIZE", "10")          # quote currency per buy
SELL_FRACTION = float(os.environ.get("SELL_FRACTION", "0.5"))
BUY_THRESHOLD = float(os.environ.get("BUY_THRESHOLD", "0.01"))
SELL_THRESHOLD = float(os.environ.get("SELL_THRESHOLD", "0.015"))
RUSH_PCT = float(os.environ.get("RUSH_PCT", "0.02"))
SMA_PERIODS = int(os.environ.get("SMA_PERIODS", "24"))
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

BASE_URL = "https://api.coinbase.com"
LOG_FILE = "trade_log.jsonl"


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def _nonce() -> str:
    return secrets.token_hex(16)


def _build_jwt(method: str, path: str) -> str:
    try:
        import jwt as pyjwt  # type: ignore
        uri = f"{method} api.coinbase.com{path}"
        now = int(time.time())
        payload = {"sub": API_KEY, "iss": "cdp", "nbf": now, "exp": now + 120, "uri": uri}
        return pyjwt.encode(payload, API_SECRET, algorithm="ES256", headers={"kid": API_KEY, "nonce": _nonce()})
    except ImportError:
        return ""


def _headers(method: str, path: str, body: str = "") -> dict:
    token = _build_jwt(method, path)
    if token:
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # Legacy HMAC fallback
    ts = str(int(time.time()))
    sig = hmac.new(API_SECRET.encode(), (ts + method.upper() + path + body).encode(), hashlib.sha256).hexdigest()
    return {"CB-ACCESS-KEY": API_KEY, "CB-ACCESS-SIGN": sig, "CB-ACCESS-TIMESTAMP": ts, "Content-Type": "application/json"}


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------
def _get(path: str) -> dict:
    resp = requests.get(BASE_URL + path, headers=_headers("GET", path), timeout=10)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict) -> dict:
    body = json.dumps(payload)
    resp = requests.post(BASE_URL + path, headers=_headers("POST", path, body), data=body, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_candles(product_id: str, count: int = 30) -> list[float]:
    """Return the last `count` hourly closing prices, oldest first."""
    end = int(time.time())
    start = end - count * 3600
    path = f"/api/v3/brokerage/products/{product_id}/candles?start={start}&end={end}&granularity=ONE_HOUR"
    data = _get(path)
    candles = data.get("candles", [])
    # Each candle: {start, low, high, open, close, volume}
    # Returned newest-first; reverse to oldest-first.
    closes = [float(c["close"]) for c in reversed(candles) if "close" in c]
    return closes[-count:]


def get_account_balance(currency: str) -> float:
    """Return available balance for a given currency (e.g. BTC, ETH)."""
    data = _get("/api/v3/brokerage/accounts")
    for acct in data.get("accounts", []):
        if acct.get("currency") == currency:
            return float(acct.get("available_balance", {}).get("value", 0))
    return 0.0


def place_buy(product_id: str, quote_size: str) -> dict:
    return _post("/api/v3/brokerage/orders", {
        "client_order_id": str(uuid.uuid4()),
        "product_id": product_id,
        "side": "BUY",
        "order_configuration": {"market_market_ioc": {"quote_size": quote_size}},
    })


def place_sell(product_id: str, base_size: str) -> dict:
    return _post("/api/v3/brokerage/orders", {
        "client_order_id": str(uuid.uuid4()),
        "product_id": product_id,
        "side": "SELL",
        "order_configuration": {"market_market_ioc": {"base_size": base_size}},
    })


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------
def day_bias() -> str:
    """
    Return 'BUY', 'SELL', or 'NEUTRAL' based on day-of-week heuristic.
      Thursday (3)     → BUY  (sell-off dip expected)
      Mon–Wed (0-2)    → SELL (early-week strength)
      Fri–Sun (4-6)    → NEUTRAL
    """
    dow = datetime.now(timezone.utc).weekday()  # 0=Mon … 6=Sun
    if dow == 3:
        return "BUY"
    if dow <= 2:
        return "SELL"
    return "NEUTRAL"


def price_signal(closes: list[float]) -> tuple[str, dict]:
    """
    Compare current price to SMA. Returns ('BUY'|'SELL'|'HOLD', info_dict).
    Also applies rush guard: blocks BUY if last-hour gain > RUSH_PCT.
    """
    if len(closes) < 2:
        return "HOLD", {"reason": "insufficient data"}

    sma = sum(closes[-SMA_PERIODS:]) / min(len(closes), SMA_PERIODS)
    current = closes[-1]
    prev = closes[-2]
    momentum = (current - prev) / prev if prev else 0

    info = {
        "current_price": round(current, 6),
        "sma": round(sma, 6),
        "momentum_1h_pct": round(momentum * 100, 3),
    }

    if momentum > RUSH_PCT:
        info["reason"] = f"rush guard triggered ({momentum*100:.2f}% surge)"
        return "HOLD", info

    if current < sma * (1 - BUY_THRESHOLD):
        info["reason"] = f"price {((sma-current)/sma*100):.2f}% below SMA"
        return "BUY", info

    if current > sma * (1 + SELL_THRESHOLD):
        info["reason"] = f"price {((current-sma)/sma*100):.2f}% above SMA"
        return "SELL", info

    info["reason"] = "price within SMA band"
    return "HOLD", info


def decide(product_id: str) -> tuple[str, dict]:
    """
    Combine day bias + price signal.
    Both must agree on BUY or SELL to act; disagreement → HOLD.
    Exception: a strong price signal alone (>2× threshold) can override NEUTRAL day.
    """
    try:
        closes = get_candles(product_id, count=max(SMA_PERIODS + 5, 30))
    except Exception as exc:
        return "HOLD", {"reason": f"candle fetch failed: {exc}"}

    bias = day_bias()
    signal, info = price_signal(closes)
    info["day_bias"] = bias
    info["price_signal"] = signal

    if signal == "HOLD":
        return "HOLD", info

    if bias == signal:
        return signal, info

    # Strong signal can override a NEUTRAL day (but never override opposite bias)
    if bias == "NEUTRAL" and signal != "HOLD":
        sma = info["sma"]
        current = info["current_price"]
        deviation = abs(current - sma) / sma
        strong_threshold = (BUY_THRESHOLD if signal == "BUY" else SELL_THRESHOLD) * 2
        if deviation >= strong_threshold:
            info["reason"] += " (strong signal overrides neutral day)"
            return signal, info

    info["reason"] = f"day bias ({bias}) conflicts with price signal ({signal}) — holding"
    return "HOLD", info


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log_event(event: dict) -> None:
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event, indent=2))


# ---------------------------------------------------------------------------
# Execute a single product
# ---------------------------------------------------------------------------
def run_product(product_id: str) -> None:
    action, info = decide(product_id)
    base_currency = product_id.split("-")[0]  # e.g. BTC from BTC-USDC

    log_event({"event": "decision", "product": product_id, "action": action, **info})

    if action == "HOLD":
        print(f"[{product_id}] HOLD — {info.get('reason', '')}")
        return

    if DRY_RUN:
        log_event({"event": "dry_run", "product": product_id, "action": action})
        print(f"[{product_id}] DRY RUN {action} — no order placed.")
        return

    if action == "BUY":
        result = place_buy(product_id, ORDER_SIZE)
    else:  # SELL
        balance = get_account_balance(base_currency)
        sell_amount = round(balance * SELL_FRACTION, 8)
        if sell_amount <= 0:
            log_event({"event": "skip_sell", "product": product_id, "reason": "zero balance", "balance": balance})
            print(f"[{product_id}] SELL skipped — no {base_currency} balance.")
            return
        result = place_sell(product_id, str(sell_amount))

    success = result.get("success", False)
    order_id = result.get("order_id") or result.get("success_response", {}).get("order_id")
    log_event({"event": "order", "product": product_id, "action": action, "success": success, "order_id": order_id})

    if not success:
        raise RuntimeError(f"[{product_id}] Order failed: {result}")

    print(f"[{product_id}] {action} order placed. ID: {order_id}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not API_KEY or not API_SECRET:
        raise EnvironmentError("COINBASE_API_KEY and COINBASE_API_SECRET must be set.")

    now = datetime.now(timezone.utc)
    print(f"Run at {now.isoformat()} UTC | Day bias: {day_bias()} | Products: {TRADE_PRODUCTS} | Dry run: {DRY_RUN}")

    errors = []
    for product_id in TRADE_PRODUCTS:
        try:
            run_product(product_id)
        except Exception as exc:
            errors.append((product_id, str(exc)))
            log_event({"event": "error", "product": product_id, "error": str(exc)})
            print(f"[{product_id}] ERROR: {exc}")

    if errors:
        raise RuntimeError(f"Errors in products: {errors}")


if __name__ == "__main__":
    main()
