import os

from tracehep.batch import run_event_batch, run_vertex_batch


def test_run_event_batch_polar_and_beam2d(tmp_path, sample_event):
    events = {7: sample_event, 179: sample_event}
    run_event_batch(events, str(tmp_path), which=("polar", "beam2d"),
                     polar_kwargs={"show_tracks": True})
    for key in events:
        assert os.path.exists(tmp_path / f"event{key}_polar.png")
        assert os.path.exists(tmp_path / f"event{key}_beam2d.png")


def test_run_event_batch_polar_only_kwarg_not_forwarded_to_beam2d(tmp_path, sample_event):
    # show_tracks is polar-only; passing it via polar_kwargs must not break beam2d.
    run_event_batch({0: sample_event}, str(tmp_path), which=("polar", "beam2d"),
                     polar_kwargs={"show_tracks": True})
    assert os.path.exists(tmp_path / "event0_beam2d.png")


def test_run_vertex_batch(tmp_path):
    from tracehep.models import Track, Vertex, VertexEvent
    ve = VertexEvent(vertices=[Vertex(z=0.0, is_hs=True, track_indices=[0])],
                      tracks=[Track(pt=10, eta=0.1, phi=0.2)])
    run_vertex_batch({37: ve}, str(tmp_path), styles=("plain", "styled"))
    assert os.path.exists(tmp_path / "vertices37_plain.png")
    assert os.path.exists(tmp_path / "vertices37_styled.png")
