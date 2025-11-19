#!/usr/bin/env python3
"""
basic_bot.py
Simplified Binance Futures Testnet trading bot (REST)
Supports: MARKET, LIMIT orders (BUY / SELL) and a simple TWAP executor
Logs requests/responses to file.
"""

import argparse
import time
import hmac
import hashlib
import requests
import logging
import sys
import threading
from urllib.parse import urlencode
from datetime import datetime, timedelta

# -------------------------
# CONFIG
# -------------------------
# Set TESTNET_BASE_URL to Binance Futures testnet
TESTNET_BASE_URL = "https://testnet.binancefuture.com"  # per assignment

# Logging setup
logger = logging.getLogger("basicbot")
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

fh = logging.FileHandler("basicbot.log")
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)


# -------------------------
# Helpers
# -------------------------
def sign_payload(secret, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def public_get(path, params=None):
    url = TESTNET_BASE_URL + path
    r = requests.get(url, params=params, timeout=10)
    logger.debug(f"GET {r.url} -> {r.status_code} {r.text}")
    r.raise_for_status()
    return r.json()


def signed_request(api_key, api_secret, http_method, path, params=None):
    if params is None:
        params = {}
    timestamp = int(time.time() * 1000)
    params["timestamp"] = timestamp
    query_string = urlencode(params, doseq=True)
    signature = sign_payload(api_secret, query_string)
    query_with_sig = f"{query_string}&signature={signature}"
    url = TESTNET_BASE_URL + path + "?" + query_with_sig
    headers = {"X-MBX-APIKEY": api_key}
    logger.debug(f"{http_method} {url} with headers={headers}")
    if http_method == "POST":
        r = requests.post(url, headers=headers, timeout=10)
    elif http_method == "DELETE":
        r = requests.delete(url, headers=headers, timeout=10)
    elif http_method == "GET":
        r = requests.get(url, headers=headers, timeout=10)
    else:
        raise ValueError("Unsupported HTTP method")
    logger.debug(f"RESP {r.status_code} {r.text}")
    try:
        r.raise_for_status()
    except Exception as e:
        logger.error(f"HTTP error: {e} - {r.text}")
        raise
    return r.json()


# -------------------------
# BasicBot
# -------------------------
class BasicBot:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    def _place_order(self, symbol: str, side: str, order_type: str, quantity: float,
                     price: float = None, time_in_force: str = "GTC", reduce_only: bool = False):
        path = "/fapi/v1/order"  # futures USDT-M order endpoint
        params = {
            "symbol": symbol.upper(),
            "side": side.upper(),  # BUY or SELL
            "type": order_type.upper(),  # MARKET or LIMIT
            "quantity": float(quantity),
            "timeInForce": time_in_force,
            "reduceOnly": str(reduce_only).lower()
        }
        if order_type.upper() == "LIMIT":
            if price is None:
                raise ValueError("LIMIT orders require a price")
            params["price"] = float(price)
        # remove None values & adjust MARKET not to send price/timeInForce
        if order_type.upper() == "MARKET":
            params.pop("price", None)
            params.pop("timeInForce", None)
        # sign and send
        try:
            resp = signed_request(self.api_key, self.api_secret, "POST", path, params)
            logger.info(f"Order placed: {resp}")
            return resp
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            raise

    def place_market_order(self, symbol: str, side: str, quantity: float):
        return self._place_order(symbol, side, "MARKET", quantity)

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float, tif="GTC"):
        return self._place_order(symbol, side, "LIMIT", quantity, price, time_in_force=tif)

    def get_account_info(self):
        path = "/fapi/v2/balance"
        return signed_request(self.api_key, self.api_secret, "GET", path, {})

    # Simple TWAP implementation: split total_qty into n slices over duration_seconds
    def twap(self, symbol: str, side: str, total_qty: float, slices: int = 5, duration_seconds: int = 30, order_type="MARKET"):
        if slices <= 0 or duration_seconds <= 0:
            raise ValueError("slices and duration_seconds must be positive integers")
        slice_qty = float(total_qty) / slices
        delay = duration_seconds / slices
        results = []
        logger.info(f"Starting TWAP: {slices} slices, {slice_qty} each, delay {delay}s")
        for i in range(slices):
            logger.info(f"TWAP slice {i+1}/{slices}")
            try:
                if order_type.upper() == "MARKET":
                    r = self.place_market_order(symbol, side, slice_qty)
                else:
                    raise NotImplementedError("TWAP currently supports only MARKET slices")
                results.append(r)
            except Exception as e:
                logger.error(f"TWAP slice {i+1} failed: {e}")
                results.append({"error": str(e)})
            time.sleep(delay)
        logger.info("TWAP complete")
        return results


# -------------------------
# CLI
# -------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="BasicBot - Binance Futures Testnet Trading Bot")
    parser.add_argument("--api-key", required=True, help="Binance API key (testnet)")
    parser.add_argument("--api-secret", required=True, help="Binance API secret (testnet)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # market
    mkt = sub.add_parser("market", help="Place a market order")
    mkt.add_argument("--symbol", required=True)
    mkt.add_argument("--side", required=True, choices=["BUY", "SELL"])
    mkt.add_argument("--qty", type=float, required=True)

    # limit
    lmt = sub.add_parser("limit", help="Place a limit order")
    lmt.add_argument("--symbol", required=True)
    lmt.add_argument("--side", required=True, choices=["BUY", "SELL"])
    lmt.add_argument("--qty", type=float, required=True)
    lmt.add_argument("--price", type=float, required=True)
    lmt.add_argument("--tif", default="GTC", choices=["GTC", "IOC", "FOK"])

    # twap
    tw = sub.add_parser("twap", help="Simple TWAP execution (slices market orders over time)")
    tw.add_argument("--symbol", required=True)
    tw.add_argument("--side", required=True, choices=["BUY", "SELL"])
    tw.add_argument("--total-qty", type=float, required=True)
    tw.add_argument("--slices", type=int, default=5)
    tw.add_argument("--duration", type=int, default=30, help="total duration in seconds")

    # info
    inf = sub.add_parser("info", help="Get account balance info")

    return parser.parse_args()


def main():
    args = parse_args()
    bot = BasicBot(args.api_key, args.api_secret)

    try:
        if args.cmd == "market":
            resp = bot.place_market_order(args.symbol, args.side, args.qty)
            print("Result:", resp)
        elif args.cmd == "limit":
            resp = bot.place_limit_order(args.symbol, args.side, args.qty, args.price, args.tif)
            print("Result:", resp)
        elif args.cmd == "twap":
            resp = bot.twap(args.symbol, args.side, args.total_qty, slices=args.slices, duration_seconds=args.duration)
            print("TWAP results:", resp)
        elif args.cmd == "info":
            print(bot.get_account_info())
    except Exception as e:
        logger.exception("Unhandled error in main: %s", e)
        print("Error:", e)


if __name__ == "__main__":
    main()


    
