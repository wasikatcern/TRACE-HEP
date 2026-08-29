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


uproot = pytest.importorskip("uproot", reason="tracehep[delphes] (uproot) not installed")


def _write_fake_root(tmp_path, tree_name, branch_name):
    import numpy as np
    path = str(tmp_path / "fake.root")
    with uproot.recreate(path) as f:
        f[tree_name] = {branch_name: np.array([1.0, 2.0, 3.0])}
    return path


def test_detect_vertex_format_recognizes_physlite_signature(tmp_path):
    from tracehep.webapp import _detect_vertex_format

    path = _write_fake_root(tmp_path, "CollectionTree", "PrimaryVerticesAuxDyn.x")
    fmt, tree = _detect_vertex_format(path)
    assert fmt == "physlite"
    assert tree == "CollectionTree"


def test_detect_vertex_format_recognizes_calotiming_signature(tmp_path):
    from tracehep.webapp import _detect_vertex_format

    path = _write_fake_root(tmp_path, "ntuple", "RecoVtx_z")
    fmt, tree = _detect_vertex_format(path)
    assert fmt == "calotiming"
    assert tree == "ntuple"


def test_detect_vertex_format_raises_clear_error_for_unknown_file(tmp_path):
    from tracehep.webapp import _detect_vertex_format

    path = _write_fake_root(tmp_path, "Events", "Jet_pt")  # a Delphes-ish, non-vertex file
    with pytest.raises(ValueError, match="Could not find a recognized vertex format"):
        _detect_vertex_format(path)


def test_render_vertex_loader_dispatches_to_calotiming(client, monkeypatch, tmp_path):
    from tracehep.models import Vertex, VertexEvent

    path = _write_fake_root(tmp_path, "ntuple", "RecoVtx_z")

    def fake_load_vertex_event(p, idx, **kwargs):
        return VertexEvent(vertices=[Vertex(z=1.0, is_hs=True)], tracks=[])

    import tracehep.io.calotiming as calotiming_mod
    monkeypatch.setattr(calotiming_mod, "load_vertex_event", fake_load_vertex_event)

    r = client.post("/api/render", json={
        "loader": "vertex", "display": "vertices_plain", "path": path,
        "event_index": "0", "vertex_index": "0", "tree_name": "",
    })
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_parse_id_list_handles_commas_whitespace_and_newlines():
    from tracehep.webapp import _parse_id_list

    assert _parse_id_list("12, 45\n88   3") == [12, 45, 88, 3]
    assert _parse_id_list("") == []
    assert _parse_id_list(None) == []


def test_parse_custom_categories_accepts_colon_or_comma():
    from tracehep.webapp import _parse_custom_categories

    text = "1023: anomalous\n1044, anomalous\n\nnot-a-line-without-separator"
    assert _parse_custom_categories(text) == {1023: "anomalous", 1044: "anomalous"}


def test_build_gallery_html_compare_mode(monkeypatch):
    from tracehep.models import Event, Jet
    import tracehep.io.delphes as delphes_mod

    def fake_load_event(path, index, **kwargs):
        return Event(jets=[Jet(pt=50 + index, eta=0.1, phi=0.2)], event_number=index)

    monkeypatch.setattr(delphes_mod, "load_event", fake_load_event)

    from tracehep.webapp import _build_gallery_html

    html = _build_gallery_html({
        "loader": "delphes", "path": "whatever.root", "display": "polar",
        "category_mode": "compare", "name_a": "clf1", "name_b": "clf2",
        "a_pass": "1, 2", "a_fail": "3, 4",
        "b_pass": "1, 4", "b_fail": "2, 3",
    })
    assert "TRACE Failure-Mode Review" in html
    assert html.count("data:image/png;base64,") == 4
    assert "both_pass" in html
    assert "both_fail" in html
    assert "clf1_pass_clf2_fail" in html
    assert "clf1_fail_clf2_pass" in html


def test_build_gallery_html_custom_mode(monkeypatch):
    from tracehep.models import Event
    import tracehep.io.delphes as delphes_mod

    monkeypatch.setattr(delphes_mod, "load_event", lambda path, index, **kw: Event(event_number=index))

    from tracehep.webapp import _build_gallery_html

    html = _build_gallery_html({
        "loader": "delphes", "path": "whatever.root", "display": "beam2d",
        "category_mode": "custom", "custom_categories": "10: anomalous\n11: anomalous",
        "gallery_title": "Anomaly review",
    })
    assert "Anomaly review" in html
    assert html.count("data:image/png;base64,") == 2
    assert "anomalous" in html


def test_build_gallery_html_no_events_raises():
    from tracehep.webapp import _build_gallery_html

    with pytest.raises(ValueError, match="No event ids"):
        _build_gallery_html({"loader": "delphes", "path": "x.root", "display": "polar",
                              "category_mode": "custom", "custom_categories": ""})


def test_build_gallery_html_too_many_events_raises(monkeypatch):
    import tracehep.webapp as webapp_mod
    monkeypatch.setattr(webapp_mod, "_MAX_GALLERY_EVENTS", 2)

    from tracehep.webapp import _build_gallery_html

    with pytest.raises(ValueError, match="safety cap"):
        _build_gallery_html({"loader": "delphes", "path": "x.root", "display": "polar",
                              "category_mode": "custom",
                              "custom_categories": "1: a\n2: a\n3: a"})


def test_api_gallery_route_returns_html(client, monkeypatch):
    from tracehep.models import Event
    import tracehep.io.delphes as delphes_mod

    monkeypatch.setattr(delphes_mod, "load_event", lambda path, index, **kw: Event(event_number=index))

    r = client.post("/api/gallery", json={
        "loader": "delphes", "path": "whatever.root", "display": "polar",
        "category_mode": "custom", "custom_categories": "1: a\n2: b",
    })
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert "<html" in body["html"]


def test_api_gallery_route_reports_error_as_400(client):
    r = client.post("/api/gallery", json={
        "loader": "delphes", "path": "whatever.root", "display": "polar",
        "category_mode": "custom", "custom_categories": "",
    })
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_render_vertex_loader_dispatches_to_physlite(client, monkeypatch, tmp_path):
    from tracehep.models import Vertex, VertexEvent

    path = _write_fake_root(tmp_path, "CollectionTree", "PrimaryVerticesAuxDyn.x")

    def fake_load_vertex_event(p, idx, **kwargs):
        return VertexEvent(vertices=[Vertex(z=1.0, is_hs=True)], tracks=[])

    import tracehep.io.atlas_physlite as physlite_mod
    monkeypatch.setattr(physlite_mod, "load_vertex_event", fake_load_vertex_event)

    r = client.post("/api/render", json={
        "loader": "vertex", "display": "vertices_plain", "path": path,
        "event_index": "0", "vertex_index": "0", "tree_name": "",
    })
    assert r.status_code == 200
    assert r.get_json()["ok"] is True
