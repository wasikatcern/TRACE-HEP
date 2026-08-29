# TRACE

**T**oolkit for **R**endering **a**nd **A**nalysis of **C**ollider **E**vents.

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

`load_events`/`load_event` read the standard Delphes `"Jet"` collection by
default; pass `jet_collection=` to read a different one instead (a given
Delphes card can define several -- `"GenJet"`, `"JetPUPPI"`,
`"ParticleFlowJet04"`, a large-R `"CaloJet08"`, ...):

```python
events = load_events("my_sample.root", indices=[0], jet_collection="ParticleFlowJet04")
```

Or from the command line, no Python required:

```bash
trace-batch --input my_sample.root --indices 0 1 2 --outdir out/ --which polar beam2d \
    --jet-collection ParticleFlowJet04 --jet-pt-min 30 --show-tracks --track-pt-min 1.0 --track-eta-max 2.5
```

## Quickstart: load real public ATLAS Open Data

`tracehep.io.atlas_opendata` reads the public ATLAS Open Data 13 TeV
"mini-ntuple" format (opendata.atlas.cern) directly -- the same flat schema
is used for every released dataset (SM, Higgs, SUSY, exotic-resonance
searches, ...), so this works unchanged across all of them. Find file URLs
with the companion `atlasopenmagic` package rather than guessing paths by
hand (`pip install trace-hep[opendata]`):

```python
import atlasopenmagic as atom
atom.set_release("2020e-13tev")
urls = atom.get_urls("410000", skim="2lep", protocol="https")  # ttbar, dilepton skim
```

```python
import tracehep as trace
from tracehep.io.atlas_opendata import load_events

events = load_events("mc_410000.ttbar_lep.2lep.root", indices=[0, 1, 2], label="ttbar (ATLAS Open Data)")
trace.plot_event_polar(events[0]).savefig("event0_polar.png")
```

Momenta are stored in MeV in this ntuple; the loader converts to GeV
automatically. B-tagging is a continuous `jet_MV2c10` discriminant rather
than a boolean -- pass `btag_cut` to choose the working point (default:
the 77%-efficiency cut used throughout the ATLAS Open Data tutorials).
Pass `include_large_r_jets=True` to also draw the large-R jet collection
(e.g. for a boosted-topology skim like `1largeRjet1lep`) -- note that a
large-R jet's label will naturally overlap its constituent small-R jets in
the polar view, since they point in the same direction by construction.
This ntuple format has no track- or vertex-level information, so it feeds
`Event`/the event-display functions only, not the vertex/pileup side of
tracehep.

## Quickstart: load real public CMS Open Data

`tracehep.io.cms_opendata` reads the public CMS Open Data reduced "NanoAOD
outreach" format (opendata.cern.ch, `AOD2NanoAODOutreachTool` derivatives)
-- covering both 2012 (8 TeV) simulated samples (`TTbar`, `SMHiggsToZZTo4L`,
`ZZTo4mu`, ...) and **real collision data** (`Run2012B_DoubleMuParked`,
`Run2012B_DoubleElectron`, ...). Different sub-releases carry different
object collections (some have Jet+Muon+Tau, some have Muon+Electron only);
the loader detects what's actually present rather than requiring
per-sample configuration. Momenta are already in GeV (standard NanoAOD
convention), unlike the ATLAS mini-ntuple's MeV.

These files can be large (tens of MB to tens of GB) -- pass an
`https://opendata.cern.ch/eos/opendata/...` URL directly as `path` and
uproot streams only the bytes it needs, without downloading the whole file:

```python
import tracehep as trace
from tracehep.io.cms_opendata import load_events

url = "https://opendata.cern.ch/eos/opendata/cms/derived-data/AOD2NanoAODOutreachTool/TTbar.root"
events = load_events(url, indices=[0, 1, 2], label="ttbar (CMS Open Data)")
trace.plot_event_polar(events[0]).savefig("event0_polar.png")
```

B-tagging is a continuous `Jet_btag` discriminant rather than a boolean --
pass `btag_cut` to choose the working point (default: 0.679, the CSVv2
"medium" working point used in 2012 CMS analyses). Like the ATLAS loader,
this format has no track- or vertex-level information.

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

## Filtering: pT/eta cuts and jet collections

Cuts are a post-load transformation, not a plotting-function argument --
`tracehep.filters` returns a filtered *copy* of an `Event` or
`VertexEvent`, and every drawing function works on it unchanged, so one cut
applies identically to the polar, beam2d, 3D, z-R, and vertex-detail views:

```python
from tracehep.filters import filter_event

event = load_events("my_sample.root", indices=[0])[0]

# keep only jets above 50 GeV within |eta| < 2.5, and tracks above 1 GeV
tight = filter_event(
    event,
    jet_pt_min=50.0, jet_eta_min=-2.5, jet_eta_max=2.5,
    track_pt_min=1.0,
)
trace.plot_event_polar(tight, show_tracks=True).savefig("event0_tight.png")
```

`eta_min`/`eta_max` bound `eta` directly (signed, not `abs(eta)`) -- pass
`jet_eta_min=0` to keep only positive-eta jets, or symmetric bounds like
`track_eta_min=-2.5, track_eta_max=2.5` for a central-only selection.
`filter_jets`/`filter_tracks` apply the same cuts to a bare list if you'd
rather filter before building an `Event` yourself; `filter_jets` also takes
`btag_only=True`.

The same cuts work on pileup scenarios via `filter_vertex_event` -- vertices
are never dropped, only the tracks fit to them (each vertex's
`track_indices` is remapped to stay consistent):

```python
from tracehep.filters import filter_vertex_event

vtx_event = load_vertex_event("my_pileup_ntuple.root", event_index=37)
vtx_event = filter_vertex_event(vtx_event, track_pt_min=1.0, track_eta_min=-2.5, track_eta_max=2.5)

plot_vertices_zr(vtx_event, style="styled").savefig("vertices_tight.png")
```

Jet *collection* (as opposed to a cut) is a loader-level choice, since it
picks which ROOT branches to read -- see `jet_collection` above for the
Delphes loader and `jet_collection`/`track_idx_branch` above for
`match_jets_to_vertex`; the flat-ntuple loader takes the analogous
`jet_branches`/`bjet_branches` (see `tracehep/io/flat_ntuple.py`).

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

`tracehep.filters` (`filter_event`, `filter_vertex_event`, `filter_jets`,
`filter_tracks`) applies pT/eta cuts to any of these objects after loading
-- see "Filtering" above.

## Status

Early (v0.1) release. The core API (`plot_event_polar`, `plot_event_beam2d`,
`plot_event_3d`, `plot_vertices_zr`, `plot_vertices_3d`) is considered
stable; loaders in `tracehep.io` may gain new formats over time.

## Citing

If you use TRACE in a publication, please cite the accompanying paper
(citation to be added once posted).
