"""Load the hard-scatter vertex's tracks, and every primary-vertex
position, out of the ATLAS Open Data 2024 **research** release
(DAOD_PHYSLITE format, opendata.cern.ch) via uproot.

PHYSLITE is ATLAS's storage-optimized analysis format: to save space it
thins away most reconstructed tracks not associated with a physics object
(lepton, jet). This was measured against 200 real events before writing
this loader, not assumed: across 2664 pileup vertices, 199/200
hard-scatter vertices kept a real, sizeable track collection, but only
97 pileup vertices (~3.6%) retained *any* tracks at all (1-12 each,
median 0) -- the rest come back with a genuinely empty
``trackParticleLinks`` (persistent key 0, an invalid container
reference). This loader decodes whatever is actually valid for *every*
vertex, hard-scatter or pileup alike -- it does not special-case the
hard-scatter vertex -- so ``Vertex.track_indices`` is simply empty for
the ~96% of pileup vertices the file itself has thinned away, and
non-empty for the rare pileup vertex (and almost every hard-scatter
vertex) PHYSLITE happened to keep something for. In practice this means
:func:`~tracehep.vertices.zr.plot_vertices_zr` on this data shows every
vertex's true position along the beamline, with track fans drawn
wherever the file actually retained tracks -- overwhelmingly the
hard-scatter vertex, occasionally a pileup one too; and
:func:`~tracehep.vertices.zr.plot_vertex_detail` on the hard-scatter
vertex works close to normally.

There is no per-track timing in this public release (that requires an
HGTD-style upgrade-R&D ntuple, not part of any public open-data release
as of this writing), so the ``time_colored`` z-R display style has
nothing to color by here -- use ``style="plain"`` or ``"styled"``.

Track kinematics are derived from the raw xAOD perigee parameters
(``qOverP``, ``theta``) since PHYSLITE stores no direct pt/eta branch;
momenta are in MeV, converted to GeV here as with every other tracehep
loader.

:func:`load_event_jets` reads this event's calibrated analysis jets
separately (PHYSLITE has no ready jet-to-vertex link comparable to
Rpt/ghost-track matching, and no per-jet truth in this release), so every
returned ``Jet.is_hs`` is ``None`` -- pass the result straight to
:func:`~tracehep.vertices.zr.plot_vertex_detail`'s ``jets=`` and it draws
them all in one neutral colour rather than a misleading HS/PU split.

Files are large (1-3 GB+); pass an
``https://opendata.cern.ch/eos/opendata/atlas/rucio/...`` URL directly as
``path`` and uproot streams only the bytes it needs.

Requires the ``delphes`` extra (uproot is shared): ``pip install trace-hep[delphes]``.

Developed by Wasikul Islam, PhD.
"""

import math
from typing import List

from ..models import Jet, Track, Vertex, VertexEvent

__all__ = ["load_vertex_event", "load_event_jets"]

_VXTYPE_HS = 1  # xAOD::VxType::PriVtx (the hard-scatter vertex)
_VXTYPE_PU = 3  # xAOD::VxType::PileUp

_BRANCHES = [
    "PrimaryVerticesAuxDyn.x", "PrimaryVerticesAuxDyn.y", "PrimaryVerticesAuxDyn.z",
    "PrimaryVerticesAuxDyn.vertexType", "PrimaryVerticesAuxDyn.trackParticleLinks",
    "InDetTrackParticlesAuxDyn.d0", "InDetTrackParticlesAuxDyn.z0",
    "InDetTrackParticlesAuxDyn.phi", "InDetTrackParticlesAuxDyn.theta",
    "InDetTrackParticlesAuxDyn.qOverP",
]


def _require_uproot():
    try:
        import uproot  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "tracehep.io.atlas_physlite requires uproot. Install with: pip install trace-hep[delphes]"
        ) from exc
    return uproot


def load_vertex_event(path: str, event_index: int, *, tree_name: str = "CollectionTree",
                       label: str = "") -> VertexEvent:
    """Load one event's primary-vertex positions and hard-scatter tracks
    from a DAOD_PHYSLITE file.

    Parameters
    ----------
    path:
        Path or URL to a DAOD_PHYSLITE ROOT file -- a local file or an
        ``https://opendata.cern.ch/...`` URL (streamed, not downloaded).
    event_index:
        Event (row) index to load.
    label:
        Free-text label stamped onto the returned VertexEvent.

    Returns
    -------
    tracehep.models.VertexEvent -- every retained vertex (hard-scatter and
    pileup) at its real (x, y, z) with is_hs/is_pu set; track_indices is
    non-empty wherever PHYSLITE actually kept tracks for that vertex --
    nearly always for the hard-scatter vertex, rarely (~3.6% of the time,
    measured) for a pileup one (see module docstring).
    """
    uproot = _require_uproot()
    f = uproot.open(path)
    tree = f[tree_name]
    arrs = tree.arrays(_BRANCHES, entry_start=event_index, entry_stop=event_index + 1)
    i = 0

    d0 = arrs["InDetTrackParticlesAuxDyn.d0"][i]
    z0 = arrs["InDetTrackParticlesAuxDyn.z0"][i]
    phi = arrs["InDetTrackParticlesAuxDyn.phi"][i]
    theta = arrs["InDetTrackParticlesAuxDyn.theta"][i]
    qop = arrs["InDetTrackParticlesAuxDyn.qOverP"][i]
    n_tracks = len(d0)

    vtx_x = arrs["PrimaryVerticesAuxDyn.x"][i]
    vtx_y = arrs["PrimaryVerticesAuxDyn.y"][i]
    vtx_z = arrs["PrimaryVerticesAuxDyn.z"][i]
    vtx_type = arrs["PrimaryVerticesAuxDyn.vertexType"][i]
    vtx_links = arrs["PrimaryVerticesAuxDyn.trackParticleLinks"][i]

    hs_x = hs_y = 0.0
    for vt, vx, vy in zip(vtx_type, vtx_x, vtx_y):
        if int(vt) == _VXTYPE_HS:
            hs_x, hs_y = float(vx), float(vy)
            break

    tracks: List[Track] = []
    for ti in range(n_tracks):
        p = abs(1.0 / float(qop[ti])) if qop[ti] != 0 else 0.0
        pt = p * math.sin(float(theta[ti])) / 1000.0  # MeV -> GeV
        eta = -math.log(math.tan(float(theta[ti]) / 2)) if theta[ti] not in (0, math.pi) else 0.0
        tracks.append(Track(
            pt=pt, eta=eta, phi=float(phi[ti]), d0=float(d0[ti]), z0=float(z0[ti]),
            x=hs_x, y=hs_y, z=float(z0[ti]),
        ))

    vertices: List[Vertex] = []
    for vx, vy, vz, vt, links in zip(vtx_x, vtx_y, vtx_z, vtx_type, vtx_links):
        vt = int(vt)
        if vt not in (_VXTYPE_HS, _VXTYPE_PU):
            continue  # skip the dummy placeholder vertex ATLAS always appends
        track_indices = [
            int(link["m_persIndex"]) for link in links
            if int(link["m_persKey"]) != 0 and int(link["m_persIndex"]) < n_tracks
        ]
        sum_pt2 = sum(tracks[idx].pt ** 2 for idx in track_indices)
        vertices.append(Vertex(
            z=float(vz), x=float(vx), y=float(vy), sum_pt2=sum_pt2,
            is_hs=(vt == _VXTYPE_HS), is_pu=(vt == _VXTYPE_PU), track_indices=track_indices,
        ))

    return VertexEvent(vertices=vertices, tracks=tracks, label=label)


def load_event_jets(path: str, event_index: int, *, tree_name: str = "CollectionTree",
                     jet_pt_min: float = 20.0) -> List[Jet]:
    """Load this event's calibrated analysis jets (``AnalysisJets``) from a
    DAOD_PHYSLITE file.

    These are not associated with any particular vertex -- PHYSLITE has no
    ready jet-to-vertex link comparable to Rpt/ghost-track matching -- and
    carry no truth-level HS/PU classification, so every returned jet's
    ``is_hs`` is ``None``. Pass the result straight to
    :func:`~tracehep.vertices.zr.plot_vertex_detail`'s ``jets=``.

    Parameters
    ----------
    jet_pt_min:
        Drop jets below this pT [GeV].

    Returns
    -------
    list of tracehep.models.Jet
    """
    uproot = _require_uproot()
    f = uproot.open(path)
    tree = f[tree_name]
    branches = ["AnalysisJetsAuxDyn.pt", "AnalysisJetsAuxDyn.eta",
                "AnalysisJetsAuxDyn.phi", "AnalysisJetsAuxDyn.m"]
    arrs = tree.arrays(branches, entry_start=event_index, entry_stop=event_index + 1)
    i = 0

    jets = []
    for pt, eta, phi, m in zip(arrs["AnalysisJetsAuxDyn.pt"][i], arrs["AnalysisJetsAuxDyn.eta"][i],
                                arrs["AnalysisJetsAuxDyn.phi"][i], arrs["AnalysisJetsAuxDyn.m"][i]):
        pt_gev = float(pt) / 1000.0
        if pt_gev < jet_pt_min:
            continue
        jets.append(Jet(pt=pt_gev, eta=float(eta), phi=float(phi), mass=float(m) / 1000.0))
    return jets
