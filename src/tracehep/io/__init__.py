"""Format-specific loaders that translate a ROOT file into the plain
:mod:`tracehep.models` data model. Each loader is independently optional --
importing :mod:`tracehep.polar` or :mod:`tracehep.view3d` never requires
uproot or ROOT at all; only importing a loader here does.

Developed by Wasikul Islam, PhD.
"""
