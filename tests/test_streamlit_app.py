import os
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "app" / "streamlit_app.py")


def _data_dir():
    for p in (os.environ.get("DASHBOARD_DATA_DIR"), ROOT / "app_demo_sample/test"):
        if p and (Path(p) / "index.json").exists():
            return str(p)
    pytest.skip("no dashboard sample data available")


def test_app_runs_and_time_travels(monkeypatch):
    monkeypatch.setenv("DASHBOARD_DATA_DIR", _data_dir())
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    labels = at.select_slider[0].options
    at.select_slider[0].set_value(labels[min(3, len(labels) - 1)]).run()
    assert not at.exception
