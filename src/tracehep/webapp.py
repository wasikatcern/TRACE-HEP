"""``trace-gui``: a small local web app for interactively browsing event
and vertex displays -- point it at a file, type an event number, pick a
display, and it renders live in your browser. No pre-rendering, no
scripting: this is the "just let me look at one event" tool, complementing
:mod:`tracehep.gallery` (which is for browsing *many* already-categorized
events at once).

Covers every loader tracehep ships: Delphes, flat-ntuple, calo-timing
(vertex), ATLAS Open Data, CMS Open Data, and ATLAS PHYSLITE (vertex) --
and every display type, both matplotlib (2D) and plotly (interactive 3D).
``path`` can be a local file or, for the loaders that support it (CMS Open
Data, ATLAS Open Data/PHYSLITE), a remote ``https://...`` URL, streamed
the same way as everywhere else in tracehep.

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
import socket
import threading
import traceback
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


def _dispatch(payload):
    loader = payload["loader"]
    display = payload["display"]
    show_tracks = bool(payload.get("show_tracks"))
    d0_displaced_mm = float(payload["d0_displaced_mm"]) if payload.get("d0_displaced_mm") else None
    jet_collection = (payload.get("jet_collection") or "").strip() or None

    if loader == "manual":
        event = _make_manual_event(payload)
        return _fig_response(_make_event_fig(event, display, show_tracks=False, d0_displaced_mm=None))

    path = payload["path"]
    event_index = int(payload["event_index"])

    if loader == "delphes":
        from .io.delphes import load_event
        kwargs = {"with_tracks": True}
        if jet_collection:
            kwargs["jet_collection"] = jet_collection
        event = load_event(path, event_index, **kwargs)
        fig = _make_event_fig(event, display, show_tracks=show_tracks, d0_displaced_mm=d0_displaced_mm)

    elif loader == "flat_ntuple":
        from .io.flat_ntuple import load_event_by_run_event
        run_number = int(payload["run_number"])
        event = load_event_by_run_event(path, run_number, event_index)
        fig = _make_event_fig(event, display, show_tracks=False, d0_displaced_mm=None)

    elif loader == "atlas_opendata":
        from .io.atlas_opendata import load_events
        event = load_events(path, [event_index],
                             include_large_r_jets=bool(payload.get("include_large_r_jets")))[event_index]
        fig = _make_event_fig(event, display, show_tracks=False, d0_displaced_mm=None)

    elif loader == "cms_opendata":
        from .io.cms_opendata import load_events
        event = load_events(path, [event_index])[event_index]
        fig = _make_event_fig(event, display, show_tracks=False, d0_displaced_mm=None)

    elif loader == "calotiming":
        from .io.calotiming import load_vertex_event, match_jets_to_vertex
        vertex_event = load_vertex_event(path, event_index)
        jets = []
        vertex_index = int(payload.get("vertex_index") or 0)
        if display == "vertex_detail":
            kwargs = {}
            if jet_collection:
                kwargs["jet_collection"] = jet_collection
            jets = match_jets_to_vertex(path, event_index, vertex_event.vertices[vertex_index].z, **kwargs)
        fig = _make_vertex_fig(vertex_event, display, vertex_index=vertex_index, jets=jets)

    elif loader == "atlas_physlite":
        from .io.atlas_physlite import load_vertex_event, load_event_jets
        vertex_event = load_vertex_event(path, event_index)
        jets = []
        vertex_index = int(payload.get("vertex_index") or 0)
        if display == "vertex_detail":
            jets = load_event_jets(path, event_index)
        fig = _make_vertex_fig(vertex_event, display, vertex_index=vertex_index, jets=jets)

    else:
        raise ValueError(f"unknown loader {loader!r}")

    return _fig_response(fig)


def create_app():
    """Build and return the Flask app (not started -- see :func:`main`)."""
    _require_flask()
    from flask import Flask, jsonify, request

    app = Flask(__name__)

    @app.route("/")
    def index():
        return _PAGE_HTML

    @app.route("/api/render", methods=["POST"])
    def render():
        payload = request.get_json(force=True)
        try:
            return jsonify({"ok": True, **_dispatch(payload)})
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
  input[type=text], input[type=number], select {
    width: 100%; padding: 7px 9px; border: 1px solid var(--border); border-radius: 6px;
    font-size: 13px; background: var(--bg); color: var(--ink);
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
  .viewer { padding: 24px; display: flex; align-items: flex-start; justify-content: center; }
  .viewer img { max-width: 100%; border-radius: 8px; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  .viewer .plotly-wrap { width: 100%; }
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
    <label for="loader">Loader</label>
    <select id="loader">
      <option value="delphes">Delphes</option>
      <option value="flat_ntuple">Flat ntuple (run/event)</option>
      <option value="calotiming">Calo-timing (vertex)</option>
      <option value="atlas_opendata">ATLAS Open Data</option>
      <option value="cms_opendata">CMS Open Data</option>
      <option value="atlas_physlite">ATLAS PHYSLITE (vertex)</option>
      <option value="manual">Build an event by hand</option>
    </select>

    <div id="row_path">
      <label for="path">File path or URL</label>
      <input type="text" id="path" placeholder="/path/to/sample.root or https://...">
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
  calotiming: [["vertices_plain", "Vertices z-R (plain)"], ["vertices_styled", "Vertices z-R (styled)"],
               ["vertices_time_colored", "Vertices z-R (time-coloured)"],
               ["vertices_3d", "Interactive 3D vertices"], ["vertex_detail", "One vertex, detail"]],
  atlas_physlite: [["vertices_plain", "Vertices z-R (plain)"], ["vertices_styled", "Vertices z-R (styled)"],
                    ["vertices_3d", "Interactive 3D vertices"], ["vertex_detail", "One vertex, detail"]],
  manual: [["polar", "Polar (phi, |eta|)"], ["beam2d", "Beam-axis 2D"], ["3d", "Interactive 3D"]],
};
var VERTEX_LOADERS = ["calotiming", "atlas_physlite"];
var MANUAL_TYPES = ["jets", "muons", "electrons", "photons"];

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
  toggle("row_jetcol", loader === "delphes" || (loader === "calotiming" && display === "vertex_detail"));
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
      if (res.body.kind === "image") {
        viewer.innerHTML = '<img src="' + res.body.data + '">';
      } else {
        var wrap = document.createElement("div");
        wrap.className = "plotly-wrap";
        wrap.innerHTML = res.body.data;
        viewer.innerHTML = "";
        viewer.appendChild(wrap);
        // re-execute any <script> tags plotly's to_html injected (innerHTML does not run them)
        wrap.querySelectorAll("script").forEach(function(oldScript) {
          var newScript = document.createElement("script");
          if (oldScript.src) { newScript.src = oldScript.src; }
          else { newScript.textContent = oldScript.textContent; }
          oldScript.parentNode.replaceChild(newScript, oldScript);
        });
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
</script>
</body>
</html>
"""

if __name__ == "__main__":
    raise SystemExit(main())
