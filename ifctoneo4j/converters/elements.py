"""
elements.py — Element classification and sub-element / hosted-element detection

Handles:
  • Determining the Neo4j labels for an IFC element (bot:Element + BEO/MEP/FURN)
  • Building the element's URI (standard GUID-based or hierarchical)
  • Detecting hosted elements  (IfcRelVoidsElement → IfcRelFillsElement)
  • Detecting aggregated sub-elements (IfcRelAggregates / IfcRelDecomposes)
  • Orphaned element scan (elements outside the spatial hierarchy)

All output is expressed as plain Python dicts that the Neo4j writer consumes.

Node dict schema
----------------
{
  "uri":       str,          # unique identifier (used as MERGE key)
  "globalId":  str,
  "labels":    list[str],    # Neo4j labels, e.g. ["Element", "Wall", "Wall_SOLIDWALL"]
  "props":     dict,         # flat properties (L1) or attribute subset
}

Relationship dict schema
------------------------
{
  "from_uri":  str,
  "rel_type":  str,          # e.g. "CONTAINS_ELEMENT", "HAS_SUB_ELEMENT"
  "to_uri":    str,
  "props":     dict,         # optional relationship properties (usually empty)
}
"""

from __future__ import annotations

import logging
from typing import Optional

from ..product_map import get_labels
from ..core.string_ops import url_encode_name

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URI construction (§5)
# ---------------------------------------------------------------------------

def build_element_uri(
    element,
    base_uri: str,
    hierarchical: bool = False,
    parent_uri: Optional[str] = None,
) -> str:
    """
    Construct the URI / unique key for an IFC element node.

    Standard mode (§5.1):
        <base><type_lowercase>_<GlobalId>

    Hierarchical mode (§5.2):
        <parent_uri>/<url_encoded_name>  or  <parent_uri>/<type_lc>_<GlobalId>
        <base><url_encoded_name>          for top-level nodes

    Parameters
    ----------
    element : ifcopenshell entity
    base_uri : str
        Must end with '#' or '/'.
    hierarchical : bool
        Use name-based hierarchical URIs.
    parent_uri : str | None
        Parent node URI (required for hierarchical child URIs).
    """
    guid       = getattr(element, "GlobalId", None)
    ifc_class  = element.is_a().lower()
    name       = getattr(element, "Name", None)

    if hierarchical:
        if name:
            encoded = url_encode_name(name)
            if parent_uri:
                return f"{parent_uri}/{encoded}"
            else:
                return f"{base_uri}{encoded}"
        # Fallback to GUID-based
        if parent_uri and guid:
            return f"{parent_uri}/{ifc_class}_{guid}"
        if guid:
            return f"{base_uri}{ifc_class}_{guid}"
        return f"{base_uri}{ifc_class}_{id(element)}"

    # Standard: flat GUID-based
    if guid:
        return f"{base_uri}{ifc_class}_{guid}"
    return f"{base_uri}{ifc_class}_{id(element)}"


# ---------------------------------------------------------------------------
# Element classification
# ---------------------------------------------------------------------------

def classify_element(element) -> list[str]:
    """
    Return the Neo4j label list for an IFC element.

    Walks the is_a() hierarchy from the most specific class upward until
    a match is found in the product map.  Always includes "Element".

    Examples
    --------
    IfcWall (PredefinedType=SOLIDWALL) → ["Element", "Wall", "Wall_SOLIDWALL"]
    IfcFan  (PredefinedType=AXIAL)     → ["Element", "Fan",  "Fan_AXIAL"]
    IfcProxy (unknown)                 → ["Element"]
    """
    predefined = getattr(element, "PredefinedType", None)
    if isinstance(predefined, str) and predefined.upper() in ("NOTDEFINED", "USERDEFINED", "NULL", "$"):
        predefined = None

    # Try the exact class first, then walk up via is_a() inheritance
    # ifcopenshell provides is_a(parent_class) for checking inheritance,
    # and the entity's direct class via is_a()
    ifc_class = element.is_a()
    labels = get_labels(ifc_class, predefined)

    if len(labels) > 1:
        return labels

    # No match found for the exact class — try the parent classes
    # Build a list of candidate class names by checking common ancestors
    for parent_class in _IFC_ELEMENT_HIERARCHY:
        if element.is_a(parent_class):
            candidate_labels = get_labels(parent_class, predefined)
            if len(candidate_labels) > 1:
                return candidate_labels

    return labels  # ["Element"]


# IFC inheritance hierarchy to check when exact class lookup fails.
# Ordered from most specific to most general.
_IFC_ELEMENT_HIERARCHY = [
    # BEO
    "IfcBeam", "IfcColumn", "IfcWall", "IfcSlab", "IfcDoor", "IfcWindow",
    "IfcStair", "IfcRamp", "IfcRoof", "IfcCovering", "IfcRailing",
    "IfcMember", "IfcPlate", "IfcPile", "IfcFooting", "IfcCurtainWall",
    "IfcChimney", "IfcShadingDevice", "IfcStairFlight", "IfcRampFlight",
    "IfcBuildingElementPart", "IfcReinforcingBar", "IfcReinforcingMesh",
    "IfcReinforcingElement", "IfcTendon", "IfcTendonAnchor",
    "IfcFastener", "IfcMechanicalFastener", "IfcDiscreteAccessory",
    "IfcElementComponent", "IfcVibrationIsolator", "IfcTransportElement",
    "IfcWallElementedCase", "IfcBuildingElement",
    # Furnishing
    "IfcFurniture", "IfcFurnishingElement", "IfcSystemFurnitureElement",
    # MEP — specific
    "IfcActuator", "IfcAlarm", "IfcBoiler", "IfcBurner", "IfcChiller",
    "IfcCoil", "IfcCompressor", "IfcCondenser", "IfcController",
    "IfcCooledBeam", "IfcCoolingTower", "IfcDamper", "IfcEngine",
    "IfcEvaporativeCooler", "IfcEvaporator", "IfcFan", "IfcFilter",
    "IfcFlowInstrument", "IfcFlowMeter", "IfcHeatExchanger",
    "IfcHumidifier", "IfcInterceptor", "IfcJunctionBox", "IfcLamp",
    "IfcLightFixture", "IfcMedicalDevice", "IfcMotorConnection",
    "IfcOutlet", "IfcPump", "IfcSensor", "IfcSolarDevice",
    "IfcSpaceHeater", "IfcSwitchingDevice", "IfcTank", "IfcTransformer",
    "IfcValve", "IfcWasteTerminal",
    "IfcAirTerminal", "IfcAirTerminalBox", "IfcAirToAirHeatRecovery",
    "IfcAudioVisualAppliance", "IfcCableCarrierFitting",
    "IfcCableCarrierSegment", "IfcCableFitting", "IfcCableSegment",
    "IfcCommunicationsAppliance", "IfcDistributionChamberElement",
    "IfcDuctFitting", "IfcDuctSegment", "IfcDuctSilencer",
    "IfcElectricAppliance", "IfcElectricDistributionBoard",
    "IfcElectricFlowStorageDevice", "IfcElectricGenerator",
    "IfcElectricMotor", "IfcElectricTimeControl",
    "IfcFireSuppressionTerminal", "IfcPipeFitting", "IfcPipeSegment",
    "IfcProtectiveDevice", "IfcProtectiveDeviceTrippingUnit",
    "IfcSanitaryTerminal", "IfcStackTerminal",
    "IfcTubeBundle", "IfcUnitaryControlElement", "IfcUnitaryEquipment",
    # MEP — abstract parents
    "IfcEnergyConversionDevice", "IfcFlowController", "IfcFlowFitting",
    "IfcFlowMovingDevice", "IfcFlowSegment", "IfcFlowStorageDevice",
    "IfcFlowTerminal", "IfcFlowTreatmentDevice",
    "IfcDistributionControlElement", "IfcDistributionFlowElement",
    "IfcDistributionElement",
]


# ---------------------------------------------------------------------------
# Node dict builders
# ---------------------------------------------------------------------------

def make_spatial_node(
    element,
    ifc_type: str,
    base_uri: str,
    hierarchical: bool = False,
    parent_uri: Optional[str] = None,
) -> dict:
    """
    Build a node dict for a spatial structure element
    (IfcSite, IfcBuilding, IfcBuildingStorey, IfcSpace).

    Parameters
    ----------
    ifc_type : str
        e.g. "Site", "Building", "Storey", "Space"
    """
    uri = build_element_uri(element, base_uri, hierarchical, parent_uri)
    guid = getattr(element, "GlobalId", None) or ""
    name = getattr(element, "Name", None) or ""
    description = getattr(element, "Description", None) or ""
    long_name = getattr(element, "LongName", None) or ""
    elevation = getattr(element, "Elevation", None)  # IfcBuildingStorey

    props: dict = {
        "globalId": guid,
        "ifcType":  element.is_a(),
    }
    if name:
        props["name"] = name
    if description:
        props["description"] = description
    if long_name:
        props["longName"] = long_name
    if elevation is not None:
        props["elevation"] = float(elevation)

    return {
        "uri":    uri,
        "labels": [ifc_type],
        "props":  props,
    }


def make_element_node(
    element,
    base_uri: str,
    hierarchical: bool = False,
    parent_uri: Optional[str] = None,
) -> dict:
    """
    Build a node dict for a building element.
    Labels are determined by classify_element().
    """
    uri    = build_element_uri(element, base_uri, hierarchical, parent_uri)
    guid   = getattr(element, "GlobalId", None) or ""
    labels = classify_element(element)

    props: dict = {
        "globalId": guid,
        "ifcType":  element.is_a(),
    }
    name = getattr(element, "Name", None)
    if name:
        props["name"] = name

    return {
        "uri":    uri,
        "labels": labels,
        "props":  props,
    }


def make_relationship(from_uri: str, rel_type: str, to_uri: str, props: Optional[dict] = None) -> dict:
    """Build a relationship dict."""
    return {
        "from_uri": from_uri,
        "rel_type": rel_type,
        "to_uri":   to_uri,
        "props":    props or {},
    }


# ---------------------------------------------------------------------------
# Hosted element detection (§3.4)
# ---------------------------------------------------------------------------

def get_hosted_elements(element, base_uri: str, hierarchical: bool = False) -> list[tuple]:
    """
    Follow IfcRelVoidsElement → IfcOpeningElement → IfcRelFillsElement path
    and return (fill_element, host_uri) pairs.

    Returns
    -------
    list of (fill_entity, host_uri)
    """
    results = []
    host_uri = build_element_uri(element, base_uri, hierarchical)

    has_openings = getattr(element, "HasOpenings", None) or []
    for void_rel in has_openings:
        opening = getattr(void_rel, "RelatedOpeningElement", None)
        if opening is None:
            continue

        has_fillings = getattr(opening, "HasFillings", None) or []
        for fill_rel in has_fillings:
            fill = getattr(fill_rel, "RelatedBuildingElement", None)
            if fill is not None:
                results.append((fill, host_uri))

    return results


# ---------------------------------------------------------------------------
# Aggregated sub-element detection (§3.5)
# ---------------------------------------------------------------------------

def get_aggregated_sub_elements(element, base_uri: str, hierarchical: bool = False) -> list[tuple]:
    """
    Follow IfcRelAggregates / IfcRelDecomposes from element down to its
    sub-elements (e.g. IfcBuildingElementPart decompositions).

    Returns
    -------
    list of (sub_entity, parent_uri)
    """
    results = []
    parent_uri = build_element_uri(element, base_uri, hierarchical)

    is_decomposed_by = getattr(element, "IsDecomposedBy", None) or []
    for rel in is_decomposed_by:
        related = getattr(rel, "RelatedObjects", None) or []
        for sub in related:
            # Only include IfcElement subclasses (not spatial structure)
            if sub.is_a("IfcElement"):
                results.append((sub, parent_uri))

    return results


# ---------------------------------------------------------------------------
# Orphaned element detection (§6.8)
# ---------------------------------------------------------------------------

def find_orphaned_elements(ifc_model, seen_guids: set[str]) -> list:
    """
    Return all IfcElement instances whose GlobalId is NOT in seen_guids.

    These are elements that exist in the IFC file but were not reachable
    through the spatial hierarchy traversal.

    Parameters
    ----------
    ifc_model : ifcopenshell.file
    seen_guids : set[str]
        GlobalIds of all elements already processed.
    """
    orphans = []
    try:
        for element in ifc_model.by_type("IfcElement"):
            guid = getattr(element, "GlobalId", None)
            if guid and guid not in seen_guids:
                orphans.append(element)
    except Exception as exc:
        logger.warning("Error scanning for orphaned elements: %s", exc)
    return orphans
