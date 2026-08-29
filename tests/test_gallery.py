import os

import pytest

from tracehep.gallery import build_gallery, compare_pass_fail
from tracehep.models import Event, Jet, MissingET


@pytest.fixture
def sample_events():
    return {
        0: Event(jets=[Jet(pt=100, eta=0.1, phi=0.2)], met=MissingET(pt=20, phi=0.0), event_number=0),
        1: Event(jets=[], met=MissingET(pt=200, phi=1.0), event_number=1),
        2: Event(jets=[Jet(pt=50, eta=-0.5, phi=1.0), Jet(pt=40, eta=0.5, phi=-1.0)],
                 met=MissingET(pt=10, phi=0.5), event_number=2),
    }


def test_compare_pass_fail_all_four_categories():
    results_a = {0: True, 1: True, 2: False, 3: False}
    results_b = {0: True, 1: False, 2: True, 3: False}
    categories = compare_pass_fail(results_a, results_b, name_a="a", name_b="b")
    assert categories[0] == "both_pass"
    assert categories[1] == "a_pass_b_fail"
    assert categories[2] == "a_fail_b_pass"
    assert categories[3] == "both_fail"


def test_compare_pass_fail_only_shared_ids():
    results_a = {0: True, 1: False}
    results_b = {1: False, 2: True}  # event 0 and 2 not shared
    categories = compare_pass_fail(results_a, results_b)
    assert set(categories) == {1}
    assert categories[1] == "both_fail"


def test_build_gallery_writes_valid_html(tmp_path, sample_events):
    categories = {0: "anomalous", 1: "anomalous", 2: "normal"}
    out_path = str(tmp_path / "gallery.html")

    from tracehep.polar import plot_event_polar
    result = build_gallery(
        sample_events, categories, plot_fn=plot_event_polar, output_path=out_path,
        title="Unit test gallery",
    )

    assert result == out_path
    assert os.path.exists(out_path)
    html = open(out_path).read()
    assert html.count("<div") == html.count("</div>")
    assert html.count('class="card"') == 3
    assert "data:image/png;base64," in html
    assert "Unit test gallery" in html
    assert "anomalous" in html and "normal" in html


def test_build_gallery_embeds_each_image_only_once(tmp_path, sample_events):
    from tracehep.polar import plot_event_polar
    categories = {0: "x", 1: "x", 2: "y"}
    out_path = str(tmp_path / "gallery.html")
    build_gallery(sample_events, categories, plot_fn=plot_event_polar, output_path=out_path)
    html = open(out_path).read()
    assert html.count("data:image/png;base64,") == 3  # one per card, not duplicated for download links


def test_build_gallery_skips_events_without_a_category(tmp_path, sample_events):
    from tracehep.polar import plot_event_polar
    categories = {0: "only_this_one"}  # events 1 and 2 have no category
    out_path = str(tmp_path / "gallery.html")
    build_gallery(sample_events, categories, plot_fn=plot_event_polar, output_path=out_path)
    html = open(out_path).read()
    assert html.count('class="card"') == 1


def test_build_gallery_raises_on_no_overlap(tmp_path, sample_events):
    from tracehep.polar import plot_event_polar
    with pytest.raises(ValueError):
        build_gallery(sample_events, {99: "nope"}, plot_fn=plot_event_polar,
                       output_path=str(tmp_path / "gallery.html"))


def test_build_gallery_caption_appears_only_for_events_with_one(tmp_path, sample_events):
    from tracehep.polar import plot_event_polar
    categories = {0: "x", 1: "x"}
    out_path = str(tmp_path / "gallery.html")
    build_gallery(sample_events, categories, plot_fn=plot_event_polar, output_path=out_path,
                  captions={0: "a very specific reason"})
    html = open(out_path).read()
    assert "a very specific reason" in html
    assert html.count('class="caption"') == 1


def test_build_gallery_single_shared_category_has_no_redundant_filter_tab(tmp_path, sample_events):
    from tracehep.polar import plot_event_polar
    categories = {0: "event", 1: "event", 2: "event"}
    out_path = str(tmp_path / "gallery.html")
    build_gallery(sample_events, categories, plot_fn=plot_event_polar, output_path=out_path)
    html = open(out_path).read()
    assert 'onclick="setFilter(\'__all__\', this)"' in html
    assert "setFilter('event'" not in html
    assert html.count('class="badge"') == 3
    assert '>event<' not in html


def test_build_gallery_multiple_categories_get_filter_tabs_and_badges(tmp_path, sample_events):
    from tracehep.polar import plot_event_polar
    categories = {0: "anomalous", 1: "anomalous", 2: "normal"}
    out_path = str(tmp_path / "gallery.html")
    build_gallery(sample_events, categories, plot_fn=plot_event_polar, output_path=out_path)
    html = open(out_path).read()
    assert "setFilter('anomalous'" in html
    assert "setFilter('normal'" in html
    assert ">anomalous<" in html
    assert ">normal<" in html
