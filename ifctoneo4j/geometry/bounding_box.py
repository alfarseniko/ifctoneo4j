"""
bounding_box.py — Geometry extraction and interface detection

Implements §6.1 (bounding boxes) and §6.2 (interface detection).

Geometry is computed using ifcopenshell.geom with IfcOpenShell's
built-in tessellator.  The result is a per-element bounding box which
is stored either as:
  • Six individual properties (x_min, x_max, y_min, y_max, z_min, z_max)
  • A WKT polygon string (2-D footprint from X/Y extents)

Interface detection uses an RTree spatial index (rtree library) over
the 3-D bounding boxes.  For each element, the RTree is queried with a
box expanded by INTERFACE_TOLERANCE (0.05 m).  Any pair of elements whose
boxes overlap within this tolerance gets a bot:Interface node.

Dependencies (optional — only required when has_geometry=True):
    ifcopenshell.geom  (bundled with ifcopenshell)
    rtree              (pip install rtree)  — for interface detection only
    numpy              (usually bundled with ifcopenshell)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

INTERFACE_TOLERANCE = 0.05  # metres (§6.2)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class BoundingBox:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    def expanded(self, tol: float) -> "BoundingBox":
        """Return a copy expanded by `tol` in all directions."""
        return BoundingBox(
            self.x_min - tol, self.x_max + tol,
            self.y_min - tol, self.y_max + tol,
            self.z_min - tol, self.z_max + tol,
        )

    def to_wkt_polygon(self) -> str:
        """
        2-D footprint polygon (X/Y plane) as WKT (§6.1 Mode A).
        Format: POLYGON((xmin ymin, xmax ymin, xmax ymax, xmin ymax, xmin ymin))
        """
        xn, xx, yn, yx = self.x_min, self.x_max, self.y_min, self.y_max
        return (
            f"POLYGON(({xn} {yn}, {xx} {yn}, {xx} {yx}, {xn} {yx}, {xn} {yn}))"
        )

    def to_props(self) -> dict:
        """Return as flat property dict (§6.1 Mode B)."""
        return {
            "bbox_x_min": self.x_min,
            "bbox_x_max": self.x_max,
            "bbox_y_min": self.y_min,
            "bbox_y_max": self.y_max,
            "bbox_z_min": self.z_min,
            "bbox_z_max": self.z_max,
        }


# ---------------------------------------------------------------------------
# Geometry extraction
# ---------------------------------------------------------------------------

def compute_bounding_boxes(
    ifc_model,
    seen_guids: Optional[set[str]] = None,
) -> dict[str, BoundingBox]:
    """
    Compute bounding boxes for all elements in the model using
    ifcopenshell.geom.

    Parameters
    ----------
    ifc_model : ifcopenshell.file
    seen_guids : set[str] | None
        If provided, only compute geometry for elements with these GlobalIds.

    Returns
    -------
    dict[str, BoundingBox]
        Mapping of GlobalId → BoundingBox.  Elements with no geometry are
        omitted.
    """
    try:
        import ifcopenshell.geom as geom
        import numpy as np
    except ImportError:
        logger.error(
            "ifcopenshell.geom or numpy not available — geometry skipped."
        )
        return {}

    settings = geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    settings.set(settings.WELD_VERTICES, True)

    results: dict[str, BoundingBox] = {}

    # Use the iterator for efficiency on large models
    try:
        it = geom.iterator(settings, ifc_model, include=ifc_model.by_type("IfcElement"))
    except Exception:
        # Fallback: iterate manually if the include kwarg is not supported
        it = geom.iterator(settings, ifc_model)

    if not it.initialize():
        logger.warning("ifcopenshell.geom iterator failed to initialize.")
        return results

    while True:
        shape = it.get()
        elem = ifc_model.by_guid(shape.guid)
        guid = shape.guid

        if seen_guids is not None and guid not in seen_guids:
            if not it.next():
                break
            continue

        try:
            geom_shape = shape.geometry
            verts = np.array(geom_shape.verts).reshape(-1, 3)
            if len(verts) == 0:
                if not it.next():
                    break
                continue

            bb = BoundingBox(
                x_min=float(verts[:, 0].min()),
                x_max=float(verts[:, 0].max()),
                y_min=float(verts[:, 1].min()),
                y_max=float(verts[:, 1].max()),
                z_min=float(verts[:, 2].min()),
                z_max=float(verts[:, 2].max()),
            )
            results[guid] = bb

        except Exception as exc:
            logger.debug("Geometry failed for %s (%s): %s", guid, elem.is_a() if elem else "?", exc)

        if not it.next():
            break

    logger.info("Computed bounding boxes for %d elements.", len(results))
    return results


# ---------------------------------------------------------------------------
# Interface detection (§6.2)
# ---------------------------------------------------------------------------

def detect_interfaces(
    bbox_map: dict[str, BoundingBox],
    tolerance: float = INTERFACE_TOLERANCE,
) -> list[tuple[str, str]]:
    """
    Detect element interfaces by 3-D bounding-box overlap.

    For each element, query an RTree with its bounding box expanded by
    `tolerance` in all directions.  Return pairs (guid_a, guid_b) where
    both elements' boxes intersect.

    Parameters
    ----------
    bbox_map : dict[str, BoundingBox]
        From compute_bounding_boxes().
    tolerance : float
        Expansion distance in model units (default 0.05 m).

    Returns
    -------
    list of (guid_a, guid_b) pairs (order-independent, no self-pairs,
    no duplicates).
    """
    try:
        from rtree import index as rtree_index
    except ImportError:
        logger.error(
            "rtree library not installed — interface detection unavailable. "
            "Install with: pip install rtree"
        )
        return []

    guids = list(bbox_map.keys())
    if not guids:
        return []

    # Build 3-D RTree
    prop = rtree_index.Property()
    prop.dimension = 3
    idx = rtree_index.Index(properties=prop)

    for i, guid in enumerate(guids):
        bb = bbox_map[guid]
        # RTree expects (left, bottom, near, right, top, far) for 3D
        idx.insert(i, (bb.x_min, bb.y_min, bb.z_min, bb.x_max, bb.y_max, bb.z_max))

    seen_pairs: set[frozenset] = set()
    interfaces: list[tuple[str, str]] = []

    for i, guid_a in enumerate(guids):
        bb_a = bbox_map[guid_a].expanded(tolerance)
        candidates = list(idx.intersection(
            (bb_a.x_min, bb_a.y_min, bb_a.z_min,
             bb_a.x_max, bb_a.y_max, bb_a.z_max)
        ))
        for j in candidates:
            if j == i:
                continue
            guid_b = guids[j]
            pair = frozenset((guid_a, guid_b))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            interfaces.append((guid_a, guid_b))

    logger.info("Detected %d element interfaces.", len(interfaces))
    return interfaces


# ---------------------------------------------------------------------------
# Attach bounding box properties to node dicts
# ---------------------------------------------------------------------------

def attach_geometry_to_nodes(
    nodes: list[dict],
    bbox_map: dict[str, BoundingBox],
    as_wkt: bool = False,
) -> None:
    """
    Mutate node dicts in-place to add bounding box data.

    Parameters
    ----------
    nodes : list[dict]
        Node dicts from traversal (modified in-place).
    bbox_map : dict[str, BoundingBox]
        guid → BoundingBox from compute_bounding_boxes().
    as_wkt : bool
        If True, add `bbox_wkt` (geo:asWKT polygon string).
        If False, add individual bbox_x_min / bbox_x_max / … properties.
    """
    attached = 0
    for node in nodes:
        guid = node.get("props", {}).get("globalId")
        if not guid:
            continue
        bb = bbox_map.get(guid)
        if bb is None:
            continue
        if as_wkt:
            node["props"]["bbox_wkt"] = bb.to_wkt_polygon()
        else:
            node["props"].update(bb.to_props())
        attached += 1

    logger.info("Attached geometry to %d nodes.", attached)


# ---------------------------------------------------------------------------
# Geolocation (§6.3)
# ---------------------------------------------------------------------------

def extract_geolocation(site) -> Optional[str]:
    """
    Read IfcSite.RefLatitude and RefLongitude and return a WKT POINT string.

    IFC stores lat/long as a sequence of four integers:
        (degrees, minutes, seconds, millionths_of_seconds)

    Conversion formula (§6.3):
        decimal = degrees + minutes/60 + seconds/3600 + millionths/3_600_000_000

    Returns
    -------
    str | None
        WKT string "POINT (<lon> <lat>)" or None if data unavailable.
    """
    def _dms_to_decimal(dms) -> Optional[float]:
        if dms is None:
            return None
        # dms is an IfcCompoundPlaneAngleMeasure — a list/tuple of ints
        try:
            parts = list(dms)
        except TypeError:
            return None
        if len(parts) < 3:
            return None
        deg = parts[0]
        minutes = parts[1] if len(parts) > 1 else 0
        sec  = parts[2] if len(parts) > 2 else 0
        msec = parts[3] if len(parts) > 3 else 0
        return deg + minutes / 60.0 + sec / 3600.0 + msec / 3_600_000_000.0

    lat_dms = getattr(site, "RefLatitude",  None)
    lon_dms = getattr(site, "RefLongitude", None)

    lat = _dms_to_decimal(lat_dms)
    lon = _dms_to_decimal(lon_dms)

    if lat is None or lon is None:
        return None

    # WKT convention: longitude first
    return f"POINT ({lon} {lat})"
