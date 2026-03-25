"""
ifc_loader.py — IFC file loading and schema version detection

Wraps ifcopenshell.open() with:
  • .ifczip decompression (handled transparently by ifcopenshell itself,
    but we validate the extension and log it)
  • IFC schema version detection (IFC2X3, IFC4, IFC4x1, IFC4x2, IFC4x3)
  • A small dataclass that carries the open model + metadata

Schema version mapping (§8.1)
------------------------------
  IFC2X3       → "IFC2X3_TC1"
  IFC4         → "IFC4_ADD2"
  IFC4X1       → "IFC4X1"
  IFC4X2       → "IFC4X3_RC1"  (same ontology used for both)
  IFC4X3 / _RC1→ "IFC4X3_RC1"
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import ifcopenshell

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema version normalisation (mirrors IfcOWLUtils.java:getExpressSchema())
# ---------------------------------------------------------------------------
_SCHEMA_MAP: dict[str, str] = {
    "IFC2X3":     "IFC2X3_TC1",
    "IFC4":       "IFC4_ADD2",
    "IFC4X1":     "IFC4X1",
    "IFC4X2":     "IFC4X3_RC1",
    "IFC4X3":     "IFC4X3_RC1",
    "IFC4X3_RC1": "IFC4X3_RC1",
    "IFC4X3_ADD1":"IFC4X3_RC1",
    "IFC4X3_ADD2":"IFC4X3_RC1",
}


def normalise_schema(raw_schema: str) -> str:
    """
    Map an IFC FILE_SCHEMA string to the canonical ifcOWL ontology version.

    Parameters
    ----------
    raw_schema : str
        Schema string as returned by ``ifc_model.schema``, e.g. "IFC4".

    Returns
    -------
    str
        One of the canonical version strings (IFC2X3_TC1, IFC4_ADD2, …).
    """
    key = raw_schema.upper().strip()
    result = _SCHEMA_MAP.get(key)
    if result is None:
        logger.warning(
            "Unknown IFC schema version %r — falling back to IFC4_ADD2", raw_schema
        )
        return "IFC4_ADD2"
    return result


def is_ifc2x3(schema_normalised: str) -> bool:
    """Return True when the file is IFC2X3 (affects some relationship names)."""
    return schema_normalised == "IFC2X3_TC1"


# ---------------------------------------------------------------------------
# LoadedIFC dataclass
# ---------------------------------------------------------------------------

@dataclass
class LoadedIFC:
    """
    Container returned by open_ifc().

    Attributes
    ----------
    model : ifcopenshell.file
        The parsed IFC model.
    path : Path
        Absolute path to the source file.
    schema_raw : str
        Schema string as reported by ifcopenshell (e.g. "IFC4").
    schema_version : str
        Normalised schema version (e.g. "IFC4_ADD2").
    is_ifc2x3 : bool
        True when the model uses IFC2X3 relationship naming.
    file_name : str
        Stem of the file name without extension.
    """
    model: ifcopenshell.file
    path: Path
    schema_raw: str
    schema_version: str
    is_ifc2x3: bool
    file_name: str = field(init=False)

    def __post_init__(self) -> None:
        # Strip .ifczip or .ifc extension(s)
        stem = self.path.name
        for ext in (".ifczip", ".ifc"):
            if stem.lower().endswith(ext):
                stem = stem[: -len(ext)]
                break
        self.file_name = stem


# ---------------------------------------------------------------------------
# Public open function
# ---------------------------------------------------------------------------

def open_ifc(path: str | Path) -> LoadedIFC:
    """
    Open an IFC or IFCzip file and return a LoadedIFC instance.

    Parameters
    ----------
    path : str | Path
        Path to the IFC file (``*.ifc`` or ``*.ifczip``).

    Returns
    -------
    LoadedIFC

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ifcopenshell.Error
        If the file cannot be parsed.
    """
    path = Path(path).resolve()

    if not path.exists():
        raise FileNotFoundError(f"IFC file not found: {path}")

    ext = path.suffix.lower()
    if ext not in (".ifc", ".ifczip"):
        logger.warning("Unexpected file extension %r — attempting to open anyway.", ext)

    if ext == ".ifczip":
        logger.info("Opening compressed IFC file: %s", path)
    else:
        size_mb = path.stat().st_size / 1_048_576
        logger.info("Opening IFC file: %s (%.1f MB)", path, size_mb)

    model: ifcopenshell.file = ifcopenshell.open(str(path))

    schema_raw = model.schema  # e.g. "IFC4", "IFC2X3"
    schema_ver = normalise_schema(schema_raw)

    logger.info(
        "Loaded %s — schema: %s → %s",
        path.name, schema_raw, schema_ver,
    )

    return LoadedIFC(
        model=model,
        path=path,
        schema_raw=schema_raw,
        schema_version=schema_ver,
        is_ifc2x3=is_ifc2x3(schema_ver),
    )


def log_model_summary(loaded: LoadedIFC) -> None:
    """Log a brief summary of what the model contains (element counts)."""
    model = loaded.model
    counts: dict[str, int] = {}
    for entity_name in (
        "IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSpace", "IfcElement"
    ):
        try:
            counts[entity_name] = len(model.by_type(entity_name))
        except Exception:
            counts[entity_name] = 0

    logger.info(
        "Model summary — Sites:%d  Buildings:%d  Storeys:%d  Spaces:%d  Elements:%d",
        counts["IfcSite"],
        counts["IfcBuilding"],
        counts["IfcBuildingStorey"],
        counts["IfcSpace"],
        counts["IfcElement"],
    )
