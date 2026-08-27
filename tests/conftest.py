import matplotlib
matplotlib.use("Agg")

import pytest

from tracehep.models import Event, Jet, Lepton, MissingET, Photon, Track


@pytest.fixture
def sample_event():
    return Event(
        jets=[Jet(pt=180, eta=1.1, phi=0.4), Jet(pt=95, eta=-0.6, phi=2.8, btag=True)],
        tracks=[Track(pt=5.0, eta=0.2, phi=0.1, d0=0.05, x=0.0, y=0.0, z=0.0),
                Track(pt=1.0, eta=-0.3, phi=1.5, d0=73.0, x=180.0, y=0.2, z=74.0)],
        muons=[Lepton(pt=60, eta=0.3, phi=-1.2, flavor="muon")],
        electrons=[Lepton(pt=40, eta=-1.0, phi=2.0, flavor="electron")],
        photons=[Photon(pt=15, eta=0.5, phi=-2.0)],
        met=MissingET(pt=140, phi=1.0),
        label="test-sample",
        event_number=42,
    )
