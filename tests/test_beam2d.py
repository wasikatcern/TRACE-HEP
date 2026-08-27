import matplotlib.figure

from tracehep.beam2d import plot_event_beam2d


def test_plot_event_beam2d_returns_figure(sample_event):
    fig = plot_event_beam2d(sample_event)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plot_event_beam2d_no_met():
    from tracehep.models import Event
    fig = plot_event_beam2d(Event())
    assert isinstance(fig, matplotlib.figure.Figure)
