"""Load events out of a flat, ATLAS-style reconstructed ntuple (jets,
b-jets, muons, electrons, photons, MET as flat JET_pt/JET_eta/... branches,
matched by a (run, event) pair rather than a plain row index) via uproot.

The jet/b-jet branch name triples default to the ``JET_*``/``bJET_*``
convention but can be overridden (``jet_branches``/``bjet_branches``) for
ntuples that name their jet collection differently, e.g.
``AntiKt4EMPFlowJet_pt``/``_eta``/``_phi``.

Requires the ``delphes`` extra (uproot is shared with the Delphes loader):
``pip install trace-hep[delphes]``.

Developed by Wasikul Islam, PhD.
"""

from typing import Dict, Iterable, List, Tuple

from ..models import Event, Jet, Lepton, Photon, MissingET

__all__ = ["load_events_by_run_event", "load_event_by_run_event"]

_LEPTON_PHOTON_BRANCHES = {
    "muon": ("MU_pt", "MU_eta", "MU_phi"),
    "electron": ("EL_pt", "EL_eta", "EL_phi"),
    "photon": ("PH_pt", "PH_eta", "PH_phi"),
}


def _require_uproot():
    try:
        import uproot  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "tracehep.io.flat_ntuple requires uproot. Install with: pip install trace-hep[delphes]"
        ) from exc
    return uproot


def load_events_by_run_event(
    path: str,
    run_event_pairs: Iterable[Tuple[int, int]],
    *,
    tree_name: str = "Ntuple",
    jet_branches: Tuple[str, str, str] = ("JET_pt", "JET_eta", "JET_phi"),
    bjet_branches: Tuple[str, str, str] = ("bJET_pt", "bJET_eta", "bJET_phi"),
    label: str = "",
) -> Dict[Tuple[int, int], Event]:
    """Scan a flat ntuple once for the requested (run, event) pairs.

    Parameters
    ----------
    jet_branches, bjet_branches:
        ``(pt, eta, phi)`` branch-name triples for the light-jet and b-jet
        collections. Override these if the ntuple uses a different jet
        collection/naming convention than the ``JET_*``/``bJET_*`` default,
        e.g. ``jet_branches=("AntiKt4EMPFlowJet_pt", "AntiKt4EMPFlowJet_eta",
        "AntiKt4EMPFlowJet_phi")``.

    Returns
    -------
    dict mapping each found (run, event) pair to its Event. Pairs not
    present in the file are simply absent from the result.
    """
    uproot = _require_uproot()
    wanted = set(run_event_pairs)
    if not wanted:
        return {}

    f = uproot.open(path)
    tree = f[tree_name]
    object_branches = dict(_LEPTON_PHOTON_BRANCHES)
    object_branches["jet"] = jet_branches
    object_branches["bjet"] = bjet_branches

    branches = ["N_RUN", "N_EVENT"]
    for pt, eta, phi in object_branches.values():
        branches += [pt, eta, phi]
    branches += ["MET_met", "MET_eta", "MET_phi"]

    found: Dict[Tuple[int, int], Event] = {}
    for chunk in tree.iterate(branches, library="ak", step_size="50 MB"):
        runs, evts = chunk["N_RUN"], chunk["N_EVENT"]
        for i in range(len(runs)):
            run = int(runs[i])
            evt = int(evts[i])
            if evt < 0:
                evt += 1 << 32  # N_EVENT is stored signed but is really unsigned
            key = (run, evt)
            if key not in wanted or key in found:
                continue

            objects = {}
            for typ, (pt_b, eta_b, phi_b) in object_branches.items():
                objects[typ] = list(zip(chunk[pt_b][i], chunk[eta_b][i], chunk[phi_b][i]))

            jets: List[Jet] = [Jet(pt=float(p), eta=float(e), phi=float(ph), btag=False)
                                for p, e, ph in objects["jet"]]
            jets += [Jet(pt=float(p), eta=float(e), phi=float(ph), btag=True)
                     for p, e, ph in objects["bjet"]]
            muons = [Lepton(pt=float(p), eta=float(e), phi=float(ph), flavor="muon")
                     for p, e, ph in objects["muon"]]
            electrons = [Lepton(pt=float(p), eta=float(e), phi=float(ph), flavor="electron")
                         for p, e, ph in objects["electron"]]
            photons = [Photon(pt=float(p), eta=float(e), phi=float(ph)) for p, e, ph in objects["photon"]]

            met_pt = chunk["MET_met"][i]
            met = MissingET(pt=float(met_pt), eta=float(chunk["MET_eta"][i]),
                             phi=float(chunk["MET_phi"][i])) if float(met_pt) > 0 else None

            found[key] = Event(jets=jets, muons=muons, electrons=electrons, photons=photons,
                                met=met, run=run, event_number=evt, label=label)
            if len(found) == len(wanted):
                return found
    return found


def load_event_by_run_event(path: str, run: int, event: int, *, tree_name: str = "Ntuple",
                             jet_branches: Tuple[str, str, str] = ("JET_pt", "JET_eta", "JET_phi"),
                             bjet_branches: Tuple[str, str, str] = ("bJET_pt", "bJET_eta", "bJET_phi"),
                             label: str = "") -> Event:
    """Load a single event by its (run, event) pair. Raises KeyError if not found."""
    result = load_events_by_run_event(path, [(run, event)], tree_name=tree_name,
                                       jet_branches=jet_branches, bjet_branches=bjet_branches,
                                       label=label)
    try:
        return result[(run, event)]
    except KeyError:
        raise KeyError(f"(run={run}, event={event}) not found in {path}") from None
