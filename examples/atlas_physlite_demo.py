"""Draw a real vertex display from ATLAS's public research-grade Open Data
(DAOD_PHYSLITE, 2024 release) -- streamed directly, nothing downloaded.

Usage:
    pip install "trace-hep[delphes]"   # uproot is all this needs
    python3 atlas_physlite_demo.py

IMPORTANT: only the hard-scatter vertex keeps its tracks in this public
release (PHYSLITE thins away pileup-vertex tracks to save space) -- see
tracehep.io.atlas_physlite's module docstring for how this was verified.
So the "styled" plot below shows every vertex's real position along the
beamline, but only the hard-scatter vertex gets a track fan; the
vertex-detail plot only makes sense for that one vertex.
"""

import tracehep as trace
from tracehep.io.atlas_physlite import load_vertex_event

URL = (
    "https://opendata.cern.ch/eos/opendata/atlas/rucio/mc20_13TeV/"
    "DAOD_PHYSLITE.37620644._000012.pool.root.1"
)

print("Streaming one event from a 2.3 GB PHYSLITE file (nothing downloaded)...")
vtx_event = load_vertex_event(URL, event_index=2, label="ATLAS Open Data (PHYSLITE research release)")
print(f"{len(vtx_event.vertices)} vertices, {len(vtx_event.tracks)} tracks total")

fig = trace.plot_vertices_zr(vtx_event, style="styled")
fig.savefig("physlite_vertices.png", dpi=150, bbox_inches="tight")
print("-> physlite_vertices.png (every vertex's real position)")

hs_idx = next(i for i, v in enumerate(vtx_event.vertices) if v.is_hs)
hs_vertex = vtx_event.vertices[hs_idx]
print(f"hard-scatter vertex: {len(hs_vertex.track_indices)} tracks, "
      f"sum(pT^2) = {hs_vertex.sum_pt2:.1f} GeV^2")

fig2 = trace.plot_vertex_detail(vtx_event, vtx_index=hs_idx, zoom_range_mm=3.0)
fig2.savefig("physlite_hs_vertex_detail.png", dpi=150, bbox_inches="tight")
print("-> physlite_hs_vertex_detail.png (its real, genuine ATLAS-reconstructed tracks)")
