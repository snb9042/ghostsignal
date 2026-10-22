import pytest
pytest.importorskip("PyQt6.QtCore")

def test_workers_importable():
    from ghostsignal.workers.osrm_worker import OsrmWorker
    from ghostsignal.workers.pipeline_worker import PipelineWorker
    from ghostsignal.workers.playback_worker import PlaybackWorker
    assert OsrmWorker and PipelineWorker and PlaybackWorker
