import matplotlib.figure
import plotly.graph_objects as go
import pytest

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
