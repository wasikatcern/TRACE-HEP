"""Draw event displays from real, public CMS Open Data -- including
genuine 2012 LHC collision data, not just simulation.

Usage:
    pip install "trace-hep[delphes]"   # uproot is all this needs
    python3 cms_opendata_demo.py

Streams two files directly from opendata.cern.ch over HTTPS (uproot reads
only the bytes it needs -- nothing is downloaded to disk): a ttbar MC
sample, and REAL 2012 8 TeV collision data (Run2012B_DoubleMuParked).
"""

import tracehep as trace
from tracehep.io.cms_opendata import load_events

TTBAR_URL = (
    "https://opendata.cern.ch/eos/opendata/cms/derived-data/"
    "AOD2NanoAODOutreachTool/TTbar.root"
)
REAL_DATA_URL = (
    "https://opendata.cern.ch/eos/opendata/cms/derived-data/"
    "AOD2NanoAODOutreachTool/ForHiggsTo4Leptons/Run2012B_DoubleMuParked.root"
)

print("Streaming a few ttbar (MC) events...")
ttbar_events = load_events(TTBAR_URL, indices=range(3), label="ttbar (CMS Open Data, MC)")
for idx, event in ttbar_events.items():
    fig = trace.plot_event_polar(event)
    fig.savefig(f"cms_ttbar_event{idx}_polar.png", dpi=150, bbox_inches="tight")
    print(f"  event {idx}: {len(event.jets)} jets, {len(event.muons)} muons "
          f"-> cms_ttbar_event{idx}_polar.png")

print("Streaming a few REAL 2012 collision events (Run2012B_DoubleMuParked)...")
real_events = load_events(REAL_DATA_URL, indices=range(3), label="CMS 2012 real data")
for idx, event in real_events.items():
    fig = trace.plot_event_polar(event)
    fig.savefig(f"cms_realdata_event{idx}_polar.png", dpi=150, bbox_inches="tight")
    print(f"  event {idx}: run={event.run}, evt#={event.event_number}, "
          f"{len(event.muons)} muons -> cms_realdata_event{idx}_polar.png")
