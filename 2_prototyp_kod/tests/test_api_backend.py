"""Aplikacja (app/main.py): routery Sprintu 2, statyczny frontend, wycofane endpointy Sprintu 1."""


def test_statyczny_index(client):
    r = client.get("/")
    assert r.status_code == 200 and "AED" in r.text


def test_routery_sprintu_2_zamontowane(client):
    from app.main import app
    sciezki = {getattr(r, "path", "") for r in app.routes}
    for prefiks in ("/api/admin/konta", "/api/partnerzy/{instytucja_id}", "/api/admin/wykazy/{typ}/przebuduj"):
        assert prefiks in sciezki
    assert any(s.startswith("/api/1.4") for s in sciezki)
    assert any(s.startswith("/api/mapa") for s in sciezki)
    assert any(s.startswith("/api/asystent") for s in sciezki)
    assert client.get("/api/admin/konta").status_code == 200


def test_stare_endpointy_v1_wycofane(client):
    assert client.get("/api/v1/aed").status_code == 404
    assert client.post("/api/v1/dysponent/walidacja").status_code in (404, 405)
