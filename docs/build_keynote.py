##############################################################
######## Build the comprehensive TRACE-HEP documentation  ######
######## as a Keynote deck, then export it to PDF.         #####
##############################################################
#
# Generates a .applescript file driving Keynote.app (via osascript) to
# create every slide, then exports the finished deck to PDF.
#
# Usage:
#   python3 build_keynote.py

import os
import subprocess

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "assets")
OUT_KEY = os.path.join(HERE, "TRACE-HEP_Documentation.key")
OUT_PDF = os.path.join(HERE, "TRACE-HEP_Documentation.pdf")
SCRIPT_PATH = os.path.join(HERE, "_build_keynote.applescript")

SLIDE_W, SLIDE_H = 1024, 768
MARGIN = 40
CONTENT_W = SLIDE_W - 2 * MARGIN


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def as_lines_expr(text: str) -> str:
    lines = text.split("\n")
    parts = [f'"{esc(line)}"' for line in lines]
    return " & return & ".join(parts)


def image_fit(path, max_w=900, max_h=560):
    im = Image.open(path)
    w, h = im.size
    scale = min(max_w / w, max_h / h)
    return int(w * scale), int(h * scale)


class Deck:
    def __init__(self):
        self.statements = []
        self.slide_count = 0

    def _new_slide_var(self):
        self.slide_count += 1
        return f"sl{self.slide_count}"

    def title_slide(self, title, subtitle):
        self.statements.append(f'''
    set slide1 to slide 1 of theDoc
    set base layout of slide1 to titleMaster
    set object text of default title item of slide1 to "{esc(title)}"
    set object text of default body item of slide1 to "{esc(subtitle)}"
''')

    def _add_slide(self):
        v = self._new_slide_var()
        self.statements.append(f'''
    set {v} to make new slide at end of slides of theDoc with properties {{base layout:blankMaster}}
''')
        return v

    def _add_heading(self, v, title):
        self.statements.append(f'''
    tell {v}
        set ttl to make new text item with properties {{position:{{{MARGIN}, 28}}, width:{CONTENT_W}, height:56}}
        set object text of ttl to "{esc(title)}"
        set font of object text of ttl to "Helvetica Neue Bold"
        set size of object text of ttl to 32
        set color of object text of ttl to {{13107, 13107, 13107}}
    end tell
''')

    def text_slide(self, title, lines, bullet=True, y=110, font_size=24, font="Helvetica Neue"):
        v = self._add_slide()
        self._add_heading(v, title)
        prefixed = []
        for l in lines:
            if not bullet or not l.strip():
                prefixed.append(l)
            elif l.startswith("  "):
                prefixed.append("   " + l)  # indented continuation, no bullet marker
            else:
                prefixed.append("*  " + l)
        body = "\n".join(prefixed)
        self.statements.append(f'''
    tell {v}
        set bd to make new text item with properties {{position:{{{MARGIN}, {y}}}, width:{CONTENT_W}, height:{SLIDE_H - y - MARGIN}}}
        set object text of bd to {as_lines_expr(body)}
        set font of object text of bd to "{font}"
        set size of object text of bd to {font_size}
        set color of object text of bd to {{6000, 6000, 6000}}
    end tell
''')

    def code_slide(self, title, code, note=None, font_size=18):
        v = self._add_slide()
        self._add_heading(v, title)
        n_lines = code.count("\n") + 1
        fs = font_size if n_lines <= 16 else max(13, int(font_size * 16 / n_lines))
        body_h = SLIDE_H - 110 - MARGIN - (40 if note else 0)
        self.statements.append(f'''
    tell {v}
        set cd to make new text item with properties {{position:{{55, 108}}, width:914, height:{body_h}}}
        set object text of cd to {as_lines_expr(code)}
        set font of object text of cd to "Menlo"
        set size of object text of cd to {fs}
        set color of object text of cd to {{0, 0, 0}}
    end tell
''')
        if note:
            self.statements.append(f'''
    tell {v}
        set nt to make new text item with properties {{position:{{{MARGIN}, {SLIDE_H - MARGIN - 34}}}, width:{CONTENT_W}, height:34}}
        set object text of nt to "{esc(note)}"
        set font of object text of nt to "Helvetica Neue Italic"
        set size of object text of nt to 16
        set color of object text of nt to {{22000, 22000, 22000}}
    end tell
''')

    def image_slide(self, title, image_name, caption=None):
        v = self._add_slide()
        self._add_heading(v, title)
        path = os.path.join(ASSETS, image_name)
        w, h = image_fit(path, max_w=900, max_h=540 if caption else 590)
        x = MARGIN + (CONTENT_W - w) / 2
        y = 100 + ((540 if caption else 590) - h) / 2
        self.statements.append(f'''
    tell {v}
        set img to make new image with properties {{file:POSIX file "{path}", position:{{{x}, {y}}}, width:{w}, height:{h}}}
    end tell
''')
        if caption:
            self.statements.append(f'''
    tell {v}
        set cap to make new text item with properties {{position:{{{MARGIN}, {SLIDE_H - MARGIN - 30}}}, width:{CONTENT_W}, height:30}}
        set object text of cap to "{esc(caption)}"
        set font of object text of cap to "Helvetica Neue Italic"
        set size of object text of cap to 17
        set color of object text of cap to {{15000, 15000, 15000}}
    end tell
''')

    def build_applescript(self):
        header = f'''
tell application "Keynote"
    activate
    repeat while (count of documents) > 0
        close document 1 saving no
    end repeat
    set theTheme to theme "White"
    set theDoc to make new document with properties {{document theme:theTheme}}
    delay 0.5
    set blankMaster to slide layout "Blank" of theDoc
    set titleMaster to slide layout "Title & Subtitle" of theDoc
'''
        footer = f'''
    save theDoc in POSIX file "{OUT_KEY}"
    export theDoc to POSIX file "{OUT_PDF}" as PDF
end tell
'''
        return header + "\n".join(self.statements) + footer


deck = Deck()

# ---------------------------------------------------------------------
deck.title_slide(
    "TRACE-HEP",
    "Comprehensive Documentation - v0.1.6 - Toolkit for Reading Annotated Collider-Event displays",
)

deck.text_slide("What is TRACE-HEP?", [
    "A format-agnostic Python library for reconstructed-level collider event and vertex displays",
    "",
    "Polar (phi, |eta|), beam-axis 2D, and interactive 3D event views",
    "A companion per-vertex / all-vertices family for pileup diagnostics",
    "Core package has zero ROOT/uproot dependency",
    "Optional loaders for Delphes, flat-ntuple, and calo-timing ROOT files",
    "Open source, MIT licensed",
])

deck.text_slide("Where to find it", [
    "GitHub:    github.com/wasikatcern/TRACE-HEP",
    "TestPyPI:  test.pypi.org/project/trace-hep",
    "License:   MIT",
], bullet=False, font="Menlo", font_size=22)

# ---------------------------------------------------------------------
deck.code_slide("Installation: core package", """python3 -m venv .venv
source .venv/bin/activate

pip install --index-url https://test.pypi.org/simple/ \\
            --extra-index-url https://pypi.org/simple/ \\
            trace-hep""",
    note="Core install pulls only numpy, matplotlib, and plotly.")

deck.code_slide("Installation: optional extras", """# ROOT-file loaders: Delphes, flat ntuple, calo-timing
pip install --index-url https://test.pypi.org/simple/ \\
            --extra-index-url https://pypi.org/simple/ \\
            "trace-hep[delphes]"

# + static image export (kaleido) and ATLAS style (mplhep)
pip install ... "trace-hep[all]"

# from source instead, editable (for developing tracehep itself)
git clone https://github.com/wasikatcern/TRACE-HEP.git
cd TRACE-HEP
pip install -e ".[dev]"
pytest -q""")

deck.code_slide("Verify the install", '''python3 -c "import tracehep as trace; print(trace.__version__)"
# -> 0.1.6

trace-batch --help
# -> usage: trace-batch [-h] --input FILE.root --indices N [N ...] ...''')

# ---------------------------------------------------------------------
deck.text_slide("The data model: one hard-scatter event", [
    "Jet(pt, eta, phi, mass=0, btag=False, is_hs=None)",
    "Track(pt, eta, phi, charge=0, d0=0, z0=0, x=0, y=0, z=0,",
    "      time=None, is_hs=None)",
    "Lepton(pt, eta, phi, flavor=\"muon\"|\"electron\")",
    "Photon(pt, eta, phi)",
    "MissingET(pt, phi, eta=0)",
    "",
    "Event(jets, tracks, muons, electrons, photons, met,",
    "      run=None, event_number=None, label=\"\")",
], bullet=False, font="Menlo", font_size=20)

deck.text_slide("The data model: one pileup scenario", [
    "Vertex(z, x=0, y=0, sum_pt2=0, is_hs=False, is_pu=False,",
    "       time=None, track_indices=[])",
    "TruthVertex(z, x=0, y=0, is_hs=False)",
    "",
    "VertexEvent(vertices, tracks, truth_vertices, mu=None, label=\"\")",
    "",
    "Nothing here knows about ROOT or any ntuple format -- build these",
    "by hand from your own analysis objects and every drawing",
    "function in the package works unchanged.",
], bullet=False, font="Menlo", font_size=20)

# ---------------------------------------------------------------------
deck.code_slide("Quickstart: build an event by hand", '''import tracehep as trace

event = trace.Event(
    jets=[trace.Jet(pt=180, eta=1.1, phi=0.4),
          trace.Jet(pt=95, eta=-0.6, phi=2.8, btag=True)],
    muons=[trace.Lepton(pt=60, eta=0.3, phi=-1.2, flavor="muon")],
    met=trace.MissingET(pt=140, phi=1.0),
)

fig = trace.plot_event_polar(event)
fig.savefig("event_polar.png")''')

deck.image_slide("Output: the polar (phi, |eta|) view", "quickstart_polar.png",
                  caption="trace.plot_event_polar(event)")

deck.code_slide("The beam-axis 2D projection", '''fig = trace.plot_event_beam2d(event)
fig.savefig("event_beam2d.png")''',
    note="Complementary side-on view: beam direction horizontal, transverse coordinate vertical.")

deck.image_slide("Output: the beam-axis 2D view", "quickstart_beam2d.png",
                  caption="trace.plot_event_beam2d(event)")

deck.code_slide("The interactive 3D view", '''fig3d = trace.plot_event_3d(event)
fig3d.write_html("event_3d.html")

# static snapshot (needs the kaleido extra)
fig3d.write_image("event_3d.png")''')

deck.image_slide("Output: the interactive 3D view", "quickstart_3d.png",
                  caption="Static snapshot of the interactive HTML (drag to orbit, scroll to zoom)")

# ---------------------------------------------------------------------
deck.code_slide("Loading real events: Delphes ROOT files", '''from tracehep.io.delphes import load_events

events = load_events(
    "ttbar_delphes_events.root",
    indices=[7],
    label="ttbar_delphes_events",
)
event = events[7]

fig = trace.plot_event_polar(event, show_tracks=True)
fig.savefig("event7_polar.png")''',
    note="Needs the [delphes] extra. Works unchanged on any Delphes sample, any physics process.")

deck.image_slide("Output: a real ttbar Delphes event", "real_event_polar_tracks.png",
                  caption="Event #7: 4 jets, 77 tracks, 1 muon, 4 photons, MET = 211 GeV")

# ---------------------------------------------------------------------
deck.code_slide("Highlighting displaced tracks (d0)", '''fig = trace.plot_event_polar(
    event, show_tracks=True, d0_displaced_mm=1.0,
)
fig.savefig("event_displaced_polar.png")

fig3d = trace.plot_event_3d(event, d0_displaced_mm=1.0)
fig3d.write_html("event_displaced_3d.html")''',
    note="Tracks with |d0| above the threshold are coloured distinctly from prompt tracks.")

deck.image_slide("Output: displaced tracks (polar view)", "displaced_polar.png",
                  caption="4 of 45 tracks flagged as displaced (|d0| > 1 mm), picked out in red")

deck.image_slide("Output: displaced tracks (3D view)", "displaced_3d.png",
                  caption="Same event -- displaced-track origins marked distinctly in 3D")

# ---------------------------------------------------------------------
deck.code_slide("Vertex displays: loading a pileup ntuple", '''from tracehep.io.calotiming import load_vertex_event

vtx_event = load_vertex_event(
    "calo_timing_ntuple.root",
    event_index=37,
)
print(len(vtx_event.vertices), "vertices")
print(vtx_event.mu, "<mu>")
# -> 99 vertices
# -> 195.0 <mu>''')

deck.code_slide("The z-R vertex display, three styles", '''from tracehep import plot_vertices_zr

plot_vertices_zr(vtx_event, style="plain").savefig("plain.png")
plot_vertices_zr(vtx_event, style="styled").savefig("styled.png")
plot_vertices_zr(vtx_event, style="time_colored").savefig("time.png")''',
    note='style is one of "plain", "styled", or "time_colored".')

deck.image_slide('Output: style="plain"', "vertices_plain.png",
                  caption="Flat HS (blue) / PU (red) track colouring, fixed vertex marker size")

deck.image_slide('Output: style="styled"', "vertices_styled.png",
                  caption="Vertex marker size proportional to sqrt(sum pT^2); <mu> reported in the title")

deck.image_slide('Output: style="time_colored"', "vertices_time_colored.png",
                  caption="PU tracks coloured by reconstructed track time (needs per-track timing)")

deck.code_slide("Zooming into one vertex", '''plot_vertices_zr(
    vtx_event, style="styled",
    zoom_center=-44.2, zoom_range_mm=5.0,
)''',
    note="Same function -- pass zoom_center/zoom_range_mm to reproduce a single-vertex zoomed view.")

deck.code_slide("Interactive 3D vertex display", '''from tracehep import plot_vertices_3d

fig = plot_vertices_3d(vtx_event)
fig.write_html("vertices_3d.html")''')

deck.image_slide("Output: the interactive 3D vertex view", "vertices_3d.png",
                  caption="Every reconstructed and truth vertex at its real (x, y, z) position")

# ---------------------------------------------------------------------
deck.code_slide("One vertex, with its associated jets", '''from tracehep import plot_vertex_detail
from tracehep.io.calotiming import match_jets_to_vertex

vtx = vtx_event.vertices[0]
jets = match_jets_to_vertex(
    "calo_timing_ntuple.root", event_index=37, vtx_z=vtx.z,
)

fig = plot_vertex_detail(vtx_event, vtx_index=0, jets=jets)
fig.savefig("vertex0_detail.png")''',
    note="match_jets_to_vertex associates jets by Rpt (track-pT-fraction) matching -- bring your own jets for a different scheme.")

deck.image_slide("Output: single-vertex detail with jets", "vertex_detail.png",
                  caption="Vertex 0 (HS): 10 jets matched (9 truth-HS, 1 truth-PU), sum(pT^2) = 2.5e3 GeV^2 -- tracks and jets each coloured by their own truth match")

# ---------------------------------------------------------------------
deck.text_slide("Filtering and jet collections", [
    "Real analyses rarely want every jet or every track --",
    "trace-hep supports both, without touching a single plotting function:",
    "",
    "1) Jet collection is a LOADER choice",
    "   -- which ROOT branches to read (Jet, GenJet, JetPUPPI, ...)",
    "",
    "2) pT / eta cuts are a POST-LOAD, format-agnostic filter",
    "   -- tracehep.filters transforms an already-loaded Event or",
    "      VertexEvent, so one cut applies identically to every",
    "      display: polar, beam2d, 3D, z-R, vertex-detail, ...",
], bullet=False, font_size=22)

deck.code_slide("Choosing a jet collection", '''from tracehep.io.delphes import load_events

# a Delphes card can define several jet collections --
# default is "Jet"; read a different one by name
events = load_events(
    "ttbar_delphes_events.root", indices=[7],
    jet_collection="ParticleFlowJet04",
)
trace.plot_event_polar(events[7], show_tracks=True)''',
    note='Also works for match_jets_to_vertex (jet_collection="AntiKt4EMPFlowJets", ...) and the flat-ntuple loader (jet_branches=(...), bjet_branches=(...)).')

deck.image_slide("Output: ParticleFlowJet04 vs. the default Jet collection", "filter_jet_collection.png",
                  caption="Same event, different jet collection: Jet 1 = 401 GeV here vs. 243 GeV with the default \"Jet\" collection -- a different clustering algorithm/input, same event")

deck.code_slide("Cutting on pT and eta", '''from tracehep.filters import filter_event

event = load_events("ttbar_delphes_events.root", indices=[7])[7]

# keep only jets above 50 GeV within |eta| < 2.5,
# and tracks above 2 GeV within |eta| < 2.5
tight = filter_event(
    event,
    jet_pt_min=50.0, jet_eta_min=-2.5, jet_eta_max=2.5,
    track_pt_min=2.0, track_eta_min=-2.5, track_eta_max=2.5,
)
trace.plot_event_polar(tight, show_tracks=True)''',
    note="eta_min/eta_max bound eta directly (signed, not abs(eta)) -- pass eta_min=0 to keep only positive-eta objects.")

deck.image_slide("Output: after pT/eta cuts", "filter_event_cuts.png",
                  caption="Same event 7: 77 -> 36 tracks after the pT/eta cut (all 4 jets already passed pT>50 GeV, |eta|<2.5)")

deck.code_slide("Filtering a vertex scenario", '''from tracehep.filters import filter_vertex_event

vtx_event = load_vertex_event("calo_timing_ntuple.root", event_index=37)
vtx_event = filter_vertex_event(
    vtx_event, track_pt_min=1.0, track_eta_min=-2.5, track_eta_max=2.5,
)
plot_vertices_zr(vtx_event, style="styled")''',
    note="Vertices are never dropped, only the tracks fit to them -- each vertex's track_indices is remapped to stay consistent.")

deck.image_slide("Output: vertex 0 after track pT/eta cuts", "filter_vertex_tight.png",
                  caption="Event 37: 969 -> 607 tracks event-wide after the cut; vertex 0 goes from 10 to 5 matched jets once jet_pt_min=50 GeV is also applied")

deck.text_slide("Filtering from the command line", [
    "trace-batch --input sample.root --indices 0 1 2 --outdir out/ \\",
    "    --jet-collection ParticleFlowJet04 \\",
    "    --jet-pt-min 30 --jet-eta-min -2.5 --jet-eta-max 2.5 \\",
    "    --show-tracks --track-pt-min 1.0 \\",
    "    --track-eta-min -2.5 --track-eta-max 2.5",
    "",
    "Every filter available in Python is also a trace-batch flag --",
    "no code needed for a batch of cut, collection-specific displays.",
], bullet=False, font="Menlo", font_size=17)

# ---------------------------------------------------------------------
deck.code_slide("Batch processing many events at once", '''from tracehep.io.delphes import load_events
from tracehep.batch import run_event_batch

events = load_events(path, indices=range(20))
run_event_batch(
    events, "out/", which=("polar", "beam2d"),
    polar_kwargs={"show_tracks": True},
)
# -> out/event0_polar.png, out/event0_beam2d.png, ...''')

deck.code_slide("Batch processing vertex scenarios", '''from tracehep.io.calotiming import load_vertex_event
from tracehep.batch import run_vertex_batch

vtx_events = {i: load_vertex_event(path, i) for i in range(10)}
run_vertex_batch(vtx_events, "out/", styles=("plain", "styled"))
# -> out/vertices0_plain.png, out/vertices0_styled.png, ...''')

deck.code_slide("The trace-batch command-line tool", '''trace-batch \\
    --input ttbar_delphes_events.root \\
    --indices 0 1 2 \\
    --outdir out/ \\
    --which polar beam2d \\
    --show-tracks \\
    --label my_sample''',
    note="No Python required -- useful for quick batch regeneration from a shell script.")

# ---------------------------------------------------------------------
deck.text_slide("Function reference: event displays", [
    "plot_event_polar(event, *, ax=None, eta_max=4.0, pt_scale=0.003,",
    "    eta_guides=(0,1,2.5,4.0), show_tracks=False,",
    "    track_pt_scale=0.15, d0_displaced_mm=None, title=None)",
    "",
    "plot_event_beam2d(event, *, ax=None,",
    "    eta_guides=(2.5,4.0), angle_scale=4.0, title=None)",
    "",
    "plot_event_3d(event, *, d0_displaced_mm=None,",
    "    jet_half_angle_deg=9.0, title=None)",
], bullet=False, font="Menlo", font_size=18)

deck.text_slide("Function reference: vertex displays", [
    'plot_vertices_zr(vertex_event, *, style="plain",',
    "    zoom_center=None, zoom_range_mm=None,",
    "    ax=None, title=None)",
    "",
    "plot_vertex_detail(vertex_event, vtx_index, jets=(),",
    "    *, zoom_range_mm=5.0, ax=None, title=None)",
    "",
    "plot_vertices_3d(vertex_event, *, title=None)",
    "",
    "run_event_batch(events, outdir, *, which=(...),",
    "    polar_kwargs=None, beam2d_kwargs=None)",
    "run_vertex_batch(vertex_events, outdir, *, styles=(...))",
], bullet=False, font="Menlo", font_size=17)

deck.text_slide("Loader reference (tracehep.io)", [
    'delphes.load_event(path, index, with_tracks=True,',
    '    jet_collection="Jet", label="")',
    "delphes.load_events(path, indices, with_tracks=True,",
    '    jet_collection="Jet", label="")',
    "",
    "flat_ntuple.load_event_by_run_event(path, run, event,",
    '    tree_name="Ntuple", jet_branches=("JET_pt","JET_eta","JET_phi"),',
    '    bjet_branches=("bJET_pt","bJET_eta","bJET_phi"), label="")',
    "flat_ntuple.load_events_by_run_event(path, pairs, ...)",
    "",
    'calotiming.load_vertex_event(path, event_index,',
    '    tree_name="ntuple", label="")',
    "calotiming.match_jets_to_vertex(path, event_index, vtx_z,",
    '    *, jet_collection="AntiKt4EMTopoJets", track_idx_branch=None,',
    "    jet_pt_min=30.0, rpt_min=0.02, sig_cut=3.0)",
    "",
    "All four require: pip install \"trace-hep[delphes]\"",
], bullet=False, font="Menlo", font_size=15)

deck.text_slide("Filter reference (tracehep.filters)", [
    "filter_event(event, *, jet_pt_min=None, jet_pt_max=None,",
    "    jet_eta_min=None, jet_eta_max=None, track_pt_min=None,",
    "    track_pt_max=None, track_eta_min=None, track_eta_max=None)",
    "",
    "filter_vertex_event(vertex_event, *, track_pt_min=None,",
    "    track_pt_max=None, track_eta_min=None, track_eta_max=None)",
    "",
    "filter_jets(jets, *, pt_min=None, pt_max=None,",
    "    eta_min=None, eta_max=None, btag_only=False)",
    "filter_tracks(tracks, *, pt_min=None, pt_max=None,",
    "    eta_min=None, eta_max=None)",
    "",
    "All four return a filtered COPY -- the input is never modified.",
], bullet=False, font="Menlo", font_size=16)

# ---------------------------------------------------------------------
deck.text_slide("Troubleshooting", [
    "ImportError: uproot required",
    "  -> pip install \"trace-hep[delphes]\"",
    "",
    "ModuleNotFoundError: No module named tracehep (right after install)",
    "  -> from TestPyPI you need BOTH --index-url and",
    "     --extra-index-url (see Installation slides)",
    "",
    "KeyError from flat_ntuple loader",
    "  -> the (run, event) pair is not present in that file",
    "",
    "A track's 3D origin looks wrong from a calo-timing ntuple",
    "  -> that format has no per-track (x, y, z); origin defaults",
    "     to the owning vertex's (x, y) plus the track's own z0",
])

deck.text_slide("Versioning and updates", [
    "Published package versions are immutable",
    "  -> updating requires bumping the version and re-uploading",
    "",
    "Typical update loop:",
    "  edit code in src/tracehep/",
    "  add/update a test",
    "  bump version in pyproject.toml and __init__.py",
    "  python3 -m build",
    "  twine upload --repository-url https://test.pypi.org/legacy/ dist/*",
])

deck.text_slide("Get involved", [
    "Source:    github.com/wasikatcern/TRACE-HEP",
    "Install:   pip install trace-hep  (TestPyPI now; PyPI planned)",
    "License:   MIT",
    "Tests:     pytest -q   (32 passing at v0.1.6)",
    "Contact:   wasikul.islam@cern.ch",
    "",
    "Citing: accompanying paper citation to be added once posted.",
], bullet=False, font="Menlo", font_size=20)

# ---------------------------------------------------------------------
script = deck.build_applescript()
with open(SCRIPT_PATH, "w") as fh:
    fh.write(script)
print(f"Wrote {SCRIPT_PATH} ({deck.slide_count + 1} slides)")

result = subprocess.run(["osascript", SCRIPT_PATH], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr)
    raise SystemExit(result.returncode)
print(f"Saved {OUT_KEY}")
print(f"Saved {OUT_PDF}")
