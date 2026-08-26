from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.5.0"


def test_new_purchase_page():
    response = client.get("/purchases/new")
    assert response.status_code == 200
    assert "New Purchase" in response.text


def test_storage_page():
    response = client.get("/storage")
    assert response.status_code == 200
    assert "Storage Locations" in response.text


def test_whatnot_shows_page():
    response = client.get("/whatnot")
    assert response.status_code == 200
    assert "Whatnot Shows" in response.text


def test_new_whatnot_show_page():
    response = client.get("/whatnot/shows/new")
    assert response.status_code == 200
    assert "New Whatnot Show" in response.text


def test_sales_page():
    response = client.get("/sales")
    assert response.status_code == 200
    assert "Sales" in response.text


def test_ebay_page():
    response = client.get("/ebay")
    assert response.status_code == 200
    assert "eBay" in response.text


def test_ebay_queue_page():
    response = client.get("/ebay/queue")
    assert response.status_code == 200
    assert "eBay Queue" in response.text
