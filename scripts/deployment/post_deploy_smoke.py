#!/usr/bin/env python3
"""Bounded authenticated development health/version smoke check."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def request_json(url: str, token: str, path: str) -> dict[str, object]:
    request = urllib.request.Request(  # noqa: S310 -- URL is operator-supplied dev target.
        f"{url.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        if response.status != 200:
            raise RuntimeError(f"{path} returned HTTP {response.status}")
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise RuntimeError(f"{path} returned a non-object response")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("DEV_BASE_URL"))
    parser.add_argument("--expected-sha", default=os.getenv("EXPECTED_GIT_SHA"))
    parser.add_argument("--token", default=os.getenv("DEV_TEST_TOKEN"))
    args = parser.parse_args()
    if not args.base_url or not args.expected_sha or not args.token:
        parser.error("base URL, expected SHA, and token are required")
    if not args.base_url.startswith("https://"):
        parser.error("development base URL must use HTTPS")
    try:
        live = request_json(args.base_url, args.token, "/health/live")
        ready = request_json(args.base_url, args.token, "/health/ready")
        version = request_json(args.base_url, args.token, "/api/version")
    except (OSError, ValueError, urllib.error.URLError, RuntimeError) as error:
        print(f"deployment smoke failed: {error}", file=sys.stderr)
        return 1
    if live.get("status") != "live" or ready.get("status") != "ready":
        print("deployment smoke failed: health response is not green", file=sys.stderr)
        return 1
    if version.get("git_commit") != args.expected_sha:
        print("deployment smoke failed: deployed commit mismatch", file=sys.stderr)
        return 1
    rendered = json.dumps(version).lower()
    if any(key in rendered for key in ("secret", "credential", "account_id", "api_key")):
        print("deployment smoke failed: version response exposes sensitive fields", file=sys.stderr)
        return 1
    print(json.dumps({"live": live, "ready": ready, "version": version}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
