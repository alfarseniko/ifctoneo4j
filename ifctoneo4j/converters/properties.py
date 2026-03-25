"""
properties.py — Property set and attribute extraction

Reimplements IFCtoLBD v2.44.0 property handling (PropertySet.java,
AttributeSet.java, §4) using direct ifcopenshell attribute access.

Three levels (§4.1–4.4):
  L1 — flat key/value literals stored directly as Neo4j node properties
  L2 — separate Property nodes linked by PSET_PROPERTY relationships (OPM)
  L3 — L2 + versioned State nodes with timestamp (OPM with provenance)

This module returns plain Python dicts / lists of graph operations so it
remains independent of any particular Neo4j driver version.

For L1 (the default) every property is returned in a flat dict of the form:
  {"isExternal_property_simple": True, "fireRating_property_simple": "30 min"}

For L2/L3 additional node/relationship dicts are returned as part of a
PropertyGraph structure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from ..core.string_ops import to_camel_case
from ..core.unit_handler import get_unit_for_property

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures for L2 / L3 output
# ---------------------------------------------------------------------------

@dataclass
class PropertyNode:
    """Represents an opm:Property node (L2/L3)."""
    uri: str
    prop_name: str          # camelCase name
    value: Any
    unit_uri: Optional[str] = None
    # L3 only
    state_uri: Optional[str] = None
    generated_at: Optional[str] = None  # xsd:dateTime string


@dataclass
class PropertyGraph:
    """
    All graph data produced from one element's property sets.

    For L1: only `flat_props` is populated.
    For L2/L3: `property_nodes` and `property_rels` are also populated.
    """
    flat_props: dict[str, Any] = field(default_factory=dict)
    property_nodes: list[PropertyNode] = field(default_factory=list)
    # (element_uri, rel_type, prop_node_uri)
    property_rels: list[tuple[str, str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Value extraction from IfcPropertySingleValue.NominalValue
# ---------------------------------------------------------------------------

def _extract_value(nominal_value) -> Optional[Any]:
    """
    Unwrap an IfcValue (IfcLabel, IfcBoolean, IfcReal, IfcInteger, etc.)
    and return a plain Python type.

    In ifcopenshell the NominalValue of an IfcPropertySingleValue is an
    entity whose .wrappedValue attribute holds the actual value.
    For older API versions the value may be accessed directly.
    """
    if nominal_value is None:
        return None

    # Modern ifcopenshell: entity with .wrappedValue
    if hasattr(nominal_value, "wrappedValue"):
        val = nominal_value.wrappedValue
    else:
        # Fallback for older API or simple Python scalars
        val = nominal_value

    # Booleans first (bool is subclass of int in Python)
    if isinstance(val, bool):
        return val
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return val
    if isinstance(val, str):
        # Handle IfcLogical strings
        upper = val.upper()
        if upper in ("TRUE", ".TRUE."):
            return True
        if upper in ("FALSE", ".FALSE."):
            return False
        return val
    # Enum types from ifcopenshell are usually strings
    return str(val) if val is not None else None


def _extract_quantity_value(qty) -> Optional[Any]:
    """Extract the numeric value from an IfcQuantityXxx entity."""
    # IfcQuantityLength  → LengthValue
    # IfcQuantityArea    → AreaValue
    # IfcQuantityVolume  → VolumeValue
    # IfcQuantityCount   → CountValue
    # IfcQuantityWeight  → WeightValue
    # IfcQuantityTime    → TimeValue
    for attr in ("LengthValue", "AreaValue", "VolumeValue", "CountValue",
                 "WeightValue", "TimeValue", "Value"):
        val = getattr(qty, attr, None)
        if val is not None:
            return val
    return None


def _quantity_unit_type(qty) -> Optional[str]:
    """Infer the QUDT unit type hint from a quantity class name."""
    name = qty.is_a().upper()
    if "LENGTH" in name:
        return "LENGTHUNIT"
    if "AREA" in name:
        return "AREAUNIT"
    if "VOLUME" in name:
        return "VOLUMEUNIT"
    if "COUNT" in name:
        return None
    if "WEIGHT" in name:
        return "MASSUNIT"
    return None


# ---------------------------------------------------------------------------
# Core property iteration helpers
# ---------------------------------------------------------------------------

def _iter_property_set(pset) -> list[tuple[str, Any, Any]]:
    """
    Yield (prop_name, value, explicit_unit) tuples from an IfcPropertySet.
    Only processes IfcPropertySingleValue (the most common type).
    Other types (IfcPropertyEnumeratedValue, IfcPropertyListValue, …) are
    skipped with a debug log.
    """
    results = []
    has_properties = getattr(pset, "HasProperties", None)
    if not has_properties:
        return results

    for prop in has_properties:
        if not prop.is_a("IfcPropertySingleValue"):
            logger.debug(
                "Skipping %s (not IfcPropertySingleValue)", prop.is_a()
            )
            continue

        name = getattr(prop, "Name", None)
        if not name:
            continue

        nominal = getattr(prop, "NominalValue", None)
        value   = _extract_value(nominal)
        unit    = getattr(prop, "Unit", None)

        results.append((name, value, unit))

    return results


def _iter_quantity_set(qty_set) -> list[tuple[str, Any, Any, Optional[str]]]:
    """
    Yield (qty_name, value, explicit_unit, unit_type_hint) tuples from
    an IfcElementQuantity.
    """
    results = []
    quantities = getattr(qty_set, "Quantities", None)
    if not quantities:
        return results

    for qty in quantities:
        name  = getattr(qty, "Name", None)
        if not name:
            continue
        value = _extract_quantity_value(qty)
        if value is None:
            continue
        unit  = getattr(qty, "Unit", None)
        hint  = _quantity_unit_type(qty)
        results.append((name, value, unit, hint))

    return results


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_properties(
    element,
    element_uri: str,
    unit_map: dict[str, str],
    level: int = 1,
    has_units: bool = False,
    base_uri: str = "https://linkedbuildingdata.org/building#",
    timestamp: Optional[str] = None,
) -> PropertyGraph:
    """
    Extract all property set data and direct IFC attributes from `element`.

    Walks:
      1. element.IsDefinedBy  → IfcPropertySet / IfcElementQuantity
      2. element.IsTypedBy    → type object's HasPropertySets
      3. Direct attributes    → GlobalId, Name, ObjectType, Tag, etc.

    Parameters
    ----------
    element : ifcopenshell entity
    element_uri : str
        The URI / Neo4j node ID for this element.
    unit_map : dict[str, str]
        Project-level unit map from build_unit_map().
    level : int
        1, 2, or 3.
    has_units : bool
        Whether to attach unit URIs to properties.
    base_uri : str
        Base URI for constructing property node URIs.
    timestamp : str | None
        ISO-8601 datetime string for L3 state nodes.  Defaults to now.

    Returns
    -------
    PropertyGraph
    """
    graph = PropertyGraph()

    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    # ------------------------------------------------------------------
    # Collect (name, value, unit, unit_hint) from all psets
    # ------------------------------------------------------------------
    raw_props: list[tuple[str, Any, Any, Optional[str]]] = []

    # 1. IsDefinedBy
    is_defined_by = getattr(element, "IsDefinedBy", None) or []
    for rel in is_defined_by:
        rel_def = getattr(rel, "RelatingPropertyDefinition", None)
        if rel_def is None:
            continue

        if rel_def.is_a("IfcPropertySet"):
            for name, value, unit in _iter_property_set(rel_def):
                raw_props.append((name, value, unit, None))

        elif rel_def.is_a("IfcElementQuantity"):
            for name, value, unit, hint in _iter_quantity_set(rel_def):
                raw_props.append((name, value, unit, hint))

    # 2. Type object property sets (IsTypedBy)
    is_typed_by = getattr(element, "IsTypedBy", None) or []
    for rel in is_typed_by:
        type_obj = getattr(rel, "RelatingType", None)
        if type_obj is None:
            continue
        type_psets = getattr(type_obj, "HasPropertySets", None) or []
        for pset in type_psets:
            if pset.is_a("IfcPropertySet"):
                for name, value, unit in _iter_property_set(pset):
                    raw_props.append((name, value, unit, None))
            elif pset.is_a("IfcElementQuantity"):
                for name, value, unit, hint in _iter_quantity_set(pset):
                    raw_props.append((name, value, unit, hint))

    # ------------------------------------------------------------------
    # Build output by level
    # ------------------------------------------------------------------
    for i, (name, value, unit_entity, unit_hint) in enumerate(raw_props):
        if value is None:
            continue

        camel = to_camel_case(name)
        if not camel:
            continue

        # Resolve unit URI
        unit_uri: Optional[str] = None
        if has_units:
            unit_uri = get_unit_for_property(unit_map, unit_entity, unit_hint)

        if level == 1:
            key = f"{camel}_property_simple"
            graph.flat_props[key] = value
            if has_units and unit_uri:
                graph.flat_props[f"{key}_unit"] = unit_uri

        else:  # L2 or L3
            prop_guid = getattr(element, "GlobalId", str(i))
            prop_uri  = f"{base_uri}{camel}_{prop_guid}"
            state_uri = None
            gen_at    = None

            if level == 3:
                state_uri = f"{base_uri}state_{camel}_{prop_guid}_p{i}"
                gen_at    = timestamp

            pnode = PropertyNode(
                uri=prop_uri,
                prop_name=camel,
                value=value,
                unit_uri=unit_uri if has_units else None,
                state_uri=state_uri,
                generated_at=gen_at,
            )
            graph.property_nodes.append(pnode)
            rel_type = f"HAS_PROPERTY_{camel.upper()}"
            graph.property_rels.append((element_uri, rel_type, prop_uri))

    # ------------------------------------------------------------------
    # 3. Direct IFC attributes (§4.2)
    # ------------------------------------------------------------------
    _extract_attributes(element, graph, level, unit_map, has_units, base_uri, timestamp)

    return graph


# ---------------------------------------------------------------------------
# Attribute extraction
# ---------------------------------------------------------------------------

# Attributes we want to capture from every element
_CORE_ATTRIBUTES = (
    "GlobalId",
    "Name",
    "Description",
    "ObjectType",
    "Tag",
    "PredefinedType",
    "LongName",
    "Elevation",        # IfcBuildingStorey
    "RefLatitude",      # IfcSite
    "RefLongitude",     # IfcSite
    "RefElevation",     # IfcSite
)


def _safe_str(val: Any) -> Optional[str]:
    """Convert a value to string, returning None for empty results."""
    if val is None:
        return None
    s = str(val)
    return s if s else None


def _extract_attributes(
    element,
    graph: PropertyGraph,
    level: int,
    unit_map: dict[str, str],
    has_units: bool,
    base_uri: str,
    timestamp: str,
) -> None:
    """
    Read a fixed set of direct IFC attributes from element and add them
    to the PropertyGraph.

    Special rules (§4.2):
    - Name           → stored as "name" key (rdfs:label equivalent)
    - GlobalId       → stored as "globalId" (also "ifc_guid")
    - Tag attributes → renamed to "batid"
    - All others     → "<camelCase>_attribute_simple"
    """
    for attr in _CORE_ATTRIBUTES:
        val = getattr(element, attr, None)
        if val is None:
            continue

        # Skip empty strings and NOTDEFINED enums
        if isinstance(val, str) and val.upper() in ("", "NOTDEFINED", "$"):
            continue

        # Determine the key name
        attr_lower = attr.lower()
        if attr_lower == "name":
            key = "name"
        elif attr_lower == "globalid":
            key = "globalId"
            # Always store as flat prop regardless of level
            graph.flat_props["globalId"] = str(val)
            continue
        elif attr_lower == "tag":
            key = "batid"
        elif attr_lower == "description":
            key = "description"
        elif attr_lower == "objecttype":
            key = "objectType_attribute_simple"
        elif attr_lower == "predefinedtype":
            key = "predefinedType_attribute_simple"
        elif attr_lower == "longname":
            key = "longName_attribute_simple"
        elif attr_lower == "elevation":
            key = "elevation_attribute_simple"
        elif attr_lower in ("reflatitude", "reflongitude", "relelevation", "refelevation"):
            # These are handled by geolocation — skip in attribute extraction
            continue
        else:
            camel = to_camel_case(attr)
            key   = f"{camel}_attribute_simple"

        # Convert value
        if isinstance(val, (list, tuple)):
            str_val = str(val)
        else:
            str_val = str(val) if not isinstance(val, (bool, int, float)) else val

        if level == 1:
            graph.flat_props[key] = str_val
        else:
            # L2/L3: treat attributes as OPM property nodes too
            prop_guid = getattr(element, "GlobalId", attr)
            prop_uri  = f"{base_uri}{key}_{prop_guid}"
            state_uri = None
            gen_at    = None

            if level == 3:
                state_uri = f"{base_uri}state_{key}_{prop_guid}_a{hash(attr) & 0xFFFF}"
                gen_at    = timestamp

            pnode = PropertyNode(
                uri=prop_uri,
                prop_name=key,
                value=str_val,
                state_uri=state_uri,
                generated_at=gen_at,
            )
            graph.property_nodes.append(pnode)
            graph.property_rels.append((element_uri_for(element, base_uri), "HAS_ATTRIBUTE", prop_uri))


def element_uri_for(element, base_uri: str) -> str:
    """Build the standard URI for an element (used internally)."""
    guid = getattr(element, "GlobalId", None)
    if guid:
        return f"{base_uri}{element.is_a().lower()}_{guid}"
    return f"{base_uri}{element.is_a().lower()}_{id(element)}"
