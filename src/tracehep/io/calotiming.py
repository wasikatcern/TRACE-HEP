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

import math
from typing import Dict, List, Optional

from ..models import Jet, Track, TruthVertex, Vertex, VertexEvent

__all__ = ["load_vertex_event", "match_jets_to_vertex"]

_BRANCHES = [
    "RecoVtx_z", "RecoVtx_x", "RecoVtx_y", "RecoVtx_sumPt2", "RecoVtx_isHS", "RecoVtx_isPU",
    "RecoVtx_track_idx",
    "Track_pt", "Track_eta", "Track_phi", "Track_d0", "Track_z0", "Track_time", "Track_hasValidTime",
    "Track_truthVtx_idx",
    "TruthVtx_z", "TruthVtx_x", "TruthVtx_y", "TruthVtx_isHS",
    "averageInteractionsPerCrossing",
]

_JET_TRACK_IDX_CANDIDATES = ["track_idx", "ghostTrack_idx"]
"""Different ntuple productions name a jet's constituent-track association
differently -- ``{collection}_track_idx`` in some, ``{collection}_ghostTrack_idx``
(ATLAS ghost-association) in others. match_jets_to_vertex tries each in turn."""


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
                truth_vtx_idx = int(arrs["Track_truthVtx_idx"][i][raw_tidx])
                track_is_hs = (bool(arrs["TruthVtx_isHS"][i][truth_vtx_idx])
                               if truth_vtx_idx != -1 else None)
                track = Track(
                    pt=float(arrs["Track_pt"][i][raw_tidx]),
                    eta=float(arrs["Track_eta"][i][raw_tidx]),
                    phi=float(arrs["Track_phi"][i][raw_tidx]),
                    d0=float(arrs["Track_d0"][i][raw_tidx]),
                    z0=float(arrs["Track_z0"][i][raw_tidx]),
                    x=vx, y=vy, z=float(arrs["Track_z0"][i][raw_tidx]),
                    time=float(arrs["Track_time"][i][raw_tidx]) if has_time else None,
                    is_hs=track_is_hs,
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


def match_jets_to_vertex(
    path: str,
    event_index: int,
    vtx_z: float,
    *,
    tree_name: str = "ntuple",
    jet_collection: str = "AntiKt4EMTopoJets",
    track_idx_branch: Optional[str] = None,
    jet_pt_min: float = 30.0,
    rpt_min: float = 0.02,
    sig_cut: float = 3.0,
) -> List[Jet]:
    """Associate reconstructed jets to one vertex by Rpt: the fraction of a
    jet's pT carried by its constituent tracks that are compatible with
    this vertex's z position (|z0 - vtx_z| / sigma(z0) <= sig_cut). This is
    the same track-pT-fraction matching used to build the original
    single-vertex-with-jets displays, factored out here as an explicit,
    reusable step rather than hidden inside a loader -- association logic
    like this is analysis-specific, unlike everything :func:`plot_vertex_detail`
    draws.

    Parameters
    ----------
    jet_collection:
        Branch-name prefix for the jet collection, e.g. "AntiKt4EMTopoJets"
        (default) or "AntiKt4EMPFlowJets".
    track_idx_branch:
        Full branch name for the jet's constituent-track indices. If
        omitted, tries ``"{jet_collection}_track_idx"`` then
        ``"{jet_collection}_ghostTrack_idx"`` (different ntuple productions
        use different names for the same jet-to-track association).

    Returns
    -------
    list of tracehep.models.Jet, each with pt >= jet_pt_min and
    Rpt >= rpt_min, for use with :func:`tracehep.vertices.zr.plot_vertex_detail`.
    """
    uproot = _require_uproot()
    f = uproot.open(path)
    tree = f[tree_name]
    available = set(tree.keys())

    if track_idx_branch is None:
        for candidate in _JET_TRACK_IDX_CANDIDATES:
            name = f"{jet_collection}_{candidate}"
            if name in available:
                track_idx_branch = name
                break
        else:
            tried = ", ".join(f"{jet_collection}_{c}" for c in _JET_TRACK_IDX_CANDIDATES)
            raise KeyError(
                f"No jet-to-track association branch found for jet_collection={jet_collection!r}. "
                f"Tried: {tried}. Pass track_idx_branch=... explicitly if this ntuple uses a "
                f"different name."
            )

    branches = [f"{jet_collection}_pt", f"{jet_collection}_eta", f"{jet_collection}_phi",
                track_idx_branch, "Track_pt", "Track_z0", "Track_var_z0"]
    arrs = tree.arrays(branches, entry_start=event_index, entry_stop=event_index + 1)
    i = 0

    jets = []
    n_jets = len(arrs[f"{jet_collection}_pt"][i])
    for j in range(n_jets):
        jet_pt = float(arrs[f"{jet_collection}_pt"][i][j])
        if jet_pt < jet_pt_min:
            continue
        track_pt_sum = 0.0
        for tidx in arrs[track_idx_branch][i][j]:
            tidx = int(tidx)
            delz = float(arrs["Track_z0"][i][tidx]) - vtx_z
            sigma = math.sqrt(max(float(arrs["Track_var_z0"][i][tidx]), 1e-12))
            if abs(delz / sigma) > sig_cut:
                continue
            track_pt_sum += float(arrs["Track_pt"][i][tidx])
        rpt = track_pt_sum / jet_pt
        if rpt < rpt_min:
            continue
        jets.append(Jet(pt=jet_pt, eta=float(arrs[f"{jet_collection}_eta"][i][j]),
                         phi=float(arrs[f"{jet_collection}_phi"][i][j])))
    return jets
