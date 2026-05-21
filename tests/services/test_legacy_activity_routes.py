from fastapi.testclient import TestClient

from app.backend.main import app


def test_legacy_stallen_page_redirects_to_activities():
    client = TestClient(app)

    response = client.get("/stallen.html", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "/aktiviteter.html"
    assert response.headers["cache-control"] == "no-store"


def test_legacy_stallen_slug_redirects_to_activities():
    client = TestClient(app)

    response = client.get("/stallen", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "/aktiviteter.html"
    assert response.headers["cache-control"] == "no-store"


def test_development_static_frontend_files_are_not_cached():
    client = TestClient(app)

    html_response = client.get("/aktiviteter.html")
    js_response = client.get("/js/common.js")
    css_response = client.get("/css/styles.css")

    assert html_response.headers["cache-control"] == "no-store"
    assert js_response.headers["cache-control"] == "no-store"
    assert css_response.headers["cache-control"] == "no-store"
