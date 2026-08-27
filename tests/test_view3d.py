import plotly.graph_objects as go

from tracehep.view3d import plot_event_3d


def test_plot_event_3d_returns_figure(sample_event):
    fig = plot_event_3d(sample_event)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0


def test_plot_event_3d_displaced_highlighting(sample_event):
    fig = plot_event_3d(sample_event, d0_displaced_mm=1.0)
    names = [trace.name for trace in fig.data if trace.name]
    assert any("Displaced" in n for n in names)
