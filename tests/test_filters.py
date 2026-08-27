import pytest

from tracehep.filters import filter_event, filter_jets, filter_tracks, filter_vertex_event
from tracehep.models import Jet, Track, Vertex, VertexEvent


def test_filter_jets_pt_and_eta():
    jets = [
        Jet(pt=20, eta=1.0, phi=0.0),
        Jet(pt=80, eta=-1.0, phi=0.0),
        Jet(pt=150, eta=3.5, phi=0.0),
    ]
    out = filter_jets(jets, pt_min=50, eta_min=-2.5, eta_max=2.5)
    assert [j.pt for j in out] == [80]


def test_filter_jets_btag_only():
    jets = [Jet(pt=50, eta=0, phi=0, btag=False), Jet(pt=50, eta=0, phi=0, btag=True)]
    out = filter_jets(jets, btag_only=True)
    assert len(out) == 1 and out[0].btag


def test_filter_tracks_pt_and_eta():
    tracks = [
        Track(pt=0.5, eta=0.1, phi=0.0),
        Track(pt=5.0, eta=0.1, phi=0.0),
        Track(pt=5.0, eta=3.0, phi=0.0),
    ]
    out = filter_tracks(tracks, pt_min=1.0, eta_max=2.5)
    assert len(out) == 1 and out[0].pt == 5.0 and out[0].eta == 0.1


def test_filter_event_leaves_other_collections_untouched(sample_event):
    filtered = filter_event(sample_event, jet_pt_min=1000)  # cuts every jet
    assert filtered.jets == []
    assert filtered.muons == sample_event.muons
    assert filtered.electrons == sample_event.electrons
    assert filtered.photons == sample_event.photons
    assert filtered.met == sample_event.met
    # original untouched
    assert sample_event.jets != []


def test_filter_vertex_event_remaps_track_indices():
    tracks = [
        Track(pt=0.5, eta=0.1, phi=0.0),  # cut by pt
        Track(pt=5.0, eta=0.1, phi=0.0),  # kept -> new index 0
        Track(pt=6.0, eta=0.1, phi=0.0),  # kept -> new index 1
    ]
    vertices = [Vertex(z=0.0, track_indices=[0, 1, 2])]
    ve = VertexEvent(vertices=vertices, tracks=tracks)

    out = filter_vertex_event(ve, track_pt_min=1.0)
    assert len(out.tracks) == 2
    assert out.vertices[0].track_indices == [0, 1]
    assert [out.tracks[i].pt for i in out.vertices[0].track_indices] == [5.0, 6.0]
    # original untouched
    assert len(ve.tracks) == 3


def test_filter_vertex_event_keeps_vertex_even_if_all_tracks_cut():
    tracks = [Track(pt=0.5, eta=0.1, phi=0.0)]
    vertices = [Vertex(z=0.0, track_indices=[0])]
    ve = VertexEvent(vertices=vertices, tracks=tracks)

    out = filter_vertex_event(ve, track_pt_min=1.0)
    assert len(out.vertices) == 1
    assert out.vertices[0].track_indices == []
