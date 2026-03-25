"""
Tests for unit_handler.py — IfcUnitAssignment → QUDT unit mapping.
"""

import pytest
from ..core.unit_handler import _qudt_uri, build_unit_map, get_unit_for_property, QUDT_BASE


class TestQudt:
    def test_length_no_prefix(self):
        assert _qudt_uri("LENGTHUNIT", None) == QUDT_BASE + "M"

    def test_length_milli(self):
        assert _qudt_uri("LENGTHUNIT", "MILLI") == QUDT_BASE + "MilliM"

    def test_area_no_prefix(self):
        assert _qudt_uri("AREAUNIT", None) == QUDT_BASE + "M2"

    def test_area_milli(self):
        assert _qudt_uri("AREAUNIT", "MILLI") == QUDT_BASE + "MilliM2"

    def test_volume_no_prefix(self):
        assert _qudt_uri("VOLUMEUNIT", None) == QUDT_BASE + "M3"

    def test_plane_angle(self):
        assert _qudt_uri("PLANEANGLEUNIT", None) == QUDT_BASE + "RAD"

    def test_case_insensitive(self):
        assert _qudt_uri("lengthunit", None) == QUDT_BASE + "M"

    def test_unknown_returns_none(self):
        assert _qudt_uri("FURLONG", None) is None


class TestBuildUnitMap:
    """Tests with a mock IfcProject."""

    def _make_mock_model(self, units):
        """Build a minimal mock that mimics ifcopenshell's interface."""

        class MockUnit:
            def __init__(self, unit_type, prefix=None, name=None, entity_type="IfcSIUnit"):
                self._type = entity_type
                self.UnitType = unit_type
                self.Prefix   = prefix
                self.Name     = name
            def is_a(self): return self._type

        class MockUnitAssignment:
            def __init__(self, units): self.Units = units

        class MockProject:
            def __init__(self, ua): self.UnitsInContext = ua

        class MockModel:
            def __init__(self, project): self._project = project
            def by_type(self, t):
                return [self._project] if t == "IfcProject" else []

        ua = MockUnitAssignment([MockUnit(*u) if isinstance(u, tuple) else u for u in units])
        return MockModel(MockProject(ua))

    def test_length_unit_mapped(self):
        model = self._make_mock_model([("LENGTHUNIT", None)])
        m = build_unit_map(model)
        assert m.get("LENGTHUNIT") == QUDT_BASE + "M"

    def test_area_unit_mapped(self):
        model = self._make_mock_model([("AREAUNIT", None)])
        m = build_unit_map(model)
        assert m.get("AREAUNIT") == QUDT_BASE + "M2"

    def test_multiple_units(self):
        model = self._make_mock_model([
            ("LENGTHUNIT", None),
            ("AREAUNIT",   None),
            ("VOLUMEUNIT", None),
            ("PLANEANGLEUNIT", None),
        ])
        m = build_unit_map(model)
        assert m["LENGTHUNIT"]     == QUDT_BASE + "M"
        assert m["AREAUNIT"]       == QUDT_BASE + "M2"
        assert m["VOLUMEUNIT"]     == QUDT_BASE + "M3"
        assert m["PLANEANGLEUNIT"] == QUDT_BASE + "RAD"

    def test_milli_prefix(self):
        model = self._make_mock_model([("LENGTHUNIT", "MILLI")])
        m = build_unit_map(model)
        assert m["LENGTHUNIT"] == QUDT_BASE + "MilliM"

    def test_no_project_returns_empty(self):
        class EmptyModel:
            def by_type(self, _): return []
        m = build_unit_map(EmptyModel())
        assert m == {}


class TestGetUnitForProperty:
    def test_returns_from_map(self):
        unit_map = {"LENGTHUNIT": QUDT_BASE + "M"}
        result = get_unit_for_property(unit_map, None, "LENGTHUNIT")
        assert result == QUDT_BASE + "M"

    def test_returns_none_if_missing(self):
        result = get_unit_for_property({}, None, "LENGTHUNIT")
        assert result is None

    def test_explicit_unit_overrides_map(self):
        class MockSIUnit:
            def is_a(self): return "IfcSIUnit"
            UnitType = "AREAUNIT"
            Prefix   = None
        unit_map = {"AREAUNIT": QUDT_BASE + "WRONG"}
        result = get_unit_for_property(unit_map, MockSIUnit(), "AREAUNIT")
        assert result == QUDT_BASE + "M2"
