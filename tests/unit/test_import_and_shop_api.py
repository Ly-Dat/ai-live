import hashlib, hmac, os, subprocess, sys, json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
from utils import tiktok_shop_api as api  # noqa: E402


def test_signature_matches_manual_hmac():
    q = {"app_key": "k", "timestamp": "1", "sign": "x", "access_token": "t", "shop_cipher": "c"}
    expected = hmac.new(b"s", b"s/p/prodapp_keykshop_cipherctimestamp1{\"a\":1}s", hashlib.sha256).hexdigest()
    assert api.sign_request("/p/prod", q, '{"a":1}', "s") == expected


def fake_http(method, url, headers, body):
    if "products/search" in url:
        assert headers["x-tts-access-token"] == "t"
        return {"code": 0, "data": {"products": [{"id": "1", "title": "Áo", "status": "ACTIVATE", "skus": [
            {"price": {"sale_price": "129000", "currency": "VND"}, "sales_attributes": [{"value_name": "Đen"}]}]}]}}
    if url.endswith("shops") or "/shops?" in url:
        return {"code": 0, "data": {"shops": [{"cipher": "CIPH"}]}}
    return {"code": 0, "data": {}}


def test_client_lists_and_maps_products():
    c = api.TikTokShopClient({"app_key": "k", "app_secret": "s", "access_token": "t"}, fake_http, lambda: 1)
    assert c.get_shop_cipher() == "CIPH"
    entry = api.to_catalog_entry(list(c.iter_products())[0])
    assert entry["price"] == "129.000đ" and entry["sizes_colors"] == "Đen" and entry["active"]


def test_api_error_raises():
    c = api.TikTokShopClient({"app_key": "k", "app_secret": "s", "access_token": "t"},
                             lambda *a: {"code": 36004, "message": "bad token"}, lambda: 1)
    try:
        c.get_shop_cipher()
    except RuntimeError as e:
        assert "bad token" in str(e)
    else:
        raise AssertionError("expected RuntimeError")


def test_importer_csv_roundtrip(tmp_path):
    sheet = tmp_path / "s.csv"
    sheet.write_text("Tên sản phẩm,Giá bán,SKU,Trạng thái\nQuạt mini,89.000đ,Q1,hết hàng\n", encoding="utf-8")
    out = tmp_path / "p.json"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "import_products.py"), str(sheet), "--products", str(out)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    p = json.load(open(out, encoding="utf-8"))["products"][0]
    assert p["name"] == "Quạt mini" and p["active"] is False and p["id"] == "Q1"
