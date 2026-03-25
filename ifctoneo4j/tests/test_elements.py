"""
Tests for elements.py — element classification, URI building, sub-element detection.
"""

import pytest
from ..converters.elements import (
    build_element_uri,
    classify_element,
    make_spatial_node,
    make_element_node,
    make_relationship,
    get_hosted_elements,
    get_aggregated_sub_elements,
)

BASE_URI = "https://example.org/building#"


# ---------------------------------------------------------------------------
# Mock element helpers
# ---------------------------------------------------------------------------

class MockElement:
    def __init__(self, ifc_class, guid, name=None, predefined=None,
                 has_openings=None, is_decomposed_by=None):
        self._ifc_class  = ifc_class
        self.GlobalId    = guid
        self.Name        = name
        self.PredefinedType = predefined
        self.HasOpenings    = has_openings or []
        self.IsDecomposedBy = is_decomposed_by or []
        self.Description = None
        self.ObjectType  = None
        self.Tag         = None
        self.LongName    = None
        self.Elevation   = None

    # Minimal but accurate IFC type hierarchy for mocking.
    # Maps child → set of ancestor class names.
    _ANCESTORS: dict = {
        "IfcWall":                 {"IfcBuildingElement", "IfcElement", "IfcProduct"},
        "IfcDoor":                 {"IfcBuildingElement", "IfcElement", "IfcProduct"},
        "IfcWindow":               {"IfcBuildingElement", "IfcElement", "IfcProduct"},
        "IfcSlab":                 {"IfcBuildingElement", "IfcElement", "IfcProduct"},
        "IfcBeam":                 {"IfcBuildingElement", "IfcElement", "IfcProduct"},
        "IfcColumn":               {"IfcBuildingElement", "IfcElement", "IfcProduct"},
        "IfcRoof":                 {"IfcBuildingElement", "IfcElement", "IfcProduct"},
        "IfcFan":                  {"IfcFlowMovingDevice", "IfcDistributionFlowElement",
                                    "IfcDistributionElement", "IfcElement", "IfcProduct"},
        "IfcBuildingElementPart":  {"IfcElement", "IfcProduct"},
        "IfcFurnishingElement":    {"IfcElement", "IfcProduct"},
        # IfcProxy inherits from IfcProduct but NOT IfcElement/IfcBuildingElement
        "IfcProxy":                {"IfcProduct"},
    }

    def is_a(self, t=None):
        if t:
            return (self._ifc_class == t or
                    t in self._ANCESTORS.get(self._ifc_class, set()))
        return self._ifc_class


class TestBuildElementUri:
    def test_standard_uri(self):
        elem = MockElement("IfcWall", "GUID123")
        uri = build_element_uri(elem, BASE_URI)
        assert uri == f"{BASE_URI}ifcwall_GUID123"

    def test_standard_uri_lowercase_class(self):
        elem = MockElement("IfcDoor", "DOOR001")
        uri = build_element_uri(elem, BASE_URI)
        assert "ifcdoor" in uri

    def test_hierarchical_with_name(self):
        elem = MockElement("IfcWall", "GUID123", name="Main Wall")
        uri = build_element_uri(elem, BASE_URI, hierarchical=True)
        assert "Main_Wall" in uri

    def test_hierarchical_with_parent(self):
        elem = MockElement("IfcWall", "GUID123", name="East Wall")
        parent = f"{BASE_URI}Level1"
        uri = build_element_uri(elem, BASE_URI, hierarchical=True, parent_uri=parent)
        assert uri.startswith(parent)
        assert "East_Wall" in uri

    def test_no_guid_fallback(self):
        elem = MockElement("IfcWall", None)
        uri = build_element_uri(elem, BASE_URI)
        assert "ifcwall" in uri

    def test_different_classes_different_uris(self):
        wall = MockElement("IfcWall", "G1")
        door = MockElement("IfcDoor", "G2")
        assert build_element_uri(wall, BASE_URI) != build_element_uri(door, BASE_URI)


class TestClassifyElement:
    def test_wall_classification(self):
        elem = MockElement("IfcWall", "G1")
        labels = classify_element(elem)
        assert "Element" in labels
        assert "Wall" in labels

    def test_wall_with_predefined_type(self):
        elem = MockElement("IfcWall", "G1", predefined="SOLIDWALL")
        labels = classify_element(elem)
        assert "Wall_SOLIDWALL" in labels

    def test_door_classification(self):
        elem = MockElement("IfcDoor", "G2")
        labels = classify_element(elem)
        assert "Door" in labels

    def test_fan_classification(self):
        elem = MockElement("IfcFan", "G3")
        labels = classify_element(elem)
        assert "Fan" in labels

    def test_fan_with_predefined_type(self):
        elem = MockElement("IfcFan", "G3", predefined="AXIAL")
        labels = classify_element(elem)
        assert "Fan_AXIAL" in labels

    def test_unknown_class_returns_element(self):
        elem = MockElement("IfcProxy", "G4")
        labels = classify_element(elem)
        assert labels == ["Element"]

    def test_element_always_first(self):
        elem = MockElement("IfcBeam", "G5")
        labels = classify_element(elem)
        assert labels[0] == "Element"

    def test_furniture_element(self):
        elem = MockElement("IfcFurnishingElement", "G6")
        labels = classify_element(elem)
        assert "Furniture" in labels

    def test_notdefined_predefined_ignored(self):
        elem = MockElement("IfcWall", "G7", predefined="NOTDEFINED")
        labels = classify_element(elem)
        assert "Wall_NOTDEFINED" not in labels


class TestMakeSpatialNode:
    def test_site_node(self):
        class MockSite:
            GlobalId = "SITE001"
            Name     = "Site A"
            Description = None
            LongName = None
            Elevation = None
            def is_a(self, t=None):
                return "IfcSite" if not t else t == "IfcSite"

        node = make_spatial_node(MockSite(), "Site", BASE_URI)
        assert "Site" in node["labels"]
        assert node["props"]["globalId"] == "SITE001"
        assert node["props"]["name"] == "Site A"
        assert "uri" in node

    def test_storey_with_elevation(self):
        class MockStorey:
            GlobalId = "STR001"
            Name     = "Ground Floor"
            Description = None
            LongName = None
            Elevation = 0.0
            def is_a(self, t=None):
                return "IfcBuildingStorey" if not t else t == "IfcBuildingStorey"

        node = make_spatial_node(MockStorey(), "Storey", BASE_URI)
        assert "Storey" in node["labels"]
        assert node["props"]["elevation"] == 0.0


class TestMakeElementNode:
    def test_wall_node(self):
        elem = MockElement("IfcWall", "W001", name="North Wall")
        node = make_element_node(elem, BASE_URI)
        assert "Wall" in node["labels"]
        assert node["props"]["globalId"] == "W001"
        assert node["props"]["name"] == "North Wall"

    def test_uri_in_node(self):
        elem = MockElement("IfcDoor", "D001")
        node = make_element_node(elem, BASE_URI)
        assert node["uri"] == f"{BASE_URI}ifcdoor_D001"


class TestMakeRelationship:
    def test_basic_relationship(self):
        rel = make_relationship("uri_a", "HAS_BUILDING", "uri_b")
        assert rel["from_uri"] == "uri_a"
        assert rel["rel_type"] == "HAS_BUILDING"
        assert rel["to_uri"]   == "uri_b"
        assert rel["props"]    == {}

    def test_relationship_with_props(self):
        rel = make_relationship("uri_a", "CONTAINS_ELEMENT", "uri_b", {"weight": 1})
        assert rel["props"]["weight"] == 1


class TestGetHostedElements:
    def test_door_in_wall(self):
        door = MockElement("IfcDoor", "DOOR001")

        class MockFillRel:
            RelatedBuildingElement = door

        class MockOpening:
            HasFillings = [MockFillRel()]
            def is_a(self, t=None): return "IfcOpeningElement"

        class MockVoidRel:
            RelatedOpeningElement = MockOpening()

        wall = MockElement("IfcWall", "WALL001", has_openings=[MockVoidRel()])
        results = get_hosted_elements(wall, BASE_URI)
        assert len(results) == 1
        fill, host_uri = results[0]
        assert fill.GlobalId == "DOOR001"
        assert "WALL001" in host_uri

    def test_no_openings(self):
        wall = MockElement("IfcWall", "WALL002")
        assert get_hosted_elements(wall, BASE_URI) == []


class TestGetAggregatedSubElements:
    def test_sub_element_found(self):
        part = MockElement("IfcBuildingElementPart", "PART001")

        class MockDecompRel:
            RelatedObjects = [part]

        wall = MockElement("IfcWall", "WALL003", is_decomposed_by=[MockDecompRel()])
        results = get_aggregated_sub_elements(wall, BASE_URI)
        assert len(results) == 1
        sub, parent_uri = results[0]
        assert sub.GlobalId == "PART001"
        assert "WALL003" in parent_uri

    def test_no_sub_elements(self):
        wall = MockElement("IfcWall", "WALL004")
        assert get_aggregated_sub_elements(wall, BASE_URI) == []
