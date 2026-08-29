"""Build a failure-mode review gallery: given a list of event numbers each
of two "algorithms" passed/failed, generate one browsable, self-contained
HTML page with all the events, filterable by disagreement category.

This is a stand-in for a real ML pipeline -- swap `algo1`/`algo2` for your
actual per-event pass/fail results (e.g. a classifier's selection, an
anomaly score above/below a threshold, ...). Everything else -- loading,
categorizing, rendering, and browsing -- stays the same regardless of what
produced the pass/fail labels.

Usage:
    python3 failure_mode_gallery_demo.py
    open failure_mode_review.html
"""

import tracehep as trace
from tracehep.io.delphes import load_events
from tracehep.gallery import build_gallery, compare_pass_fail

PATH = "my_sample.root"  # a Delphes ROOT file -- point this at your own sample

events = load_events(PATH, indices=range(200), with_tracks=True, label="my_sample")

# Stand-in "algorithm 1": a simple jet-multiplicity cut.
# Stand-in "algorithm 2": a MET cut. Replace both with your real results,
# e.g. algo1 = {evt_num: my_classifier.passes(evt_num) for evt_num in ...}
algo1_pass = {i: len(ev.jets) >= 3 for i, ev in events.items()}
algo2_pass = {i: (ev.met.pt if ev.met else 0.0) > 60.0 for i, ev in events.items()}

categories = compare_pass_fail(algo1_pass, algo2_pass, name_a="jet_cut", name_b="met_cut")

# Optional: a one-line reason per event, shown under its thumbnail.
captions = {
    i: f"{len(ev.jets)} jets, MET={ev.met.pt:.0f} GeV" if ev.met else f"{len(ev.jets)} jets"
    for i, ev in events.items()
}

build_gallery(
    events, categories,
    plot_fn=lambda ev: trace.plot_event_polar(ev, show_tracks=True),
    output_path="failure_mode_review.html",
    title="jet_cut vs. met_cut: disagreement review",
    captions=captions,
)
print("Wrote failure_mode_review.html -- open it in a browser: filter by category, "
      "click a thumbnail to page through with the arrow keys, click Download to keep one.")
