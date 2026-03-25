"""
Tests for properties.py — property set extraction.
"""

import pytest
from ..converters.properties import (
    _extract_value,
    _extract_quantity_value,
    extract_properties,
    PropertyGraph,
)


class TestExtractValue:
    def test_string_value(self):
        class MockVal:
            wrappedValue = "30 min"
        assert _extract_value(MockVal()) == "30 min"

    def test_boolean_true(self):
        class MockVal:
            wrappedValue = True
        assert _extract_value(MockVal()) is True

    def test_boolean_false(self):
        class MockVal:
            wrappedValue = False
        assert _extract_value(MockVal()) is False

    def test_integer(self):
        class MockVal:
            wrappedValue = 42
        assert _extract_value(MockVal()) == 42

    def test_float(self):
        class MockVal:
            wrappedValue = 3.14
        assert abs(_extract_value(MockVal()) - 3.14) < 1e-9

    def test_logical_true_string(self):
        class MockVal:
            wrappedValue = "TRUE"
        assert _extract_value(MockVal()) is True

    def test_logical_false_string(self):
        class MockVal:
            wrappedValue = "FALSE"
        assert _extract_value(MockVal()) is False

    def test_none_returns_none(self):
        assert _extract_value(None) is None

    def test_plain_python_bool(self):
        assert _extract_value(True) is True

    def test_plain_python_int(self):
        assert _extract_value(99) == 99

    def test_plain_python_string(self):
        assert _extract_value("Concrete") == "Concrete"


class TestExtractQuantityValue:
    def test_length_value(self):
        class MockQty:
            LengthValue = 5.5
            def is_a(self): return "IfcQuantityLength"
        assert _extract_quantity_value(MockQty()) == 5.5

    def test_area_value(self):
        class MockQty:
            AreaValue = 12.0
            def is_a(self): return "IfcQuantityArea"
        assert _extract_quantity_value(MockQty()) == 12.0

    def test_count_value(self):
        class MockQty:
            CountValue = 3
            def is_a(self): return "IfcQuantityCount"
        assert _extract_quantity_value(MockQty()) == 3

    def test_no_value_returns_none(self):
        class MockQty:
            def is_a(self): return "IfcQuantityLength"
        assert _extract_quantity_value(MockQty()) is None


class TestExtractProperties:
    """Integration-style tests using mock IFC entities."""

    def _make_element(self, pset_props=None):
        """Build a minimal mock element with one property set."""

        class MockWrapped:
            def __init__(self, v): self.wrappedValue = v

        class MockProp:
            def __init__(self, name, value, unit=None):
                self.Name = name
                self.NominalValue = MockWrapped(value)
                self.Unit = unit
            def is_a(self, t=None): return t == "IfcPropertySingleValue" if t else "IfcPropertySingleValue"

        class MockPSet:
            def __init__(self, props):
                self.HasProperties = props
            def is_a(self, t=None):
                if t: return t == "IfcPropertySet"
                return "IfcPropertySet"

        class MockRel:
            def __init__(self, pset):
                self.RelatingPropertyDefinition = pset

        class MockElement:
            GlobalId = "TEST001"
            Name = "TestWall"
            Description = None
            ObjectType = None
            Tag = None
            PredefinedType = None
            LongName = None
            Elevation = None
            IsTypedBy = []

            def __init__(self, psets):
                self.IsDefinedBy = [MockRel(p) for p in psets]

            def is_a(self, t=None):
                if t: return t == "IfcWall"
                return "IfcWall"

        props = pset_props or []
        pset_entities = [
            MockPSet([MockProp(n, v) for n, v in props])
        ]
        return MockElement(pset_entities)

    def test_l1_flat_properties(self):
        elem = self._make_element([
            ("Is External", True),
            ("Fire Rating", "60 min"),
            ("LoadBearing", False),
        ])
        pg = extract_properties(elem, "http://test/wall_001", {}, level=1)
        assert isinstance(pg, PropertyGraph)
        assert pg.flat_props.get("isExternal_property_simple") is True
        assert pg.flat_props.get("fireRating_property_simple") == "60 min"
        assert pg.flat_props.get("loadbearing_property_simple") is False

    def test_l1_global_id_always_present(self):
        elem = self._make_element([])
        pg = extract_properties(elem, "http://test/wall_001", {}, level=1)
        assert pg.flat_props.get("globalId") == "TEST001"

    def test_l1_name_stored(self):
        elem = self._make_element([])
        pg = extract_properties(elem, "http://test/wall_001", {}, level=1)
        assert pg.flat_props.get("name") == "TestWall"

    def test_l2_creates_property_nodes(self):
        elem = self._make_element([("Area", 25.5)])
        pg = extract_properties(elem, "http://test/wall_001", {}, level=2,
                                base_uri="http://test/")
        assert len(pg.property_nodes) > 0
        assert len(pg.flat_props) > 0  # attributes still go flat

    def test_l1_empty_psets(self):
        elem = self._make_element([])
        pg = extract_properties(elem, "http://test/wall_001", {}, level=1)
        # Should still have globalId and name from attributes
        assert "globalId" in pg.flat_props

    def test_none_value_skipped(self):
        elem = self._make_element([("EmptyProp", None)])
        pg = extract_properties(elem, "http://test/wall_001", {}, level=1)
        # None values should not appear
        assert "emptyProp_property_simple" not in pg.flat_props
