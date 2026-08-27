##############################################################
######## Generate every output image used in the         ######
######## trace-hep documentation, from the real installed ######
######## package against real data (not synthetic mocks)  ######
##############################################################
#
# Usage:
#   python3 generate_doc_assets.py

import os

import matplotlib
matplotlib.use("Agg")

import tracehep as trace
from tracehep.io.delphes import load_events
from tracehep.io.calotiming import load_vertex_event, match_jets_to_vertex
from tracehep.filters import filter_event, filter_vertex_event

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "assets")
os.makedirs(OUTDIR, exist_ok=True)

DELPHES_FILE = "/Users/wasikul/Desktop/madgraph/MG5_aMC_v2_9_16/ttbar_HLLHC_1/Events/run_01/ttbar_delphes_events.root"
VERTEX_FILE = "/Users/wasikul/Desktop/4D_tracking/my_results/ttbar/user.scheong.42774615.EXT0._000002.CaloTimingNtuple.root"

print("=== 1. Quickstart: hand-built Event ===")
event = trace.Event(
    jets=[trace.Jet(pt=180, eta=1.1, phi=0.4), trace.Jet(pt=95, eta=-0.6, phi=2.8, btag=True)],
    muons=[trace.Lepton(pt=60, eta=0.3, phi=-1.2, flavor="muon")],
    met=trace.MissingET(pt=140, phi=1.0),
)
fig = trace.plot_event_polar(event)
fig.savefig(os.path.join(OUTDIR, "quickstart_polar.png"), dpi=150, bbox_inches="tight")
print("  quickstart_polar.png")

fig2 = trace.plot_event_beam2d(event)
fig2.savefig(os.path.join(OUTDIR, "quickstart_beam2d.png"), dpi=150, bbox_inches="tight")
print("  quickstart_beam2d.png")

fig3 = trace.plot_event_3d(event)
fig3.write_image(os.path.join(OUTDIR, "quickstart_3d.png"), width=1000, height=700, scale=2)
print("  quickstart_3d.png")

print("=== 2. Real Delphes sample (event 7, with tracks) ===")
events = load_events(DELPHES_FILE, indices=[7], with_tracks=True, label="ttbar_delphes_events")
ev7 = events[7]
fig4 = trace.plot_event_polar(ev7, show_tracks=True)
fig4.savefig(os.path.join(OUTDIR, "real_event_polar_tracks.png"), dpi=150, bbox_inches="tight")
print(f"  real_event_polar_tracks.png ({len(ev7.jets)} jets, {len(ev7.tracks)} tracks)")

print("=== 3. Displaced-track highlighting (event 183, has a genuinely displaced track) ===")
events2 = load_events(DELPHES_FILE, indices=[183], with_tracks=True, label="ttbar_delphes_events")
ev183 = events2[183]
n_disp = sum(1 for t in ev183.tracks if abs(t.d0) > 1.0)
fig5 = trace.plot_event_polar(ev183, show_tracks=True, d0_displaced_mm=1.0)
fig5.savefig(os.path.join(OUTDIR, "displaced_polar.png"), dpi=150, bbox_inches="tight")
print(f"  displaced_polar.png ({n_disp} displaced tracks)")

fig6 = trace.plot_event_3d(ev183, d0_displaced_mm=1.0)
fig6.write_image(os.path.join(OUTDIR, "displaced_3d.png"), width=1000, height=700, scale=2)
print("  displaced_3d.png")

print("=== 4. Vertex displays (real CaloTiming ntuple, event 37) ===")
vtx_event = load_vertex_event(VERTEX_FILE, event_index=37, label="ttbar CaloTiming, event 37")
print(f"  loaded {len(vtx_event.vertices)} vertices, {len(vtx_event.tracks)} tracks, mu={vtx_event.mu}")

for style in ("plain", "styled", "time_colored"):
    fig = trace.plot_vertices_zr(vtx_event, style=style)
    fig.savefig(os.path.join(OUTDIR, f"vertices_{style}.png"), dpi=140, bbox_inches="tight")
    print(f"  vertices_{style}.png")

fig7 = trace.plot_vertices_3d(vtx_event)
fig7.write_image(os.path.join(OUTDIR, "vertices_3d.png"), width=1000, height=700, scale=2)
print("  vertices_3d.png")

print("=== 5. Single-vertex detail with associated jets (event 37, vertex 0 = HS) ===")
vtx0 = vtx_event.vertices[0]
jets = match_jets_to_vertex(VERTEX_FILE, event_index=37, vtx_z=vtx0.z)
print(f"  vertex 0: is_hs={vtx0.is_hs}, sum_pt2={vtx0.sum_pt2:.1f}, {len(jets)} jets matched")
fig8 = trace.plot_vertex_detail(vtx_event, vtx_index=0, jets=jets)
fig8.savefig(os.path.join(OUTDIR, "vertex_detail.png"), dpi=150, bbox_inches="tight")
print("  vertex_detail.png")

print("=== 6. Filtering: a different jet collection (event 7) ===")
events_pf = load_events(DELPHES_FILE, indices=[7], with_tracks=True, jet_collection="ParticleFlowJet04",
                         label="ttbar_delphes_events, ParticleFlowJet04")
ev7_pf = events_pf[7]
fig9 = trace.plot_event_polar(ev7_pf, show_tracks=True)
fig9.savefig(os.path.join(OUTDIR, "filter_jet_collection.png"), dpi=150, bbox_inches="tight")
print(f"  filter_jet_collection.png (ParticleFlowJet04: {len(ev7_pf.jets)} jets, "
      f"default Jet collection: {len(ev7.jets)} jets)")

print("=== 7. Filtering: pT/eta cuts on the same event (event 7) ===")
ev7_tight = filter_event(ev7, jet_pt_min=50.0, jet_eta_min=-2.5, jet_eta_max=2.5,
                          track_pt_min=2.0, track_eta_min=-2.5, track_eta_max=2.5)
fig10 = trace.plot_event_polar(ev7_tight, show_tracks=True)
fig10.savefig(os.path.join(OUTDIR, "filter_event_cuts.png"), dpi=150, bbox_inches="tight")
print(f"  filter_event_cuts.png ({len(ev7.jets)} -> {len(ev7_tight.jets)} jets, "
      f"{len(ev7.tracks)} -> {len(ev7_tight.tracks)} tracks)")

print("=== 8. Filtering: pT/eta cuts on a vertex scenario (event 37, vertex 0) ===")
vtx_event_tight = filter_vertex_event(vtx_event, track_pt_min=1.0, track_eta_min=-2.5, track_eta_max=2.5)
jets_tight = match_jets_to_vertex(VERTEX_FILE, event_index=37, vtx_z=vtx0.z, jet_pt_min=50.0)
fig11 = trace.plot_vertex_detail(vtx_event_tight, vtx_index=0, jets=jets_tight)
fig11.savefig(os.path.join(OUTDIR, "filter_vertex_tight.png"), dpi=150, bbox_inches="tight")
print(f"  filter_vertex_tight.png ({len(vtx_event.tracks)} -> {len(vtx_event_tight.tracks)} tracks total, "
      f"{len(jets)} -> {len(jets_tight)} jets on vertex 0)")

print("\nAll documentation assets written to", OUTDIR)
