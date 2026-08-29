"""Draw a real vertex display from ATLAS's public research-grade Open Data
(DAOD_PHYSLITE, 2024 release) -- streamed directly, nothing downloaded.

Usage:
    pip install "trace-hep[delphes]"   # uproot is all this needs
    python3 atlas_physlite_demo.py

IMPORTANT (measured against 200 real events, not assumed): PHYSLITE thins
away most pileup-vertex tracks to save space -- 199/200 hard-scatter
vertices keep a real track collection, but only ~3.6% of pileup vertices
retain any tracks at all. See tracehep.io.atlas_physlite's module
docstring for the full numbers. Event 50 below was picked because it's
one of the ~3.6% -- most events won't show any pileup tracks in the
"styled" survey plot. Jets and tracks here carry no truth-level HS/PU
classification, so they're drawn in one neutral colour each --
"Tracks"/"Jet" -- rather than a split the data doesn't support.
"""

import tracehep as trace
from tracehep.io.atlas_physlite import load_event_jets, load_vertex_event

URL = (
    "https://opendata.cern.ch/eos/opendata/atlas/rucio/mc20_13TeV/"
    "DAOD_PHYSLITE.37620644._000012.pool.root.1"
)

print("Streaming event 50 (has real pileup-vertex tracks) from a 2.3 GB PHYSLITE file...")
survey_event = load_vertex_event(URL, event_index=50, label="ATLAS Open Data (PHYSLITE research release)")
n_pu_with_tracks = sum(1 for v in survey_event.vertices if v.is_pu and v.track_indices)
print(f"{len(survey_event.vertices)} vertices, {len(survey_event.tracks)} tracks total "
      f"({n_pu_with_tracks} pileup vertices retained tracks)")

fig = trace.plot_vertices_zr(survey_event, style="styled")
fig.savefig("physlite_vertices.png", dpi=150, bbox_inches="tight")
print("-> physlite_vertices.png (every vertex's real position)")

print("Streaming event 2 (a richer hard-scatter vertex) for the detail plot...")
vtx_event = load_vertex_event(URL, event_index=2, label="ATLAS Open Data (PHYSLITE research release)")
hs_idx = next(i for i, v in enumerate(vtx_event.vertices) if v.is_hs)
hs_vertex = vtx_event.vertices[hs_idx]
print(f"hard-scatter vertex: {len(hs_vertex.track_indices)} tracks, "
      f"sum(pT^2) = {hs_vertex.sum_pt2:.1f} GeV^2")

# This event's calibrated jets -- not vertex-associated and no truth in this
# release, so plot_vertex_detail draws them all in one neutral colour rather
# than a misleading HS/PU split (see tracehep.io.atlas_physlite's docstring).
jets = load_event_jets(URL, event_index=2)
print(f"{len(jets)} jets (pT >= 20 GeV, no vertex association or truth)")

fig2 = trace.plot_vertex_detail(vtx_event, vtx_index=hs_idx, jets=jets, zoom_range_mm=3.0)
fig2.savefig("physlite_hs_vertex_detail.png", dpi=150, bbox_inches="tight")
print("-> physlite_hs_vertex_detail.png (its real, genuine ATLAS-reconstructed tracks and jets)")
