"""Generic batch drivers: given a dict of already-loaded events, save each
one's display(s) to a flat output directory. Deliberately format-agnostic
-- combine with any :mod:`tracehep.io` loader (or your own) to batch over a
whole sample.

Developed by Wasikul Islam, PhD.
"""

import os
from typing import Any, Dict, Optional, Sequence

import matplotlib.pyplot as plt

from .beam2d import plot_event_beam2d
from .models import Event, VertexEvent
from .polar import plot_event_polar
from .vertices.zr import plot_vertices_zr

__all__ = ["run_event_batch", "run_vertex_batch"]


def run_event_batch(
    events: Dict[Any, Event],
    outdir: str,
    *,
    which: Sequence[str] = ("polar", "beam2d"),
    file_prefix: str = "event",
    dpi: int = 160,
    polar_kwargs: Optional[Dict[str, Any]] = None,
    beam2d_kwargs: Optional[Dict[str, Any]] = None,
) -> None:
    """Save polar and/or beam-axis 2D displays for every event in ``events``.

    Parameters
    ----------
    events:
        Mapping of an arbitrary key (an index, an (run, event) pair, ...)
        to an already-loaded :class:`~tracehep.models.Event`.
    outdir:
        Output directory (created if missing); every file lands here flat,
        named ``{file_prefix}{key}_{polar,beam2d}.png``.
    which:
        Which display(s) to produce: any of ``"polar"``, ``"beam2d"``.
    polar_kwargs, beam2d_kwargs:
        Forwarded to :func:`~tracehep.polar.plot_event_polar` /
        :func:`~tracehep.beam2d.plot_event_beam2d` respectively -- kept
        separate since the two functions don't share every parameter
        (e.g. ``show_tracks`` is polar-only).
    """
    os.makedirs(outdir, exist_ok=True)
    polar_kwargs = polar_kwargs or {}
    beam2d_kwargs = beam2d_kwargs or {}
    for key, event in events.items():
        if "polar" in which:
            fig = plot_event_polar(event, **polar_kwargs)
            fig.savefig(os.path.join(outdir, f"{file_prefix}{key}_polar.png"), dpi=dpi, bbox_inches="tight")
            plt.close(fig)
        if "beam2d" in which:
            fig = plot_event_beam2d(event, **beam2d_kwargs)
            fig.savefig(os.path.join(outdir, f"{file_prefix}{key}_beam2d.png"), dpi=dpi, bbox_inches="tight")
            plt.close(fig)


def run_vertex_batch(
    vertex_events: Dict[Any, VertexEvent],
    outdir: str,
    *,
    styles: Sequence[str] = ("plain",),
    file_prefix: str = "vertices",
    dpi: int = 150,
    **draw_kwargs,
) -> None:
    """Save an all-vertices z-R display for every :class:`VertexEvent`.

    Parameters
    ----------
    styles:
        Any of ``"plain"``, ``"styled"``, ``"time_colored"`` -- one file is
        written per style, per event.
    """
    os.makedirs(outdir, exist_ok=True)
    for key, vertex_event in vertex_events.items():
        for style in styles:
            fig = plot_vertices_zr(vertex_event, style=style, **draw_kwargs)
            fig.savefig(os.path.join(outdir, f"{file_prefix}{key}_{style}.png"), dpi=dpi, bbox_inches="tight")
            plt.close(fig)
