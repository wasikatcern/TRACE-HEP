import pytest

flask = pytest.importorskip("flask", reason="tracehep[gui] (flask) not installed")

from tracehep.webapp import create_app


@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    return app.test_client()


def test_index_serves_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"TRACE Live Viewer" in r.data
    assert b"<script>" in r.data


def test_render_missing_file_returns_400_not_500(client):
    r = client.post("/api/render", json={
        "path": "/definitely/not/a/real/file.root", "loader": "delphes",
        "display": "polar", "event_index": "0",
    })
    assert r.status_code == 400
    body = r.get_json()
    assert body["ok"] is False
    assert "error" in body


def test_render_rejects_unknown_loader(client):
    r = client.post("/api/render", json={
        "path": "whatever.root", "loader": "not_a_real_loader",
        "display": "polar", "event_index": "0",
    })
    assert r.status_code == 400
    assert "unknown loader" in r.get_json()["error"]


def test_render_rejects_invalid_display_for_loader(client, monkeypatch):
    # patch the delphes loader so we don't need a real file, then request a
    # vertex-only display name on an event-level loader
    from tracehep.models import Event

    def fake_load_event(path, index, **kwargs):
        return Event()

    import tracehep.io.delphes as delphes_mod
    monkeypatch.setattr(delphes_mod, "load_event", fake_load_event)

    r = client.post("/api/render", json={
        "path": "whatever.root", "loader": "delphes",
        "display": "vertices_plain", "event_index": "0",
    })
    assert r.status_code == 400
    assert "not valid for an event-level loader" in r.get_json()["error"]


def test_render_polar_with_stubbed_delphes_loader(client, monkeypatch):
    from tracehep.models import Event, Jet

    def fake_load_event(path, index, **kwargs):
        return Event(jets=[Jet(pt=50, eta=0.1, phi=0.2)], event_number=index)

    import tracehep.io.delphes as delphes_mod
    monkeypatch.setattr(delphes_mod, "load_event", fake_load_event)

    r = client.post("/api/render", json={
        "path": "whatever.root", "loader": "delphes", "display": "polar",
        "event_index": "3", "show_tracks": False,
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["kind"] == "image"
    assert body["data"].startswith("data:image/png;base64,")


def test_render_3d_returns_html_kind(client, monkeypatch):
    from tracehep.models import Event

    def fake_load_event(path, index, **kwargs):
        return Event()

    import tracehep.io.delphes as delphes_mod
    monkeypatch.setattr(delphes_mod, "load_event", fake_load_event)

    r = client.post("/api/render", json={
        "path": "whatever.root", "loader": "delphes", "display": "3d",
        "event_index": "0",
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["kind"] == "html"
    assert "<div" in body["data"]


def test_render_manual_event_needs_no_path_or_event_index(client):
    r = client.post("/api/render", json={
        "loader": "manual", "display": "polar",
        "manual_jets": [{"pt": 120, "eta": 0.5, "phi": 1.0, "btag": True}],
        "manual_muons": [{"pt": 40, "eta": 0.2, "phi": 2.5}],
        "manual_electrons": [], "manual_photons": [{"pt": 20, "eta": -0.5, "phi": 0.3}],
        "manual_met_pt": "80", "manual_met_phi": "1.1",
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["kind"] == "image"


def test_render_manual_event_with_no_objects_still_renders(client):
    r = client.post("/api/render", json={"loader": "manual", "display": "polar"})
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_make_manual_event_builds_expected_objects():
    from tracehep.webapp import _make_manual_event

    event = _make_manual_event({
        "manual_jets": [{"pt": 120, "eta": 0.5, "phi": 1.0, "btag": True},
                         {"pt": 60, "eta": -1.0, "phi": -2.0}],
        "manual_muons": [{"pt": 40, "eta": 0.2, "phi": 2.5}],
        "manual_electrons": [],
        "manual_photons": [{"pt": 20, "eta": -0.5, "phi": 0.3}],
        "manual_met_pt": "80", "manual_met_phi": "1.1",
    })
    assert len(event.jets) == 2
    assert event.jets[0].btag is True
    assert event.jets[1].btag is False
    assert len(event.muons) == 1 and event.muons[0].flavor == "muon"
    assert len(event.electrons) == 0
    assert len(event.photons) == 1
    assert event.met.pt == 80.0 and event.met.phi == 1.1


def test_make_manual_event_no_met_when_pt_blank():
    from tracehep.webapp import _make_manual_event

    event = _make_manual_event({})
    assert event.met is None
    assert event.jets == []


def test_find_available_port_returns_requested_port_when_free():
    import socket
    from tracehep.webapp import _find_available_port

    # bind and release immediately to get a genuinely free ephemeral port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    free_port = s.getsockname()[1]
    s.close()

    assert _find_available_port("127.0.0.1", free_port) == free_port


def test_find_available_port_skips_busy_port():
    import socket
    from tracehep.webapp import _find_available_port

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    busy_port = blocker.getsockname()[1]
    try:
        found = _find_available_port("127.0.0.1", busy_port)
        assert found != busy_port
        assert found > busy_port
    finally:
        blocker.close()
