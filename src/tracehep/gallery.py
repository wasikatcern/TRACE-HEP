"""Build a single, self-contained, portable HTML gallery of many event
displays for fast visual failure-mode review -- e.g. "algorithm 1 failed
these events but algorithm 2 passed them, why do they look different?" or
"these 400 events look anomalous, let's eyeball them."

No dependencies beyond what tracehep's core already requires (matplotlib;
plotly figures also work if the ``kaleido`` extra is installed for static
export). Every image is embedded directly in the HTML file as a base64
PNG, so the single ``.html`` file is fully portable -- email it, put it on
a shared drive, open it anywhere -- and there is no folder of hundreds of
loose image files to manage. Open it in a browser: filter by category,
search by event id, click a thumbnail to page through a full-size
lightbox with the arrow keys, and click "Download" on any image you want
to keep.

File size scales roughly linearly with event count x resolution, since
every image is embedded -- lower ``dpi`` for very large batches (see
:func:`build_gallery`).

Developed by Wasikul Islam, PhD.
"""

import base64
import html as _html
import io
from typing import Any, Callable, Dict, Optional

__all__ = ["build_gallery", "compare_pass_fail"]

_CATEGORY_PALETTE = [
    "#2a78d6", "#e34948", "#2ca02c", "#9467bd", "#ff7f0e",
    "#17becf", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22",
]


def _category_color(label: str, ordered_labels) -> str:
    idx = ordered_labels.index(label) if label in ordered_labels else 0
    return _CATEGORY_PALETTE[idx % len(_CATEGORY_PALETTE)]


def _fig_to_data_uri(fig, dpi: int) -> str:
    if hasattr(fig, "savefig"):
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        try:
            import matplotlib.pyplot as plt
            plt.close(fig)
        except ImportError:
            pass
        png_bytes = buf.getvalue()
    elif hasattr(fig, "to_image"):
        # a plotly Figure -- requires the kaleido extra for static export
        png_bytes = fig.to_image(format="png")
    else:
        raise TypeError(
            f"plot_fn must return a matplotlib Figure or a plotly Figure with "
            f"a .to_image() method (needs the 'kaleido' extra), got {type(fig)!r}"
        )
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def compare_pass_fail(
    results_a: Dict[Any, bool],
    results_b: Dict[Any, bool],
    *,
    name_a: str = "algo1",
    name_b: str = "algo2",
) -> Dict[Any, str]:
    """Turn two algorithms' per-event pass/fail results into one
    :func:`build_gallery`-ready category mapping.

    Parameters
    ----------
    results_a, results_b:
        Mapping of event id to ``True`` (passed) / ``False`` (failed) for
        each algorithm. Only event ids present in *both* mappings are
        categorized -- an event either algorithm didn't run on is skipped.
    name_a, name_b:
        Used to build readable category labels.

    Returns
    -------
    dict mapping each shared event id to one of four labels:
    ``f"{name_a}_fail_{name_b}_pass"``, ``f"{name_a}_pass_{name_b}_fail"``,
    ``"both_pass"``, or ``"both_fail"`` -- exactly the disagreement-vs-
    agreement split a failure-mode study wants to eyeball, with the two
    disagreement categories (the interesting ones) kept distinct from
    the two agreement ones.
    """
    categories: Dict[Any, str] = {}
    for eid in set(results_a) & set(results_b):
        a, b = results_a[eid], results_b[eid]
        if a and b:
            categories[eid] = "both_pass"
        elif not a and not b:
            categories[eid] = "both_fail"
        elif a and not b:
            categories[eid] = f"{name_a}_pass_{name_b}_fail"
        else:
            categories[eid] = f"{name_a}_fail_{name_b}_pass"
    return categories


def build_gallery(
    events: Dict[Any, Any],
    categories: Dict[Any, str],
    plot_fn: Callable[[Any], Any],
    output_path: str,
    *,
    title: str = "TRACE Event Review",
    dpi: int = 100,
    captions: Optional[Dict[Any, str]] = None,
) -> str:
    """Render one display per event and assemble them into a single
    self-contained HTML gallery for fast visual failure-mode review.

    Parameters
    ----------
    events:
        Mapping of event id (event number, index, a (run, event) pair,
        ...) to an already-loaded object your ``plot_fn`` knows how to
        draw -- typically a :class:`~tracehep.models.Event` or
        :class:`~tracehep.models.VertexEvent`.
    categories:
        Mapping of the same event ids to a free-text category label, e.g.
        ``{1234: "algo1_fail_algo2_pass", 5678: "both_fail"}`` (see
        :func:`compare_pass_fail` for building this from two algorithms'
        pass/fail results), or ``{eid: "anomalous" for eid in ...}`` for
        a single-bucket anomaly-detection review. Every distinct label
        becomes a clickable filter tab in the gallery. Event ids in
        ``events`` but not in ``categories`` are skipped.
    plot_fn:
        Called as ``plot_fn(event)`` for each event; must return a
        matplotlib Figure (e.g.
        ``lambda ev: trace.plot_event_polar(ev, show_tracks=True)``) or a
        plotly Figure (needs the ``kaleido`` extra for static export).
        Pick whichever display best shows the effect you're investigating
        -- there is nothing gallery-specific about it.
    output_path:
        Where to write the ``.html`` file.
    dpi:
        Resolution of the embedded PNGs. Every image is embedded
        directly, so the output file size scales roughly linearly with
        event count x dpi^2 -- for a few dozen events the default (100) is
        fine; for hundreds-to-thousands, drop to 60-80 to keep the file a
        reasonable size and the browser responsive.
    captions:
        Optional per-event caption shown under each thumbnail, e.g. a
        one-line summary of why the algorithms disagreed on this event.

    Returns
    -------
    ``output_path``, for convenience/chaining.
    """
    shared_ids = [eid for eid in events if eid in categories]
    if not shared_ids:
        raise ValueError("No event id is present in both 'events' and 'categories'.")

    ordered_labels = sorted(set(categories[eid] for eid in shared_ids))
    captions = captions or {}

    cards_html = []
    for eid in shared_ids:
        label = categories[eid]
        color = _category_color(label, ordered_labels)
        fig = plot_fn(events[eid])
        data_uri = _fig_to_data_uri(fig, dpi)
        caption = _html.escape(captions.get(eid, ""))
        safe_eid = _html.escape(str(eid))
        safe_label = _html.escape(label)
        cards_html.append(f'''
      <div class="card" data-category="{safe_label}" data-eid="{safe_eid.lower()}">
        <img src="{data_uri}" alt="event {safe_eid}" loading="lazy"
             onclick="openLightbox('{safe_eid}')">
        <div class="card-meta">
          <span class="badge" style="background:{color}">{safe_label}</span>
          <span class="eid">#{safe_eid}</span>
        </div>
        {f'<div class="caption">{caption}</div>' if caption else ""}
        <a class="download" data-fname="event_{safe_eid}.png">Download</a>
      </div>''')

    filter_buttons = ['<button class="filter-btn active" onclick="setFilter(\'__all__\', this)">'
                       f'All ({len(shared_ids)})</button>']
    for label in ordered_labels:
        n = sum(1 for eid in shared_ids if categories[eid] == label)
        color = _category_color(label, ordered_labels)
        safe_label = _html.escape(label)
        filter_buttons.append(
            f'<button class="filter-btn" style="--dot:{color}" '
            f'onclick="setFilter(\'{safe_label}\', this)">{safe_label} ({n})</button>'
        )

    html_doc = _PAGE_TEMPLATE.format(
        title=_html.escape(title),
        n_events=len(shared_ids),
        filter_buttons="\n".join(filter_buttons),
        cards="\n".join(cards_html),
    )

    with open(output_path, "w") as fh:
        fh.write(html_doc)
    return output_path


_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{
    --bg: #f7f7f8; --surface: #ffffff; --ink: #1a1a1a; --muted: #6b6b6b;
    --border: #e2e2e4; --accent: #2a78d6;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
  }}
  header {{
    position: sticky; top: 0; z-index: 10; background: var(--surface);
    border-bottom: 1px solid var(--border); padding: 14px 24px;
  }}
  h1 {{ font-size: 18px; margin: 0 0 10px 0; }}
  .toolbar {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
  .filter-btn {{
    border: 1px solid var(--border); background: var(--surface); color: var(--ink);
    border-radius: 999px; padding: 5px 12px; font-size: 13px; cursor: pointer;
    display: inline-flex; align-items: center; gap: 6px;
  }}
  .filter-btn[style*="--dot"]::before {{
    content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--dot);
    display: inline-block;
  }}
  .filter-btn.active {{ background: var(--ink); color: white; border-color: var(--ink); }}
  #search {{
    margin-left: auto; padding: 6px 10px; border: 1px solid var(--border);
    border-radius: 6px; font-size: 13px; width: 200px;
  }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 16px; padding: 20px 24px;
  }}
  .card {{
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px;
    overflow: hidden; display: flex; flex-direction: column;
  }}
  .card img {{ width: 100%; display: block; cursor: zoom-in; background: #fafafa; }}
  .card-meta {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 8px 10px 0 10px; font-size: 12px;
  }}
  .badge {{ color: white; border-radius: 4px; padding: 2px 7px; font-size: 11px; }}
  .eid {{ color: var(--muted); font-variant-numeric: tabular-nums; }}
  .caption {{ padding: 4px 10px 0 10px; font-size: 12px; color: var(--muted); }}
  .download {{
    margin: 8px 10px 10px 10px; text-align: center; font-size: 12px;
    text-decoration: none; color: var(--accent); border: 1px solid var(--border);
    border-radius: 6px; padding: 5px; background: var(--bg);
  }}
  .download:hover {{ background: var(--accent); color: white; border-color: var(--accent); }}
  .card.hidden {{ display: none; }}
  #lightbox {{
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.88);
    z-index: 100; align-items: center; justify-content: center; flex-direction: column;
  }}
  #lightbox.open {{ display: flex; }}
  #lightbox img {{ max-width: 92vw; max-height: 78vh; border-radius: 6px; background: white; }}
  #lightbox .lb-meta {{ color: white; margin-top: 12px; font-size: 14px; display: flex; gap: 16px; align-items: center; }}
  #lightbox .lb-download {{ color: white; text-decoration: underline; }}
  .nav-btn {{
    position: fixed; top: 50%; transform: translateY(-50%); background: rgba(255,255,255,0.12);
    color: white; border: none; width: 48px; height: 48px; border-radius: 50%;
    font-size: 22px; cursor: pointer;
  }}
  .nav-btn:hover {{ background: rgba(255,255,255,0.25); }}
  #prevBtn {{ left: 20px; }}
  #nextBtn {{ right: 20px; }}
  #closeBtn {{ position: fixed; top: 20px; right: 24px; background: none; border: none;
               color: white; font-size: 28px; cursor: pointer; }}
  .empty-msg {{ padding: 40px; text-align: center; color: var(--muted); display: none; }}
</style>
</head>
<body>
<header>
  <h1>{title} &middot; {n_events} events</h1>
  <div class="toolbar">
    {filter_buttons}
    <button class="filter-btn" id="dlAllBtn" onclick="downloadAllVisible()">&#8681; Download all (visible)</button>
    <input id="search" type="text" placeholder="Jump to event #..." oninput="applySearch()">
  </div>
</header>
<div class="grid" id="grid">
{cards}
</div>
<div class="empty-msg" id="emptyMsg">No events match this filter/search.</div>

<div id="lightbox" onclick="if(event.target===this) closeLightbox()">
  <button class="nav-btn" id="prevBtn" onclick="event.stopPropagation(); step(-1)">&#8249;</button>
  <img id="lightboxImg" src="">
  <div class="lb-meta">
    <span id="lightboxLabel"></span>
    <a class="lb-download" id="lightboxDownload" href="#" download>Download</a>
  </div>
  <button class="nav-btn" id="nextBtn" onclick="event.stopPropagation(); step(1)">&#8250;</button>
  <button id="closeBtn" onclick="closeLightbox()">&times;</button>
</div>

<script>
var currentFilter = "__all__";

function cardsList() {{
  return Array.from(document.querySelectorAll("#grid .card"));
}}

function visibleCards() {{
  return cardsList().filter(function(c) {{ return !c.classList.contains("hidden"); }});
}}

function setFilter(label, btn) {{
  currentFilter = label;
  document.querySelectorAll(".filter-btn").forEach(function(b) {{ b.classList.remove("active"); }});
  btn.classList.add("active");
  applySearch();
}}

function applySearch() {{
  var q = document.getElementById("search").value.trim().toLowerCase();
  var anyVisible = false;
  cardsList().forEach(function(card) {{
    var matchesCat = (currentFilter === "__all__") || (card.dataset.category === currentFilter);
    var matchesSearch = (q === "") || (card.dataset.eid.indexOf(q) !== -1);
    var show = matchesCat && matchesSearch;
    card.classList.toggle("hidden", !show);
    if (show) anyVisible = true;
  }});
  document.getElementById("emptyMsg").style.display = anyVisible ? "none" : "block";
}}

function openLightbox(eid) {{
  var cards = visibleCards();
  var idx = cards.findIndex(function(c) {{ return c.dataset.eid === String(eid).toLowerCase(); }});
  if (idx === -1) idx = 0;
  showAt(idx);
  document.getElementById("lightbox").classList.add("open");
}}

function showAt(idx) {{
  var cards = visibleCards();
  if (cards.length === 0) return;
  idx = (idx + cards.length) % cards.length;
  var card = cards[idx];
  var img = card.querySelector("img");
  var dl = card.querySelector(".download");
  document.getElementById("lightboxImg").src = img.src;
  document.getElementById("lightboxImg").dataset.idx = idx;
  document.getElementById("lightboxLabel").textContent = "#" + card.dataset.eid + " -- " + card.dataset.category;
  document.getElementById("lightboxDownload").href = dl.href;
  document.getElementById("lightboxDownload").download = dl.download;
}}

function step(delta) {{
  var idx = parseInt(document.getElementById("lightboxImg").dataset.idx || "0", 10);
  showAt(idx + delta);
}}

function closeLightbox() {{
  document.getElementById("lightbox").classList.remove("open");
}}

function downloadAllVisible() {{
  var cards = visibleCards();
  if (cards.length === 0) return;
  if (cards.length > 25 && !confirm("This will download " + cards.length + " separate image files. Continue?")) return;
  cards.forEach(function(card, i) {{
    setTimeout(function() {{
      var img = card.querySelector("img");
      var dl = card.querySelector(".download");
      var a = document.createElement("a");
      a.href = img.src;
      a.download = dl.dataset.fname;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }}, i * 150);
  }});
}}

document.addEventListener("keydown", function(e) {{
  if (!document.getElementById("lightbox").classList.contains("open")) return;
  if (e.key === "Escape") closeLightbox();
  if (e.key === "ArrowLeft") step(-1);
  if (e.key === "ArrowRight") step(1);
}});

// Each image's data URI is embedded once (on <img>); wire the sibling
// download link to it here instead of duplicating the payload in the HTML.
cardsList().forEach(function(card) {{
  var img = card.querySelector("img");
  var dl = card.querySelector(".download");
  dl.href = img.src;
  dl.download = dl.dataset.fname;
}});
</script>
</body>
</html>
"""
