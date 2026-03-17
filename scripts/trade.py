"""
Coinbase Advanced Trade API - Market Order Script
Reads COINBASE_API_KEY and COINBASE_API_SECRET from environment variables.

Required env vars:
  COINBASE_API_KEY      - Coinbase API key name (e.g. "organizations/.../apiKeys/...")
  COINBASE_API_SECRET   - Coinbase API private key (EC private key PEM string)

Optional env vars:
  TRADE_PRODUCT_ID  - Trading pair (default: BTC-USDC)
  ORDER_SIZE        - Quote currency amount to spend (default: 10)
  DRY_RUN           - Set to "true" to skip order placement (default: false)
"""

import hashlib
import hmac
import json
import os
import time
import uuid
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_KEY = os.environ.get("COINBASE_API_KEY", "")
API_SECRET = os.environ.get("COINBASE_API_SECRET", "")

PRODUCT_ID = os.environ.get("TRADE_PRODUCT_ID", "BTC-USDC")
ORDER_SIZE = os.environ.get("ORDER_SIZE", "10")  # quote currency amount (USD/USDC)
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

BASE_URL = "https://api.coinbase.com"
LOG_FILE = "trade_log.jsonl"


# ---------------------------------------------------------------------------
# Auth helpers (Coinbase Advanced Trade API uses JWT-style HMAC signing)
# ---------------------------------------------------------------------------
def _build_jwt(method: str, path: str) -> str:
    """
    Build a JWT for the Coinbase Advanced Trade REST API.
    Coinbase uses ES256 (EC key). For simplicity this implementation
    uses the legacy HMAC approach supported by API key + secret pairs
    created in the Coinbase Developer Platform.
    """
    import base64

    try:
        import jwt as pyjwt  # type: ignore
    except ImportError:
        pyjwt = None  # fallback: use HMAC

    if pyjwt is not None:
        # CDP keys use EC P-256; the secret is a PEM-encoded private key.
        uri = f"{method} api.coinbase.com{path}"
        payload = {
            "sub": API_KEY,
            "iss": "cdp",
            "nbf": int(time.time()),
            "exp": int(time.time()) + 120,
            "uri": uri,
        }
        return pyjwt.encode(
            payload,
            API_SECRET,
            algorithm="ES256",
            headers={"kid": API_KEY, "nonce": secrets_nonce()},
        )
    return ""  # handled in _headers below


def secrets_nonce() -> str:
    import secrets as _s
    return _s.token_hex(16)


def _headers_legacy(method: str, path: str, body: str = "") -> dict:
    """HMAC-SHA256 authentication for older API key/secret pairs."""
    timestamp = str(int(time.time()))
    message = timestamp + method.upper() + path + body
    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    return {
        "CB-ACCESS-KEY": API_KEY,
        "CB-ACCESS-SIGN": signature,
        "CB-ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json",
    }


def _headers(method: str, path: str, body: str = "") -> dict:
    """Return appropriate auth headers, preferring JWT if PyJWT is installed."""
    try:
        import jwt  # noqa: F401
        token = _build_jwt(method, path)
        if token:
            return {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
    except ImportError:
        pass
    return _headers_legacy(method, path, body)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------
def get_best_bid_ask(product_id: str) -> dict:
    path = f"/api/v3/brokerage/best_bid_ask?product_ids={product_id}"
    resp = requests.get(BASE_URL + path, headers=_headers("GET", path), timeout=10)
    resp.raise_for_status()
    return resp.json()


def place_market_order(product_id: str, quote_size: str) -> dict:
    """Place a market BUY order spending `quote_size` of the quote currency."""
    path = "/api/v3/brokerage/orders"
    order_id = str(uuid.uuid4())
    payload = {
        "client_order_id": order_id,
        "product_id": product_id,
        "side": "BUY",
        "order_configuration": {
            "market_market_ioc": {
                "quote_size": quote_size,
            }
        },
    }
    body = json.dumps(payload)
    resp = requests.post(
        BASE_URL + path,
        headers=_headers("POST", path, body),
        data=body,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def log_event(event: dict) -> None:
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")
    print(json.dumps(event, indent=2))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    if not API_KEY or not API_SECRET:
        raise EnvironmentError(
            "COINBASE_API_KEY and COINBASE_API_SECRET must be set."
        )

    print(f"Product: {PRODUCT_ID} | Size: {ORDER_SIZE} | Dry run: {DRY_RUN}")

    # Fetch current price for reference
    try:
        bba = get_best_bid_ask(PRODUCT_ID)
        pricebooks = bba.get("pricebooks", [{}])
        best_ask = pricebooks[0].get("asks", [{}])[0].get("price", "N/A") if pricebooks else "N/A"
        print(f"Current best ask: {best_ask}")
        log_event({"event": "price_check", "product": PRODUCT_ID, "best_ask": best_ask})
    except Exception as exc:
        print(f"Warning: could not fetch price — {exc}")

    if DRY_RUN:
        log_event({
            "event": "dry_run_order",
            "product": PRODUCT_ID,
            "quote_size": ORDER_SIZE,
            "side": "BUY",
        })
        print("DRY RUN — no order placed.")
        return

    # Place the market order
    result = place_market_order(PRODUCT_ID, ORDER_SIZE)
    success = result.get("success", False)
    order_id = result.get("order_id") or result.get("success_response", {}).get("order_id")

    log_event({
        "event": "order_placed",
        "success": success,
        "order_id": order_id,
        "product": PRODUCT_ID,
        "quote_size": ORDER_SIZE,
        "response": result,
    })

    if not success:
        raise RuntimeError(f"Order failed: {result}")

    print(f"Order placed successfully. ID: {order_id}")


if __name__ == "__main__":
    main()
