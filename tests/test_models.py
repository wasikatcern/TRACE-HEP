from tracehep.models import Event, Jet, VertexEvent, Vertex


def test_event_bjet_split():
    event = Event(jets=[Jet(pt=100, eta=0.1, phi=0.2, btag=True),
                         Jet(pt=50, eta=-0.5, phi=1.0, btag=False)])
    assert len(event.bjets) == 1
    assert len(event.light_jets) == 1
    assert event.bjets[0].pt == 100


def test_event_leptons_property():
    from tracehep.models import Lepton
    event = Event(muons=[Lepton(pt=10, eta=0, phi=0, flavor="muon")],
                  electrons=[Lepton(pt=20, eta=0, phi=0, flavor="electron")])
    assert len(event.leptons) == 2


def test_vertex_event_defaults():
    ve = VertexEvent(vertices=[Vertex(z=1.0, is_hs=True)])
    assert ve.tracks == []
    assert ve.mu is None
    assert ve.vertices[0].is_hs is True
