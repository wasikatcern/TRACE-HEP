"""Polar (phi, |eta|) event display.

Azimuthal angle phi maps to the polar angle of the plot; pseudorapidity
|eta| maps to radius, with central objects (|eta|=0) at the outer ring and
forward objects near the centre -- the centre of the plot represents the
beam axis itself. Jets are drawn as filled cones whose angular width scales
inversely with pT; leptons and photons as radial lines; MET as a labelled
arrow. Reconstructed tracks are optional and, when a displacement threshold
is given, coloured to separate prompt tracks from displaced ones (see
Track.d0 in :mod:`tracehep.models`).

Developed by Wasikul Islam, PhD.
"""

import math
from typing import Optional, Sequence

import matplotlib.pyplot as plt
import numpy as np

from .colors import DEFAULT_COLORS, TRACK_COLOR, DISPLACED_COLOR, type_title
from .models import Event

__all__ = ["plot_event_polar", "eta_to_radius", "eta_to_theta_deg"]


def eta_to_radius(abs_eta: float, eta_max: float, r_max: float = 1.0) -> float:
    """Linear |eta| -> radius map: 0 at |eta|=0 maps to r_max (outer ring),
    |eta|>=eta_max maps to 0 (centre, i.e. the beam axis)."""
    a = min(abs(abs_eta), eta_max)
    return r_max * (eta_max - a) / eta_max


def eta_to_theta_deg(abs_eta: float) -> float:
    """Polar angle [deg] of a particle at this |eta| relative to the beam axis."""
    return 2.0 * math.degrees(math.atan(math.exp(-abs(abs_eta))))


def _draw_polar_cone(ax, theta, r_tip, pt, color, *,
                      cone_min=0.06, cone_max=0.40, cone_k=10.0, max_dtheta=0.6):
    pt = max(1e-6, float(pt))
    base = max(cone_min, min(cone_k / pt, cone_max))
    dtheta = min(base / max(r_tip, 1e-6), max_dtheta)
    thetas = [theta, theta - 0.5 * dtheta, theta + 0.5 * dtheta]
    rs = [0.0, r_tip, r_tip]
    ax.fill(thetas, rs, facecolor=color, edgecolor=color, linewidth=1.2, alpha=0.28, zorder=4)


def plot_event_polar(
    event: Event,
    *,
    ax: Optional["plt.Axes"] = None,
    eta_max: float = 4.0,
    pt_scale: float = 0.003,
    eta_guides: Sequence[float] = (0, 1, 2.5, 4.0),
    show_tracks: bool = False,
    track_pt_scale: float = 0.15,
    d0_displaced_mm: Optional[float] = None,
    title: Optional[str] = None,
):
    """Draw one event on a polar (phi, |eta|) axes.

    Parameters
    ----------
    event:
        The event to draw.
    ax:
        An existing polar-projection matplotlib Axes to draw into. If
        omitted, a new figure+axes is created.
    show_tracks:
        Also draw event.tracks as thin background lines.
    d0_displaced_mm:
        If given (and show_tracks=True), tracks with |Track.d0| above this
        threshold [mm] are drawn in a distinct accent colour instead of the
        flat background colour, and the legend reports both counts.
    title:
        Plot title. Defaults to a string built from event.label /
        event.event_number if omitted.

    Returns
    -------
    matplotlib.figure.Figure
    """
    R_max = 1.0
    if ax is None:
        fig = plt.figure(figsize=(8, 8), dpi=140)
        ax = fig.add_subplot(111, projection="polar")
    else:
        fig = ax.figure

    ax.set_theta_zero_location("E")
    ax.set_theta_direction(1)
    ax.set_rmax(R_max * 1.02)
    ax.set_rticks([])
    ax.grid(alpha=0.15, linestyle=":")

    for g in sorted(set(abs(v) for v in eta_guides), reverse=True):
        r_g = eta_to_radius(g, eta_max, R_max)
        ax.plot(np.linspace(0, 2 * np.pi, 361), np.full(361, r_g), color="gray", alpha=0.35, lw=0.8)
        ax.text(math.radians(10), r_g + 0.012, f"|η|={g:g} (θ≈{eta_to_theta_deg(g):.0f}°)",
                fontsize=8, ha="left", va="bottom", color="gray")

    if title is None:
        parts = [p for p in (event.label, f"Event# {event.event_number}"
                              if event.event_number is not None else None) if p]
        title = " ".join(parts) if parts else "Event display"
    ax.set_title(title, pad=14)

    track_handles = []
    if show_tracks and event.tracks:
        if d0_displaced_mm is not None:
            prompt = [t for t in event.tracks if abs(t.d0) <= d0_displaced_mm]
            displaced = [t for t in event.tracks if abs(t.d0) > d0_displaced_mm]
        else:
            prompt, displaced = list(event.tracks), []

        for tr in prompt:
            r_eta = eta_to_radius(abs(tr.eta), eta_max, R_max)
            r_len = min(track_pt_scale * tr.pt, r_eta)
            ax.plot([tr.phi, tr.phi], [0, r_len], color=TRACK_COLOR, lw=1.0, alpha=0.55, zorder=1)
        track_handles.append(
            ax.plot([], [], color=TRACK_COLOR, lw=1.5, label=f"Prompt tracks (n={len(prompt)})")[0])

        if displaced:
            for tr in displaced:
                r_eta = eta_to_radius(abs(tr.eta), eta_max, R_max)
                r_len = min(track_pt_scale * tr.pt, r_eta)
                ax.plot([tr.phi, tr.phi], [0, r_len], color=DISPLACED_COLOR, lw=2.2, alpha=0.95, zorder=3)
                ax.plot([tr.phi], [r_len], marker="o", color=DISPLACED_COLOR, markersize=4, zorder=4)
            track_handles.append(ax.plot(
                [], [], color=DISPLACED_COLOR, lw=2.2,
                label=fr"Displaced tracks (n={len(displaced)}, $|d_0|>${d0_displaced_mm:g} mm)")[0])

    if event.met is not None and event.met.pt > 0:
        m = event.met
        r_met = min(pt_scale * m.pt, R_max)
        ax.annotate("", xy=(m.phi, r_met), xytext=(m.phi, 0),
                    arrowprops=dict(arrowstyle="-|>", color=DEFAULT_COLORS["met"], lw=2.0,
                                     alpha=0.9, shrinkA=0, shrinkB=0, mutation_scale=14), zorder=5)
        label_ha = "left" if math.cos(m.phi) >= 0 else "right"
        ax.text(m.phi + math.radians(3 if label_ha == "left" else -3), r_met + 0.05 * R_max,
                f"MET\n pT={m.pt:.0f} GeV\n φ={math.degrees(m.phi):.0f}°",
                fontsize=9, ha=label_ha, va="bottom", color=DEFAULT_COLORS["met"], zorder=5)

    handles = {}
    groups = [
        ("jet", event.light_jets, DEFAULT_COLORS["jet"]),
        ("bjet", event.bjets, DEFAULT_COLORS["bjet"]),
        ("muon", event.muons, DEFAULT_COLORS["muon"]),
        ("electron", event.electrons, DEFAULT_COLORS["electron"]),
        ("photon", event.photons, DEFAULT_COLORS["photon"]),
    ]
    for typ, objs, color in groups:
        if not objs:
            continue
        for idx, o in enumerate(objs, start=1):
            r_eta = eta_to_radius(abs(o.eta), eta_max, R_max)
            r_len = min(pt_scale * o.pt, r_eta)
            theta = o.phi
            if typ in ("jet", "bjet"):
                _draw_polar_cone(ax, theta, r_len, o.pt, color)
            else:
                ax.plot([theta, theta], [0, r_len], color=color, lw=2.0, alpha=0.95,
                        linestyle="--" if typ in ("muon", "electron") else "-", zorder=4)
            ax.text(theta, r_eta + 0.015, f"{type_title(typ)} {idx}\n pT={o.pt:.0f} GeV\n η={abs(o.eta):.2f}",
                    fontsize=8, ha="center", va="bottom", color=color, zorder=4)
        handles[typ] = ax.plot([], [], color=color, lw=2.0,
                                linestyle="--" if typ in ("muon", "electron") else "-",
                                label=type_title(typ))[0]

    ax.legend(handles=track_handles + list(handles.values()), loc="upper left",
              bbox_to_anchor=(1.02, 1.02), frameon=True, fontsize=9)
    fig.tight_layout()
    return fig
