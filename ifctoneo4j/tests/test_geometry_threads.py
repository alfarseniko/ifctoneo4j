"""
Tests for the geometry thread count (--geometry-workers) and the progress log.
"""

import logging

import pytest

from ..config import ConversionConfig
from ..geometry import bounding_box as bb_mod
from ..geometry.bounding_box import BoundingBox, compute_bounding_boxes, resolve_threads


class TestResolveThreads:
    def test_explicit_counts_are_used_as_given(self):
        assert resolve_threads(1) == 1
        assert resolve_threads(8) == 8

    def test_zero_means_all_cores(self, monkeypatch):
        monkeypatch.setattr(bb_mod.os, "cpu_count", lambda: 6)
        assert resolve_threads(0) == 6

    def test_zero_without_cpu_count_falls_back_to_one(self, monkeypatch):
        monkeypatch.setattr(bb_mod.os, "cpu_count", lambda: None)
        assert resolve_threads(0) == 1

    def test_negative_is_rejected(self):
        with pytest.raises(ValueError):
            resolve_threads(-1)


class TestConfig:
    def test_default_is_single_threaded(self):
        assert ConversionConfig().geometry_workers == 1

    def test_negative_workers_fail_validation(self):
        with pytest.raises(ValueError, match="geometry_workers"):
            ConversionConfig(geometry_workers=-2).validate()

    def test_zero_and_positive_are_valid(self):
        ConversionConfig(geometry_workers=0).validate()
        ConversionConfig(geometry_workers=8).validate()


# ── a fake ifcopenshell iterator, to check what is passed and what is logged ──

class _Geom:
    def __init__(self, verts):
        self.verts = verts


class _Shape:
    def __init__(self, guid, verts):
        self.guid = guid
        self.geometry = _Geom(verts)


class _FakeModel:
    def __init__(self, guids):
        self._guids = guids

    def by_type(self, name):
        return list(self._guids)

    def by_guid(self, guid):
        return None


def _install_fake_iterator(monkeypatch, shapes, calls):
    import ifcopenshell.geom as geom

    class FakeIterator:
        def __init__(self, settings, model, num_threads=1, include=None, **kw):
            calls.append({"num_threads": num_threads, "include": include})
            self._shapes, self._i = shapes, 0

        def initialize(self):
            return bool(self._shapes)

        def get(self):
            return self._shapes[self._i]

        def next(self):
            self._i += 1
            return self._i < len(self._shapes)

        def progress(self):
            return 100.0 * (self._i + 1) / len(self._shapes)

    monkeypatch.setattr(geom, "iterator", FakeIterator)


class TestIteratorUsage:
    SHAPES = [_Shape(f"G{i}", [i, 0, 0, i + 1, 2, 3]) for i in range(10)]

    def test_thread_count_reaches_the_iterator(self, monkeypatch):
        calls = []
        _install_fake_iterator(monkeypatch, self.SHAPES, calls)
        out = compute_bounding_boxes(_FakeModel([s.guid for s in self.SHAPES]), num_threads=5)
        assert calls == [{"num_threads": 5, "include": [s.guid for s in self.SHAPES]}]
        assert len(out) == 10 and out["G3"] == BoundingBox(3, 4, 0, 2, 0, 3)

    def test_default_stays_single_threaded(self, monkeypatch):
        calls = []
        _install_fake_iterator(monkeypatch, self.SHAPES, calls)
        compute_bounding_boxes(_FakeModel(["G0"]))
        assert calls[0]["num_threads"] == 1

    def test_zero_uses_all_cores(self, monkeypatch):
        monkeypatch.setattr(bb_mod.os, "cpu_count", lambda: 3)
        calls = []
        _install_fake_iterator(monkeypatch, self.SHAPES, calls)
        compute_bounding_boxes(_FakeModel(["G0"]), num_threads=0)
        assert calls[0]["num_threads"] == 3

    def test_seen_guids_filter_still_applies(self, monkeypatch):
        _install_fake_iterator(monkeypatch, self.SHAPES, [])
        out = compute_bounding_boxes(_FakeModel(["G0"]), seen_guids={"G1", "G2"})
        assert set(out) == {"G1", "G2"}


class TestProgressLog:
    def test_progress_is_logged_with_percent_and_eta(self, monkeypatch, caplog):
        shapes = [_Shape(f"G{i}", [0, 0, 0, 1, 1, 1]) for i in range(20)]
        _install_fake_iterator(monkeypatch, shapes, [])
        with caplog.at_level(logging.INFO, logger=bb_mod.logger.name):
            compute_bounding_boxes(_FakeModel([s.guid for s in shapes]), num_threads=2, progress_step=25.0)
        text = "\n".join(r.getMessage() for r in caplog.records)
        assert "for 20 elements with 2 thread(s)" in text
        assert "Geometry  25%" in text and "Geometry 100%" in text and "ETA" in text
        assert "Computed bounding boxes for 20 elements" in text
        # logged in steps, not once per element
        assert sum("Geometry " in r.getMessage() and "%" in r.getMessage() for r in caplog.records) <= 6


# ── real geometry: thread count must not change the result ────────────────────

def _tiny_model(n_walls=12):
    ifcopenshell = pytest.importorskip("ifcopenshell")
    np = pytest.importorskip("numpy")
    import ifcopenshell.api as api

    f = api.run("project.create_file")
    api.run("root.create_entity", f, ifc_class="IfcProject", name="p")
    api.run("unit.assign_unit", f)
    ctx = api.run("context.add_context", f, context_type="Model")
    body = api.run("context.add_context", f, context_type="Model", context_identifier="Body",
                   target_view="MODEL_VIEW", parent=ctx)
    expected = {}
    for i in range(n_walls):
        wall = api.run("root.create_entity", f, ifc_class="IfcWall", name=f"w{i}")
        rep = api.run("geometry.add_wall_representation", f, context=body, length=5.0, height=3.0, thickness=0.2)
        api.run("geometry.assign_representation", f, product=wall, representation=rep)
        m = np.eye(4)
        m[0, 3], m[1, 3] = 10.0 * i, 2.0 * i
        api.run("geometry.edit_object_placement", f, product=wall, matrix=m)
        expected[wall.GlobalId] = (10.0 * i, 10.0 * i + 5.0, 2.0 * i)    # x_min, x_max, y_min of the wall
    return f, expected


class TestRealGeometry:
    def test_boxes_are_correct_and_identical_for_any_thread_count(self):
        model, expected = _tiny_model()
        single = compute_bounding_boxes(model, num_threads=1)
        multi = compute_bounding_boxes(model, num_threads=3)
        everything = compute_bounding_boxes(model, num_threads=0)
        assert set(single) == set(expected) and single == multi == everything
        for guid, (x_min, x_max, y_min) in expected.items():
            box = single[guid]
            assert box.x_min == pytest.approx(x_min, abs=1e-6) and box.x_max == pytest.approx(x_max, abs=1e-6)
            assert box.y_min == pytest.approx(y_min, abs=1e-6)
            assert box.z_min == pytest.approx(0.0, abs=1e-6) and box.z_max == pytest.approx(3.0, abs=1e-6)
