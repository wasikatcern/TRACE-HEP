"""Validated colour palette shared by every drawer in tracehep.

Named/individually-identified physics objects (jets, b-jets, muons,
electrons, photons, MET) each get one fixed, mutually-distinct hue.
Background tracks get a single flat neutral colour so a busy event's ~100+
tracks read as supporting texture rather than competing with the
individually-labelled objects for attention.

Developed by Wasikul Islam, PhD.
"""

DEFAULT_COLORS = {
    "jet": "#1f77b4",
    "bjet": "#9467bd",
    "muon": "#2ca02c",
    "electron": "#ff7f0e",
    "photon": "#d62728",
    "met": "#0b0b0b",
}

TRACK_COLOR = "#9a9a9a"
"""Flat neutral colour for prompt (non-highlighted) tracks."""

DISPLACED_COLOR = "#e34948"
"""Accent colour for tracks flagged as displaced (large |d0|), or any
other highlighted subset a caller wants picked out from the background."""


def type_title(typ: str) -> str:
    """Human-readable label for an object-type key, e.g. "bjet" -> "Bjet"."""
    return "Bjet" if typ == "bjet" else typ.capitalize()
