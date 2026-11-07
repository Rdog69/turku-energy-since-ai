"""Every feature that can appear in `top_drivers` needs a plain-language label for the dashboard.

Feature groups are collected dynamically (every *_COLUMNS list in src.features.build except
TARGET_COLUMNS), so a new group added later is covered automatically.
Drafted by a Featherless worker (Qwen3-Coder-30B), reviewed by the coordinator.
"""
import warnings

import pytest

import src.features.build as build


def _features() -> list[str]:
    names = {"step"}
    for attr in dir(build):
        value = getattr(build, attr)
        if attr.endswith("_COLUMNS") and attr != "TARGET_COLUMNS" and isinstance(value, list) \
                and all(isinstance(x, str) for x in value):
            names.update(value)
    return sorted(names)


@pytest.fixture(scope="module")
def labels() -> dict:
    dashboard = pytest.importorskip("src.export.dashboard")
    return dashboard.DRIVER_LABELS


def test_every_feature_has_a_label(labels):
    missing = [f for f in _features() if f not in labels]
    assert not missing, f"features without a DRIVER_LABELS entry: {missing}"


def test_labels_are_plain_language(labels):
    for key, value in labels.items():
        assert isinstance(value, str) and value, f"empty label for {key!r}"
        assert len(value) <= 50, f"label for {key!r} is too long ({len(value)} chars): {value!r}"
        assert "_" not in value, f"label for {key!r} contains an underscore: {value!r}"
        assert value != key, f"label for {key!r} equals its key"


def test_no_stale_labels(labels):
    stale = sorted(set(labels) - set(_features()))
    if stale:   # some labels describe dashboard inputs, so this is only a warning
        warnings.warn(f"DRIVER_LABELS entries that are not features: {stale}", UserWarning)
