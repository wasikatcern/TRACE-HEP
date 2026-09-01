"""``trace-gui``: a small local web app for interactively browsing event
and vertex displays -- point it at a file, type an event number, pick a
display, and it renders live in your browser. No pre-rendering, no
scripting: this is the "just let me look at one event" tool.

It also has two gallery modes built in, both using :mod:`tracehep.gallery`
under the hood and rendering every event on demand into a browsable,
filterable gallery right inside the GUI (with a one-click "Save full
gallery as .html" for the whole self-contained page) -- no separate
script needed:

- **Many events**: just a plain list of event numbers, e.g.
  ``1, 2, 4-6`` -- for "let me look at a batch of events", with no
  categorization dimension at all.
- **Failure-mode gallery**: the events come with a category -- two
  algorithms' pass/fail lists (built into the
  ``both_pass``/``both_fail``/disagreement 4-way split via
  :func:`tracehep.gallery.compare_pass_fail`), free-text custom labels
  (for an anomaly-detection bucket, say), or **auto-flag**: give it an
  event range (e.g. ``1-200``), pick one of eleven built-in criteria
  (Delta-phi(MET, closest jet); the standard SUSY-style min-Delta-phi
  among the leading 4 jets; MET/H_T; MET; H_T; jet/b-jet/lepton
  multiplicity; leading-jet p_T; dijet back-to-back deviation; or max
  displaced-track |d0|, an LLP signature), and a threshold with an
  above/below direction, and it loads every event in the range, computes
  the metric itself, and sorts events into "flagged"/"not flagged" with
  no pass/fail list to prepare by hand -- the same off-axis-MET
  diagnostic developed in the accompanying paper's debugging case study,
  generalized to a small library of standard HEP event-selection
  variables, all as a real, scriptless GUI feature rather than a
  one-off analysis script (see :data:`_FLAG_CRITERIA` for the full list).

Covers every loader tracehep ships: Delphes, flat-ntuple, ATLAS Open Data,
CMS Open Data, and one unified "Vertex display" loader that auto-detects
which vertex-ntuple format a file actually is (calo-timing-style or
PHYSLITE-style) by checking for each format's signature branch, rather
than requiring the format to be picked in advance -- so the same dropdown
entry handles a calo-timing ntuple, a PHYSLITE derivation, or (as long as
it carries one of those two known signature branches) a file with less
complete information than either reference format. Every display type is
covered, both matplotlib (2D) and plotly (interactive 3D), and every
rendered image/view has a "Download image" button -- for 2D this saves
the PNG directly; for 3D it uses Plotly's own ``downloadImage`` to capture
the *current* camera angle, not just a default view.

``path`` can be a local file or, for the loaders that support it (CMS Open
Data, ATLAS Open Data, Vertex display), a remote ``https://...`` URL,
streamed the same way as everywhere else in tracehep. Every "File path or
URL" field also has an "Or upload a .root file" button, for when trace-gui
is running as a shared server rather than on your own laptop -- a remote
visitor's browser has no way to hand the server a local path, so it
uploads the bytes instead (capped at 150 MB, auto-deleted after about an
hour; see ``deploy/huggingface-space/`` in the repo for one way to host
it publicly).

Requires the ``gui`` extra: ``pip install trace-hep[gui]`` (adds Flask,
the only new dependency this introduces -- the core library still never
requires it).

Run with ``trace-gui`` (installed console script) or
``python -m tracehep.webapp``.

Developed by Wasikul Islam, PhD.
"""

import argparse
import base64
import io
import math
import os
import re
import shutil
import socket
import tempfile
import threading
import time
import traceback
import uuid
import webbrowser

import matplotlib
matplotlib.use("Agg")  # must happen before any figure is created -- a server
# request isn't the main thread, and matplotlib's default GUI backend
# (e.g. macosx) crashes the whole process if a figure is built off it.

__all__ = ["create_app", "main"]


def _require_flask():
    try:
        from flask import Flask  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "tracehep.webapp requires Flask. Install with: pip install trace-hep[gui]"
        ) from exc


def _fig_response(fig):
    """Turn a matplotlib or plotly figure into a JSON-able payload."""
    if hasattr(fig, "savefig"):
        import matplotlib.pyplot as plt
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
        plt.close(fig)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return {"kind": "image", "data": f"data:image/png;base64,{b64}"}
    elif hasattr(fig, "to_html"):
        html = fig.to_html(full_html=False, include_plotlyjs="cdn",
                            config={"displaylogo": False})
        return {"kind": "html", "data": html}
    raise TypeError(f"Don't know how to render a {type(fig)!r} (expected a matplotlib or plotly figure)")


def _make_event_fig(event, display, *, show_tracks, d0_displaced_mm):
    import tracehep as trace
    if display == "polar":
        return trace.plot_event_polar(event, show_tracks=show_tracks,
                                       d0_displaced_mm=d0_displaced_mm or None)
    if display == "beam2d":
        return trace.plot_event_beam2d(event)
    if display == "3d":
        return trace.plot_event_3d(event, d0_displaced_mm=d0_displaced_mm or None)
    raise ValueError(f"display {display!r} is not valid for an event-level loader")


def _make_vertex_fig(vertex_event, display, *, vertex_index, jets):
    import tracehep as trace
    if display == "vertices_plain":
        return trace.plot_vertices_zr(vertex_event, style="plain")
    if display == "vertices_styled":
        return trace.plot_vertices_zr(vertex_event, style="styled")
    if display == "vertices_time_colored":
        return trace.plot_vertices_zr(vertex_event, style="time_colored")
    if display == "vertices_3d":
        return trace.plot_vertices_3d(vertex_event)
    if display == "vertex_detail":
        return trace.plot_vertex_detail(vertex_event, vtx_index=vertex_index, jets=jets)
    raise ValueError(f"display {display!r} is not valid for a vertex-level loader")


def _make_manual_event(payload):
    from .models import Event, Jet, Lepton, MissingET, Photon

    jets = [Jet(pt=float(j["pt"]), eta=float(j["eta"]), phi=float(j["phi"]),
                mass=float(j.get("mass") or 0), btag=bool(j.get("btag")))
            for j in payload.get("manual_jets", [])]
    muons = [Lepton(pt=float(m["pt"]), eta=float(m["eta"]), phi=float(m["phi"]), flavor="muon")
             for m in payload.get("manual_muons", [])]
    electrons = [Lepton(pt=float(e["pt"]), eta=float(e["eta"]), phi=float(e["phi"]), flavor="electron")
                 for e in payload.get("manual_electrons", [])]
    photons = [Photon(pt=float(p["pt"]), eta=float(p["eta"]), phi=float(p["phi"]))
               for p in payload.get("manual_photons", [])]
    met = None
    if payload.get("manual_met_pt"):
        met = MissingET(pt=float(payload["manual_met_pt"]), phi=float(payload.get("manual_met_phi") or 0))
    return Event(jets=jets, muons=muons, electrons=electrons, photons=photons, met=met, label="Hand-built event")


def _detect_vertex_format(path, tree_name_hint=None):
    """Figure out which vertex-ntuple format a file actually is, by looking
    for each known format's signature branch -- rather than requiring the
    caller to know in advance whether a file is a calo-timing ntuple or a
    PHYSLITE derivation. Tries ``tree_name_hint`` first if given, then every
    tree in the file.

    Returns
    -------
    (format, tree_name) -- format is ``"physlite"`` or ``"calotiming"``.

    Raises
    ------
    ValueError if no known signature branch is found in any tree, listing
    what was actually checked so a real error is diagnosable rather than a
    generic "branch not found" deep inside a loader.
    """
    uproot = _require_uproot_for_detection()
    f = uproot.open(path)
    tree_names = list(dict.fromkeys(k.split(";")[0] for k in f.keys()))
    ordered = ([tree_name_hint] if tree_name_hint else []) + tree_names

    checked = []
    for name in ordered:
        if not name or name in checked:
            continue
        checked.append(name)
        try:
            available = set(f[name].keys())
        except Exception:
            continue
        if "PrimaryVerticesAuxDyn.x" in available:
            return "physlite", name
        if "RecoVtx_z" in available:
            return "calotiming", name

    raise ValueError(
        f"Could not find a recognized vertex format in {path!r}. Checked tree(s): "
        f"{checked or 'none'}. Expected either 'PrimaryVerticesAuxDyn.x' (a PHYSLITE-style "
        f"file) or 'RecoVtx_z' (a calo-timing-style ntuple) in one of them."
    )


def _require_uproot_for_detection():
    try:
        import uproot
    except ImportError as exc:
        raise ImportError(
            "The Vertex display loader requires uproot. Install with: pip install trace-hep[delphes]"
        ) from exc
    return uproot


def _load_object(payload):
    """Load whatever ``payload['loader']``/``payload['path']`` points at,
    without drawing it. Returns ``("event", event)`` or
    ``("vertex", (vertex_event, vertex_index, jets))``. Factored out of
    :func:`_load_figure` so a caller can inspect physics quantities on the
    loaded object -- e.g. Δφ(MET, closest jet) for auto-flagging -- before
    deciding whether/how to draw it, without loading the same event twice."""
    loader = payload["loader"]
    jet_collection = (payload.get("jet_collection") or "").strip() or None

    if loader == "manual":
        return "event", _make_manual_event(payload)

    path = payload["path"]
    event_index = int(payload["event_index"])

    if loader == "delphes":
        from .io.delphes import load_event
        kwargs = {"with_tracks": True}
        if jet_collection:
            kwargs["jet_collection"] = jet_collection
        return "event", load_event(path, event_index, **kwargs)

    if loader == "flat_ntuple":
        from .io.flat_ntuple import load_event_by_run_event
        run_number = int(payload["run_number"])
        return "event", load_event_by_run_event(path, run_number, event_index)

    if loader == "atlas_opendata":
        from .io.atlas_opendata import load_events
        event = load_events(path, [event_index],
                             include_large_r_jets=bool(payload.get("include_large_r_jets")))[event_index]
        return "event", event

    if loader == "cms_opendata":
        from .io.cms_opendata import load_events
        event = load_events(path, [event_index])[event_index]
        return "event", event

    if loader == "vertex":
        display = payload.get("display")
        tree_name_hint = (payload.get("tree_name") or "").strip() or None
        fmt, detected_tree = _detect_vertex_format(path, tree_name_hint)
        vertex_index = int(payload.get("vertex_index") or 0)
        jets = []

        if fmt == "physlite":
            from .io.atlas_physlite import load_vertex_event, load_event_jets
            vertex_event = load_vertex_event(path, event_index, tree_name=detected_tree)
            if display == "vertex_detail":
                jets = load_event_jets(path, event_index, tree_name=detected_tree)
        else:  # "calotiming"
            from .io.calotiming import load_vertex_event, match_jets_to_vertex
            vertex_event = load_vertex_event(path, event_index, tree_name=detected_tree)
            if display == "vertex_detail":
                kwargs = {}
                if jet_collection:
                    kwargs["jet_collection"] = jet_collection
                jets = match_jets_to_vertex(path, event_index, vertex_event.vertices[vertex_index].z,
                                             tree_name=detected_tree, **kwargs)

        return "vertex", (vertex_event, vertex_index, jets)

    raise ValueError(f"unknown loader {loader!r}")


def _event_display_kwargs(payload):
    """``show_tracks``/``d0_displaced_mm`` only apply to the Delphes loader
    (the only one that carries a Track collection); every other event-level
    loader ignores them, matching the single-event viewer's behavior."""
    if payload.get("loader") == "delphes":
        show_tracks = bool(payload.get("show_tracks"))
        d0_displaced_mm = float(payload["d0_displaced_mm"]) if payload.get("d0_displaced_mm") else None
        return show_tracks, d0_displaced_mm
    return False, None


def _load_figure(payload):
    """Load whatever ``payload['loader']`` points at and render the requested
    ``payload['display']``, returning the raw matplotlib/plotly figure.
    Shared by the single-event viewer (:func:`_dispatch`) and the
    gallery builder (:func:`_build_gallery_html`), which calls this once
    per event id."""
    display = payload["display"]
    kind, obj = _load_object(payload)
    if kind == "event":
        show_tracks, d0_displaced_mm = _event_display_kwargs(payload)
        return _make_event_fig(obj, display, show_tracks=show_tracks, d0_displaced_mm=d0_displaced_mm)
    vertex_event, vertex_index, jets = obj
    return _make_vertex_fig(vertex_event, display, vertex_index=vertex_index, jets=jets)


def _dispatch(payload):
    return _fig_response(_load_figure(payload))


def _dphi(phi1, phi2):
    """Smallest absolute angular separation between two phi values, in [0, pi]."""
    d = abs(phi1 - phi2) % (2 * math.pi)
    return min(d, 2 * math.pi - d)


def _leading(objs, n=None):
    """Objects sorted by descending pT, optionally truncated to the
    leading ``n``."""
    ordered = sorted(objs, key=lambda o: -o.pt)
    return ordered[:n] if n is not None else ordered


# Every auto-flag criterion: a metric computed from one Event, plus enough
# metadata to render the GUI control and a readable category label. Each
# ``compute`` returns None when the metric can't be evaluated for a given
# event (missing MET, too few jets, no track collection, ...) -- such
# events are skipped from the gallery entirely, the same as the original
# Δφ(MET, closest jet) criterion, rather than being miscategorized.
_FLAG_CRITERIA = {
    "dphi_met_jet": {
        "label": "Δφ(MET, closest jet)",
        "unit": "rad",
        "default_threshold": 0.5,
        "default_direction": "above",
        "needs": "MET and ≥ 1 jet",
        "compute": lambda ev: (
            None if ev.met is None or not ev.jets
            else min(_dphi(ev.met.phi, j.phi) for j in ev.jets)
        ),
    },
    "min_dphi_leading4": {
        "label": "min Δφ(MET, jet) among leading 4 jets",
        "unit": "rad",
        "default_threshold": 0.4,
        "default_direction": "below",
        "needs": "MET and ≥ 1 jet",
        "compute": lambda ev: (
            None if ev.met is None or not ev.jets
            else min(_dphi(ev.met.phi, j.phi) for j in _leading(ev.jets, 4))
        ),
    },
    "met_over_ht": {
        "label": "MET / H_T (scalar sum jet p_T)",
        "unit": "",
        "default_threshold": 0.3,
        "default_direction": "above",
        "needs": "MET and ≥ 1 jet",
        "compute": lambda ev: (
            None if ev.met is None or not ev.jets or sum(j.pt for j in ev.jets) <= 0
            else ev.met.pt / sum(j.pt for j in ev.jets)
        ),
    },
    "met_pt": {
        "label": "MET",
        "unit": "GeV",
        "default_threshold": 200.0,
        "default_direction": "above",
        "needs": "MET",
        "compute": lambda ev: None if ev.met is None else ev.met.pt,
    },
    "ht": {
        "label": "H_T (scalar sum jet p_T)",
        "unit": "GeV",
        "default_threshold": 500.0,
        "default_direction": "above",
        "needs": "≥ 1 jet",
        "compute": lambda ev: None if not ev.jets else sum(j.pt for j in ev.jets),
    },
    "n_jets": {
        "label": "Number of jets",
        "unit": "",
        "default_threshold": 6.0,
        "default_direction": "above",
        "needs": "always computable",
        "compute": lambda ev: float(len(ev.jets)),
    },
    "n_bjets": {
        "label": "Number of b-tagged jets",
        "unit": "",
        "default_threshold": 2.0,
        "default_direction": "above",
        "needs": "always computable",
        "compute": lambda ev: float(len(ev.bjets)),
    },
    "leading_jet_pt": {
        "label": "Leading jet p_T",
        "unit": "GeV",
        "default_threshold": 300.0,
        "default_direction": "above",
        "needs": "≥ 1 jet",
        "compute": lambda ev: None if not ev.jets else max(j.pt for j in ev.jets),
    },
    "dijet_dphi_balance": {
        "label": "|π − Δφ(jet1, jet2)| (deviation from back-to-back)",
        "unit": "rad",
        "default_threshold": 0.5,
        "default_direction": "above",
        "needs": "≥ 2 jets",
        "compute": lambda ev: (
            None if len(ev.jets) < 2
            else abs(math.pi - _dphi(_leading(ev.jets, 2)[0].phi, _leading(ev.jets, 2)[1].phi))
        ),
    },
    "max_track_d0": {
        "label": "Max |d0| among tracks (displaced-track / LLP signature)",
        "unit": "mm",
        "default_threshold": 1.0,
        "default_direction": "above",
        "needs": "≥ 1 track (Delphes/calo-timing only)",
        "compute": lambda ev: None if not ev.tracks else max(abs(t.d0) for t in ev.tracks),
    },
    "n_leptons": {
        "label": "Number of leptons (muons + electrons)",
        "unit": "",
        "default_threshold": 2.0,
        "default_direction": "above",
        "needs": "always computable",
        "compute": lambda ev: float(len(ev.leptons)),
    },
}


def _flag_metric(criterion, event):
    """Compute the named auto-flag criterion's metric for one event, or
    raise a clear error for an unknown criterion name."""
    spec = _FLAG_CRITERIA.get(criterion)
    if spec is None:
        raise ValueError(
            f"unknown auto-flag criterion {criterion!r}; choose one of: "
            f"{', '.join(sorted(_FLAG_CRITERIA))}"
        )
    return spec["compute"](event)


_MAX_GALLERY_EVENTS = 300


def _parse_id_list(text):
    """Parse a comma/whitespace/newline-separated list of event ids, e.g.
    from a textarea like ``"12, 45\\n88"``."""
    return [int(tok) for tok in re.split(r"[,\s]+", (text or "").strip()) if tok]


def _parse_id_range_list(text):
    """Like :func:`_parse_id_list`, but each token may also be an inclusive
    range ``"a-b"`` -- e.g. ``"1, 2, 4-6"`` -> ``[1, 2, 4, 5, 6]``. Used by
    the "Many events" gallery mode, where there's no pass/fail/label
    distinction, just a plain list of event numbers to look at."""
    ids = []
    for tok in re.split(r"[,\s]+", (text or "").strip()):
        if not tok:
            continue
        if "-" in tok and not tok.startswith("-"):
            start_str, end_str = tok.split("-", 1)
            start, end = int(start_str), int(end_str)
            step = 1 if end >= start else -1
            ids.extend(range(start, end + step, step))
        else:
            ids.append(int(tok))
    return ids


def _parse_custom_categories(text):
    """Parse ``"event_id: label"`` (or ``"event_id, label"``) lines, one per
    event, into a :func:`~tracehep.gallery.build_gallery`-ready dict."""
    categories = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        sep = ":" if ":" in line else ("," if "," in line else None)
        if sep is None:
            continue
        eid_str, label = line.split(sep, 1)
        eid_str, label = eid_str.strip(), label.strip()
        if eid_str and label:
            categories[int(eid_str)] = label
    return categories


def _build_gallery_html(payload):
    """Build a failure-mode/anomaly-review gallery (see
    :mod:`tracehep.gallery`) from a webapp form payload. Returns the
    self-contained gallery HTML as a string.

    Every ``category_mode`` except ``"auto_flag"`` decides each event's
    category from the form input alone, then loads/draws the events
    (:func:`_load_figure`) in a second pass. ``"auto_flag"`` is different --
    the category (flagged/not flagged) depends on a physics quantity
    computed from the loaded event itself (Δφ(MET, closest jet), the same
    diagnostic developed in the accompanying paper's debugging case study),
    so loading and categorizing happen together, one event at a time, so
    each event is only fetched once."""
    from .gallery import build_gallery, compare_pass_fail

    category_mode = payload.get("category_mode", "compare")
    captions = None

    if category_mode == "auto_flag":
        criterion = payload.get("flag_criterion") or "dphi_met_jet"
        spec = _FLAG_CRITERIA.get(criterion)
        if spec is None:
            raise ValueError(
                f"unknown auto-flag criterion {criterion!r}; choose one of: "
                f"{', '.join(sorted(_FLAG_CRITERIA))}"
            )
        if payload.get("loader") == "vertex":
            raise ValueError(
                f"Auto-flagging by {spec['label']} needs an event-level loader "
                "(Delphes, flat-ntuple, ATLAS/CMS Open Data, or a hand-built event) -- the "
                "Vertex display loader has no jets, leptons, or MET to compute it from."
            )
        threshold = float(payload.get("flag_threshold") if payload.get("flag_threshold") not in (None, "")
                           else spec["default_threshold"])
        direction = payload.get("flag_direction") or spec["default_direction"]
        if direction not in ("above", "below"):
            raise ValueError(f"flag_direction must be 'above' or 'below', got {direction!r}")
        event_ids = _parse_id_range_list(payload.get("event_list"))
        if not event_ids:
            raise ValueError(
                "No event ids to scan -- fill in the event range (e.g. \"1-200\")."
            )
        if len(event_ids) > _MAX_GALLERY_EVENTS:
            raise ValueError(
                f"{len(event_ids)} events requested, above the {_MAX_GALLERY_EVENTS}-event safety "
                f"cap for the live viewer (each is loaded and scanned on demand in this one "
                f"request). Narrow the range, or use tracehep directly from a script for larger scans."
            )

        unit_suffix = f" {spec['unit']}" if spec["unit"] else ""
        cmp_symbol = ">" if direction == "above" else "<"
        events, categories, captions = {}, {}, {}
        skipped = 0
        for eid in event_ids:
            per_event_payload = dict(payload)
            per_event_payload["event_index"] = eid
            kind, obj = _load_object(per_event_payload)
            if kind != "event":
                raise ValueError("auto-flagging requires an event-level loader")
            value = _flag_metric(criterion, obj)
            if value is None:
                skipped += 1
                continue
            is_flagged = (value > threshold) if direction == "above" else (value < threshold)
            show_tracks, d0_displaced_mm = _event_display_kwargs(per_event_payload)
            events[eid] = _make_event_fig(obj, payload["display"], show_tracks=show_tracks,
                                           d0_displaced_mm=d0_displaced_mm)
            categories[eid] = (f"flagged ({spec['label']} {cmp_symbol} {threshold:g}{unit_suffix})"
                                if is_flagged else "not flagged")
            captions[eid] = f"{spec['label']} = {value:.3f}{unit_suffix}"

        if not categories:
            raise ValueError(
                f"None of the {len(event_ids)} scanned event(s) had enough information to "
                f"compute {spec['label']} (needs {spec['needs']})."
            )
        n_flagged = sum(1 for c in categories.values() if c.startswith("flagged"))
        skip_note = f", {skipped} skipped ({spec['needs']} not available)" if skipped else ""
        default_title = f"Auto-flagged review ({n_flagged}/{len(categories)} events flagged{skip_note})"
    elif category_mode == "list":
        categories = {eid: "event" for eid in _parse_id_range_list(payload.get("event_list"))}
        default_title = "TRACE Failure-Mode Review"
    elif category_mode == "custom":
        categories = _parse_custom_categories(payload.get("custom_categories"))
        default_title = "TRACE Failure-Mode Review"
    else:
        name_a = (payload.get("name_a") or "").strip() or "algo1"
        name_b = (payload.get("name_b") or "").strip() or "algo2"
        results_a = {eid: True for eid in _parse_id_list(payload.get("a_pass"))}
        results_a.update({eid: False for eid in _parse_id_list(payload.get("a_fail"))})
        results_b = {eid: True for eid in _parse_id_list(payload.get("b_pass"))}
        results_b.update({eid: False for eid in _parse_id_list(payload.get("b_fail"))})
        categories = compare_pass_fail(results_a, results_b, name_a=name_a, name_b=name_b)
        default_title = "TRACE Failure-Mode Review"

    if not categories:
        raise ValueError(
            "No event ids to build a gallery from -- fill in the event list (or the "
            "pass/fail lists, or the custom label list) with at least one event id."
        )

    if category_mode != "auto_flag":
        eids = sorted(categories)
        if len(eids) > _MAX_GALLERY_EVENTS:
            raise ValueError(
                f"{len(eids)} events requested, above the {_MAX_GALLERY_EVENTS}-event safety cap for "
                f"the live viewer (each is rendered on demand in this one request). Narrow the event "
                f"list, or call tracehep.gallery.build_gallery directly from a script for larger batches."
            )

        events = {}
        for eid in eids:
            per_event_payload = dict(payload)
            per_event_payload["event_index"] = eid
            events[eid] = _load_figure(per_event_payload)

    title = (payload.get("gallery_title") or "").strip() or default_title
    dpi = int(payload.get("dpi") or 90)

    tmp_path = tempfile.NamedTemporaryFile(suffix=".html", delete=False).name
    try:
        build_gallery(events, categories, lambda fig: fig, tmp_path, title=title, dpi=dpi,
                      captions=captions)
        with open(tmp_path) as fh:
            return fh.read()
    finally:
        os.remove(tmp_path)


# Uploads (only relevant when trace-gui is running as a shared/public server,
# e.g. deployed on Hugging Face Spaces, rather than someone's own laptop --
# a remote visitor's browser has no way to hand the server a local file path,
# so it uploads the bytes instead). Kept out of the local single-user path
# entirely: nothing is written under this directory unless someone actually
# uses the upload widget.
UPLOAD_ROOT = os.path.join(tempfile.gettempdir(), "tracehep_uploads")
MAX_UPLOAD_BYTES = 150 * 1024 * 1024  # 150 MB -- generous for a demo, small enough for a free-tier host
UPLOAD_MAX_AGE_SECONDS = 3600  # uploaded files are not kept around indefinitely


def _cleanup_old_uploads(max_age_seconds=UPLOAD_MAX_AGE_SECONDS):
    """Delete uploaded-file directories older than ``max_age_seconds``. Safe
    to call often -- most calls will find nothing to do."""
    if not os.path.isdir(UPLOAD_ROOT):
        return
    cutoff = time.time() - max_age_seconds
    for name in os.listdir(UPLOAD_ROOT):
        path = os.path.join(UPLOAD_ROOT, name)
        try:
            if os.path.getmtime(path) < cutoff:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            pass


def _start_upload_cleanup_thread(interval_seconds=600):
    """Periodically sweep stale uploads. Only started by :func:`main` (a real
    running server) -- never by :func:`create_app` alone, so importing/testing
    this module doesn't spin up a background thread."""
    def _loop():
        while True:
            _cleanup_old_uploads()
            time.sleep(interval_seconds)
    threading.Thread(target=_loop, daemon=True).start()


def create_app():
    """Build and return the Flask app (not started -- see :func:`main`)."""
    _require_flask()
    from flask import Flask, jsonify, request
    from werkzeug.utils import secure_filename

    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + 1_000_000  # + slack for form overhead

    @app.errorhandler(413)
    def _too_large(exc):  # noqa: ARG001 -- Flask passes the exception in
        return jsonify({"ok": False, "error": f"file too large (over {MAX_UPLOAD_BYTES / 1e6:.0f} MB limit)"}), 413

    @app.route("/")
    def index():
        return _PAGE_HTML

    @app.route("/api/upload", methods=["POST"])
    def upload():
        _cleanup_old_uploads()
        f = request.files.get("file")
        if f is None or f.filename == "":
            return jsonify({"ok": False, "error": "no file provided"}), 400
        filename = secure_filename(f.filename) or "upload.root"
        if not filename.lower().endswith(".root"):
            return jsonify({"ok": False, "error": "only .root files are accepted"}), 400

        os.makedirs(UPLOAD_ROOT, exist_ok=True)
        dest_dir = os.path.join(UPLOAD_ROOT, uuid.uuid4().hex)
        os.makedirs(dest_dir)
        dest_path = os.path.join(dest_dir, filename)
        f.save(dest_path)

        size = os.path.getsize(dest_path)
        if size > MAX_UPLOAD_BYTES:
            shutil.rmtree(dest_dir, ignore_errors=True)
            return jsonify({"ok": False, "error": f"file too large ({size / 1e6:.0f} MB > "
                                                    f"{MAX_UPLOAD_BYTES / 1e6:.0f} MB limit)"}), 400

        return jsonify({"ok": True, "path": dest_path, "filename": filename, "size_mb": round(size / 1e6, 1)})

    @app.route("/api/render", methods=["POST"])
    def render():
        payload = request.get_json(force=True)
        try:
            return jsonify({"ok": True, **_dispatch(payload)})
        except Exception as exc:  # noqa: BLE001 -- surface any loader/plot error to the UI
            return jsonify({"ok": False, "error": str(exc), "traceback": traceback.format_exc()}), 400

    @app.route("/api/gallery", methods=["POST"])
    def gallery():
        payload = request.get_json(force=True)
        try:
            return jsonify({"ok": True, "html": _build_gallery_html(payload)})
        except Exception as exc:  # noqa: BLE001 -- surface any loader/plot error to the UI
            return jsonify({"ok": False, "error": str(exc), "traceback": traceback.format_exc()}), 400

    return app


def _find_available_port(host: str, start_port: int, max_tries: int = 50) -> int:
    """Return the first free port at/after ``start_port``. A stopped-but-not-
    killed previous ``trace-gui`` (e.g. Ctrl+Z instead of Ctrl+C leaves it
    suspended, still holding the port) is the most common reason the
    default port is busy -- rather than failing, just move to the next one."""
    port = start_port
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((host, port))
                return port
            except OSError:
                port += 1
    raise OSError(f"no free port found in {start_port}-{port} on {host}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="trace-gui", description="Launch the interactive TRACE viewer.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5057,
                         help="Port to try first (default: 5057) -- if busy, the next free one is used")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open a browser tab")
    args = parser.parse_args(argv)

    try:
        app = create_app()
    except ImportError as exc:
        print(f"error: {exc}")
        return 1

    try:
        port = _find_available_port(args.host, args.port)
    except OSError as exc:
        print(f"error: {exc}")
        return 1
    if port != args.port:
        print(f"Port {args.port} is already in use -- likely a previous trace-gui left running "
              f"(e.g. stopped with Ctrl+Z instead of Ctrl+C, or a background/tmux/other terminal "
              f"still has it open). Using port {port} instead. To find and stop the old one: "
              f"lsof -i :{args.port}  then  kill <PID> (or kill -9 <PID> if it won't stop).")

    _start_upload_cleanup_thread()

    url = f"http://{args.host}:{port}/"
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"TRACE viewer running at {url} (Ctrl+C to stop)")
    app.run(host=args.host, port=port, debug=False)
    return 0


_PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TRACE Live Viewer</title>
<style>
  :root {
    --bg: #f7f7f8; --surface: #ffffff; --ink: #1a1a1a; --muted: #6b6b6b;
    --border: #e2e2e4; --accent: #2a78d6; --error: #c0392b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink); min-height: 100vh;
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  }
  header {
    background: var(--surface); border-bottom: 1px solid var(--border);
    padding: 16px 24px;
  }
  h1 { font-size: 18px; margin: 0; }
  .sub { color: var(--muted); font-size: 13px; margin-top: 2px; }
  .layout { display: grid; grid-template-columns: 340px 1fr; gap: 0; min-height: calc(100vh - 65px); }
  .panel {
    background: var(--surface); border-right: 1px solid var(--border);
    padding: 20px; overflow-y: auto;
  }
  label { display: block; font-size: 12px; font-weight: 600; margin: 14px 0 5px 0; color: var(--muted); }
  label:first-child { margin-top: 0; }
  input[type=text], input[type=number], select, textarea {
    width: 100%; padding: 7px 9px; border: 1px solid var(--border); border-radius: 6px;
    font-size: 13px; background: var(--bg); color: var(--ink);
  }
  textarea { font-family: Menlo, monospace; font-size: 12px; resize: vertical; }
  .mode-toggle { display: flex; gap: 6px; margin-bottom: 16px; }
  .mode-btn {
    flex: 1; padding: 8px; border: 1px solid var(--border); border-radius: 8px;
    background: var(--surface); color: var(--ink); font-size: 12px; font-weight: 600; cursor: pointer;
  }
  .mode-btn.active { background: var(--ink); color: white; border-color: var(--ink); }
  .field-note { font-size: 10px; color: var(--muted); margin-top: -3px; }
  .upload-row { margin-top: 6px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .upload-input { display: none; }
  .upload-btn {
    display: inline-block; padding: 5px 10px; border: 1px dashed var(--border); border-radius: 6px;
    font-size: 11px; color: var(--accent); cursor: pointer; background: var(--bg); font-weight: 600;
  }
  .upload-btn:hover { background: var(--surface); }
  .upload-status { font-size: 11px; color: var(--muted); }
  .upload-status.error { color: var(--error); }
  .gallery-frame {
    width: 100%; height: calc(100vh - 150px); border: none; border-radius: 8px;
    background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }
  .checkbox-row { display: flex; align-items: center; gap: 8px; margin-top: 12px; }
  .checkbox-row label { margin: 0; }
  button#renderBtn {
    width: 100%; margin-top: 20px; padding: 10px; border: none; border-radius: 8px;
    background: var(--accent); color: white; font-size: 14px; font-weight: 600; cursor: pointer;
  }
  button#renderBtn:hover { opacity: 0.9; }
  button#renderBtn:disabled { opacity: 0.5; cursor: default; }
  .hidden { display: none !important; }
  .viewer { padding: 24px; display: flex; flex-direction: column; align-items: center; }
  .viewer img { max-width: 100%; border-radius: 8px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .viewer .plotly-wrap { width: 100%; }
  .viewer-toolbar { width: 100%; max-width: 900px; display: flex; justify-content: flex-end; margin-bottom: 10px; }
  .dl-btn {
    padding: 6px 14px; border: 1px solid var(--border); border-radius: 6px; background: var(--surface);
    color: var(--ink); font-size: 12px; cursor: pointer;
  }
  .dl-btn:hover { background: var(--accent); color: white; border-color: var(--accent); }
  .placeholder { color: var(--muted); font-size: 14px; text-align: center; margin-top: 80px; }
  .error-box {
    background: #fdecea; border: 1px solid #f5c6c0; color: var(--error);
    border-radius: 8px; padding: 14px; font-size: 13px; white-space: pre-wrap;
    font-family: Menlo, monospace; max-width: 700px;
  }
  .spinner {
    width: 28px; height: 28px; border: 3px solid var(--border); border-top-color: var(--accent);
    border-radius: 50%; animation: spin 0.8s linear infinite; margin: 80px auto 0 auto;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  .builder-section { margin-top: 16px; border-top: 1px solid var(--border); padding-top: 12px; }
  .builder-title { font-size: 12px; font-weight: 700; color: var(--ink); margin-bottom: 6px; }
  .builder-row {
    display: flex; gap: 4px; align-items: center; margin-bottom: 5px;
  }
  .builder-row input[type=number] { width: 0; flex: 1; padding: 5px 6px; font-size: 12px; }
  .builder-row label.chk { display: flex; align-items: center; gap: 3px; font-size: 11px; color: var(--muted); font-weight: 400; margin: 0; white-space: nowrap; }
  .builder-row .rm {
    background: none; border: none; color: var(--muted); cursor: pointer; font-size: 16px;
    line-height: 1; padding: 0 4px; flex: 0 0 auto;
  }
  .builder-row .rm:hover { color: var(--error); }
  .add-row-btn {
    width: 100%; padding: 5px; margin-top: 2px; border: 1px dashed var(--border); border-radius: 6px;
    background: none; color: var(--accent); font-size: 12px; cursor: pointer;
  }
  .add-row-btn:hover { background: var(--bg); }
  .field-hint { font-size: 10px; color: var(--muted); display: flex; gap: 4px; margin-bottom: 2px; }
  .field-hint span { flex: 1; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>TRACE Live Viewer</h1>
  <div class="sub">Point at a file, pick a loader and display, type an event number.</div>
</header>
<div class="layout">
  <div class="panel">
    <div class="mode-toggle">
      <button type="button" class="mode-btn active" id="modeSingleBtn" onclick="setMode('single')">Single event</button>
      <button type="button" class="mode-btn" id="modeManyBtn" onclick="setMode('many')">Many events</button>
      <button type="button" class="mode-btn" id="modeGalleryBtn" onclick="setMode('gallery')">Failure-mode gallery</button>
    </div>

    <div id="singleModePanel">
    <label for="loader">Loader</label>
    <select id="loader">
      <option value="delphes">Delphes</option>
      <option value="flat_ntuple">Flat ntuple (run/event)</option>
      <option value="atlas_opendata">ATLAS Open Data</option>
      <option value="cms_opendata">CMS Open Data</option>
      <option value="vertex">Vertex display</option>
      <option value="manual">Build an event by hand</option>
    </select>

    <div id="row_path">
      <label for="path">File path or URL</label>
      <input type="text" id="path" placeholder="/path/to/sample.root or https://...">
      <div class="upload-row">
        <label for="path_file" class="upload-btn">Or upload a .root file</label>
        <input type="file" id="path_file" class="upload-input" accept=".root">
        <span class="upload-status" id="path_file_status"></span>
      </div>
    </div>

    <label for="display">Display</label>
    <select id="display"></select>

    <div id="row_eventidx">
      <label for="event_index">Event #</label>
      <input type="number" id="event_index" value="0" min="0">
    </div>

    <div id="row_manual" class="hidden">
      <div class="builder-section" style="margin-top:0;border-top:none;padding-top:0;">
        <div class="builder-title">Jets</div>
        <div class="field-hint"><span>pT</span><span>eta</span><span>phi</span><span>b-tag</span></div>
        <div id="manual_jets_list"></div>
        <button type="button" class="add-row-btn" onclick="addManualRow('jets')">+ Add jet</button>
      </div>
      <div class="builder-section">
        <div class="builder-title">Muons</div>
        <div class="field-hint"><span>pT</span><span>eta</span><span>phi</span></div>
        <div id="manual_muons_list"></div>
        <button type="button" class="add-row-btn" onclick="addManualRow('muons')">+ Add muon</button>
      </div>
      <div class="builder-section">
        <div class="builder-title">Electrons</div>
        <div class="field-hint"><span>pT</span><span>eta</span><span>phi</span></div>
        <div id="manual_electrons_list"></div>
        <button type="button" class="add-row-btn" onclick="addManualRow('electrons')">+ Add electron</button>
      </div>
      <div class="builder-section">
        <div class="builder-title">Photons</div>
        <div class="field-hint"><span>pT</span><span>eta</span><span>phi</span></div>
        <div id="manual_photons_list"></div>
        <button type="button" class="add-row-btn" onclick="addManualRow('photons')">+ Add photon</button>
      </div>
      <div class="builder-section">
        <div class="builder-title">Missing E<sub>T</sub></div>
        <div class="builder-row">
          <input type="number" id="manual_met_pt" placeholder="pT [GeV]">
          <input type="number" id="manual_met_phi" placeholder="phi [rad]">
        </div>
      </div>
    </div>

    <div id="row_run" class="hidden">
      <label for="run_number">Run #</label>
      <input type="number" id="run_number" value="0">
    </div>

    <div id="row_vertex" class="hidden">
      <label for="vertex_index">Vertex #</label>
      <input type="number" id="vertex_index" value="0" min="0">
    </div>

    <div id="row_treename" class="hidden">
      <label for="tree_name">Tree name (optional -- auto-detected)</label>
      <input type="text" id="tree_name" placeholder="auto">
    </div>

    <div id="row_jetcol" class="hidden">
      <label for="jet_collection">Jet collection (optional)</label>
      <input type="text" id="jet_collection" placeholder="default">
    </div>

    <div id="row_showtracks" class="checkbox-row hidden">
      <input type="checkbox" id="show_tracks">
      <label for="show_tracks" style="margin:0">Show tracks</label>
    </div>

    <div id="row_largeR" class="checkbox-row hidden">
      <input type="checkbox" id="include_large_r_jets">
      <label for="include_large_r_jets" style="margin:0">Include large-R jets</label>
    </div>

    <div id="row_d0" class="hidden">
      <label for="d0_displaced_mm">Displaced-track threshold [mm] (optional)</label>
      <input type="number" id="d0_displaced_mm" step="0.1" placeholder="none">
    </div>

    <button id="renderBtn" onclick="renderEvent()">Render</button>
    </div>

    <div id="manyModePanel" class="hidden">
      <label for="m_loader">Loader</label>
      <select id="m_loader">
        <option value="delphes">Delphes</option>
        <option value="flat_ntuple">Flat ntuple (run/event)</option>
        <option value="atlas_opendata">ATLAS Open Data</option>
        <option value="cms_opendata">CMS Open Data</option>
        <option value="vertex">Vertex display</option>
      </select>

      <label for="m_path">File path or URL</label>
      <input type="text" id="m_path" placeholder="/path/to/sample.root or https://...">
      <div class="upload-row">
        <label for="m_path_file" class="upload-btn">Or upload a .root file</label>
        <input type="file" id="m_path_file" class="upload-input" accept=".root">
        <span class="upload-status" id="m_path_file_status"></span>
      </div>

      <label for="m_display">Display</label>
      <select id="m_display"></select>

      <label for="m_event_list">Event numbers</label>
      <textarea id="m_event_list" rows="3" placeholder="e.g. 1, 2, 4, 5 or 1-10"></textarea>
      <div class="field-note">Comma/space/newline-separated; "a-b" expands to an inclusive range.</div>

      <label for="m_run_number">Run # (flat_ntuple only)</label>
      <input type="number" id="m_run_number" value="0">

      <label for="m_vertex_index">Vertex # (vertex display only)</label>
      <input type="number" id="m_vertex_index" value="0" min="0">

      <label for="m_tree_name">Tree name (vertex display, optional -- auto-detected)</label>
      <input type="text" id="m_tree_name" placeholder="auto">

      <label for="m_jet_collection">Jet collection (delphes / vertex detail, optional)</label>
      <input type="text" id="m_jet_collection" placeholder="default">

      <div class="checkbox-row">
        <input type="checkbox" id="m_show_tracks">
        <label for="m_show_tracks" style="margin:0">Show tracks (delphes)</label>
      </div>
      <div class="checkbox-row">
        <input type="checkbox" id="m_include_large_r">
        <label for="m_include_large_r" style="margin:0">Include large-R jets (ATLAS Open Data)</label>
      </div>

      <label for="m_d0">Displaced-track threshold [mm] (delphes, optional)</label>
      <input type="number" id="m_d0" step="0.1" placeholder="none">

      <label for="m_gallery_title">Gallery title</label>
      <input type="text" id="m_gallery_title" placeholder="TRACE Event Review">

      <label for="m_gallery_dpi">Image DPI (lower = smaller/faster for many events)</label>
      <input type="number" id="m_gallery_dpi" value="90" min="40" max="200">
      <div class="field-note">Up to 300 events per gallery; for more, use tracehep.gallery from a script.</div>

      <button id="manyGalleryBtn" onclick="buildManyGallery()">Build gallery</button>
    </div>

    <div id="galleryModePanel" class="hidden">
      <label for="g_loader">Loader</label>
      <select id="g_loader">
        <option value="delphes">Delphes</option>
        <option value="flat_ntuple">Flat ntuple (run/event)</option>
        <option value="atlas_opendata">ATLAS Open Data</option>
        <option value="cms_opendata">CMS Open Data</option>
        <option value="vertex">Vertex display</option>
      </select>

      <label for="g_path">File path or URL</label>
      <input type="text" id="g_path" placeholder="/path/to/sample.root or https://...">
      <div class="upload-row">
        <label for="g_path_file" class="upload-btn">Or upload a .root file</label>
        <input type="file" id="g_path_file" class="upload-input" accept=".root">
        <span class="upload-status" id="g_path_file_status"></span>
      </div>

      <label for="g_display">Display</label>
      <select id="g_display"></select>

      <label for="g_run_number">Run # (flat_ntuple only)</label>
      <input type="number" id="g_run_number" value="0">

      <label for="g_vertex_index">Vertex # (vertex display only)</label>
      <input type="number" id="g_vertex_index" value="0" min="0">

      <label for="g_tree_name">Tree name (vertex display, optional -- auto-detected)</label>
      <input type="text" id="g_tree_name" placeholder="auto">

      <label for="g_jet_collection">Jet collection (delphes / vertex detail, optional)</label>
      <input type="text" id="g_jet_collection" placeholder="default">

      <div class="checkbox-row">
        <input type="checkbox" id="g_show_tracks">
        <label for="g_show_tracks" style="margin:0">Show tracks (delphes)</label>
      </div>
      <div class="checkbox-row">
        <input type="checkbox" id="g_include_large_r">
        <label for="g_include_large_r" style="margin:0">Include large-R jets (ATLAS Open Data)</label>
      </div>

      <label for="g_d0">Displaced-track threshold [mm] (delphes, optional)</label>
      <input type="number" id="g_d0" step="0.1" placeholder="none">

      <label for="category_mode">Categorize events by</label>
      <select id="category_mode">
        <option value="compare">Compare two algorithms (pass/fail)</option>
        <option value="custom">Custom labels</option>
        <option value="auto_flag">Auto-flag by &Delta;&phi;(MET, closest jet)</option>
      </select>

      <div id="compareFields">
        <div class="builder-section" style="margin-top:12px;border-top:none;padding-top:0;">
          <div class="builder-title">Algorithm 1</div>
          <input type="text" id="name_a" placeholder="Name (default: algo1)">
          <label for="a_pass">Passed event IDs</label>
          <textarea id="a_pass" rows="2" placeholder="e.g. 12, 45, 88"></textarea>
          <label for="a_fail">Failed event IDs</label>
          <textarea id="a_fail" rows="2"></textarea>
        </div>
        <div class="builder-section">
          <div class="builder-title">Algorithm 2</div>
          <input type="text" id="name_b" placeholder="Name (default: algo2)">
          <label for="b_pass">Passed event IDs</label>
          <textarea id="b_pass" rows="2"></textarea>
          <label for="b_fail">Failed event IDs</label>
          <textarea id="b_fail" rows="2"></textarea>
        </div>
      </div>

      <div id="customFields" class="hidden">
        <label for="custom_categories">Event id: label (one per line)</label>
        <textarea id="custom_categories" rows="6" placeholder="1023: anomalous&#10;1044: anomalous"></textarea>
        <div class="field-note">Any free-text label works -- every distinct one becomes a filter tab.</div>
      </div>

      <div id="autoFlagFields" class="hidden">
        <label for="flag_event_list">Event range to scan</label>
        <textarea id="flag_event_list" rows="2" placeholder="e.g. 1-200 or 1, 2, 4-10"></textarea>
        <div class="field-note">Comma/space-separated; "a-b" expands to an inclusive range. Every event is loaded and scanned, so keep it under the 300-event cap.</div>

        <label for="flag_criterion">Flag criterion</label>
        <select id="flag_criterion"></select>
        <div class="field-note" id="flag_criterion_needs"></div>

        <div class="builder-row" style="align-items:flex-end;gap:8px;margin-top:8px;">
          <div style="flex:1;">
            <label for="flag_direction" style="margin:0 0 5px 0;">Flag when</label>
            <select id="flag_direction">
              <option value="above">above threshold</option>
              <option value="below">below threshold</option>
            </select>
          </div>
          <div style="flex:1;">
            <label for="flag_threshold" style="margin:0 0 5px 0;">Threshold <span id="flag_threshold_unit"></span></label>
            <input type="number" id="flag_threshold" step="any" style="width:100%;">
          </div>
        </div>
        <div class="field-note">Events where the criterion can't be computed (e.g. no MET, no tracks) are skipped, not miscategorized. Needs an event-level loader (not Vertex display).</div>
      </div>

      <label for="gallery_title">Gallery title</label>
      <input type="text" id="gallery_title" placeholder="TRACE Failure-Mode Review">

      <label for="gallery_dpi">Image DPI (lower = smaller/faster for many events)</label>
      <input type="number" id="gallery_dpi" value="90" min="40" max="200">
      <div class="field-note">Up to 300 events per gallery; for more, use tracehep.gallery from a script.</div>

      <button id="galleryBtn" onclick="buildGallery()">Build gallery</button>
    </div>
  </div>
  <div class="viewer" id="viewer">
    <div class="placeholder">Fill in the form and click Render.</div>
  </div>
</div>

<script>
var DISPLAYS = {
  delphes: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"], ["3d", "Interactive 3D"]],
  flat_ntuple: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"], ["3d", "Interactive 3D"]],
  atlas_opendata: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"], ["3d", "Interactive 3D"]],
  cms_opendata: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"], ["3d", "Interactive 3D"]],
  vertex: [["vertices_plain", "Vertices z-R (plain)"], ["vertices_styled", "Vertices z-R (styled)"],
           ["vertices_time_colored", "Vertices z-R (time-coloured)"],
           ["vertices_3d", "Interactive 3D vertices"], ["vertex_detail", "One vertex, detail"]],
  manual: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"], ["3d", "Interactive 3D"]],
};
var VERTEX_LOADERS = ["vertex"];
var MANUAL_TYPES = ["jets", "muons", "electrons", "photons"];

// Gallery mode only offers static (matplotlib-exportable) displays -- the
// interactive 3D ones need the optional kaleido extra to export as a PNG,
// which tracehep doesn't require by default.
var GALLERY_DISPLAYS = {
  delphes: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"]],
  flat_ntuple: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"]],
  atlas_opendata: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"]],
  cms_opendata: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"]],
  vertex: [["vertices_plain", "Vertices z-R (plain)"], ["vertices_styled", "Vertices z-R (styled)"],
           ["vertices_time_colored", "Vertices z-R (time-coloured)"], ["vertex_detail", "One vertex, detail"]],
};
var lastGalleryHtml = "";

function addManualRow(type) {
  var list = document.getElementById("manual_" + type + "_list");
  var row = document.createElement("div");
  row.className = "builder-row";
  var extra = type === "jets" ? '<label class="chk"><input type="checkbox" class="m-btag"> b</label>' : "";
  row.innerHTML =
    '<input type="number" class="m-pt" placeholder="GeV">' +
    '<input type="number" class="m-eta" placeholder="η" step="0.1">' +
    '<input type="number" class="m-phi" placeholder="rad" step="0.1">' +
    extra +
    '<button type="button" class="rm" onclick="this.parentElement.remove()">×</button>';
  list.appendChild(row);
}

function collectManualObjects() {
  var result = {};
  MANUAL_TYPES.forEach(function(type) {
    var rows = document.querySelectorAll("#manual_" + type + "_list .builder-row");
    result[type] = Array.from(rows).map(function(row) {
      var obj = {
        pt: parseFloat(row.querySelector(".m-pt").value) || 0,
        eta: parseFloat(row.querySelector(".m-eta").value) || 0,
        phi: parseFloat(row.querySelector(".m-phi").value) || 0,
      };
      var btagEl = row.querySelector(".m-btag");
      if (btagEl) obj.btag = btagEl.checked;
      return obj;
    });
  });
  return result;
}

function populateDisplays() {
  var loader = document.getElementById("loader").value;
  var sel = document.getElementById("display");
  sel.innerHTML = "";
  DISPLAYS[loader].forEach(function(pair) {
    var opt = document.createElement("option");
    opt.value = pair[0]; opt.textContent = pair[1];
    sel.appendChild(opt);
  });
  updateVisibleFields();
}

function updateVisibleFields() {
  var loader = document.getElementById("loader").value;
  var display = document.getElementById("display").value;
  var isVertexLoader = VERTEX_LOADERS.indexOf(loader) !== -1;
  var isManual = loader === "manual";

  toggle("row_path", !isManual);
  toggle("row_eventidx", !isManual);
  toggle("row_manual", isManual);
  toggle("row_run", loader === "flat_ntuple");
  toggle("row_vertex", isVertexLoader && display === "vertex_detail");
  toggle("row_treename", isVertexLoader);
  toggle("row_jetcol", loader === "delphes" || (loader === "vertex" && display === "vertex_detail"));
  toggle("row_showtracks", loader === "delphes" && display !== "beam2d");
  toggle("row_largeR", loader === "atlas_opendata");
  toggle("row_d0", loader === "delphes" && display !== "beam2d");
}

function toggle(id, show) {
  document.getElementById(id).classList.toggle("hidden", !show);
}

document.getElementById("loader").addEventListener("change", populateDisplays);
document.getElementById("display").addEventListener("change", updateVisibleFields);
populateDisplays();

function setMode(mode) {
  document.getElementById("modeSingleBtn").classList.toggle("active", mode === "single");
  document.getElementById("modeManyBtn").classList.toggle("active", mode === "many");
  document.getElementById("modeGalleryBtn").classList.toggle("active", mode === "gallery");
  toggle("singleModePanel", mode === "single");
  toggle("manyModePanel", mode === "many");
  toggle("galleryModePanel", mode === "gallery");
  var placeholders = {
    single: "Fill in the form and click Render.",
    many: "List the event numbers and click Build gallery.",
    gallery: "Describe the event categories and click Build gallery.",
  };
  document.getElementById("viewer").innerHTML = '<div class="placeholder">' + placeholders[mode] + '</div>';
}

function populateDisplaysInto(selectId, loaderId) {
  var loader = document.getElementById(loaderId).value;
  var sel = document.getElementById(selectId);
  sel.innerHTML = "";
  GALLERY_DISPLAYS[loader].forEach(function(pair) {
    var opt = document.createElement("option");
    opt.value = pair[0]; opt.textContent = pair[1];
    sel.appendChild(opt);
  });
}

function populateGalleryDisplays() { populateDisplaysInto("g_display", "g_loader"); }
function populateManyDisplays() { populateDisplaysInto("m_display", "m_loader"); }

function updateCategoryFields() {
  var mode = document.getElementById("category_mode").value;
  toggle("compareFields", mode === "compare");
  toggle("customFields", mode === "custom");
  toggle("autoFlagFields", mode === "auto_flag");
}

// Mirrors tracehep.webapp._FLAG_CRITERIA (server-side is authoritative and
// re-validates independently) -- just enough here to populate the dropdown
// and pre-fill a sensible threshold/direction/help text per criterion.
var FLAG_CRITERIA = [
  ["dphi_met_jet", "Δφ(MET, closest jet)", "rad", 0.5, "above", "MET and ≥ 1 jet"],
  ["min_dphi_leading4", "min Δφ(MET, jet) among leading 4 jets", "rad", 0.4, "below", "MET and ≥ 1 jet"],
  ["met_over_ht", "MET / H_T (scalar sum jet p_T)", "", 0.3, "above", "MET and ≥ 1 jet"],
  ["met_pt", "MET", "GeV", 200, "above", "MET"],
  ["ht", "H_T (scalar sum jet p_T)", "GeV", 500, "above", "≥ 1 jet"],
  ["n_jets", "Number of jets", "", 6, "above", "always computable"],
  ["n_bjets", "Number of b-tagged jets", "", 2, "above", "always computable"],
  ["leading_jet_pt", "Leading jet p_T", "GeV", 300, "above", "≥ 1 jet"],
  ["dijet_dphi_balance", "|π − Δφ(jet1, jet2)| (deviation from back-to-back)", "rad", 0.5, "above", "≥ 2 jets"],
  ["max_track_d0", "Max |d0| among tracks (displaced-track / LLP signature)", "mm", 1.0, "above", "≥ 1 track (Delphes/calo-timing only)"],
  ["n_leptons", "Number of leptons (muons + electrons)", "", 2, "above", "always computable"],
];

function populateFlagCriteria() {
  var sel = document.getElementById("flag_criterion");
  FLAG_CRITERIA.forEach(function(c) {
    var opt = document.createElement("option");
    opt.value = c[0]; opt.textContent = c[1] + (c[2] ? " [" + c[2] + "]" : "");
    sel.appendChild(opt);
  });
  updateFlagCriterionDefaults();
}

function updateFlagCriterionDefaults() {
  var key = document.getElementById("flag_criterion").value;
  var c = FLAG_CRITERIA.filter(function(x) { return x[0] === key; })[0];
  if (!c) return;
  document.getElementById("flag_threshold").value = c[3];
  document.getElementById("flag_direction").value = c[4];
  document.getElementById("flag_threshold_unit").textContent = c[2] ? "[" + c[2] + "]" : "";
  document.getElementById("flag_criterion_needs").textContent = "Needs: " + c[5] + ".";
}

document.getElementById("g_loader").addEventListener("change", populateGalleryDisplays);
document.getElementById("category_mode").addEventListener("change", updateCategoryFields);
document.getElementById("flag_criterion").addEventListener("change", updateFlagCriterionDefaults);
populateGalleryDisplays();
updateCategoryFields();
populateFlagCriteria();

document.getElementById("m_loader").addEventListener("change", populateManyDisplays);
populateManyDisplays();

// ?mode=many deep-links straight into the Many-events panel; m_* params
// pre-fill fields, &build=1 auto-builds -- same pattern as the gallery
// deep-linking below.
(function applyManyQueryParams() {
  var params = new URLSearchParams(window.location.search);
  if (params.get("mode") !== "many") return;
  setMode("many");

  if (params.has("m_loader")) {
    document.getElementById("m_loader").value = params.get("m_loader");
    populateManyDisplays();
  }
  if (params.has("m_display")) document.getElementById("m_display").value = params.get("m_display");

  ["m_path", "m_event_list", "m_run_number", "m_vertex_index", "m_tree_name", "m_jet_collection",
   "m_d0", "m_gallery_title", "m_gallery_dpi"].forEach(function(id) {
    if (params.has(id)) document.getElementById(id).value = params.get(id);
  });
  ["m_show_tracks", "m_include_large_r"].forEach(function(id) {
    if (params.has(id)) document.getElementById(id).checked = (params.get(id) === "true" || params.get(id) === "1");
  });

  if (params.get("build") === "1") buildManyGallery();
})();

// ?mode=gallery deep-links straight into the failure-mode gallery panel;
// any g_*/category_mode/name_a/a_pass/etc. param pre-fills that field too,
// and &build=1 auto-builds it -- mirroring the single-event deep-linking
// above, so a gallery is shareable as a URL the same way a single render is.
(function applyGalleryQueryParams() {
  var params = new URLSearchParams(window.location.search);
  if (params.get("mode") !== "gallery") return;
  setMode("gallery");

  if (params.has("g_loader")) {
    document.getElementById("g_loader").value = params.get("g_loader");
    populateGalleryDisplays();
  }
  if (params.has("g_display")) document.getElementById("g_display").value = params.get("g_display");

  ["g_path", "g_run_number", "g_vertex_index", "g_tree_name", "g_jet_collection", "g_d0",
   "category_mode", "name_a", "name_b", "a_pass", "a_fail", "b_pass", "b_fail",
   "custom_categories", "gallery_title", "gallery_dpi"].forEach(function(id) {
    if (params.has(id)) document.getElementById(id).value = params.get(id);
  });
  if (params.has("event_list")) document.getElementById("flag_event_list").value = params.get("event_list");
  if (params.has("flag_criterion")) document.getElementById("flag_criterion").value = params.get("flag_criterion");
  if (params.has("flag_direction")) document.getElementById("flag_direction").value = params.get("flag_direction");
  if (params.has("flag_threshold")) document.getElementById("flag_threshold").value = params.get("flag_threshold");
  ["g_show_tracks", "g_include_large_r"].forEach(function(id) {
    if (params.has(id)) document.getElementById(id).checked = (params.get(id) === "true" || params.get(id) === "1");
  });
  updateCategoryFields();

  if (params.get("build") === "1") buildGallery();
})();

function submitGalleryPayload(payload, btnId) {
  var btn = document.getElementById(btnId);
  var viewer = document.getElementById("viewer");
  btn.disabled = true;
  viewer.innerHTML = '<div class="spinner"></div>';

  fetch("/api/gallery", {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
  }).then(function(r) { return r.json().then(function(body) { return {status: r.status, body: body}; }); })
    .then(function(res) {
      btn.disabled = false;
      if (!res.body.ok) {
        viewer.innerHTML = '<div class="error-box">' + escapeHtml(res.body.error || "Unknown error") + '</div>';
        return;
      }
      lastGalleryHtml = res.body.html;
      viewer.innerHTML = "";

      var toolbar = document.createElement("div");
      toolbar.className = "viewer-toolbar";
      var saveBtn = document.createElement("button");
      saveBtn.className = "dl-btn";
      saveBtn.textContent = "⬇ Save full gallery as .html";
      saveBtn.onclick = function() {
        var blob = new Blob([lastGalleryHtml], {type: "text/html"});
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "trace_gallery.html";
        a.click();
      };
      toolbar.appendChild(saveBtn);
      viewer.appendChild(toolbar);

      var frame = document.createElement("iframe");
      frame.className = "gallery-frame";
      frame.srcdoc = lastGalleryHtml;
      viewer.appendChild(frame);
    })
    .catch(function(err) {
      btn.disabled = false;
      viewer.innerHTML = '<div class="error-box">' + escapeHtml(String(err)) + '</div>';
    });
}

function buildGallery() {
  submitGalleryPayload({
    loader: document.getElementById("g_loader").value,
    path: document.getElementById("g_path").value,
    display: document.getElementById("g_display").value,
    run_number: document.getElementById("g_run_number").value,
    vertex_index: document.getElementById("g_vertex_index").value,
    tree_name: document.getElementById("g_tree_name").value,
    jet_collection: document.getElementById("g_jet_collection").value,
    show_tracks: document.getElementById("g_show_tracks").checked,
    include_large_r_jets: document.getElementById("g_include_large_r").checked,
    d0_displaced_mm: document.getElementById("g_d0").value,
    category_mode: document.getElementById("category_mode").value,
    name_a: document.getElementById("name_a").value,
    name_b: document.getElementById("name_b").value,
    a_pass: document.getElementById("a_pass").value,
    a_fail: document.getElementById("a_fail").value,
    b_pass: document.getElementById("b_pass").value,
    b_fail: document.getElementById("b_fail").value,
    custom_categories: document.getElementById("custom_categories").value,
    event_list: document.getElementById("flag_event_list").value,
    flag_criterion: document.getElementById("flag_criterion").value,
    flag_direction: document.getElementById("flag_direction").value,
    flag_threshold: document.getElementById("flag_threshold").value,
    gallery_title: document.getElementById("gallery_title").value,
    dpi: document.getElementById("gallery_dpi").value,
  }, "galleryBtn");
}

function buildManyGallery() {
  submitGalleryPayload({
    loader: document.getElementById("m_loader").value,
    path: document.getElementById("m_path").value,
    display: document.getElementById("m_display").value,
    run_number: document.getElementById("m_run_number").value,
    vertex_index: document.getElementById("m_vertex_index").value,
    tree_name: document.getElementById("m_tree_name").value,
    jet_collection: document.getElementById("m_jet_collection").value,
    show_tracks: document.getElementById("m_show_tracks").checked,
    include_large_r_jets: document.getElementById("m_include_large_r").checked,
    d0_displaced_mm: document.getElementById("m_d0").value,
    category_mode: "list",
    event_list: document.getElementById("m_event_list").value,
    gallery_title: document.getElementById("m_gallery_title").value,
    dpi: document.getElementById("m_gallery_dpi").value,
  }, "manyGalleryBtn");
}

// Deep-linking: ?path=...&loader=...&display=...&event_index=... (+ any other
// field name) pre-fills the form from the URL and auto-renders -- share a
// link straight to one event instead of re-typing everything. For loader=manual,
// pass manual_jets/manual_muons/manual_electrons/manual_photons as JSON arrays,
// e.g. manual_jets=[{"pt":100,"eta":0.1,"phi":0.2,"btag":true}] (URL-encoded).
(function applyQueryParams() {
  var params = new URLSearchParams(window.location.search);
  if (!params.has("path") && params.get("loader") !== "manual") return;

  function setField(key, value) {
    var el = document.getElementById(key);
    if (!el) return;
    if (el.type === "checkbox") { el.checked = (value === "true" || value === "1"); }
    else { el.value = value; }
  }

  // loader first, so populateDisplays() rebuilds the <select> options
  // before "display" is set -- otherwise the rebuild wipes it out again.
  if (params.has("loader")) { setField("loader", params.get("loader")); populateDisplays(); }

  MANUAL_TYPES.forEach(function(type) {
    var key = "manual_" + type;
    if (!params.has(key)) return;
    try {
      JSON.parse(params.get(key)).forEach(function(obj) {
        addManualRow(type);
        var rows = document.querySelectorAll("#" + key + "_list .builder-row");
        var row = rows[rows.length - 1];
        row.querySelector(".m-pt").value = obj.pt || 0;
        row.querySelector(".m-eta").value = obj.eta || 0;
        row.querySelector(".m-phi").value = obj.phi || 0;
        var btagEl = row.querySelector(".m-btag");
        if (btagEl) btagEl.checked = !!obj.btag;
      });
    } catch (e) { /* malformed JSON in the URL -- ignore that field */ }
  });

  params.forEach(function(value, key) {
    if (key === "loader" || MANUAL_TYPES.indexOf(key.replace("manual_", "")) !== -1) return;
    setField(key, value);
  });
  updateVisibleFields();
  renderEvent();
})();

function renderEvent() {
  var btn = document.getElementById("renderBtn");
  var viewer = document.getElementById("viewer");
  btn.disabled = true;
  viewer.innerHTML = '<div class="spinner"></div>';

  var loader = document.getElementById("loader").value;
  var payload = {
    path: document.getElementById("path").value,
    loader: loader,
    display: document.getElementById("display").value,
    event_index: document.getElementById("event_index").value,
    run_number: document.getElementById("run_number").value,
    vertex_index: document.getElementById("vertex_index").value,
    tree_name: document.getElementById("tree_name").value,
    jet_collection: document.getElementById("jet_collection").value,
    show_tracks: document.getElementById("show_tracks").checked,
    include_large_r_jets: document.getElementById("include_large_r_jets").checked,
    d0_displaced_mm: document.getElementById("d0_displaced_mm").value,
  };

  if (loader === "manual") {
    var objs = collectManualObjects();
    payload.manual_jets = objs.jets;
    payload.manual_muons = objs.muons;
    payload.manual_electrons = objs.electrons;
    payload.manual_photons = objs.photons;
    payload.manual_met_pt = document.getElementById("manual_met_pt").value;
    payload.manual_met_phi = document.getElementById("manual_met_phi").value;
  }

  fetch("/api/render", {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
  }).then(function(r) { return r.json().then(function(body) { return {status: r.status, body: body}; }); })
    .then(function(res) {
      btn.disabled = false;
      if (!res.body.ok) {
        viewer.innerHTML = '<div class="error-box">' + escapeHtml(res.body.error || "Unknown error") + '</div>';
        return;
      }
      viewer.innerHTML = "";
      var toolbar = document.createElement("div");
      toolbar.className = "viewer-toolbar";
      var dlBtn = document.createElement("button");
      dlBtn.className = "dl-btn";
      dlBtn.textContent = "⬇ Download image";
      toolbar.appendChild(dlBtn);
      viewer.appendChild(toolbar);

      if (res.body.kind === "image") {
        var img = document.createElement("img");
        img.src = res.body.data;
        viewer.appendChild(img);
        dlBtn.onclick = function() {
          var a = document.createElement("a");
          a.href = img.src;
          a.download = "trace_event.png";
          a.click();
        };
      } else {
        var wrap = document.createElement("div");
        wrap.className = "plotly-wrap";
        wrap.innerHTML = res.body.data;
        viewer.appendChild(wrap);
        // re-execute any <script> tags plotly's to_html injected (innerHTML does not run them)
        wrap.querySelectorAll("script").forEach(function(oldScript) {
          var newScript = document.createElement("script");
          if (oldScript.src) { newScript.src = oldScript.src; }
          else { newScript.textContent = oldScript.textContent; }
          oldScript.parentNode.replaceChild(newScript, oldScript);
        });
        dlBtn.onclick = function() {
          var gd = wrap.querySelector(".plotly-graph-div");
          if (gd && window.Plotly) {
            Plotly.downloadImage(gd, {format: "png", filename: "trace_event_3d", width: 1200, height: 900});
          }
        };
      }
    })
    .catch(function(err) {
      btn.disabled = false;
      viewer.innerHTML = '<div class="error-box">' + escapeHtml(String(err)) + '</div>';
    });
}

function escapeHtml(s) {
  var d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// Lets a browser hand the server a file's bytes instead of a local path --
// needed when trace-gui is running on a shared/public server rather than
// someone's own laptop, where a local path means nothing to the server.
// On success, the returned server-side path is written into the sibling
// "File path or URL" field, so everything downstream (render/gallery) needs
// no changes at all.
function wireFileUpload(fileInputId, pathInputId, statusId) {
  var fileInput = document.getElementById(fileInputId);
  if (!fileInput) return;
  fileInput.addEventListener("change", function(e) {
    var file = e.target.files[0];
    var statusEl = document.getElementById(statusId);
    if (!file) return;
    statusEl.className = "upload-status";
    statusEl.textContent = "Uploading " + file.name + " (" + (file.size / 1e6).toFixed(1) + " MB)...";

    var fd = new FormData();
    fd.append("file", file);
    fetch("/api/upload", {method: "POST", body: fd})
      .then(function(r) { return r.json().then(function(body) { return {status: r.status, body: body}; }); })
      .then(function(res) {
        if (!res.body.ok) {
          statusEl.className = "upload-status error";
          statusEl.textContent = "Upload failed: " + (res.body.error || "unknown error");
          return;
        }
        document.getElementById(pathInputId).value = res.body.path;
        statusEl.className = "upload-status";
        statusEl.textContent = "Uploaded " + res.body.filename + " (" + res.body.size_mb + " MB)";
      })
      .catch(function(err) {
        statusEl.className = "upload-status error";
        statusEl.textContent = "Upload failed: " + String(err);
      });
  });
}
wireFileUpload("path_file", "path", "path_file_status");
wireFileUpload("m_path_file", "m_path", "m_path_file_status");
wireFileUpload("g_path_file", "g_path", "g_path_file_status");
</script>
</body>
</html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
