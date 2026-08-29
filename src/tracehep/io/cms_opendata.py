"""Load events out of the public CMS Open Data reduced "NanoAOD outreach"
format (opendata.cern.ch, ``AOD2NanoAODOutreachTool`` derivatives) via
uproot -- covers the 2012 (8 TeV) education/outreach releases: MC samples
(``TTbar``, ``DYJetsToLL``, ``SMHiggsToZZTo4L``, ``ZZTo4mu``, ...) and real
collision data (``Run2012B_DoubleMuParked``, ``Run2012B_DoubleElectron``, ...).

Unlike the ATLAS Open Data mini-ntuple, different sub-releases of this
format carry different object collections -- the ``TTbar`` file has
Jet+Muon+Tau, the ``ForHiggsTo4Leptons`` files have Muon+Electron only, and
so on. This loader detects what's actually present in the file (via
``tree.keys()``) and reads only those branches, so nothing needs to be
configured per sample. Momenta/masses are already in GeV, the standard
NanoAOD convention -- no unit conversion needed (unlike the ATLAS
mini-ntuple, which is in MeV).

These files are large (tens of MB to tens of GB); uproot can stream them
directly over HTTP or XRootD without downloading the whole file first,
since ROOT files support random-access reads -- pass either
``https://opendata.cern.ch/eos/opendata/...`` or
``root://eospublic.cern.ch//eos/opendata/...`` as ``path`` and only the
needed baskets are fetched.

This ntuple format has no track- or vertex-level information, so it feeds
:class:`~tracehep.models.Event` and the event-display functions only -- not
the vertex/pileup side of tracehep.

Requires the ``delphes`` extra (uproot is shared): ``pip install trace-hep[delphes]``.

Developed by Wasikul Islam, PhD.
"""

from typing import Dict, Iterable, List

from ..models import Event, Jet, Lepton, MissingET

__all__ = ["load_events", "load_event"]


def _require_uproot():
    try:
        import uproot  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "tracehep.io.cms_opendata requires uproot. Install with: pip install trace-hep[delphes]"
        ) from exc
    return uproot


def load_events(
    path: str,
    indices: Iterable[int],
    *,
    tree_name: str = "Events",
    btag_cut: float = 0.679,
    label: str = "",
) -> Dict[int, Event]:
    """Load several events at once from a CMS Open Data reduced NanoAOD file.

    Parameters
    ----------
    path:
        Path or URL to a reduced NanoAOD ROOT file -- a local file, an
        ``https://opendata.cern.ch/...`` URL, or a
        ``root://eospublic.cern.ch/...`` URL. Large remote files are read
        lazily; nothing is downloaded up front.
    indices:
        Event (row) indices to load.
    btag_cut:
        Jets with ``Jet_btag`` above this value are marked b-tagged (only
        applies if the file has a Jet collection at all). The default,
        0.679, is the CSVv2 "medium" working point used in 2012 CMS
        analyses.
    label:
        Free-text label stamped onto every returned Event.

    Returns
    -------
    dict mapping each requested index to its :class:`~tracehep.models.Event`.
    """
    uproot = _require_uproot()
    indices = sorted(set(indices))
    if not indices:
        return {}

    f = uproot.open(path)
    tree = f[tree_name]
    available = set(tree.keys())

    has_jets = "Jet_pt" in available
    has_btag = "Jet_btag" in available
    has_muons = "Muon_pt" in available
    has_electrons = "Electron_pt" in available
    has_met = "MET_pt" in available
    has_evtinfo = "run" in available and "event" in available

    branches: List[str] = []
    if has_jets:
        branches += ["Jet_pt", "Jet_eta", "Jet_phi", "Jet_mass"]
        if has_btag:
            branches.append("Jet_btag")
    if has_muons:
        branches += ["Muon_pt", "Muon_eta", "Muon_phi"]
    if has_electrons:
        branches += ["Electron_pt", "Electron_eta", "Electron_phi"]
    if has_met:
        branches += ["MET_pt", "MET_phi"]
    if has_evtinfo:
        branches += ["run", "event"]

    lo, hi = indices[0], indices[-1] + 1
    arrs = tree.arrays(branches, entry_start=lo, entry_stop=hi)

    events: Dict[int, Event] = {}
    for idx in indices:
        i = idx - lo
        jets: List[Jet] = []
        if has_jets:
            jpt, jeta, jphi, jmass = (arrs["Jet_pt"][i], arrs["Jet_eta"][i],
                                       arrs["Jet_phi"][i], arrs["Jet_mass"][i])
            jbtag = arrs["Jet_btag"][i] if has_btag else [0.0] * len(jpt)
            jets = [
                Jet(pt=float(pt), eta=float(eta), phi=float(phi), mass=float(m),
                    btag=bool(bt > btag_cut))
                for pt, eta, phi, m, bt in zip(jpt, jeta, jphi, jmass, jbtag)
            ]

        muons = [
            Lepton(pt=float(pt), eta=float(eta), phi=float(phi), flavor="muon")
            for pt, eta, phi in zip(arrs["Muon_pt"][i], arrs["Muon_eta"][i], arrs["Muon_phi"][i])
        ] if has_muons else []

        electrons = [
            Lepton(pt=float(pt), eta=float(eta), phi=float(phi), flavor="electron")
            for pt, eta, phi in zip(arrs["Electron_pt"][i], arrs["Electron_eta"][i],
                                     arrs["Electron_phi"][i])
        ] if has_electrons else []

        met = None
        if has_met:
            met_pt = float(arrs["MET_pt"][i])
            if met_pt > 0:
                met = MissingET(pt=met_pt, phi=float(arrs["MET_phi"][i]))

        events[idx] = Event(
            jets=jets, muons=muons, electrons=electrons, met=met,
            run=int(arrs["run"][i]) if has_evtinfo else None,
            event_number=int(arrs["event"][i]) if has_evtinfo else None,
            label=label,
        )
    return events


def load_event(path: str, index: int, *, tree_name: str = "Events", btag_cut: float = 0.679,
                label: str = "") -> Event:
    """Load a single event. See :func:`load_events` for the batch form."""
    return load_events(path, [index], tree_name=tree_name, btag_cut=btag_cut, label=label)[index]
