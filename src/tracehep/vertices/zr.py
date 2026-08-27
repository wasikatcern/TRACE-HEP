"""z-R vertex display: every reconstructed vertex plotted along the beam
axis (Z), with each of its tracks drawn as a short schematic line whose
length/angle is set by the track's pT and eta -- the classic "splay" view
for spotting hard-scatter/pileup vertex merging by eye.

Developed by Wasikul Islam, PhD.
"""

import math
from typing import Optional, Sequence

import matplotlib
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np

from ..colors import DEFAULT_COLORS
from ..models import Jet, VertexEvent

__all__ = ["plot_vertices_zr", "plot_vertex_detail"]

COLOR_HS = "#2a78d6"
COLOR_PU = "#e34948"


def _schematic_offset(pt: float, eta: float, phi: float, scale: float):
    """Schematic (dz, dr) offset from a vertex position, scaled by pT/eta --
    not a physical trajectory, purely a visibility convention shared with
    the rest of tracehep. ``scale`` controls how far pT=1 GeV reaches."""
    eta = eta if eta != 0 else 1e-9
    pz = pt * math.sinh(eta)
    sign_x = eta / abs(eta)
    sin_phi = math.sin(phi)
    sign_y = sin_phi / abs(sin_phi) if sin_phi != 0 else 1.0
    theta = math.atan(pt / max(abs(pz), 1e-9))
    dz = (pt / scale) * math.cos(theta) * sign_x
    dr = (pt / scale) * math.sin(theta) * sign_y
    return dz, dr


def _track_offset(track):
    return _schematic_offset(track.pt, track.eta, track.phi, scale=2.0)


def plot_vertices_zr(
    vertex_event: VertexEvent,
    *,
    style: str = "plain",
    zoom_center: Optional[float] = None,
    zoom_range_mm: Optional[float] = None,
    ax: Optional["plt.Axes"] = None,
    title: Optional[str] = None,
):
    """Draw every vertex and track in a :class:`~tracehep.models.VertexEvent`.

    Parameters
    ----------
    style:
        ``"plain"`` -- flat-coloured tracks (blue=HS, red=PU by the owning
        vertex's is_hs/is_pu flag), fixed-size vertex markers.
        ``"styled"`` -- vertex marker size scales with sqrt(sum pT^2), and
        <mu> is reported in the title if available.
        ``"time_colored"`` -- PU tracks coloured by Track.time (requires
        per-track timing; falls back to "plain" colouring for tracks with
        time=None).
    zoom_center, zoom_range_mm:
        If both given, the x-axis is limited to
        ``[zoom_center - zoom_range_mm, zoom_center + zoom_range_mm]``
        instead of showing every vertex in the event -- pass the z of one
        vertex of interest and e.g. 5.0 mm to reproduce a single-vertex
        zoomed view with the same function used for the full-event overview.
    title:
        Plot title. Defaults to a string built from vertex_event.label /
        vertex count / <mu> if omitted.

    Returns
    -------
    matplotlib.figure.Figure
    """
    if style not in ("plain", "styled", "time_colored"):
        raise ValueError(f"style must be 'plain', 'styled', or 'time_colored', got {style!r}")

    if ax is None:
        fig, ax = plt.subplots(figsize=(15, 5.5))
    else:
        fig = ax.figure

    tnorm = tcmap = None
    if style == "time_colored":
        pu_times = np.array([t.time for t in vertex_event.tracks if t.time is not None])
        if len(pu_times) > 5:
            tnorm = mcolors.Normalize(vmin=np.percentile(pu_times, 1), vmax=np.percentile(pu_times, 99))
        else:
            tnorm = mcolors.Normalize(vmin=-1, vmax=1)
        tcmap = matplotlib.colormaps["coolwarm"]

    for vtx in vertex_event.vertices:
        for ti in vtx.track_indices:
            if ti >= len(vertex_event.tracks):
                continue
            track = vertex_event.tracks[ti]
            dz, dr = _track_offset(track)
            z0, z1 = vtx.z, vtx.z + dz
            if style == "time_colored" and not vtx.is_hs and track.time is not None:
                color, lw = tcmap(tnorm(track.time)), 1.0
            elif vtx.is_hs:
                color, lw = COLOR_HS, 1.4
            else:
                color, lw = COLOR_PU, 1.0
            ax.plot([z0, z1], [0, dr], color=color, linewidth=lw)

    for vtx in vertex_event.vertices:
        if style == "styled":
            size = 5 + 3.0 * math.sqrt(max(vtx.sum_pt2, 0.0))
        else:
            size = 5
        ax.plot([vtx.z], [0], "o", color="#444444" if style == "styled" else "black",
                 markersize=size, alpha=0.85, zorder=4)

    truth_z = [tv.z for tv in vertex_event.truth_vertices]
    if truth_z:
        ax.scatter(truth_z, [-0.75] * len(truth_z), color="black", marker="|", s=100, zorder=3)

    if style == "time_colored" and tnorm is not None:
        sm = cm.ScalarMappable(norm=tnorm, cmap=tcmap)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, pad=0.01)
        cbar.set_label("PU track time [ps]")

    legend_handles = [
        plt.Line2D([], [], color=COLOR_HS, label="HS tracks"),
        plt.Line2D([], [], color=COLOR_PU, label="PU tracks"),
    ]
    if style == "styled":
        legend_handles.append(plt.Line2D([], [], marker="o", color="#444444", linestyle="None",
                                          markersize=8, label=r"Vertex (size $\propto\sqrt{\sum p_T^2}$)"))
    ax.legend(handles=legend_handles, loc="upper right", fontsize=9)

    ax.axhline(y=0.0, color="black", linestyle="--", linewidth=0.8)
    ax.axhline(y=-0.75, color="black", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Z [mm]")
    ax.set_ylabel("R [mm]")
    ax.set_ylim(-1, 1)

    if zoom_center is not None and zoom_range_mm is not None:
        ax.set_xlim(zoom_center - zoom_range_mm, zoom_center + zoom_range_mm)
    else:
        all_z = [v.z for v in vertex_event.vertices] + truth_z
        if all_z:
            pad = 0.05 * (max(all_z) - min(all_z) or 1.0)
            ax.set_xlim(min(all_z) - pad, max(all_z) + pad)

    if title is None:
        parts = [vertex_event.label, f"N_vtx={len(vertex_event.vertices)}"]
        if vertex_event.mu is not None:
            parts.append(f"<mu>={vertex_event.mu:.0f}")
        title = ", ".join(p for p in parts if p)
    ax.set_title(title)
    fig.tight_layout()
    return fig


def plot_vertex_detail(
    vertex_event: VertexEvent,
    vtx_index: int,
    jets: Sequence[Jet] = (),
    *,
    zoom_range_mm: float = 5.0,
    ax: Optional["plt.Axes"] = None,
    title: Optional[str] = None,
):
    """Detailed single-vertex display: this vertex's own tracks, plus any
    jets already associated with it, drawn as cones -- the companion to
    :func:`plot_vertices_zr` for inspecting *one* vertex closely (jets,
    sum(pT^2), nearest truth vertex) rather than surveying every vertex in
    the event.

    Jet-to-vertex association (e.g. by track-pT-fraction/Rpt matching) is
    deliberately left to the caller or a loader-specific helper -- it is
    analysis-specific, unlike everything else this function draws.

    Parameters
    ----------
    vertex_event:
        The event containing the vertex to draw.
    vtx_index:
        Index into ``vertex_event.vertices`` of the vertex to draw.
    jets:
        Jets already associated with this vertex, drawn as cones from its
        position. Coloured by :class:`~tracehep.models.Jet`.btag.
    zoom_range_mm:
        The x-axis is limited to ``[vtx.z - zoom_range_mm, vtx.z + zoom_range_mm]``.
    title:
        Plot title. Defaults to a string built from vertex_event.label /
        vtx_index if omitted.

    Returns
    -------
    matplotlib.figure.Figure
    """
    vtx = vertex_event.vertices[vtx_index]

    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 6))
    else:
        fig = ax.figure

    track_color = COLOR_HS if vtx.is_hs else COLOR_PU
    for ti in vtx.track_indices:
        if ti >= len(vertex_event.tracks):
            continue
        dz, dr = _track_offset(vertex_event.tracks[ti])
        ax.plot([vtx.z, vtx.z + dz], [0, dr], color=track_color, linewidth=1.2)

    for eta_ref, ls in [(2.5, "dashed"), (4.0, "dotted")]:
        theta = 2 * math.atan(math.exp(-eta_ref))
        x_ref, y_ref = 50.0 * math.cos(theta), 50.0 * math.sin(theta)
        for sign in (1, -1):
            ax.plot([vtx.z, vtx.z + x_ref], [0, sign * y_ref], linestyle=ls, color="lightgrey", linewidth=1)
            ax.plot([vtx.z, vtx.z - x_ref], [0, sign * y_ref], linestyle=ls, color="lightgrey", linewidth=1)
        ax.text(vtx.z + zoom_range_mm * 0.55, -0.9 - 0.06 * (eta_ref - 2.5), rf"$\eta={eta_ref:g}$",
                fontsize=10, color="lightgrey")

    jet_labels = []
    for j in jets:
        dz, dr = _schematic_offset(j.pt, j.eta, j.phi, scale=40.0)
        length = math.hypot(dz, dr)
        width = length * 0.3
        norm = max(length, 1e-9)
        perp_x, perp_y = -dr / norm * width / 2, dz / norm * width / 2
        color = DEFAULT_COLORS["bjet"] if j.btag else DEFAULT_COLORS["jet"]
        ax.fill([vtx.z, vtx.z + dz + perp_x, vtx.z + dz - perp_x],
                [0, dr + perp_y, dr - perp_y], color=color, alpha=0.5)
        jet_labels.append((f"Jet {len(jet_labels) + 1}: pT={j.pt:.0f} GeV, eta={j.eta:.1f}"
                            + (" (b)" if j.btag else ""), color))

    x0 = vtx.z - zoom_range_mm
    ax.text(x0 + 0.1, 0.95, f"Reco z = {vtx.z:.1f} mm", fontsize=11, weight="bold")
    nearest_truth = min(vertex_event.truth_vertices, key=lambda tv: abs(tv.z - vtx.z), default=None)
    if nearest_truth is not None:
        ax.text(x0 + 0.1, 0.85, f"Truth z = {nearest_truth.z:.1f} mm", fontsize=11, weight="bold")
    ax.text(x0 + 0.1, 0.75, rf"$\sum p_T^2$ = {vtx.sum_pt2:.1e} GeV$^2$", fontsize=11, weight="bold")
    for k, (label, color) in enumerate(jet_labels):
        ax.text(x0 + 0.1, 0.55 - k * 0.12, label, fontsize=10, weight="bold", color=color)

    ax.legend(handles=[
        plt.Line2D([], [], color=COLOR_HS, label="HS vertex tracks"),
        plt.Line2D([], [], color=COLOR_PU, label="PU vertex tracks"),
        plt.Rectangle((0, 0), 1, 1, color=DEFAULT_COLORS["jet"], alpha=0.5, label="Jet"),
        plt.Rectangle((0, 0), 1, 1, color=DEFAULT_COLORS["bjet"], alpha=0.5, label="b-jet"),
    ], loc="upper right", fontsize=9)

    ax.axhline(y=0.0, color="black", linestyle="--", linewidth=0.8)
    ax.set_xlabel("Z [mm]")
    ax.set_ylabel("R [mm]")
    ax.set_xlim(x0, vtx.z + zoom_range_mm)
    ax.set_ylim(-1.0, 1.0)

    if title is None:
        parts = [vertex_event.label, f"vertex {vtx_index}", "HS" if vtx.is_hs else "PU"]
        title = ", ".join(p for p in parts if p)
    ax.set_title(title)
    fig.tight_layout()
    return fig
