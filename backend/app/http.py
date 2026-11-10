"""Minimal stdlib HTTP helper with retry/backoff. Adapters take `get` so tests can inject fixtures."""
from __future__ import annotations
import time
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; shanghao-dashboard/0.1; +public-data-only)"


class FetchError(Exception):
    pass


def get(url: str, headers: dict | None = None, timeout: float = 40, retries: int = 2, backoff: float = 2.0) -> bytes:
    h = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        h.update(headers)
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(backoff * (attempt + 1))
                continue
            break
        except Exception as e:  # timeouts, DNS, SSL
            last = e
            if attempt < retries:
                time.sleep(backoff * (attempt + 1))
                continue
            break
    raise FetchError(f"{url.split('?')[0]}: {last}")
