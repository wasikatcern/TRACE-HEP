"""Interactive 3D vertex display: every reconstructed and truth vertex at
its real (x, y, z) position, each track drawn as a schematic straight
segment along its true (theta, phi) direction from its owning vertex.

Developed by Wasikul Islam, PhD.
"""

import math
from typing import Optional

import plotly.graph_objects as go

from ..models import VertexEvent

__all__ = ["plot_vertices_3d"]

COLOR_HS = "#2a78d6"
COLOR_PU = "#e34948"
COLOR_OTHER = "#898781"
COLOR_TRUTH = "#52514e"


def _unit_vec(eta: float, phi: float):
    theta = 2.0 * math.atan(math.exp(-eta))
    return math.sin(theta) * math.cos(phi), math.sin(theta) * math.sin(phi), math.cos(theta)


def _to_plot(px, py, pz):
    return pz, px, py


def _vsize(sum_pt2: float) -> float:
    return min(3.0 + 1.0 * math.sqrt(max(sum_pt2, 0.0)), 18.0)


def plot_vertices_3d(vertex_event: VertexEvent, *, title: Optional[str] = None) -> go.Figure:
    """Build an interactive 3D Plotly figure for one :class:`VertexEvent`.

    Returns
    -------
    plotly.graph_objects.Figure
    """
    reco_hs = [v for v in vertex_event.vertices if v.is_hs]
    reco_pu = [v for v in vertex_event.vertices if not v.is_hs]

    traces = []
    if vertex_event.truth_vertices:
        tv = vertex_event.truth_vertices
        tx, ty, tz = _to_plot([v.x for v in tv], [v.y for v in tv], [v.z for v in tv])
        traces.append(go.Scatter3d(
            x=tx, y=ty, z=tz, mode="markers", name="Truth vertices",
            marker=dict(size=3, symbol="diamond", color=COLOR_TRUTH, opacity=0.75), hoverinfo="skip",
        ))

    if reco_pu:
        vx, vy, vz = _to_plot([v.x for v in reco_pu], [v.y for v in reco_pu], [v.z for v in reco_pu])
        traces.append(go.Scatter3d(
            x=vx, y=vy, z=vz, mode="markers", name="Reco vertices (PU)",
            marker=dict(size=[_vsize(v.sum_pt2) for v in reco_pu], color=COLOR_OTHER,
                        opacity=0.8, line=dict(width=0.5, color="#3a3a38")), hoverinfo="skip",
        ))

    if reco_hs:
        vx, vy, vz = _to_plot([v.x for v in reco_hs], [v.y for v in reco_hs], [v.z for v in reco_hs])
        traces.append(go.Scatter3d(
            x=vx, y=vy, z=vz, mode="markers", name="Reco vertex (hard-scatter)",
            marker=dict(size=[_vsize(v.sum_pt2) + 4 for v in reco_hs], color=COLOR_HS, symbol="diamond",
                        opacity=0.95, line=dict(width=1, color="#0b0b0b")), hoverinfo="skip",
        ))

    def _track_len(pt: float) -> float:
        return min(4.0 + 5.0 * math.sqrt(max(pt, 0.0)), 30.0)

    def _line_trace(vtx, indices, color, name_parts):
        xs, ys, zs = [], [], []
        for ti in indices:
            if ti >= len(vertex_event.tracks):
                continue
            t = vertex_event.tracks[ti]
            ux, uy, uz = _unit_vec(t.eta, t.phi)
            length = _track_len(t.pt)
            x1, y1, z1 = vtx.x + length * ux, vtx.y + length * uy, vtx.z + length * uz
            px0, py0, pz0 = _to_plot(vtx.x, vtx.y, vtx.z)
            px1, py1, pz1 = _to_plot(x1, y1, z1)
            xs += [px0, px1, None]; ys += [py0, py1, None]; zs += [pz0, pz1, None]
        return xs, ys, zs

    hs_xs, hs_ys, hs_zs, pu_xs, pu_ys, pu_zs = [], [], [], [], [], []
    for vtx in vertex_event.vertices:
        xs, ys, zs = _line_trace(vtx, vtx.track_indices, None, None)
        if vtx.is_hs:
            hs_xs += xs; hs_ys += ys; hs_zs += zs
        else:
            pu_xs += xs; pu_ys += ys; pu_zs += zs

    if hs_xs:
        traces.append(go.Scatter3d(x=hs_xs, y=hs_ys, z=hs_zs, mode="lines", name="HS tracks",
                                    line=dict(color=COLOR_HS, width=4), hoverinfo="skip"))
    if pu_xs:
        traces.append(go.Scatter3d(x=pu_xs, y=pu_ys, z=pu_zs, mode="lines", name="PU tracks",
                                    line=dict(color=COLOR_PU, width=3), hoverinfo="skip"))

    if title is None:
        parts = [vertex_event.label, f"N_vtx={len(vertex_event.vertices)}"]
        if vertex_event.mu is not None:
            parts.append(f"<mu>={vertex_event.mu:.0f}")
        title = ", ".join(p for p in parts if p)

    fig = go.Figure(data=traces)
    fig.update_layout(
        template=None,
        scene=dict(
            xaxis=dict(title="z [mm]", backgroundcolor="rgba(0,0,0,0)", gridcolor="#e1e0d9",
                       zerolinecolor="#c3c2b7", color="#52514e"),
            yaxis=dict(title="x [mm] (schematic)", backgroundcolor="rgba(0,0,0,0)", gridcolor="#e1e0d9",
                       zerolinecolor="#c3c2b7", color="#52514e"),
            zaxis=dict(title="y [mm] (schematic)", backgroundcolor="rgba(0,0,0,0)", gridcolor="#e1e0d9",
                       zerolinecolor="#c3c2b7", color="#52514e"),
            aspectmode="manual", aspectratio=dict(x=2.4, y=1, z=1),
            camera=dict(eye=dict(x=0.9, y=1.5, z=1.5)),
        ),
        paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
        font=dict(family="Arial, sans-serif", color="#0b0b0b"),
        title=dict(text=title, x=0.02, xanchor="left"),
        legend=dict(bgcolor="rgba(252,252,251,0.85)", bordercolor="#e1e0d9", borderwidth=1),
        margin=dict(l=10, r=10, t=60, b=10),
        height=760,
    )
    return fig
