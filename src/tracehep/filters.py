"""Post-load selection: apply pT/eta cuts (or drop non-b-tagged jets, etc.)
to an already-loaded :class:`~tracehep.models.Event` or
:class:`~tracehep.models.VertexEvent` before drawing it.

Filtering is a plain transformation on the format-agnostic dataclasses, not
a plotting-function argument -- so it works identically for every display
in tracehep (polar, beam2d, 3D, z-R, vertex-detail, ...) without any of
them needing to know about cuts at all. Call one of these once on a loaded
event, then pass the result to any ``plot_*`` function as usual.

Developed by Wasikul Islam, PhD.
"""

from dataclasses import replace
from typing import List, Optional

from .models import Event, Jet, Track, VertexEvent

__all__ = ["filter_tracks", "filter_jets", "filter_event", "filter_vertex_event"]


def filter_tracks(
    tracks: List[Track],
    *,
    pt_min: Optional[float] = None,
    pt_max: Optional[float] = None,
    eta_min: Optional[float] = None,
    eta_max: Optional[float] = None,
) -> List[Track]:
    """Return the subset of ``tracks`` passing the given cuts.

    ``eta_min``/``eta_max`` bound ``Track.eta`` directly (signed, not
    ``abs(eta)``) -- pass e.g. ``eta_min=0`` to keep only positive-eta
    tracks, or ``eta_min=-2.5, eta_max=2.5`` for a central-only selection.
    Any bound left as ``None`` is not applied.
    """
    out = tracks
    if pt_min is not None:
        out = [t for t in out if t.pt >= pt_min]
    if pt_max is not None:
        out = [t for t in out if t.pt <= pt_max]
    if eta_min is not None:
        out = [t for t in out if t.eta >= eta_min]
    if eta_max is not None:
        out = [t for t in out if t.eta <= eta_max]
    return out


def filter_jets(
    jets: List[Jet],
    *,
    pt_min: Optional[float] = None,
    pt_max: Optional[float] = None,
    eta_min: Optional[float] = None,
    eta_max: Optional[float] = None,
    btag_only: bool = False,
) -> List[Jet]:
    """Return the subset of ``jets`` passing the given cuts. See
    :func:`filter_tracks` for the eta_min/eta_max convention. Pass
    ``btag_only=True`` to additionally keep only b-tagged jets."""
    out = jets
    if pt_min is not None:
        out = [j for j in out if j.pt >= pt_min]
    if pt_max is not None:
        out = [j for j in out if j.pt <= pt_max]
    if eta_min is not None:
        out = [j for j in out if j.eta >= eta_min]
    if eta_max is not None:
        out = [j for j in out if j.eta <= eta_max]
    if btag_only:
        out = [j for j in out if j.btag]
    return out


def filter_event(
    event: Event,
    *,
    jet_pt_min: Optional[float] = None,
    jet_pt_max: Optional[float] = None,
    jet_eta_min: Optional[float] = None,
    jet_eta_max: Optional[float] = None,
    track_pt_min: Optional[float] = None,
    track_pt_max: Optional[float] = None,
    track_eta_min: Optional[float] = None,
    track_eta_max: Optional[float] = None,
) -> Event:
    """Return a copy of ``event`` with pT/eta cuts applied to its jets
    and/or tracks. Every other collection (leptons, photons, MET) is left
    untouched. The original ``event`` is not modified.

    >>> tight = filter_event(event, jet_pt_min=50.0, track_pt_min=1.0, track_eta_max=2.5)
    >>> trace.plot_event_polar(tight, show_tracks=True)
    """
    return replace(
        event,
        jets=filter_jets(event.jets, pt_min=jet_pt_min, pt_max=jet_pt_max,
                          eta_min=jet_eta_min, eta_max=jet_eta_max),
        tracks=filter_tracks(event.tracks, pt_min=track_pt_min, pt_max=track_pt_max,
                              eta_min=track_eta_min, eta_max=track_eta_max),
    )


def filter_vertex_event(
    vertex_event: VertexEvent,
    *,
    track_pt_min: Optional[float] = None,
    track_pt_max: Optional[float] = None,
    track_eta_min: Optional[float] = None,
    track_eta_max: Optional[float] = None,
) -> VertexEvent:
    """Return a copy of ``vertex_event`` with pT/eta cuts applied to its
    tracks. Every ``Vertex.track_indices`` list is remapped to the filtered
    track list so each vertex still points at the right (surviving) tracks;
    vertices themselves are never dropped, even if all their tracks are cut.
    The original ``vertex_event`` is not modified.
    """
    keep = [
        i for i, t in enumerate(vertex_event.tracks)
        if (track_pt_min is None or t.pt >= track_pt_min)
        and (track_pt_max is None or t.pt <= track_pt_max)
        and (track_eta_min is None or t.eta >= track_eta_min)
        and (track_eta_max is None or t.eta <= track_eta_max)
    ]
    old_to_new = {old: new for new, old in enumerate(keep)}
    new_tracks = [vertex_event.tracks[i] for i in keep]
    new_vertices = [
        replace(v, track_indices=[old_to_new[i] for i in v.track_indices if i in old_to_new])
        for v in vertex_event.vertices
    ]
    return replace(vertex_event, tracks=new_tracks, vertices=new_vertices)
