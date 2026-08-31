---
title: TRACE HEP Viewer
emoji: 🔭
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# TRACE-HEP: live event &amp; vertex viewer

Upload a ROOT file -- Delphes, ATLAS/CMS Open Data, a PHYSLITE derivation, or
a calo-timing vertex ntuple -- and see it rendered as an interactive 2D or
3D collider event / vertex display, right in your browser. No install, no
local Python.

Three modes: **Single event** (one file, one event, one display), **Many
events** (a plain event-number list, e.g. `1, 2, 4-6`, browsed as a
filterable gallery), and **Failure-mode gallery** (compare two algorithms'
pass/fail lists, or apply custom labels, and review the split visually).

**Privacy note:** uploaded files are used only to render what you ask for
and are automatically deleted after about an hour. This is a public demo
instance -- please don't upload sensitive or private data, and keep files
under 150&nbsp;MB.

Full project, source, and documentation:
[github.com/wasikatcern/TRACE-HEP](https://github.com/wasikatcern/TRACE-HEP)
