"""Draw event displays from real, public ATLAS Open Data (13 TeV
mini-ntuples) -- no Delphes, no private ntuple, just data anyone can
download.

Usage:
    pip install "trace-hep[opendata]"   # adds atlasopenmagic + uproot
    python3 atlas_opendata_demo.py

Downloads one file if not already present (~14 MB, a Z' -> ttbar boosted
resonance sample) and draws a polar event display for a few events.
"""

import os

import atlasopenmagic as atom

import tracehep as trace
from tracehep.io.atlas_opendata import load_events

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_FILE = os.path.join(HERE, "zprime2000_tt_1largeRjet1lep.root")

if not os.path.exists(LOCAL_FILE):
    print("Downloading a sample ATLAS Open Data file (~14 MB)...")
    atom.set_release("2020e-13tev")
    url = atom.get_urls("301329", skim="1largeRjet1lep", protocol="https")[0]
    url = url.split("simplecache::")[-1]  # atlasopenmagic prefixes an fsspec cache scheme
    import urllib.request
    urllib.request.urlretrieve(url, LOCAL_FILE)

events = load_events(
    LOCAL_FILE, indices=range(5), include_large_r_jets=True,
    label="ATLAS Open Data: Z'(2 TeV) -> ttbar (boosted)",
)
for idx, event in events.items():
    fig = trace.plot_event_polar(event)
    fig.savefig(f"opendata_event{idx}_polar.png", dpi=150, bbox_inches="tight")
    print(f"event {idx}: {len(event.jets)} jets, met={event.met.pt if event.met else 0:.0f} GeV "
          f"-> opendata_event{idx}_polar.png")
