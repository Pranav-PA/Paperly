#!/usr/bin/env python3
"""
Publish the server's current public address to its private ntfy channel, signed with the discovery key,
so the Paperly app can switch to it automatically when the tunnel URL changes.
    python scripts/publish_url.py https://example.trycloudflare.com
"""
import hashlib
import hmac
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.config import settings  # noqa: E402


def sign(url: str, ts: int) -> str:
    return hmac.new(settings.DISCOVERY_KEY.encode(), f"{url}|{ts}".encode(), hashlib.sha256).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: publish_url.py URL")
        return 2
    url = sys.argv[1].strip().rstrip("/")
    ts = int(time.time())
    body = json.dumps({"url": url, "ts": ts, "sig": sign(url, ts)}).encode()
    request = urllib.request.Request(
        f"{settings.DISCOVERY_SERVER.rstrip('/')}/{settings.DISCOVERY_TOPIC}", data=body, method="POST",
        headers={"Title": "paperly-address", "Cache": "yes"},
    )
    try:
        urllib.request.urlopen(request, timeout=20).read()
        print(f"[*] Published address for the app: {url}")
        return 0
    except Exception as e:  # network hiccup: the supervisor retries later
        print(f"[!] Could not publish address ({e}); will retry.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
