"""Format-agnostic data model every drawing function in tracehep accepts.

Nothing in this module knows about ROOT, uproot, or any specific ntuple's
branch names -- that translation lives in :mod:`tracehep.io`. Build an
:class:`Event` or :class:`VertexEvent` by hand from your own analysis
objects and every plotting function in this package works unchanged.

Developed by Wasikul Islam, PhD.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Jet:
    pt: float
    eta: float
    phi: float
    mass: float = 0.0
    btag: bool = False
    is_hs: Optional[bool] = None
    """Truth-level hard-scatter match for this jet (e.g. from a
    truthHSJet_idx-style branch). None if truth information isn't
    available (e.g. on real data)."""


@dataclass
class Track:
    pt: float
    eta: float
    phi: float
    charge: int = 0
    d0: float = 0.0
    """Transverse impact parameter [mm], the closest-approach distance to
    the beam axis in the plane perpendicular to it."""
    z0: float = 0.0
    """Longitudinal impact parameter [mm] (offset along the beam axis)."""
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    """Real (x, y, z) production point [mm], used by the 3D display."""
    time: Optional[float] = None
    """Reconstructed track time [ps], if the ntuple provides per-track
    timing (e.g. an HGTD-style "4D tracking" ntuple). Used by the
    time-coloured vertex display."""
    is_hs: Optional[bool] = None
    """Truth-level hard-scatter match for this individual track (not the
    same as the owning vertex's is_hs -- a reconstructed "HS" vertex can,
    and often does, include some truth-PU tracks). None if truth
    information isn't available (e.g. on real data). When set, vertex
    displays colour this track by it instead of by the owning vertex's
    flag."""


@dataclass
class Lepton:
    pt: float
    eta: float
    phi: float
    flavor: str = "muon"  # "muon" or "electron"


@dataclass
class Photon:
    pt: float
    eta: float
    phi: float


@dataclass
class MissingET:
    pt: float
    phi: float
    eta: float = 0.0


@dataclass
class Event:
    """Every reconstructed object for one hard-scatter interaction."""

    jets: List[Jet] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    muons: List[Lepton] = field(default_factory=list)
    electrons: List[Lepton] = field(default_factory=list)
    photons: List[Photon] = field(default_factory=list)
    met: Optional[MissingET] = None
    run: Optional[int] = None
    event_number: Optional[int] = None
    label: str = ""
    """Free-text sample/event label, used in default plot titles."""

    @property
    def bjets(self) -> List[Jet]:
        return [j for j in self.jets if j.btag]

    @property
    def light_jets(self) -> List[Jet]:
        return [j for j in self.jets if not j.btag]

    @property
    def leptons(self) -> List[Lepton]:
        return self.muons + self.electrons


@dataclass
class Vertex:
    z: float
    x: float = 0.0
    y: float = 0.0
    sum_pt2: float = 0.0
    is_hs: bool = False
    is_pu: bool = False
    time: Optional[float] = None
    """Reconstructed vertex time [ps], if the ntuple provides per-track/
    per-vertex timing (e.g. an HGTD-style "4D tracking" ntuple)."""
    track_indices: List[int] = field(default_factory=list)
    """Indices into the parent VertexEvent.tracks list for tracks fit to
    this vertex."""


@dataclass
class TruthVertex:
    z: float
    x: float = 0.0
    y: float = 0.0
    is_hs: bool = False


@dataclass
class VertexEvent:
    """One pileup scenario: many reconstructed vertices sharing a single
    track collection. Distinct from :class:`Event`, which represents one
    physics-object collection for a single hard-scatter interaction."""

    vertices: List[Vertex] = field(default_factory=list)
    tracks: List[Track] = field(default_factory=list)
    truth_vertices: List[TruthVertex] = field(default_factory=list)
    mu: Optional[float] = None
    """<mu>, average interactions per bunch crossing, if available."""
    label: str = ""
