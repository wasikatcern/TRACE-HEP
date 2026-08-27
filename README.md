# TRACE

**T**oolkit for **R**eading **A**nnotated **C**ollider-**E**vent displays.

A lightweight, format-agnostic library for reconstructed-level collider
event and vertex displays: polar (phi, |eta|) views, beam-axis 2D
projections, and interactive 3D views, plus a companion family of
per-vertex / all-vertices displays for pileup diagnostics.

## Install

```bash
pip install trace-hep              # core: numpy, matplotlib, plotly only
pip install trace-hep[delphes]     # + uproot/awkward, for the bundled Delphes/flat-ntuple/calo-timing loaders
pip install trace-hep[all]         # + kaleido (static image export), mplhep (ATLAS style)
```

## Quickstart: build an event by hand

The core library never requires ROOT, uproot, or any specific ntuple
format -- build an `Event` from whatever objects your own analysis already
has, and every drawing function works unchanged:

```python
import tracehep as trace

event = trace.Event(
    jets=[trace.Jet(pt=180, eta=1.1, phi=0.4), trace.Jet(pt=95, eta=-0.6, phi=2.8, btag=True)],
    muons=[trace.Lepton(pt=60, eta=0.3, phi=-1.2, flavor="muon")],
    met=trace.MissingET(pt=140, phi=1.0),
)

fig = trace.plot_event_polar(event)
fig.savefig("event_polar.png")

fig3d = trace.plot_event_3d(event)
fig3d.write_html("event_3d.html")
```

## Quickstart: load events from a Delphes ROOT file

```python
import tracehep as trace
from tracehep.io.delphes import load_events

events = load_events("my_sample.root", indices=[0, 1, 2], label="my_sample")
for idx, event in events.items():
    trace.plot_event_polar(event, show_tracks=True).savefig(f"event{idx}_polar.png")
```

Or from the command line, no Python required:

```bash
trace-batch --input my_sample.root --indices 0 1 2 --outdir out/ --which polar beam2d
```

## Vertex displays

```python
from tracehep.io.calotiming import load_vertex_event
from tracehep import plot_vertices_zr, plot_vertices_3d

vtx_event = load_vertex_event("my_pileup_ntuple.root", event_index=37)
plot_vertices_zr(vtx_event, style="styled").savefig("vertices.png")
plot_vertices_3d(vtx_event).write_html("vertices_3d.html")
```

### One vertex, with its associated jets

`plot_vertices_zr`/`plot_vertices_3d` survey every vertex in the event.
`plot_vertex_detail` instead zooms into *one* vertex and draws any jets
already associated with it as cones, plus a sum(pT^2) / reco-z / truth-z
annotation. Tracks and jets are each coloured by their own truth-level
hard-scatter match (`Track.is_hs` / `Jet.is_hs`) when available, not by the
owning vertex's overall flag -- a reconstructed "HS" vertex routinely
contains a genuine mix of truth-HS and truth-PU tracks, and the jets
matched to it are usually mostly-but-not-entirely truth-HS too:

```python
from tracehep import plot_vertex_detail
from tracehep.io.calotiming import match_jets_to_vertex

vtx = vtx_event.vertices[0]
jets = match_jets_to_vertex("my_pileup_ntuple.root", event_index=37, vtx_z=vtx.z)

plot_vertex_detail(vtx_event, vtx_index=0, jets=jets).savefig("vertex0_detail.png")
```

`match_jets_to_vertex` associates jets to a vertex by Rpt (the fraction of a
jet's pT carried by tracks compatible with that vertex's z) -- the same
matching used to build the original single-vertex displays this function
replaces. Jet-to-vertex association is analysis-specific, so it's kept as
an explicit, separate step rather than hidden inside `plot_vertex_detail`;
bring your own jets (any list of `Jet`) if you have a different matching
scheme, or if you're not using a calo-timing ntuple at all.

Different ntuple productions name the jet collection and its
constituent-track branch differently -- pass `jet_collection` and/or
`track_idx_branch` to override the defaults
(`jet_collection="AntiKt4EMTopoJets"`, and either `{jet_collection}_track_idx`
or `{jet_collection}_ghostTrack_idx`, auto-detected):

```python
jets = match_jets_to_vertex(
    "my_pileup_ntuple.root", event_index=37, vtx_z=vtx.z,
    jet_collection="AntiKt4EMPFlowJets", track_idx_branch="AntiKt4EMPFlowJets_ghostTrack_idx",
)
```

## Displaced tracks

`Track.d0` (transverse impact parameter) is a first-class field on every
track. Pass `d0_displaced_mm` to `plot_event_polar` or `plot_event_3d` to
colour tracks above that threshold distinctly -- useful for spotting
long-lived-particle decay topologies:

```python
trace.plot_event_polar(event, show_tracks=True, d0_displaced_mm=1.0)
```

## Data model

Every drawing function accepts plain dataclasses from `tracehep.models`:
`Jet`, `Track`, `Lepton`, `Photon`, `MissingET`, `Event` (one hard-scatter
interaction's objects) and `Vertex`, `TruthVertex`, `VertexEvent` (one
pileup scenario's many vertices sharing a track collection). See
`tracehep/models.py` for the full field list.

`Jet.is_hs` and `Track.is_hs` carry each object's own truth-level
hard-scatter match (`Optional[bool]`, `None` when truth information isn't
available, e.g. on real data). The calo-timing loaders populate both from
truth branches when present; vertex displays colour tracks and jets by
these fields, falling back to the owning vertex's `is_hs`/`is_pu` flag only
when an individual object has no truth match of its own.

## Status

Early (v0.1) release. The core API (`plot_event_polar`, `plot_event_beam2d`,
`plot_event_3d`, `plot_vertices_zr`, `plot_vertices_3d`) is considered
stable; loaders in `tracehep.io` may gain new formats over time.

## Citing

If you use TRACE in a publication, please cite the accompanying paper
(citation to be added once posted).
