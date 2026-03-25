"""
Tests for product_map.py — IFC class → LBD label mapping.

Verifies all major BEO, MEP, and FURN mappings and predefined-type resolution.
"""

import pytest
from ..product_map import get_labels, get_namespace, PRODUCT_MAP


class TestGetLabels:
    # ── Always returns Element ──────────────────────────────────────────────
    def test_unknown_class_returns_element_only(self):
        labels = get_labels("IfcProxy")
        assert labels == ["Element"]

    def test_element_always_first(self):
        labels = get_labels("IfcWall")
        assert labels[0] == "Element"

    # ── BEO base classes ─────────────────────────────────────────────────────
    def test_ifc_wall(self):
        labels = get_labels("IfcWall")
        assert "Wall" in labels

    def test_ifc_door(self):
        assert "Door" in get_labels("IfcDoor")

    def test_ifc_window(self):
        assert "Window" in get_labels("IfcWindow")

    def test_ifc_slab(self):
        assert "Slab" in get_labels("IfcSlab")

    def test_ifc_beam(self):
        assert "Beam" in get_labels("IfcBeam")

    def test_ifc_column(self):
        assert "Column" in get_labels("IfcColumn")

    def test_ifc_roof(self):
        assert "Roof" in get_labels("IfcRoof")

    def test_ifc_stair(self):
        assert "Stair" in get_labels("IfcStair")

    def test_ifc_railing(self):
        assert "Railing" in get_labels("IfcRailing")

    # ── BEO predefined types ─────────────────────────────────────────────────
    def test_wall_solidwall(self):
        labels = get_labels("IfcWall", "SOLIDWALL")
        assert "Wall" in labels
        assert "Wall_SOLIDWALL" in labels

    def test_wall_no_predefined(self):
        labels = get_labels("IfcWall", None)
        assert "Wall" in labels
        assert not any("_" in l and "SOLIDWALL" in l for l in labels)

    def test_wall_notdefined_ignored(self):
        labels = get_labels("IfcWall", "NOTDEFINED")
        assert "Wall_NOTDEFINED" not in labels

    def test_door_gate(self):
        labels = get_labels("IfcDoor", "GATE")
        assert "Door_GATE" in labels

    def test_slab_floor(self):
        labels = get_labels("IfcSlab", "FLOOR")
        assert "Slab_FLOOR" in labels

    def test_slab_roof(self):
        labels = get_labels("IfcSlab", "ROOF")
        assert "Slab_ROOF" in labels

    def test_beam_lintel(self):
        labels = get_labels("IfcBeam", "LINTEL")
        assert "Beam_LINTEL" in labels

    def test_column_pilaster(self):
        labels = get_labels("IfcColumn", "PILASTER")
        assert "Column_PILASTER" in labels

    def test_roof_gable(self):
        labels = get_labels("IfcRoof", "GABLE_ROOF")
        assert "Roof_GABLE_ROOF" in labels

    def test_covering_ceiling(self):
        labels = get_labels("IfcCovering", "CEILING")
        assert "Covering_CEILING" in labels

    def test_covering_flooring(self):
        labels = get_labels("IfcCovering", "FLOORING")
        assert "Covering_FLOORING" in labels

    # ── Furniture ────────────────────────────────────────────────────────────
    def test_furnishing_element(self):
        assert "Furniture" in get_labels("IfcFurnishingElement")

    def test_furniture_chair(self):
        labels = get_labels("IfcFurnishingElement", "CHAIR")
        assert "Chair" in labels

    def test_furniture_bed(self):
        labels = get_labels("IfcFurnishingElement", "BED")
        assert "Bed" in labels

    def test_furniture_table(self):
        labels = get_labels("IfcFurnishingElement", "TABLE")
        assert "Table" in labels

    # ── MEP ──────────────────────────────────────────────────────────────────
    def test_ifc_fan(self):
        assert "Fan" in get_labels("IfcFan")

    def test_ifc_fan_axial(self):
        labels = get_labels("IfcFan", "AXIAL")
        assert "Fan_AXIAL" in labels

    def test_ifc_pump(self):
        assert "Pump" in get_labels("IfcPump")

    def test_ifc_pump_circulator(self):
        labels = get_labels("IfcPump", "CIRCULATOR")
        assert "Pump_CIRCULATOR" in labels

    def test_ifc_sensor(self):
        assert "Sensor" in get_labels("IfcSensor")

    def test_ifc_sensor_temperature(self):
        labels = get_labels("IfcSensor", "TEMPERATURESENSOR")
        assert "Sensor_TEMPERATURESENSOR" in labels

    def test_ifc_valve(self):
        assert "Valve" in get_labels("IfcValve")

    def test_ifc_valve_isolating(self):
        labels = get_labels("IfcValve", "ISOLATING")
        assert "Valve_ISOLATING" in labels

    def test_ifc_boiler(self):
        assert "Boiler" in get_labels("IfcBoiler")

    def test_ifc_pipe_segment(self):
        assert "PipeSegment" in get_labels("IfcPipeSegment")

    def test_ifc_duct_segment(self):
        assert "DuctSegment" in get_labels("IfcDuctSegment")

    def test_ifc_light_fixture(self):
        assert "LightFixture" in get_labels("IfcLightFixture")

    def test_ifc_sanitary_terminal(self):
        assert "SanitaryTerminal" in get_labels("IfcSanitaryTerminal")

    def test_ifc_sanitary_toilet(self):
        labels = get_labels("IfcSanitaryTerminal", "TOILETPAN")
        assert "SanitaryTerminal_TOILETPAN" in labels

    # ── Case insensitivity of predefined types ─────────────────────────────
    def test_predefined_type_lowercase(self):
        # get_labels should normalise to uppercase
        labels = get_labels("IfcWall", "solidwall")
        assert "Wall_SOLIDWALL" in labels

    def test_predefined_type_mixed_case(self):
        labels = get_labels("IfcSlab", "Floor")
        assert "Slab_FLOOR" in labels


class TestGetNamespace:
    def test_wall_is_beo(self):
        assert get_namespace("IfcWall") == "beo"

    def test_fan_is_mep(self):
        assert get_namespace("IfcFan") == "mep"

    def test_furniture_is_furn(self):
        assert get_namespace("IfcFurnishingElement") == "furn"

    def test_unknown_is_none(self):
        assert get_namespace("IfcProxy") is None


class TestProductMapCompleteness:
    """Verify critical entries are present in the PRODUCT_MAP."""

    BEO_REQUIRED = [
        "IfcBeam", "IfcBuildingElementPart", "IfcChimney", "IfcColumn",
        "IfcCovering", "IfcCurtainWall", "IfcDiscreteAccessory", "IfcDoor",
        "IfcElementComponent", "IfcFastener", "IfcFooting",
        "IfcMechanicalFastener", "IfcMember", "IfcPile", "IfcPlate",
        "IfcRailing", "IfcRamp", "IfcRampFlight", "IfcReinforcingBar",
        "IfcReinforcingElement", "IfcReinforcingMesh", "IfcRoof",
        "IfcShadingDevice", "IfcSlab", "IfcStair", "IfcStairFlight",
        "IfcTendon", "IfcTendonAnchor", "IfcTransportElement",
        "IfcVibrationIsolator", "IfcWall", "IfcWallElementedCase", "IfcWindow",
    ]

    MEP_REQUIRED = [
        "IfcActuator", "IfcAirTerminal", "IfcAirTerminalBox",
        "IfcAirToAirHeatRecovery", "IfcAlarm", "IfcBoiler", "IfcBurner",
        "IfcChiller", "IfcCoil", "IfcCompressor", "IfcCondenser",
        "IfcController", "IfcCooledBeam", "IfcCoolingTower", "IfcDamper",
        "IfcDuctFitting", "IfcDuctSegment", "IfcDuctSilencer",
        "IfcElectricAppliance", "IfcElectricGenerator", "IfcElectricMotor",
        "IfcEngine", "IfcFan", "IfcFilter", "IfcHeatExchanger",
        "IfcHumidifier", "IfcInterceptor", "IfcJunctionBox", "IfcLamp",
        "IfcLightFixture", "IfcMedicalDevice", "IfcOutlet",
        "IfcPipeFitting", "IfcPipeSegment", "IfcProtectiveDevice",
        "IfcPump", "IfcSanitaryTerminal", "IfcSensor", "IfcSolarDevice",
        "IfcSpaceHeater", "IfcStackTerminal", "IfcSwitchingDevice",
        "IfcTank", "IfcTransformer", "IfcValve", "IfcWasteTerminal",
    ]

    def test_all_beo_classes_present(self):
        missing = [c for c in self.BEO_REQUIRED if c not in PRODUCT_MAP]
        assert not missing, f"Missing BEO classes: {missing}"

    def test_all_mep_classes_present(self):
        missing = [c for c in self.MEP_REQUIRED if c not in PRODUCT_MAP]
        assert not missing, f"Missing MEP classes: {missing}"
