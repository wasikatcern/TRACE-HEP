"""Load a high-pileup "4D tracking" / calo-timing ntuple (RecoVtx_*,
Track_*, TruthVtx_* branches, per-track and per-vertex timing) into a
:class:`~tracehep.models.VertexEvent` via uproot.

A track's real (x, y) is not stored directly in this ntuple format -- only
its z0 impact parameter and its owning vertex's (x, y, z) are -- so each
track's origin is set to (owning vertex's x, owning vertex's y, track's own
z0), the same convention the underlying displays have always used.

Requires the ``delphes`` extra (uproot is shared): ``pip install trace-hep[delphes]``.

Developed by Wasikul Islam, PhD.
"""

from typing import Dict

from ..models import Track, TruthVertex, Vertex, VertexEvent

__all__ = ["load_vertex_event"]

_BRANCHES = [
    "RecoVtx_z", "RecoVtx_x", "RecoVtx_y", "RecoVtx_sumPt2", "RecoVtx_isHS", "RecoVtx_isPU",
    "RecoVtx_track_idx",
    "Track_pt", "Track_eta", "Track_phi", "Track_d0", "Track_z0", "Track_time", "Track_hasValidTime",
    "TruthVtx_z", "TruthVtx_x", "TruthVtx_y", "TruthVtx_isHS",
    "averageInteractionsPerCrossing",
]


def _require_uproot():
    try:
        import uproot  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "tracehep.io.calotiming requires uproot. Install with: pip install trace-hep[delphes]"
        ) from exc
    return uproot


def load_vertex_event(path: str, event_index: int, *, tree_name: str = "ntuple",
                       label: str = "") -> VertexEvent:
    """Load every reconstructed vertex, truth vertex, and track for one
    event out of a calo-timing / 4D-tracking ntuple.

    Returns
    -------
    tracehep.models.VertexEvent
    """
    uproot = _require_uproot()
    f = uproot.open(path)
    tree = f[tree_name]
    arrs = tree.arrays(_BRANCHES, entry_start=event_index, entry_stop=event_index + 1)
    i = 0

    tracks = []
    track_idx_map: Dict[int, int] = {}
    vertices = []

    n_vtx = len(arrs["RecoVtx_z"][i])
    for vid in range(n_vtx):
        vz = float(arrs["RecoVtx_z"][i][vid])
        vx = float(arrs["RecoVtx_x"][i][vid])
        vy = float(arrs["RecoVtx_y"][i][vid])
        sum_pt2 = float(arrs["RecoVtx_sumPt2"][i][vid])
        is_hs = bool(arrs["RecoVtx_isHS"][i][vid])
        is_pu = bool(arrs["RecoVtx_isPU"][i][vid])

        track_indices = []
        for raw_tidx in arrs["RecoVtx_track_idx"][i][vid]:
            raw_tidx = int(raw_tidx)
            if raw_tidx not in track_idx_map:
                has_time = bool(arrs["Track_hasValidTime"][i][raw_tidx])
                track = Track(
                    pt=float(arrs["Track_pt"][i][raw_tidx]),
                    eta=float(arrs["Track_eta"][i][raw_tidx]),
                    phi=float(arrs["Track_phi"][i][raw_tidx]),
                    d0=float(arrs["Track_d0"][i][raw_tidx]),
                    z0=float(arrs["Track_z0"][i][raw_tidx]),
                    x=vx, y=vy, z=float(arrs["Track_z0"][i][raw_tidx]),
                    time=float(arrs["Track_time"][i][raw_tidx]) if has_time else None,
                )
                track_idx_map[raw_tidx] = len(tracks)
                tracks.append(track)
            track_indices.append(track_idx_map[raw_tidx])

        vertices.append(Vertex(z=vz, x=vx, y=vy, sum_pt2=sum_pt2, is_hs=is_hs, is_pu=is_pu,
                                track_indices=track_indices))

    truth_vertices = [
        TruthVertex(z=float(z), x=float(x), y=float(y), is_hs=bool(hs))
        for z, x, y, hs in zip(arrs["TruthVtx_z"][i], arrs["TruthVtx_x"][i],
                                arrs["TruthVtx_y"][i], arrs["TruthVtx_isHS"][i])
    ]

    mu = float(arrs["averageInteractionsPerCrossing"][i])
    return VertexEvent(vertices=vertices, tracks=tracks, truth_vertices=truth_vertices, mu=mu, label=label)
