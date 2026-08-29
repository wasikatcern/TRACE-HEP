import matplotlib.colors as mcolors
import matplotlib.figure
import plotly.graph_objects as go
import pytest

from tracehep.colors import DEFAULT_COLORS, TRACK_COLOR
from tracehep.models import Jet, Track, TruthVertex, Vertex, VertexEvent
from tracehep.vertices.zr import plot_vertices_zr, plot_vertex_detail, COLOR_HS, COLOR_PU
from tracehep.vertices.view3d import plot_vertices_3d


@pytest.fixture
def sample_vertex_event():
    tracks = [
        Track(pt=20, eta=0.5, phi=0.1, x=0.0, y=0.0, z=-2.0, time=5.0),
        Track(pt=15, eta=-0.3, phi=1.2, x=0.0, y=0.0, z=-2.0, time=6.0),
        Track(pt=3, eta=1.0, phi=2.5, x=1.0, y=0.5, z=40.0, time=-30.0),
    ]
    vertices = [
        Vertex(z=-2.0, sum_pt2=625.0, is_hs=True, track_indices=[0, 1]),
        Vertex(z=40.0, x=1.0, y=0.5, sum_pt2=9.0, is_pu=True, track_indices=[2]),
    ]
    truth = [TruthVertex(z=-2.0, is_hs=True), TruthVertex(z=41.0)]
    return VertexEvent(vertices=vertices, tracks=tracks, truth_vertices=truth, mu=195.0, label="test-vtx")


@pytest.mark.parametrize("style", ["plain", "styled", "time_colored"])
def test_plot_vertices_zr_styles(sample_vertex_event, style):
    fig = plot_vertices_zr(sample_vertex_event, style=style)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plot_vertices_zr_invalid_style(sample_vertex_event):
    with pytest.raises(ValueError):
        plot_vertices_zr(sample_vertex_event, style="not-a-style")


def test_plot_vertices_zr_zoom(sample_vertex_event):
    fig = plot_vertices_zr(sample_vertex_event, zoom_center=-2.0, zoom_range_mm=5.0)
    ax = fig.axes[0]
    xlim = ax.get_xlim()
    assert xlim[0] == pytest.approx(-7.0)
    assert xlim[1] == pytest.approx(3.0)


def test_plot_vertices_3d_returns_figure(sample_vertex_event):
    fig = plot_vertices_3d(sample_vertex_event)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


def test_plot_vertex_detail_returns_figure(sample_vertex_event):
    fig = plot_vertex_detail(sample_vertex_event, vtx_index=0)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plot_vertex_detail_with_jets(sample_vertex_event):
    jets = [Jet(pt=80, eta=0.4, phi=0.2, btag=True), Jet(pt=40, eta=-1.0, phi=1.5)]
    fig = plot_vertex_detail(sample_vertex_event, vtx_index=0, jets=jets)
    ax = fig.axes[0]
    assert "vertex 0" in ax.get_title()
    # 2 jet cones (fill) + track lines should all have been drawn without error
    assert len(ax.patches) >= 2


def test_plot_vertex_detail_jets_coloured_by_is_hs(sample_vertex_event):
    jets = [Jet(pt=80, eta=0.4, phi=0.2, is_hs=True), Jet(pt=40, eta=-1.0, phi=1.5, is_hs=False)]
    fig = plot_vertex_detail(sample_vertex_event, vtx_index=0, jets=jets)
    patch_colors = [p.get_facecolor()[:3] for p in fig.axes[0].patches]
    assert mcolors.to_rgb(COLOR_HS) in patch_colors  # jet 0: is_hs=True
    assert mcolors.to_rgb(COLOR_PU) in patch_colors  # jet 1: is_hs=False


def test_plot_vertex_detail_zoom_range(sample_vertex_event):
    fig = plot_vertex_detail(sample_vertex_event, vtx_index=0, zoom_range_mm=3.0)
    ax = fig.axes[0]
    xlim = ax.get_xlim()
    assert xlim[0] == pytest.approx(-5.0)
    assert xlim[1] == pytest.approx(1.0)


def test_track_colour_prefers_own_truth_match_over_vertex_flag():
    # A reconstructed "HS" vertex routinely contains some truth-PU tracks --
    # each track must be coloured by its own is_hs, not painted uniformly
    # by the vertex's flag (regression test for that exact bug).
    tracks = [
        Track(pt=20, eta=0.5, phi=0.1, x=0.0, y=0.0, z=-2.0, is_hs=True),
        Track(pt=15, eta=-0.3, phi=1.2, x=0.0, y=0.0, z=-2.0, is_hs=False),
        Track(pt=10, eta=0.2, phi=0.8, x=0.0, y=0.0, z=-2.0, is_hs=None),  # no truth info
    ]
    vertices = [Vertex(z=-2.0, sum_pt2=625.0, is_hs=True, track_indices=[0, 1, 2])]
    ve = VertexEvent(vertices=vertices, tracks=tracks, label="test-mixed")

    fig = plot_vertex_detail(ve, vtx_index=0)
    colors = [line.get_color() for line in fig.axes[0].get_lines()]
    assert COLOR_HS in colors  # track 0 (own is_hs=True) and track 2 (falls back to vertex's HS flag)
    assert COLOR_PU in colors  # track 1: own is_hs=False, despite the vertex being HS


def test_plot_vertex_detail_no_truth_uses_neutral_tracks_legend():
    # If NO track in this vertex has its own is_hs, falling back to the
    # vertex's single flag for every one of them would paint everything
    # one colour while the legend still claimed an HS/PU split that isn't
    # backed by any data -- regression test for that exact bug.
    tracks = [
        Track(pt=20, eta=0.5, phi=0.1, x=0.0, y=0.0, z=-2.0),
        Track(pt=15, eta=-0.3, phi=1.2, x=0.0, y=0.0, z=-2.0),
    ]
    vertices = [Vertex(z=-2.0, sum_pt2=100.0, is_hs=True, track_indices=[0, 1])]
    ve = VertexEvent(vertices=vertices, tracks=tracks, label="test-no-truth")

    fig = plot_vertex_detail(ve, vtx_index=0)
    ax = fig.axes[0]
    colors = [line.get_color() for line in ax.get_lines()]
    assert TRACK_COLOR in colors
    assert COLOR_HS not in colors and COLOR_PU not in colors
    legend_labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert legend_labels == ["Tracks"]


def test_plot_vertex_detail_no_jet_truth_uses_neutral_jet_legend(sample_vertex_event):
    jets = [Jet(pt=80, eta=0.4, phi=0.2), Jet(pt=40, eta=-1.0, phi=1.5)]  # is_hs unset on both
    fig = plot_vertex_detail(sample_vertex_event, vtx_index=0, jets=jets)
    ax = fig.axes[0]
    patch_colors = {p.get_facecolor()[:3] for p in ax.patches}
    assert mcolors.to_rgb(DEFAULT_COLORS["jet"]) in patch_colors
    assert mcolors.to_rgb(COLOR_HS) not in patch_colors
    assert mcolors.to_rgb(COLOR_PU) not in patch_colors
    legend_labels = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "Jet" in legend_labels
    assert "HS jet" not in legend_labels and "PU jet" not in legend_labels


def test_plot_vertex_detail_no_jets_passed_omits_jet_legend(sample_vertex_event):
    fig = plot_vertex_detail(sample_vertex_event, vtx_index=0)  # jets=() default
    legend_labels = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    assert not any("jet" in label.lower() for label in legend_labels)
