"""
schema.py — Neo4j constraint and index creation

Run once before the first write to ensure:
  • Uniqueness constraint on :Site(uri), :Building(uri), etc.
  • Full-text or range index on globalId for fast lookups
  • Composite index on label+globalId for query performance

All DDL is idempotent (CREATE … IF NOT EXISTS).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neo4j import Driver

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Label definitions
# ---------------------------------------------------------------------------
SPATIAL_LABELS = ("Site", "Building", "Storey", "Space")

ELEMENT_LABELS = (
    "Element",
    # BEO
    "BuildingElement", "Beam", "BuildingElementPart", "Chimney", "Column",
    "Covering", "CurtainWall", "DiscreteAccessory", "Door", "ElementComponent",
    "Fastener", "Footing", "MechanicalFastener", "Member", "Pile", "Plate",
    "Railing", "Ramp", "RampFlight", "ReinforcingBar", "ReinforcingElement",
    "ReinforcingMesh", "Roof", "ShadingDevice", "Slab", "Stair", "StairFlight",
    "Tendon", "TendonAnchor", "TransportElement", "VibrationIsolator",
    "Wall", "WallElementedCase", "Window",
    # Furnishing
    "Furniture",
    # MEP
    "DistributionElement", "DistributionFlowElement", "DistributionControlElement",
    "EnergyConversionDevice", "FlowController", "FlowFitting", "FlowMovingDevice",
    "FlowSegment", "FlowStorageDevice", "FlowTerminal", "FlowTreatmentDevice",
    "Actuator", "AirTerminal", "AirTerminalBox", "AirToAirHeatRecovery",
    "Alarm", "AudioVisualAppliance", "Boiler", "Burner",
    "CableCarrierFitting", "CableCarrierSegment", "CableFitting", "CableSegment",
    "Chiller", "Coil", "CommunicationsAppliance", "Compressor", "Condenser",
    "Controller", "CooledBeam", "CoolingTower", "Damper",
    "DistributionChamberElement", "DuctFitting", "DuctSegment", "DuctSilencer",
    "ElectricAppliance", "ElectricDistributionBoard", "ElectricFlowStorageDevice",
    "ElectricGenerator", "ElectricMotor", "ElectricTimeControl",
    "Engine", "EvaporativeCooler", "Evaporator", "Fan", "Filter",
    "FireSuppressionTerminal", "FlowInstrument", "FlowMeter",
    "HeatExchanger", "Humidifier", "Interceptor", "JunctionBox",
    "Lamp", "LightFixture", "MedicalDevice", "MotorConnection",
    "Outlet", "PipeFitting", "PipeSegment", "ProtectiveDevice",
    "ProtectiveDeviceTrippingUnit", "Pump", "SanitaryTerminal",
    "Sensor", "SolarDevice", "SpaceHeater", "StackTerminal",
    "SwitchingDevice", "Tank", "Transformer", "TubeBundle",
    "UnitaryControlElement", "UnitaryEquipment", "Valve", "WasteTerminal",
    # Optional
    "Interface",
)

ALL_LABELS = SPATIAL_LABELS + ELEMENT_LABELS


# ---------------------------------------------------------------------------
# DDL statements
# ---------------------------------------------------------------------------

def _constraint_statement(label: str) -> str:
    """
    CREATE CONSTRAINT IF NOT EXISTS for uniqueness on `uri` property.
    Compatible with Neo4j 4.4+ and 5.x.
    """
    safe_name = f"unique_{label.lower()}_uri"
    return (
        f"CREATE CONSTRAINT {safe_name} IF NOT EXISTS "
        f"FOR (n:{label}) REQUIRE n.uri IS UNIQUE"
    )


def _index_statement(label: str, prop: str) -> str:
    safe_name = f"idx_{label.lower()}_{prop.lower()}"
    return (
        f"CREATE INDEX {safe_name} IF NOT EXISTS "
        f"FOR (n:{label}) ON (n.{prop})"
    )


# ---------------------------------------------------------------------------
# Setup function
# ---------------------------------------------------------------------------

def setup_schema(driver: "Driver", database: str = "neo4j") -> None:
    """
    Create all constraints and indexes required by the converter.

    Parameters
    ----------
    driver : neo4j.Driver
    database : str
        Target database name (default "neo4j").
    """
    statements: list[str] = []

    # Uniqueness constraints on uri for every label we might create
    for label in ALL_LABELS:
        statements.append(_constraint_statement(label))

    # Index on globalId for all labels (useful for lookup and deduplication)
    for label in ("Site", "Building", "Storey", "Space", "Element"):
        statements.append(_index_statement(label, "globalId"))

    # Index on ifcType for filtering queries
    for label in ("Element",):
        statements.append(_index_statement(label, "ifcType"))

    with driver.session(database=database) as session:
        for stmt in statements:
            try:
                session.run(stmt)
                logger.debug("DDL OK: %s", stmt[:80])
            except Exception as exc:
                # Neo4j may raise if the constraint/index already exists in
                # older versions that don't support IF NOT EXISTS.  Log and
                # continue.
                logger.debug("DDL skipped (%s): %.80s", exc, stmt)

    logger.info("Schema setup complete (%d statements).", len(statements))


def drop_all_data(driver: "Driver", database: str = "neo4j") -> None:
    """
    Remove ALL nodes and relationships from the database.
    USE WITH CAUTION — intended for development/testing only.
    """
    with driver.session(database=database) as session:
        session.run("MATCH (n) DETACH DELETE n")
    logger.warning("All data deleted from database '%s'.", database)
