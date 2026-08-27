import matplotlib.figure

from tracehep.polar import eta_to_radius, eta_to_theta_deg, plot_event_polar


def test_eta_to_radius_endpoints():
    assert eta_to_radius(0.0, eta_max=4.0, r_max=1.0) == 1.0
    assert eta_to_radius(4.0, eta_max=4.0, r_max=1.0) == 0.0
    assert eta_to_radius(8.0, eta_max=4.0, r_max=1.0) == 0.0  # clamped


def test_eta_to_theta_deg_center_is_90():
    assert abs(eta_to_theta_deg(0.0) - 90.0) < 1e-9


def test_plot_event_polar_returns_figure(sample_event):
    fig = plot_event_polar(sample_event)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plot_event_polar_with_displaced_tracks(sample_event):
    fig = plot_event_polar(sample_event, show_tracks=True, d0_displaced_mm=1.0)
    labels = [line.get_label() for line in fig.axes[0].get_lines()]
    assert any("Displaced" in lbl for lbl in labels)
    assert any("Prompt" in lbl for lbl in labels)


def test_plot_event_polar_custom_title(sample_event):
    fig = plot_event_polar(sample_event, title="My Custom Title")
    assert fig.axes[0].get_title() == "My Custom Title"
