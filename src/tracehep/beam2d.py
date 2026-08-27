"""Beam-axis 2D projection: a side-on view with the beam direction (related
to eta) on the horizontal axis and one transverse coordinate on the
vertical axis, giving a complementary sense of how forward/central an
event is relative to the polar view in :mod:`tracehep.polar`.

Developed by Wasikul Islam, PhD.
"""

import math
from typing import Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np

from .colors import DEFAULT_COLORS
from .models import Event

__all__ = ["plot_event_beam2d"]

XLIM = 1.6
YLIM = 1.2
LABEL_MAX_R = 1.1
"""Hard cap on label/line-tip radius so labels stay inside the fixed axes
box regardless of pT -- without this, high-pT leptons/MET can render their
labels outside the visible plot area."""


def _eta_to_theta(eta: float) -> float:
    return 2.0 * math.atan(math.exp(-eta))


def _dir2d(eta: float, phi: float):
    theta = _eta_to_theta(eta)
    st, ct = math.sin(theta), math.cos(theta)
    ux, uz = st * math.cos(phi), ct
    return float(uz), float(ux)  # beam (z) -> horizontal; transverse x -> vertical


def _normalize(vx, vy):
    n = math.hypot(vx, vy)
    return (0.0, 0.0) if n <= 0 else (vx / n, vy / n)


def _draw_cone_2d(ax, dirx, diry, length, half_width, color, alpha=0.35):
    dx, dy = _normalize(dirx, diry)
    bx, by = dx * length, dy * length
    nx, ny = -dy, dx
    x1, y1 = bx + nx * half_width, by + ny * half_width
    x2, y2 = bx - nx * half_width, by - ny * half_width
    ax.fill([0.0, x1, x2], [0.0, y1, y2], alpha=alpha, color=color, linewidth=0)


def _pt_ref(event: Event) -> float:
    pts = [o.pt for o in event.jets + event.muons + event.electrons + event.photons]
    if event.met is not None:
        pts.append(event.met.pt)
    if not pts:
        return 1.0
    arr = np.array(pts, dtype=float)
    return max(float(np.percentile(arr, 95)) if len(arr) > 4 else float(arr.max()), 1.0)


def _scale_length(pt, pt_ref, lmin=0.35, lmax=1.0):
    frac = min(max(pt / pt_ref, 0.0), 1.0)
    return lmin + frac * (lmax - lmin)


def _scale_width(pt, pt_ref, wmax=0.30, wmin=0.06):
    frac = min(max(pt / pt_ref, 0.0), 1.0)
    return wmax - frac * (wmax - wmin)


def plot_event_beam2d(
    event: Event,
    *,
    ax: Optional["plt.Axes"] = None,
    eta_guides: Sequence[float] = (2.5, 4.0),
    angle_scale: float = 4.0,
    title: Optional[str] = None,
):
    """Draw one event's beam-axis (Z) vs. transverse-coordinate projection.

    Returns
    -------
    matplotlib.figure.Figure
    """
    if ax is None:
        fig, ax = plt.subplots(figsize=(12, 8))
    else:
        fig = ax.figure

    if title is None:
        parts = [p for p in (event.label, f"Event# {event.event_number}"
                              if event.event_number is not None else None) if p]
        title = " ".join(parts) if parts else "Beam-axis event display"
    ax.set_title(title)
    ax.set_xlabel("Beam axis (Z)")
    ax.set_xticks([])
    ax.set_ylabel("Transverse projection")

    ax.annotate("", xy=(XLIM - 0.05, 0), xytext=(-(XLIM - 0.05), 0),
                arrowprops=dict(arrowstyle="->", color="black", lw=2, alpha=0.5))

    eta_colors = ["#444444", "#7a3b2e"]
    for i, eta in enumerate(eta_guides):
        theta = _eta_to_theta(eta)
        theta_scaled = min(theta * angle_scale, math.pi / 2 * 0.98)
        m = math.tan(theta_scaled)
        color = eta_colors[i % len(eta_colors)]
        for sgn in (+1, -1):
            xs = np.array([-XLIM, XLIM])
            ax.plot(xs, sgn * m * xs, linestyle="--", linewidth=2, color=color, alpha=0.3)
        ax.text(0.86, 0.08 + i * 0.05, rf"$\eta = {eta}$", transform=ax.transAxes,
                fontsize=12, color=color, bbox=dict(facecolor="white", alpha=0.85, edgecolor="none"))

    pt_ref = _pt_ref(event)

    for typ, objs in [("jet", event.light_jets), ("bjet", event.bjets)]:
        color = DEFAULT_COLORS[typ]
        for idx, o in enumerate(objs, start=1):
            dx, dy = _dir2d(o.eta, o.phi)
            length = _scale_length(o.pt, pt_ref)
            width = min(_scale_width(o.pt, pt_ref), length * 0.4)
            _draw_cone_2d(ax, dx, dy, length, width, color)
            tx, ty = _normalize(dx, dy)
            ax.text(tx * length * 1.05, ty * length * 1.05,
                    f"{typ.capitalize()} {idx}\npT={o.pt:.1f} GeV\nη={o.eta:.2f}",
                    color=color, fontsize=8, ha="center", va="center")

    for typ, objs, key in [("muon", event.muons, "muon"), ("electron", event.electrons, "electron"),
                            ("photon", event.photons, "photon")]:
        color = DEFAULT_COLORS[key]
        for idx, o in enumerate(objs, start=1):
            dx, dy = _dir2d(o.eta, o.phi)
            length = min(_scale_length(o.pt, pt_ref) * 3.0, LABEL_MAX_R)
            ax.plot([0, dx * length], [0, dy * length], linestyle="--", linewidth=2, color=color)
            ax.text(dx * length * 1.05, dy * length * 1.05,
                    f"{typ.capitalize()} {idx}\npT={o.pt:.1f} GeV\nη={o.eta:.2f}",
                    color=color, fontsize=8, ha="center", va="center")

    if event.met is not None and event.met.pt > 0:
        color = DEFAULT_COLORS["met"]
        length = min(_scale_length(event.met.pt, pt_ref) * 1.5, LABEL_MAX_R)
        mx, my = _normalize(0.0, math.cos(event.met.phi))
        ax.arrow(0, 0, mx * length, my * length, length_includes_head=True,
                  head_width=0.03, head_length=0.06, color=color)
        ax.text(mx * length * 1.05, my * length * 1.05, f"MET\npT={event.met.pt:.1f} GeV",
                color=color, fontsize=9, ha="center", va="center")

    handles = [
        plt.Line2D([0], [0], color=DEFAULT_COLORS["jet"], linewidth=8, label="jet (cone, pT-scaled)"),
        plt.Line2D([0], [0], color=DEFAULT_COLORS["bjet"], linewidth=8, label="b-jet (cone, pT-scaled)"),
        plt.Line2D([0], [0], color=DEFAULT_COLORS["electron"], linestyle="--", linewidth=2, label="electron"),
        plt.Line2D([0], [0], color=DEFAULT_COLORS["muon"], linestyle="--", linewidth=2, label="muon"),
        plt.Line2D([0], [0], color=DEFAULT_COLORS["photon"], linestyle="--", linewidth=2, label="photon"),
        plt.Line2D([0], [0], color=DEFAULT_COLORS["met"], linewidth=2, label="MET (arrow, pT)"),
    ]
    ax.legend(handles=handles, loc="upper left", fontsize=9)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-XLIM, XLIM)
    ax.set_ylim(-YLIM, YLIM)
    ax.grid(True, linestyle="--", alpha=0.35)
    fig.tight_layout()
    return fig
