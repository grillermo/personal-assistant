import json
import time
from unittest.mock import patch, MagicMock


def _write_fixtures(tmp_path):
    """Write minimal credentials.json and tokens.json to tmp_path."""
    creds = {"app_id": "APP1", "secret_key": "SECRET1"}
    tokens = {
        "access_token": "AT-initial",
        "refresh_token": "RT-initial",
        "expires_in": 21600,
    }
    (tmp_path / "credentials.json").write_text(json.dumps(creds))
    (tmp_path / "tokens.json").write_text(json.dumps(tokens))
    return str(tmp_path / "tokens.json"), str(tmp_path / "credentials.json")


def test_get_returns_json_on_200(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"id": 42}
    mock_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", return_value=mock_resp):
        result = client.get("https://api.mercadolibre.com/users/me")

    assert result == {"id": 42}


def test_get_retries_on_429(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    rate_limited = MagicMock()
    rate_limited.status_code = 429
    rate_limited.headers = {"Retry-After": "1"}

    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"ok": True}
    ok.raise_for_status = MagicMock()

    with patch("extract.requests.get", side_effect=[rate_limited, ok]):
        with patch("extract.time.sleep"):
            result = client.get("https://example.com")

    assert result == {"ok": True}


def test_get_refreshes_on_401(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    unauthorized = MagicMock()
    unauthorized.status_code = 401

    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {"refreshed": True}
    ok.raise_for_status = MagicMock()

    refresh_resp = MagicMock()
    refresh_resp.json.return_value = {
        "access_token": "AT-new",
        "refresh_token": "RT-new",
        "expires_in": 21600,
    }
    refresh_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", side_effect=[unauthorized, ok]):
        with patch("extract.requests.post", return_value=refresh_resp):
            result = client.get("https://example.com")

    assert result == {"refreshed": True}


def test_refresh_at_computed_from_expires_in(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient

    before = time.time()
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)
    after = time.time()

    expected_min = before + 21600 - 300
    expected_max = after + 21600 - 300
    assert expected_min <= client._refresh_at <= expected_max


def test_get_all_orders_paginates(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    page1 = MagicMock()
    page1.status_code = 200
    page1.json.return_value = {
        "results": [{"id": f"order_{i}"} for i in range(50)],
        "paging": {"total": 75, "offset": 0, "limit": 50},
    }
    page1.raise_for_status = MagicMock()

    page2 = MagicMock()
    page2.status_code = 200
    page2.json.return_value = {
        "results": [{"id": f"order_{i}"} for i in range(50, 75)],
        "paging": {"total": 75, "offset": 50, "limit": 50},
    }
    page2.raise_for_status = MagicMock()

    with patch("extract.requests.get", side_effect=[page1, page2]):
        with patch("extract.time.sleep"):
            orders = client.get_all_orders(user_id=123456)

    assert len(orders) == 75
    assert orders[0]["id"] == "order_0"
    assert orders[74]["id"] == "order_74"


def test_get_all_orders_stops_on_empty_results(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    empty_resp = MagicMock()
    empty_resp.status_code = 200
    empty_resp.json.return_value = {
        "results": [],
        "paging": {"total": 0},
    }
    empty_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", return_value=empty_resp):
        orders = client.get_all_orders(user_id=123456)

    assert orders == []


def test_collect_item_ids_splits_by_title_presence():
    from extract import collect_item_ids
    orders = [
        {
            "order_items": [
                {"item": {"id": "MLA1", "title": "Laptop"}},
                {"item": {"id": "MLA2", "title": ""}},
                {"item": {"id": "MLA3"}},
            ]
        }
    ]
    all_ids, has_title = collect_item_ids(orders)
    assert set(all_ids) == {"MLA1", "MLA2", "MLA3"}
    assert has_title == {"MLA1"}


def test_hydrate_items_filters_non_200(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    batch_resp = MagicMock()
    batch_resp.status_code = 200
    batch_resp.json.return_value = [
        {"code": 200, "body": {"id": "MLA1", "title": "Good Item", "category_id": "MLA1055"}},
        {"code": 404, "body": {"id": "MLA2", "message": "Item not found"}},
    ]
    batch_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", return_value=batch_resp):
        result = client.hydrate_items(["MLA1", "MLA2"])

    assert "MLA1" in result
    assert result["MLA1"]["title"] == "Good Item"
    assert "MLA2" not in result


def test_hydrate_items_deduplicates_ids(tmp_path):
    tokens_path, creds_path = _write_fixtures(tmp_path)
    from extract import MeliClient
    client = MeliClient(tokens_path=tokens_path, creds_path=creds_path)

    batch_resp = MagicMock()
    batch_resp.status_code = 200
    batch_resp.json.return_value = [
        {"code": 200, "body": {"id": "MLA1", "title": "Item", "category_id": "CAT1"}},
    ]
    batch_resp.raise_for_status = MagicMock()

    with patch("extract.requests.get", return_value=batch_resp) as mock_get:
        client.hydrate_items(["MLA1", "MLA1", "MLA1"])

    # Only one batch call for one unique ID
    assert mock_get.call_count == 1


def test_extract_order_rows_single_item():
    from extract import extract_order_rows
    order = {
        "id": "ORD1",
        "date_created": "2024-01-15T10:00:00.000Z",
        "status": "paid",
        "total_amount": 299.0,
        "currency_id": "MXN",
        "order_items": [
            {"item": {"id": "MLA1", "title": "Laptop"}, "quantity": 1, "unit_price": 299.0}
        ],
    }
    rows = extract_order_rows(order, {})
    assert len(rows) == 1
    assert rows[0]["order_id"] == "ORD1"
    assert rows[0]["item_title"] == "Laptop"
    assert rows[0]["item_quantity"] == 1
    assert rows[0]["item_unit_price"] == 299.0
    assert rows[0]["order_total_amount"] == 299.0
    assert rows[0]["currency"] == "MXN"


def test_extract_order_rows_multi_item_shares_order_total():
    from extract import extract_order_rows
    order = {
        "id": "ORD2",
        "date_created": "2024-02-01T08:00:00.000Z",
        "status": "paid",
        "total_amount": 500.0,
        "currency_id": "MXN",
        "order_items": [
            {"item": {"id": "MLA1", "title": "Book"}, "quantity": 2, "unit_price": 150.0},
            {"item": {"id": "MLA2"}, "quantity": 1, "unit_price": 200.0},
        ],
    }
    cache = {"MLA2": {"title": "Headphones", "category_id": "ELEC"}}
    rows = extract_order_rows(order, cache)

    assert len(rows) == 2
    assert rows[0]["order_id"] == rows[1]["order_id"] == "ORD2"
    assert rows[0]["order_total_amount"] == rows[1]["order_total_amount"] == 500.0
    assert rows[0]["item_title"] == "Book"
    assert rows[1]["item_title"] == "Headphones"
    assert rows[1]["item_category"] == "ELEC"


def test_extract_order_rows_no_items_produces_placeholder():
    from extract import extract_order_rows
    order = {
        "id": "ORD3",
        "date_created": "2024-03-01T00:00:00.000Z",
        "status": "cancelled",
        "total_amount": 0,
        "currency_id": "MXN",
        "order_items": [],
    }
    rows = extract_order_rows(order, {})
    assert len(rows) == 1
    assert rows[0]["item_title"] == "N/A"


def test_extract_order_rows_falls_back_to_cache_for_missing_title():
    from extract import extract_order_rows
    order = {
        "id": "ORD4",
        "date_created": "2024-04-01T00:00:00.000Z",
        "status": "paid",
        "total_amount": 100.0,
        "currency_id": "MXN",
        "order_items": [
            {"item": {"id": "MLA9"}, "quantity": 1, "unit_price": 100.0},
        ],
    }
    cache = {"MLA9": {"title": "Widget", "category_id": "TOOLS"}}
    rows = extract_order_rows(order, cache)
    assert rows[0]["item_title"] == "Widget"
    assert rows[0]["item_category"] == "TOOLS"
