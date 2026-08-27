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

## Status

Early (v0.1) release. The core API (`plot_event_polar`, `plot_event_beam2d`,
`plot_event_3d`, `plot_vertices_zr`, `plot_vertices_3d`) is considered
stable; loaders in `tracehep.io` may gain new formats over time.

## Citing

If you use TRACE in a publication, please cite the accompanying paper
(citation to be added once posted).
