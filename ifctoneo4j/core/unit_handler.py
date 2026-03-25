"""
unit_handler.py — IfcUnitAssignment → QUDT unit map

Reimplements the unit-reading logic from IFCtoLBD v2.44.0 (UNIT.java, SMLS.java,
IFCtoLBDConverterCore.java:handleUnitsAndPropertySetData()).

The unit map is built once during setup (Phase 1) by walking the IfcProject's
IfcUnitAssignment.  It is then consulted during property extraction to attach
QUDT unit URIs to numeric values (L2/L3) or as parallel "<prop>_unit" properties
(L1 with has_units=True).

QUDT unit URIs (§4.7)
----------------------
  LENGTHUNIT (no prefix)  → http://qudt.org/vocab/unit/M
  LENGTHUNIT + MILLI      → http://qudt.org/vocab/unit/MilliM
  AREAUNIT   (no prefix)  → http://qudt.org/vocab/unit/M2
  AREAUNIT   + MILLI      → http://qudt.org/vocab/unit/MilliM2
  VOLUMEUNIT (no prefix)  → http://qudt.org/vocab/unit/M3
  VOLUMEUNIT + MILLI      → http://qudt.org/vocab/unit/MilliM3
  PLANEANGLEUNIT          → http://qudt.org/vocab/unit/RAD
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

QUDT_BASE = "http://qudt.org/vocab/unit/"

# ---------------------------------------------------------------------------
# Static lookup: (unit_type, prefix) → QUDT unit URI suffix
# ---------------------------------------------------------------------------
_UNIT_TABLE: dict[tuple[str, Optional[str]], str] = {
    ("LENGTHUNIT",     None):    "M",
    ("LENGTHUNIT",     "MILLI"): "MilliM",
    ("LENGTHUNIT",     "CENTI"): "CentiM",
    ("LENGTHUNIT",     "KILO"):  "KiloM",
    ("AREAUNIT",       None):    "M2",
    ("AREAUNIT",       "MILLI"): "MilliM2",
    ("VOLUMEUNIT",     None):    "M3",
    ("VOLUMEUNIT",     "MILLI"): "MilliM3",
    ("PLANEANGLEUNIT", None):    "RAD",
    ("MASSUNIT",       None):    "KiloGM",
    ("MASSUNIT",       "KILO"):  "KiloGM",
    ("MASSUNIT",       "MILLI"): "MilliGM",
    ("THERMODYNAMICTEMPERATUREUNIT", None): "DEG_C",
    ("TIMEUNIT",       None):    "SEC",
    ("FREQUENCYUNIT",  None):    "HZ",
    ("PRESSUREUNIT",   None):    "PA",
    ("FORCEUNIT",      None):    "N",
    ("ENERGYUNIT",     None):    "J",
    ("POWERUNIT",      None):    "W",
    ("ELECTRICCURRENTUNIT", None): "A",
    ("ELECTRICVOLTAGEUNIT", None): "V",
    ("LUMINOUSINTENSITYUNIT", None): "CD",
}


def _qudt_uri(unit_type: str, prefix: Optional[str]) -> Optional[str]:
    """Return the full QUDT URI for a (unit_type, prefix) pair, or None."""
    key = (unit_type.upper(), prefix.upper() if prefix else None)
    suffix = _UNIT_TABLE.get(key)
    if suffix:
        return QUDT_BASE + suffix
    # Try without prefix as fallback
    if prefix:
        suffix = _UNIT_TABLE.get((unit_type.upper(), None))
        if suffix:
            return QUDT_BASE + suffix
    return None


def build_unit_map(ifc_model) -> dict[str, str]:
    """
    Walk IfcProject → IfcUnitAssignment → IfcSIUnit / IfcConversionBasedUnit
    and return a mapping from IFC unit type (e.g. "LENGTHUNIT") to a QUDT URI.

    Parameters
    ----------
    ifc_model : ifcopenshell.file
        Opened IFC model.

    Returns
    -------
    dict[str, str]
        {unit_type_upper: qudt_uri}  e.g. {"LENGTHUNIT": "http://qudt.org/vocab/unit/M"}
    """
    unit_map: dict[str, str] = {}

    try:
        projects = ifc_model.by_type("IfcProject")
        if not projects:
            logger.warning("No IfcProject found — unit map will be empty.")
            return unit_map

        project = projects[0]
        units_in_context = getattr(project, "UnitsInContext", None)
        if units_in_context is None:
            logger.debug("IfcProject has no UnitsInContext.")
            return unit_map

        units = getattr(units_in_context, "Units", []) or []
        for unit in units:
            entity_type = unit.is_a()

            if entity_type == "IfcSIUnit":
                unit_type = getattr(unit, "UnitType", None)
                prefix    = getattr(unit, "Prefix",   None)

                if not unit_type:
                    continue

                qudt = _qudt_uri(unit_type, prefix)
                if qudt:
                    unit_map[unit_type.upper()] = qudt
                    logger.debug("Unit: %s (prefix=%s) → %s", unit_type, prefix, qudt)
                else:
                    logger.debug(
                        "No QUDT mapping for IfcSIUnit %s (prefix=%s)", unit_type, prefix
                    )

            elif entity_type in ("IfcConversionBasedUnit", "IfcConversionBasedUnitWithOffset"):
                # e.g. inches, feet — we record the unit type but note it's
                # non-SI.  Store the name as the URI so downstream code can
                # still display something meaningful.
                unit_type = getattr(unit, "UnitType", None)
                name      = getattr(unit, "Name",     None)
                if unit_type and name:
                    unit_map[unit_type.upper()] = f"urn:ifc:unit:{name.lower()}"
                    logger.debug("Conversion unit: %s → urn:ifc:unit:%s", unit_type, name)

            elif entity_type == "IfcDerivedUnit":
                # Derived units (e.g. m/s²) — not mapped to QUDT in the
                # reference implementation; skip.
                pass

    except Exception as exc:
        logger.warning("Error reading unit assignment: %s", exc)

    return unit_map


def get_unit_for_property(
    unit_map: dict[str, str],
    ifc_unit=None,
    unit_type_hint: Optional[str] = None,
) -> Optional[str]:
    """
    Return the QUDT URI for a property, consulting:
    1. An explicit IfcUnit attached to the property (overrides project default).
    2. The project unit_map using `unit_type_hint` (e.g. "LENGTHUNIT").

    Parameters
    ----------
    unit_map : dict[str, str]
        The project-level unit map from build_unit_map().
    ifc_unit : ifcopenshell entity | None
        The explicit unit attached to an IfcPropertySingleValue or quantity.
    unit_type_hint : str | None
        Fallback key into unit_map (e.g. "LENGTHUNIT" for IfcQuantityLength).
    """
    # Explicit per-property unit takes precedence
    if ifc_unit is not None:
        entity_type = ifc_unit.is_a()
        if entity_type == "IfcSIUnit":
            unit_type = getattr(ifc_unit, "UnitType", None)
            prefix    = getattr(ifc_unit, "Prefix",   None)
            if unit_type:
                qudt = _qudt_uri(unit_type, prefix)
                if qudt:
                    return qudt
        elif entity_type in ("IfcConversionBasedUnit", "IfcConversionBasedUnitWithOffset"):
            name = getattr(ifc_unit, "Name", None)
            if name:
                return f"urn:ifc:unit:{name.lower()}"

    # Fall back to project default
    if unit_type_hint:
        return unit_map.get(unit_type_hint.upper())

    return None
