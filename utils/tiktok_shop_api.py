"""
Minimal TikTok Shop Partner API client - reads the seller's own products so the catalog can be filled automatically.

Requires an APPROVED app in TikTok Shop Partner Center and an authorized shop:
    app_key, app_secret, access_token, refresh_token (+ shop_cipher, which this client can look up).
Credentials live in `tiktok_shop_credentials.json` (git-ignored) or the env vars TTS_APP_KEY, TTS_APP_SECRET,
TTS_ACCESS_TOKEN, TTS_REFRESH_TOKEN, TTS_SHOP_CIPHER. Never put them in config.json.

Signing (per TikTok Shop docs / open-source SDKs): HMAC-SHA256 over
    app_secret + path + sorted(query params except sign/access_token){key}{value}... + body + app_secret
with the token sent in the `x-tts-access-token` header. Base URL https://open-api.tiktokglobalshop.com .

NOTE: written from the public docs/SDKs and unit-tested with fake responses only; it has not been run against a
real shop. If TikTok bumped an API version, change PRODUCT_VERSION / AUTH_VERSION below.
"""
import hashlib
import hmac
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, Iterator, List, Optional

BASE_URL = "https://open-api.tiktokglobalshop.com"
AUTH_URL = "https://auth.tiktok-shops.com"
PRODUCT_VERSION = "202309"
AUTH_VERSION = "202309"
CREDENTIALS_FILE = "tiktok_shop_credentials.json"


def load_credentials(path: str = CREDENTIALS_FILE) -> Dict[str, str]:
    creds = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            creds = json.load(f)
    env_map = {"app_key": "TTS_APP_KEY", "app_secret": "TTS_APP_SECRET", "access_token": "TTS_ACCESS_TOKEN",
               "refresh_token": "TTS_REFRESH_TOKEN", "shop_cipher": "TTS_SHOP_CIPHER"}
    for k, env in env_map.items():
        if os.environ.get(env):
            creds[k] = os.environ[env]
    return creds


def sign_request(path: str, query: Dict[str, str], body: str, app_secret: str) -> str:
    """HMAC-SHA256 signature as described in the module docstring."""
    excluded = {"sign", "access_token"}
    parts = "".join(f"{k}{query[k]}" for k in sorted(query) if k not in excluded)
    to_sign = f"{app_secret}{path}{parts}{body}{app_secret}"
    return hmac.new(app_secret.encode(), to_sign.encode(), hashlib.sha256).hexdigest()


def _default_http(method: str, url: str, headers: Dict[str, str], body: Optional[bytes]) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


class TikTokShopClient:
    def __init__(self, creds: Dict[str, str], http: Callable = _default_http, clock: Callable[[], float] = time.time):
        for k in ("app_key", "app_secret", "access_token"):
            if not creds.get(k):
                raise ValueError(f"Missing credential: {k}")
        self.creds = creds
        self._http = http
        self._clock = clock

    # ---------------------------------------------------------------- low level
    def _call(self, method: str, path: str, query: Optional[Dict] = None, body: Optional[Dict] = None,
              need_shop: bool = True) -> dict:
        q = {k: str(v) for k, v in (query or {}).items()}
        q["app_key"] = self.creds["app_key"]
        q["timestamp"] = str(int(self._clock()))
        if need_shop and self.creds.get("shop_cipher"):
            q["shop_cipher"] = self.creds["shop_cipher"]
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False) if body is not None else ""
        q["sign"] = sign_request(path, q, body_str, self.creds["app_secret"])
        url = f"{BASE_URL}{path}?{urllib.parse.urlencode(q)}"
        headers = {"x-tts-access-token": self.creds["access_token"], "Content-Type": "application/json"}
        out = self._http(method, url, headers, body_str.encode("utf-8") if body_str else None)
        if out.get("code") not in (0, "0", None):
            raise RuntimeError(f"TikTok Shop API error {out.get('code')}: {out.get('message')}")
        return out.get("data") or {}

    # ---------------------------------------------------------------- auth
    def refresh_access_token(self) -> Dict[str, str]:
        """Exchange the refresh token for a new access token (tokens expire); returns and stores the new pair."""
        q = urllib.parse.urlencode({"app_key": self.creds["app_key"], "app_secret": self.creds["app_secret"],
                                    "refresh_token": self.creds["refresh_token"], "grant_type": "refresh_token"})
        out = self._http("GET", f"{AUTH_URL}/api/v2/token/refresh?{q}", {}, None)
        if out.get("code") not in (0, "0"):
            raise RuntimeError(f"Token refresh failed: {out.get('message')}")
        data = out["data"]
        self.creds["access_token"] = data["access_token"]
        self.creds["refresh_token"] = data.get("refresh_token", self.creds["refresh_token"])
        return {"access_token": self.creds["access_token"], "refresh_token": self.creds["refresh_token"]}

    def get_shop_cipher(self) -> str:
        """Look up the authorized shop's cipher (needed on every shop-level call)."""
        data = self._call("GET", f"/authorization/{AUTH_VERSION}/shops", need_shop=False)
        shops = data.get("shops") or []
        if not shops:
            raise RuntimeError("No authorized shops found for this token")
        self.creds["shop_cipher"] = shops[0]["cipher"]
        return self.creds["shop_cipher"]

    # ---------------------------------------------------------------- products
    def iter_products(self, status: str = "ACTIVATE", page_size: int = 50) -> Iterator[dict]:
        """Yield the seller's products (summary objects), following pagination."""
        token = ""
        while True:
            query = {"page_size": page_size}
            if token:
                query["page_token"] = token
            data = self._call("POST", f"/product/{PRODUCT_VERSION}/products/search", query, {"status": status})
            for p in data.get("products", []):
                yield p
            token = data.get("next_page_token") or ""
            if not token:
                return

    def get_product(self, product_id: str) -> dict:
        return self._call("GET", f"/product/{PRODUCT_VERSION}/products/{product_id}")


# -------------------------------------------------------------------- mapping to the catalog
def _strip_html(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _fmt_price(price: dict) -> str:
    amount = price.get("sale_price") or price.get("tax_exclusive_price") or ""
    if not amount:
        return ""
    cur = price.get("currency", "")
    try:
        n = float(amount)
        amount = f"{int(n):,}".replace(",", ".") if n == int(n) else str(n)
    except ValueError:
        pass
    return f"{amount}{'đ' if cur == 'VND' else ' ' + cur if cur else ''}"


def to_catalog_entry(p: dict) -> dict:
    """Map a TikTok Shop product (summary or detail) to a catalog dict used by import/upsert."""
    skus = p.get("skus") or []
    prices = [_fmt_price(s.get("price", {})) for s in skus if s.get("price")]
    prices = [x for x in prices if x]
    options = []
    for s in skus:
        for attr in s.get("sales_attributes", []):
            v = attr.get("value_name")
            if v and v not in options:
                options.append(v)
    return {
        "id": str(p.get("id", "")),
        "name": p.get("title", "").strip(),
        "price": prices[0] if prices else "",
        "description": _strip_html(p.get("description", "")),
        "sizes_colors": ", ".join(options),
        "active": p.get("status", "ACTIVATE") == "ACTIVATE",
    }
