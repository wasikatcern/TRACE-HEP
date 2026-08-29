# Examples

Most of the runnable example scripts that originally motivated this library --
Delphes ttbar/LLP event displays, the discussion-demo prototypes (non-linear
scaling, filterable gallery, displaced-track highlighting, ...) -- live in
the companion paper repository's `codes/` directory, not here. This
directory is reserved for small, self-contained examples built directly on
the `tracehep` public API (see the README quickstart) as the package
matures.

## atlas_opendata_demo.py

Downloads one small (~14 MB) public ATLAS Open Data file (a Z' -> ttbar
boosted-resonance sample) via `atlasopenmagic` and draws polar event
displays for a few events -- no private data needed. Run with
`pip install "trace-hep[opendata]"` first.

## cms_opendata_demo.py

Streams (no download -- reads directly over HTTPS) a few events from a
CMS ttbar MC sample and, separately, from **real 2012 8 TeV LHC collision
data** (`Run2012B_DoubleMuParked`). Run with `pip install "trace-hep[delphes]"`
first (only uproot is needed; no companion discovery package required for
CMS, unlike ATLAS Open Data).

## atlas_physlite_demo.py

Streams one event from ATLAS's 2024 research-grade Open Data release
(DAOD_PHYSLITE) and draws both an all-vertices survey and a hard-scatter
vertex-detail plot. Read the module docstring in
`tracehep/io/atlas_physlite.py` first -- PHYSLITE thins away pileup-vertex
tracks, so only the hard-scatter vertex has real track content here (this
was verified against real files, not assumed).

## legacy/

`legacy/event_vertex_display.py` (originally `event_display_tt_R25.py`) is
the standalone, analysis-specific script (hardcoded ntuple path, argparse
`--event_num`/`--vtxID`, no `tracehep` dependency) that `plot_vertex_detail`
and `match_jets_to_vertex` are a clean, reusable reimplementation of -- kept
here as the reference the library's output was validated against, not as a
usage example to copy. For actual usage, see `plot_vertex_detail` in the
main README instead. (The WAVeS/SumptW discriminant calculations from the
original have been removed here since nothing in the actual display used
them -- confirmed by re-running against real data before and after.)
