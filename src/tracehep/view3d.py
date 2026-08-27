"""Interactive 3D event display: every jet as a real cone mesh, every track
drawn from its true (x, y, z) production point, leptons/photons/MET as
lines, and an explicit beam axis through the primary vertex -- the same
"centre = beam axis" mental model as the polar view, just not flattened.

Developed by Wasikul Islam, PhD.
"""

import math
from typing import Optional

import numpy as np
import plotly.graph_objects as go

from .colors import DEFAULT_COLORS, TRACK_COLOR, DISPLACED_COLOR
from .models import Event

__all__ = ["plot_event_3d"]


def _unit_vec(eta: float, phi: float):
    theta = 2.0 * math.atan(math.exp(-eta))
    return math.sin(theta) * math.cos(phi), math.sin(theta) * math.sin(phi), math.cos(theta)


def _to_plot(px, py, pz):
    """Beamline (physics z) -> plotly's horizontal x slot; transverse
    (x, y) -> plotly's y/z slots."""
    return pz, px, py


def _track_len(pt: float) -> float:
    return min(40.0 + 25.0 * math.sqrt(max(pt, 0.0)), 350.0)


def _jet_len(pt: float) -> float:
    return min(60.0 + 30.0 * math.sqrt(max(pt, 0.0)), 420.0)


def _cone_mesh_xyz(direction, length, half_angle_deg=9.0, n_sides=24, apex=(0.0, 0.0, 0.0)):
    u = np.array(direction, dtype=float)
    ref = np.array([0.0, 0.0, 1.0]) if abs(u[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    perp1 = np.cross(u, ref); perp1 /= np.linalg.norm(perp1)
    perp2 = np.cross(u, perp1)
    r = length * math.tan(math.radians(half_angle_deg))
    apex_v = np.array(apex, dtype=float)
    tip = apex_v + length * u
    thetas = np.linspace(0, 2 * np.pi, n_sides, endpoint=False)
    base_pts = [tip + r * (math.cos(th) * perp1 + math.sin(th) * perp2) for th in thetas]
    verts_plot = [_to_plot(*v) for v in [apex_v] + base_pts]
    xs = [v[0] for v in verts_plot]; ys = [v[1] for v in verts_plot]; zs = [v[2] for v in verts_plot]
    i_idx, j_idx, k_idx = [], [], []
    for idx in range(n_sides):
        nxt = (idx + 1) % n_sides
        i_idx += [0]; j_idx += [1 + idx]; k_idx += [1 + nxt]
    return xs, ys, zs, i_idx, j_idx, k_idx


def plot_event_3d(
    event: Event,
    *,
    d0_displaced_mm: Optional[float] = None,
    jet_half_angle_deg: float = 9.0,
    title: Optional[str] = None,
) -> go.Figure:
    """Build an interactive 3D Plotly figure for one event.

    Parameters
    ----------
    event:
        The event to draw. Tracks without a real (x, y, z) production
        point default to the origin.
    d0_displaced_mm:
        If given, tracks with |Track.d0| above this threshold [mm] are
        coloured distinctly and their production points are marked, so a
        displaced-decay origin is visible even where the track segment
        itself is short.
    title:
        Plot title. Defaults to a string built from event.label /
        event.event_number if omitted.

    Returns
    -------
    plotly.graph_objects.Figure
    """
    traces = []
    traces.append(go.Scatter3d(
        x=[0], y=[0], z=[0], mode="markers", name="Primary vertex",
        marker=dict(size=7, symbol="diamond", color="#0b0b0b", opacity=0.95), hoverinfo="skip",
    ))

    if d0_displaced_mm is not None:
        prompt_tracks = [t for t in event.tracks if abs(t.d0) <= d0_displaced_mm]
        disp_tracks = [t for t in event.tracks if abs(t.d0) > d0_displaced_mm]
    else:
        prompt_tracks, disp_tracks = list(event.tracks), []

    for subset, color, name in [(prompt_tracks, TRACK_COLOR, "Prompt-track origins"),
                                 (disp_tracks, DISPLACED_COLOR, "Displaced-track origins")]:
        if not subset:
            continue
        px, py, pz = _to_plot([t.x for t in subset], [t.y for t in subset], [t.z for t in subset])
        traces.append(go.Scatter3d(
            x=px, y=py, z=pz, mode="markers", name=name,
            marker=dict(size=6 if color == DISPLACED_COLOR else 3, color=color,
                        opacity=0.9, line=dict(width=0.6, color="#3a3a38")),
            hoverinfo="skip",
        ))

    def _line_trace(subset, color, width, name):
        xs, ys, zs = [], [], []
        for t in subset:
            ux, uy, uz = _unit_vec(t.eta, t.phi)
            length = _track_len(t.pt)
            x1, y1, z1 = t.x + length * ux, t.y + length * uy, t.z + length * uz
            px0, py0, pz0 = _to_plot(t.x, t.y, t.z)
            px1, py1, pz1 = _to_plot(x1, y1, z1)
            xs += [px0, px1, None]; ys += [py0, py1, None]; zs += [pz0, pz1, None]
        return go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", name=name,
                             line=dict(color=color, width=width), hoverinfo="skip")

    if prompt_tracks:
        traces.append(_line_trace(prompt_tracks, TRACK_COLOR, 3, f"Prompt tracks (n={len(prompt_tracks)})"))
    if disp_tracks:
        traces.append(_line_trace(disp_tracks, DISPLACED_COLOR, 6, f"Displaced tracks (n={len(disp_tracks)})"))

    def _add_jet_cones(objs, color, legend_name):
        for n, j in enumerate(objs):
            direction = _unit_vec(j.eta, j.phi)
            xs, ys, zs, i_idx, j_idx, k_idx = _cone_mesh_xyz(direction, _jet_len(j.pt), jet_half_angle_deg)
            traces.append(go.Mesh3d(
                x=xs, y=ys, z=zs, i=i_idx, j=j_idx, k=k_idx, color=color, opacity=0.45,
                flatshading=True, lighting=dict(diffuse=0.6, ambient=0.5),
                name=legend_name, legendgroup=legend_name, showlegend=(n == 0), hoverinfo="skip",
            ))

    _add_jet_cones(event.light_jets, DEFAULT_COLORS["jet"], "Jets")
    _add_jet_cones(event.bjets, DEFAULT_COLORS["bjet"], "b-jets")

    def _object_line_trace(objs, length, color, name, dash=None):
        xs, ys, zs = [], [], []
        for o in objs:
            ux, uy, uz = _unit_vec(o.eta, o.phi)
            px1, py1, pz1 = _to_plot(length * ux, length * uy, length * uz)
            xs += [0, px1, None]; ys += [0, py1, None]; zs += [0, pz1, None]
        line = dict(color=color, width=6)
        if dash:
            line["dash"] = dash
        return go.Scatter3d(x=xs, y=ys, z=zs, mode="lines", name=name, line=line, hoverinfo="skip")

    if event.muons:
        traces.append(_object_line_trace(event.muons, 300.0, DEFAULT_COLORS["muon"],
                                          f"Muons (n={len(event.muons)})"))
    if event.electrons:
        traces.append(_object_line_trace(event.electrons, 300.0, DEFAULT_COLORS["electron"],
                                          f"Electrons (n={len(event.electrons)})"))
    if event.photons:
        traces.append(_object_line_trace(event.photons, 260.0, DEFAULT_COLORS["photon"],
                                          f"Photons (n={len(event.photons)})", dash="dot"))
    if event.met is not None and event.met.pt > 0:
        length = min(40.0 + 1.4 * event.met.pt, 300.0)
        px1, py1, pz1 = _to_plot(length * math.cos(event.met.phi), length * math.sin(event.met.phi), 0.0)
        traces.append(go.Scatter3d(
            x=[0, px1], y=[0, py1], z=[0, pz1], mode="lines+markers", name=f"MET ({event.met.pt:.0f} GeV)",
            line=dict(color=DEFAULT_COLORS["met"], width=6, dash="dash"),
            marker=dict(size=[0, 6], color=DEFAULT_COLORS["met"], symbol="diamond"), hoverinfo="skip",
        ))

    z_extent = [0.0] + [t.z for t in event.tracks] + [
        t.z + _track_len(t.pt) * _unit_vec(t.eta, t.phi)[2] for t in event.tracks
    ]
    beam_half_range = max(1.0, max(abs(v) for v in z_extent)) * 1.15
    bx0, by0, bz0 = _to_plot(0.0, 0.0, -beam_half_range)
    bx1, by1, bz1 = _to_plot(0.0, 0.0, beam_half_range)
    traces.insert(0, go.Scatter3d(
        x=[bx0, bx1], y=[by0, by1], z=[bz0, bz1], mode="lines", name="Beam axis",
        line=dict(color="#c3c2b7", width=4, dash="dot"), hoverinfo="skip",
    ))

    if title is None:
        parts = [p for p in (event.label, f"Event# {event.event_number}"
                              if event.event_number is not None else None) if p]
        title = " ".join(parts) if parts else "3D event display"

    fig = go.Figure(data=traces)
    fig.update_layout(
        template=None,
        scene=dict(
            xaxis=dict(title="z [mm]", backgroundcolor="rgba(0,0,0,0)", gridcolor="#e1e0d9",
                       zerolinecolor="#c3c2b7", color="#52514e"),
            yaxis=dict(title="x [mm]", backgroundcolor="rgba(0,0,0,0)", gridcolor="#e1e0d9",
                       zerolinecolor="#c3c2b7", color="#52514e"),
            zaxis=dict(title="y [mm]", backgroundcolor="rgba(0,0,0,0)", gridcolor="#e1e0d9",
                       zerolinecolor="#c3c2b7", color="#52514e"),
            aspectmode="manual", aspectratio=dict(x=1.7, y=1, z=1),
            camera=dict(eye=dict(x=1.3, y=1.5, z=1.2)),
        ),
        paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb",
        font=dict(family="Arial, sans-serif", color="#0b0b0b"),
        title=dict(text=title, x=0.02, xanchor="left"),
        legend=dict(bgcolor="rgba(252,252,251,0.85)", bordercolor="#e1e0d9", borderwidth=1),
        margin=dict(l=10, r=10, t=60, b=10),
        height=780,
    )
    return fig
