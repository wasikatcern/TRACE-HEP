"""Load the hard-scatter vertex's tracks, and every primary-vertex
position, out of the ATLAS Open Data 2024 **research** release
(DAOD_PHYSLITE format, opendata.cern.ch) via uproot.

PHYSLITE is ATLAS's storage-optimized analysis format: to save space it
thins away nearly all reconstructed tracks except those associated with
physics objects (leptons, jets) at the hard-scatter vertex. This was
verified against real files before writing this loader: every pileup
vertex's ``trackParticleLinks`` are broken (persistent key 0, an invalid
container reference) in every event checked -- only the hard-scatter
vertex (xAOD ``vertexType`` == 1) keeps a real, if partial, track
collection. This loader is honest about that limit: every retained
vertex's real (x, y, z) position and is_hs/is_pu flag is returned, but
only the hard-scatter vertex ever gets non-empty ``Vertex.track_indices``
-- pileup vertices come back with an empty track list because that is
what the file actually contains, not a bug in this loader. In practice
this means :func:`~tracehep.vertices.zr.plot_vertices_zr` on this data
shows every vertex's true position along the beamline but only draws
track fans at the hard-scatter one; :func:`~tracehep.vertices.zr.plot_vertex_detail`
on the hard-scatter vertex works close to normally.

There is no per-track timing in this public release (that requires an
HGTD-style upgrade-R&D ntuple, not part of any public open-data release
as of this writing), so the ``time_colored`` z-R display style has
nothing to color by here -- use ``style="plain"`` or ``"styled"``.

Track kinematics are derived from the raw xAOD perigee parameters
(``qOverP``, ``theta``) since PHYSLITE stores no direct pt/eta branch;
momenta are in MeV, converted to GeV here as with every other tracehep
loader.

Files are large (1-3 GB+); pass an
``https://opendata.cern.ch/eos/opendata/atlas/rucio/...`` URL directly as
``path`` and uproot streams only the bytes it needs.

Requires the ``delphes`` extra (uproot is shared): ``pip install trace-hep[delphes]``.

Developed by Wasikul Islam, PhD.
"""

import math
from typing import List

from ..models import Track, Vertex, VertexEvent

__all__ = ["load_vertex_event"]

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
    pileup) at its real (x, y, z) with is_hs/is_pu set; only the
    hard-scatter vertex has non-empty track_indices (see module docstring).
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
