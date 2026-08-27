# Examples

Most of the runnable example scripts that originally motivated this library --
Delphes ttbar/LLP event displays, the discussion-demo prototypes (non-linear
scaling, filterable gallery, displaced-track highlighting, ...) -- live in
the companion paper repository's `codes/` directory, not here. This
directory is reserved for small, self-contained examples built directly on
the `tracehep` public API (see the README quickstart) as the package
matures.

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
