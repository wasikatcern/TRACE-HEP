"""Load events out of the public ATLAS Open Data 13 TeV "mini-ntuple"
format (opendata.atlas.cern, 2020 education release) via uproot -- the same
flat ntuple schema is used for every released 13 TeV physics dataset (SM,
Higgs, SUSY, exotic-resonance searches, ...), so this loader works
unchanged across all of them without any per-sample configuration.

Get file URLs with the ``atlasopenmagic`` package rather than guessing
paths by hand, e.g.::

    import atlasopenmagic as atom
    atom.set_release("2020e-13tev")
    urls = atom.get_urls("410000", skim="2lep", protocol="https")  # ttbar

Momenta/energies in this ntuple are stored in MeV; this loader converts to
GeV to match every other tracehep loader's convention. B-tagging is a
continuous ``jet_MV2c10`` discriminant rather than a boolean -- pass
``btag_cut`` to choose the working point (default: the 77%-efficiency cut
used throughout the ATLAS Open Data documentation).

This ntuple format has no track- or vertex-level information (only fully
reconstructed objects), so it feeds :class:`~tracehep.models.Event` and the
event-display functions only -- not the vertex/pileup side of tracehep.

Requires the ``delphes`` extra (uproot is shared): ``pip install trace-hep[delphes]``.

Developed by Wasikul Islam, PhD.
"""

from typing import Dict, Iterable, List

from ..models import Event, Jet, Lepton, MissingET, Photon

__all__ = ["load_events", "load_event"]

_MEV_TO_GEV = 1e-3

_BRANCHES = [
    "runNumber", "eventNumber",
    "jet_pt", "jet_eta", "jet_phi", "jet_MV2c10",
    "lep_pt", "lep_eta", "lep_phi", "lep_type",
    "photon_pt", "photon_eta", "photon_phi",
    "met_et", "met_phi",
]
_LARGE_R_BRANCHES = ["largeRjet_pt", "largeRjet_eta", "largeRjet_phi", "largeRjet_m"]


def _require_uproot():
    try:
        import uproot  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "tracehep.io.atlas_opendata requires uproot. Install with: pip install trace-hep[delphes]"
        ) from exc
    return uproot


def load_events(
    path: str,
    indices: Iterable[int],
    *,
    tree_name: str = "mini",
    btag_cut: float = 0.6459,
    include_large_r_jets: bool = False,
    label: str = "",
) -> Dict[int, Event]:
    """Load several events at once (a single, contiguous-range read).

    Parameters
    ----------
    path:
        Path to an ATLAS Open Data 13 TeV mini-ntuple ROOT file.
    indices:
        Event (row) indices to load.
    btag_cut:
        Jets with ``jet_MV2c10`` above this value are marked b-tagged.
    include_large_r_jets:
        Also append the large-R (``largeRjet_*``) jet collection to
        ``Event.jets``, e.g. for boosted-topology samples (skim
        ``1largeRjet1lep``). Large-R jets are never b-tagged (``btag=False``)
        since MV2c10 isn't defined for them in this ntuple.
    label:
        Free-text label stamped onto every returned Event (used in default
        plot titles), e.g. a sample name.

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
    branches = list(_BRANCHES) + (list(_LARGE_R_BRANCHES) if include_large_r_jets else [])
    lo, hi = indices[0], indices[-1] + 1
    arrs = tree.arrays(branches, entry_start=lo, entry_stop=hi)

    events: Dict[int, Event] = {}
    for idx in indices:
        i = idx - lo
        jets: List[Jet] = [
            Jet(pt=float(pt) * _MEV_TO_GEV, eta=float(eta), phi=float(phi),
                btag=bool(mv2 > btag_cut))
            for pt, eta, phi, mv2 in zip(arrs["jet_pt"][i], arrs["jet_eta"][i],
                                          arrs["jet_phi"][i], arrs["jet_MV2c10"][i])
        ]
        if include_large_r_jets:
            jets += [
                Jet(pt=float(pt) * _MEV_TO_GEV, eta=float(eta), phi=float(phi),
                    mass=float(m) * _MEV_TO_GEV, btag=False)
                for pt, eta, phi, m in zip(arrs["largeRjet_pt"][i], arrs["largeRjet_eta"][i],
                                            arrs["largeRjet_phi"][i], arrs["largeRjet_m"][i])
            ]

        muons: List[Lepton] = []
        electrons: List[Lepton] = []
        for pt, eta, phi, ltype in zip(arrs["lep_pt"][i], arrs["lep_eta"][i],
                                        arrs["lep_phi"][i], arrs["lep_type"][i]):
            flavor = "muon" if int(ltype) == 13 else "electron"
            lep = Lepton(pt=float(pt) * _MEV_TO_GEV, eta=float(eta), phi=float(phi), flavor=flavor)
            (muons if flavor == "muon" else electrons).append(lep)

        photons = [
            Photon(pt=float(pt) * _MEV_TO_GEV, eta=float(eta), phi=float(phi))
            for pt, eta, phi in zip(arrs["photon_pt"][i], arrs["photon_eta"][i], arrs["photon_phi"][i])
        ]

        met_pt = float(arrs["met_et"][i]) * _MEV_TO_GEV
        met = MissingET(pt=met_pt, phi=float(arrs["met_phi"][i])) if met_pt > 0 else None

        events[idx] = Event(
            jets=jets, muons=muons, electrons=electrons, photons=photons, met=met,
            run=int(arrs["runNumber"][i]), event_number=int(arrs["eventNumber"][i]), label=label,
        )
    return events


def load_event(path: str, index: int, *, tree_name: str = "mini", btag_cut: float = 0.6459,
                include_large_r_jets: bool = False, label: str = "") -> Event:
    """Load a single event. See :func:`load_events` for the batch form."""
    return load_events(path, [index], tree_name=tree_name, btag_cut=btag_cut,
                        include_large_r_jets=include_large_r_jets, label=label)[index]
