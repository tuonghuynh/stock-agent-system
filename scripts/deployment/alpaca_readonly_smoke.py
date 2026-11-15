#!/usr/bin/env python3
"""Optional Alpaca paper read-only smoke; this module has no order method."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

PAPER_URL = "https://paper-api.alpaca.markets"


def main() -> int:
    key = os.getenv("ALPACA_PAPER_KEY")
    secret = os.getenv("ALPACA_PAPER_SECRET")
    base_url = os.getenv("ALPACA_PAPER_BASE_URL", PAPER_URL).rstrip("/")
    if not key or not secret:
        print("SKIP: Alpaca paper credentials are not configured")
        return 0
    if base_url != PAPER_URL:
        print("Refusing non-paper Alpaca endpoint", file=sys.stderr)
        return 1
    headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}
    results: dict[str, object] = {}
    try:
        for name, path in (
            ("account", "/v2/account"),
            ("clock", "/v2/clock"),
            ("positions", "/v2/positions"),
            ("orders", "/v2/orders?status=open"),
        ):
            request = urllib.request.Request(f"{base_url}{path}", headers=headers)  # noqa: S310
            with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
                results[name] = response.status
    except (OSError, urllib.error.URLError) as error:
        print(f"Alpaca paper read-only smoke failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(results, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
