"""TRACE: a lightweight toolkit for reconstructed-level collider-event and
vertex displays.

    import tracehep as trace

    event = trace.Event(jets=[...], met=trace.MissingET(pt=120, phi=0.3))
    fig = trace.plot_event_polar(event, show_tracks=True)

Loaders for specific ROOT ntuple formats live in :mod:`tracehep.io` and are
imported separately so the core package never requires uproot or ROOT.

Developed by Wasikul Islam, PhD.
"""

from .models import Event, Jet, Lepton, MissingET, Photon, Track, TruthVertex, Vertex, VertexEvent
from .polar import plot_event_polar
from .beam2d import plot_event_beam2d
from .view3d import plot_event_3d
from .vertices.zr import plot_vertices_zr
from .vertices.view3d import plot_vertices_3d
from .colors import DEFAULT_COLORS, TRACK_COLOR, DISPLACED_COLOR

__version__ = "0.1.1"

__all__ = [
    "__version__",
    # data model
    "Event", "Jet", "Track", "Lepton", "Photon", "MissingET",
    "Vertex", "TruthVertex", "VertexEvent",
    # drawing
    "plot_event_polar", "plot_event_beam2d", "plot_event_3d",
    "plot_vertices_zr", "plot_vertices_3d",
    # colours
    "DEFAULT_COLORS", "TRACK_COLOR", "DISPLACED_COLOR",
]
