"""Load events out of a Delphes fast-simulation ROOT file's "Delphes" tree
via uproot -- no Delphes shared-library or dictionary needed. Works
unchanged on any Delphes sample for any generated physics process, since
every Delphes sample shares the same object-collection branch names.

Pass ``jet_collection`` to read a jet collection other than the default
``"Jet"`` (e.g. a Delphes card that also defines ``"GenJet"`` or
``"JetPUPPI"``). Track/jet pT and eta cuts are not a loader concern -- load
the full event, then use :func:`tracehep.filters.filter_event`.

Requires the ``delphes`` extra: ``pip install trace-hep[delphes]``.

Developed by Wasikul Islam, PhD.
"""

from typing import Dict, Iterable, List

from ..models import Event, Jet, Lepton, Photon, MissingET, Track

__all__ = ["load_event", "load_events"]

_BRANCHES = [
    "Muon/Muon.PT", "Muon/Muon.Eta", "Muon/Muon.Phi",
    "Electron/Electron.PT", "Electron/Electron.Eta", "Electron/Electron.Phi",
    "Photon/Photon.PT", "Photon/Photon.Eta", "Photon/Photon.Phi",
    "MissingET/MissingET.MET", "MissingET/MissingET.Eta", "MissingET/MissingET.Phi",
    "Event/Event.Number",
]
_TRACK_BRANCHES = [
    "Track/Track.PT", "Track/Track.Eta", "Track/Track.Phi", "Track/Track.Charge",
    "Track/Track.D0", "Track/Track.DZ", "Track/Track.X", "Track/Track.Y", "Track/Track.Z",
]


def _require_uproot():
    try:
        import uproot  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "tracehep.io.delphes requires uproot. Install with: pip install trace-hep[delphes]"
        ) from exc
    return uproot


def load_events(path: str, indices: Iterable[int], *, with_tracks: bool = True,
                 jet_collection: str = "Jet", label: str = "") -> Dict[int, Event]:
    """Load several events at once (a single, contiguous-range read).

    Parameters
    ----------
    path:
        Path to a Delphes ROOT file.
    indices:
        Event indices to load.
    with_tracks:
        Also read the (much larger) Track collection.
    jet_collection:
        Branch-name prefix for the jet collection to load, e.g. ``"Jet"``
        (default -- the standard Delphes anti-kt jet collection), or
        whatever else a given Delphes card defines (e.g. ``"GenJet"``,
        ``"JetPUPPI"``, ``"FatJet"``). Raises ``KeyError`` (listing the
        collections actually present) if the branch isn't found.
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
    tree = f["Delphes"]
    available = set(tree.keys())

    jet_pt_b = f"{jet_collection}/{jet_collection}.PT"
    jet_eta_b = f"{jet_collection}/{jet_collection}.Eta"
    jet_phi_b = f"{jet_collection}/{jet_collection}.Phi"
    jet_mass_b = f"{jet_collection}/{jet_collection}.Mass"
    jet_btag_b = f"{jet_collection}/{jet_collection}.BTag"
    if jet_pt_b not in available:
        collections = sorted({k.split("/")[0] for k in available if "/" in k})
        raise KeyError(
            f"Jet collection {jet_collection!r} not found in {path} (tried branch "
            f"{jet_pt_b!r}). Collections present in this file: {collections}"
        )
    has_mass = jet_mass_b in available
    has_btag = jet_btag_b in available

    jet_branches = [jet_pt_b, jet_eta_b, jet_phi_b]
    if has_mass:
        jet_branches.append(jet_mass_b)
    if has_btag:
        jet_branches.append(jet_btag_b)

    branches = jet_branches + list(_BRANCHES) + (list(_TRACK_BRANCHES) if with_tracks else [])
    lo, hi = indices[0], indices[-1] + 1
    arrs = tree.arrays(branches, entry_start=lo, entry_stop=hi)

    events: Dict[int, Event] = {}
    for idx in indices:
        i = idx - lo
        jpt, jeta, jphi = arrs[jet_pt_b][i], arrs[jet_eta_b][i], arrs[jet_phi_b][i]
        jmass = arrs[jet_mass_b][i] if has_mass else [0.0] * len(jpt)
        jbtag = arrs[jet_btag_b][i] if has_btag else [0] * len(jpt)
        jets: List[Jet] = [
            Jet(pt=float(pt), eta=float(eta), phi=float(phi), mass=float(m), btag=bool(int(bt) & 1))
            for pt, eta, phi, m, bt in zip(jpt, jeta, jphi, jmass, jbtag)
        ]

        def _leptons(prefix: str, flavor: str) -> List[Lepton]:
            pts, etas, phis = arrs[f"{prefix}.PT"][i], arrs[f"{prefix}.Eta"][i], arrs[f"{prefix}.Phi"][i]
            return [Lepton(pt=float(p), eta=float(e), phi=float(ph), flavor=flavor)
                    for p, e, ph in zip(pts, etas, phis)]

        muons = _leptons("Muon/Muon", "muon")
        electrons = _leptons("Electron/Electron", "electron")
        photons = [Photon(pt=float(p), eta=float(e), phi=float(ph))
                   for p, e, ph in zip(arrs["Photon/Photon.PT"][i], arrs["Photon/Photon.Eta"][i],
                                        arrs["Photon/Photon.Phi"][i])]

        met_pt_arr = arrs["MissingET/MissingET.MET"][i]
        met = None
        if len(met_pt_arr) > 0:
            met = MissingET(pt=float(met_pt_arr[0]), phi=float(arrs["MissingET/MissingET.Phi"][i][0]),
                             eta=float(arrs["MissingET/MissingET.Eta"][i][0]))

        tracks: List[Track] = []
        if with_tracks:
            tpt, teta, tphi = arrs["Track/Track.PT"][i], arrs["Track/Track.Eta"][i], arrs["Track/Track.Phi"][i]
            tq, td0, tdz = arrs["Track/Track.Charge"][i], arrs["Track/Track.D0"][i], arrs["Track/Track.DZ"][i]
            tx, ty, tz = arrs["Track/Track.X"][i], arrs["Track/Track.Y"][i], arrs["Track/Track.Z"][i]
            tracks = [
                Track(pt=float(pt), eta=float(eta), phi=float(phi), charge=int(q),
                      d0=float(d0), z0=float(dz), x=float(x), y=float(y), z=float(z))
                for pt, eta, phi, q, d0, dz, x, y, z
                in zip(tpt, teta, tphi, tq, td0, tdz, tx, ty, tz)
            ]

        events[idx] = Event(
            jets=jets, tracks=tracks, muons=muons, electrons=electrons, photons=photons,
            met=met, event_number=int(arrs["Event/Event.Number"][i][0]), label=label,
        )
    return events


def load_event(path: str, index: int, *, with_tracks: bool = True,
                jet_collection: str = "Jet", label: str = "") -> Event:
    """Load a single event. See :func:`load_events` for the batch form."""
    return load_events(path, [index], with_tracks=with_tracks,
                        jet_collection=jet_collection, label=label)[index]
