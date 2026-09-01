# TRACE

**T**oolkit for **R**endering **a**nd **A**nalysis of **C**ollider **E**vents.

A lightweight, format-agnostic library for reconstructed-level collider
event and vertex displays: polar (phi, |eta|) views, beam-axis 2D
projections, and interactive 3D views, plus a companion family of
per-vertex / all-vertices displays for pileup diagnostics.

**[See it in action &rarr;](https://wasikatcern.github.io/TRACE-HEP/)** --
a static showcase with screenshots of `trace-gui` and real, self-contained
example galleries you can browse right in the page, no install needed.

## Install

```bash
pip install trace-hep              # core: numpy, matplotlib, plotly only
pip install trace-hep[delphes]     # + uproot/awkward, for the bundled Delphes/flat-ntuple/calo-timing loaders
pip install trace-hep[gui]         # + Flask, for the interactive trace-gui viewer
pip install trace-hep[all]         # + kaleido (static image export), mplhep (ATLAS style), gui, opendata
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

## Quickstart: a real public vertex display (ATLAS PHYSLITE)

`tracehep.io.atlas_physlite` reads ATLAS's 2024 **research** Open Data
release (DAOD_PHYSLITE format) for genuine track/vertex-level information
-- measured against 200 real events first, not assumed: PHYSLITE thins
away most tracks not tied to a reconstructed lepton/jet, so **199/200
hard-scatter vertices keep a real track collection, but only ~3.6% of
pileup vertices retain any tracks at all** (1-12 each; the rest come back
with a genuinely empty track list, which is what the file contains, not a
loader bug). This loader doesn't special-case the hard-scatter vertex --
it decodes whatever's actually valid for every vertex -- so a
many-vertices survey plot is possible and occasionally shows a pileup
vertex with real tracks, but it will look sparse compared to the
private-ntuple examples above, where every vertex keeps its full track
content (see "Status" below).

```python
import tracehep as trace
from tracehep.io.atlas_physlite import load_event_jets, load_vertex_event

url = "https://opendata.cern.ch/eos/opendata/atlas/rucio/mc20_13TeV/DAOD_PHYSLITE.37620644._000012.pool.root.1"
vtx_event = load_vertex_event(url, event_index=2, label="ATLAS Open Data (PHYSLITE)")

trace.plot_vertices_zr(vtx_event, style="styled").savefig("vertices.png")  # every vertex's position
hs_idx = next(i for i, v in enumerate(vtx_event.vertices) if v.is_hs)
jets = load_event_jets(url, event_index=2)  # this event's calibrated jets, no vertex association
trace.plot_vertex_detail(vtx_event, vtx_index=hs_idx, jets=jets).savefig("hs_vertex_detail.png")
```

There's no per-track timing in this release, so `style="time_colored"` has
nothing to color by -- use `"plain"` or `"styled"`. Neither these tracks
nor these jets carry a truth-level HS/PU classification, so
`plot_vertex_detail` draws them all in one flat colour each -- "Tracks"
and "Jet" -- rather than an HS/PU split with no data behind it. Whenever
none of the objects passed to `plot_vertex_detail` have `is_hs` set, this
is automatic: it only colours by HS/PU when at least one track (or jet)
actually has that field populated.

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
matched to it are usually mostly-but-not-entirely truth-HS too. If *none*
of the tracks (or jets) passed in have `is_hs` set at all -- no truth
available, as on real detector data -- `plot_vertex_detail` draws them all
in one flat colour and labels the legend plain "Tracks"/"Jet" rather than
implying an HS/PU split the data doesn't back up:

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

## Failure-mode / anomaly review: a browsable gallery of many events

The recurring question this solves: *"algorithm 1 failed these events but
algorithm 2 passed them -- what do they actually look like?"* (or, for an
anomaly-detection study, *"here are 400 events flagged anomalous, let's
eyeball them"*). `tracehep.gallery` turns a list of event numbers plus a
category per event into one self-contained, portable HTML file -- no
folder of hundreds of loose PNGs to manage, and no new dependency:

```python
import tracehep as trace
from tracehep.io.delphes import load_events
from tracehep.gallery import build_gallery, compare_pass_fail

events = load_events("my_sample.root", indices=range(500), with_tracks=True)

# your real per-event pass/fail results, e.g. from two ML classifiers
algo1_pass = {i: my_classifier_1.passes(i) for i in events}
algo2_pass = {i: my_classifier_2.passes(i) for i in events}
categories = compare_pass_fail(algo1_pass, algo2_pass, name_a="clf1", name_b="clf2")

build_gallery(
    events, categories,
    plot_fn=lambda ev: trace.plot_event_polar(ev, show_tracks=True),
    output_path="review.html",
    title="clf1 vs. clf2 disagreement review",
)
```

Open `review.html` in any browser: filter by category (`clf1_pass_clf2_fail`,
`clf1_fail_clf2_pass`, `both_pass`, `both_fail`), search/jump to an event
number, click a thumbnail to page through a full-size lightbox with the
arrow keys, and click "Download" on any image you want to keep -- nothing
is written to disk until you click it. A **"Download all (visible)"**
button next to the filter tabs downloads every currently-filtered image
in one go, for when you've narrowed down to one category and want all of
it.

Prefer a GUI to a script? `trace-gui`'s **Many events** and
**Failure-mode gallery** tabs build the exact same kind of gallery
interactively (see below) -- useful for a quick look without writing
`load_events`/`compare_pass_fail` calls by hand.

`compare_pass_fail` builds the four-category split for a 2-algorithm
comparison; for a single-bucket anomaly-detection review (or any other
grouping), just build the `{event_id: label}` mapping yourself --
`build_gallery` doesn't care where the labels came from:

```python
categories = {eid: "anomalous" for eid in anomalous_event_numbers}
build_gallery(events, categories, plot_fn=trace.plot_event_polar, output_path="anomalies.html")
```

`plot_fn` can be any callable returning a matplotlib or plotly figure --
`plot_event_polar`, `plot_event_beam2d`, `plot_vertices_zr`, a
`lambda ev: plot_vertex_detail(ev, vtx_index=0)`, or your own function.
Every image is embedded directly in the HTML, so file size scales with
event count x `dpi`; the default (100) is fine for dozens of events, but
drop to 60-80 for hundreds-to-thousands to keep the file a reasonable size
and the browser responsive (measured: ~150 KB/event at dpi=100 for a
polar view with tracks, ~95 KB/event at dpi=70).

## Live interactive viewer (`trace-gui`)

For "just let me look at one event" -- no script, no pre-rendering --
`trace-gui` starts a small local web app: type a file path (or URL) and an
event number, pick a loader and a display, click Render, and it draws live
in your browser.

```bash
pip install "trace-hep[gui]"   # adds Flask -- the only new dependency
trace-gui                      # opens http://127.0.0.1:5057/ in your browser
```

Loaders: **Delphes**, **flat-ntuple**, **ATLAS Open Data**, **CMS Open
Data**, and one unified **Vertex display** loader that auto-detects
whether a file is a calo-timing-style ntuple or a PHYSLITE-style
derivation by checking for each format's signature branch -- point it at
`.../CaloTimingNtuple.root`, a `DAOD_PHYSLITE...root` file, or any other
file carrying one of those two signature branches (even with less
complete information than either reference format), and it just works
without you picking a format first. An optional "Tree name" field is
there for the rare case auto-detection guesses wrong. Every display type
is covered, both 2D (matplotlib) and interactive 3D (plotly).

It also has a **"Build an event by hand"** loader: skip files entirely and
add jets/muons/electrons/photons/MET by typing their pT/eta/phi directly,
then see the same 2D/beam2d/3D displays render live from what you typed --
useful for teaching, or for quickly checking how a hypothetical topology
would look.

Every rendered view has a **"Download image"** button: for a 2D display
it saves the PNG directly; for an interactive 3D display it uses Plotly's
own capture, so it saves whatever camera angle you've rotated to, not
just the default view.

Every render is shareable as a URL: `?path=...&loader=...&display=...&event_index=...`
(and `manual_jets=[...]` etc. as JSON for a hand-built event) pre-fills the
form and renders automatically -- paste a link straight to one event
instead of re-typing the form.

Every "File path or URL" field also has an **"Or upload a .root file"**
button, for when `trace-gui` is running as a shared server rather than on
your own laptop -- a visitor's browser can't hand the server a local path,
so it uploads the file's bytes instead (capped at 150 MB, and the server
auto-deletes uploads after about an hour). Want to let colleagues try
their own files without anyone installing anything? See
[`deploy/huggingface-space/`](deploy/huggingface-space/) for a ready-made
Docker setup for Hugging Face Spaces' free tier -- push it, and you have a
public URL.

Two more tabs build the same kind of browsable review gallery
`tracehep.gallery` produces (see below), without leaving the browser or
writing a script -- point either one at a file, click **Build gallery**,
and it renders every event on demand and shows the resulting filterable
gallery right there in an embedded frame (up to 300 events per request):

- **Many events** (`?mode=many` deep-links to it): just a plain list of
  event numbers, e.g. `1, 2, 4, 5` or `1-10` (ranges expand inclusively,
  and mix freely with single ids) -- for "let me look at a batch of
  events," no categories, no second file needed.
- **Failure-mode gallery** (`?mode=gallery`): the events come with a
  category -- describe them either as two algorithms' pass/fail event-id
  lists (built into the usual `both_pass`/`both_fail`/disagreement 4-way
  split), as free-text custom labels (`1023: anomalous`, one per line, for
  an anomaly-detection bucket), or **auto-flag by Δφ(MET, closest jet)**:
  give it an event range (`1-200`) and a threshold, and it loads every
  event itself, computes the angle, and sorts them into
  flagged/not-flagged -- no pass/fail list to build by hand.

Every gallery, whether built in either tab or with `tracehep.gallery`
directly, has a **"Download all (visible)"** button next to the filter
tabs that downloads every currently-filtered image in one click (in
addition to each card's individual Download link), and the
webapp additionally offers **"Save full gallery as .html"** to keep the
whole self-contained page.

To stop the server, use **Ctrl+C**, not Ctrl+Z -- Ctrl+Z only *suspends*
it, leaving the port held by a now-invisible process, which is the usual
cause of a "port already in use" error on the next run. `trace-gui`
already handles this for you: if its default port (5057) is busy, it
automatically moves to the next free one and prints which port it picked
and how to find/stop the stale process (`lsof -i :5057` then `kill <PID>`)
if you want the original port back. Pass `--port` to pick a different
starting port yourself.

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

A many-pileup-vertices survey display as dense as the earlier
private-ntuple examples in this README (dozens of vertices, each with its
own full, per-track-timed track fan) has no public-open-data equivalent:
neither ATLAS's nor CMS's public education releases carry track/vertex
information at all, and ATLAS's 2024 PHYSLITE research release thins away
most pileup-vertex tracks (measured against 200 real events: only ~3.6%
of pileup vertices retain any -- see `tracehep.io.atlas_physlite`), so a
PHYSLITE survey plot will look sparse rather than dense. CMS's full AOD
does have complete track/vertex collections but requires the CMSSW
software framework to read (not just uproot). If that ever changes, a new
loader is the way it would show up here.

## Citing

If you use TRACE in a publication, please cite the accompanying paper
(citation to be added once posted).
