"""
spatial.py — Spatial hierarchy traversal

Implements Phase 2 of the conversion pipeline (§3.1, §3.2, §3.3):

  IfcSite
    └─ bot:hasBuilding ──► IfcBuilding
         └─ bot:hasStorey ──► IfcBuildingStorey
              ├─ bot:containsElement ──► IfcElement  (direct storey elements)
              └─ bot:hasSpace ──► IfcSpace
                   ├─ bot:containsElement ──► IfcElement
                   └─ bot:adjacentElement ──► IfcElement  (space boundaries)

Produces two flat lists:
  nodes  — node dicts (see elements.py)
  rels   — relationship dicts (see elements.py)

The traversal also collects all processed GlobalIds into `seen_guids` so that
the orphaned-element scanner can identify anything left outside the hierarchy.

Relationship types used
-----------------------
  HAS_BUILDING      → bot:hasBuilding
  HAS_STOREY        → bot:hasStorey
  HAS_SPACE         → bot:hasSpace
  CONTAINS_ELEMENT  → bot:containsElement
  ADJACENT_ELEMENT  → bot:adjacentElement
  HAS_SUB_ELEMENT   → bot:hasSubElement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from ..config import ConversionConfig
from ..core.unit_handler import build_unit_map
from .elements import (
    make_spatial_node,
    make_element_node,
    make_relationship,
    build_element_uri,
    get_hosted_elements,
    get_aggregated_sub_elements,
    find_orphaned_elements,
)
from .properties import extract_properties

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Traversal result container
# ---------------------------------------------------------------------------

@dataclass
class TraversalResult:
    """All nodes and relationships produced by spatial hierarchy traversal."""
    nodes:     list[dict] = field(default_factory=list)
    rels:      list[dict] = field(default_factory=list)
    seen_guids: set[str]  = field(default_factory=set)

    # L2/L3 property nodes (not used for L1)
    prop_nodes: list = field(default_factory=list)  # list[PropertyNode]
    prop_rels:  list[tuple] = field(default_factory=list)

    def add_node(self, node: dict) -> None:
        self.nodes.append(node)
        guid = node.get("props", {}).get("globalId")
        if guid:
            self.seen_guids.add(guid)

    def add_rel(self, rel: dict) -> None:
        self.rels.append(rel)


# ---------------------------------------------------------------------------
# Main traversal function
# ---------------------------------------------------------------------------

def traverse(ifc_loaded, cfg: ConversionConfig) -> TraversalResult:
    """
    Walk the complete IFC spatial hierarchy and return all nodes + rels.

    Parameters
    ----------
    ifc_loaded : core.ifc_loader.LoadedIFC
    cfg : ConversionConfig

    Returns
    -------
    TraversalResult
    """
    model   = ifc_loaded.model
    base    = cfg.base_uri
    hier    = cfg.has_hierarchical_naming
    result  = TraversalResult()
    unit_map = build_unit_map(model) if cfg.has_units else {}

    # ------------------------------------------------------------------
    # Process a single element (shared helper)
    # ------------------------------------------------------------------
    def process_element(
        elem,
        container_uri: str,
        rel_type: str,
        parent_uri: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a node + containment relationship for one element.
        Recursively handles hosted and aggregated sub-elements.
        Returns the element URI.
        """
        elem_uri = build_element_uri(elem, base, hier, parent_uri)
        guid = getattr(elem, "GlobalId", None) or ""

        if guid in result.seen_guids:
            # Already processed (e.g. shared element) — still add the
            # relationship if it's new
            result.add_rel(make_relationship(container_uri, rel_type, elem_uri))
            return elem_uri

        node = make_element_node(elem, base, hier, parent_uri)
        result.seen_guids.add(guid)

        # Attach properties
        if cfg.has_building_properties:
            pg = extract_properties(
                elem, elem_uri, unit_map,
                level=cfg.properties_level,
                has_units=cfg.has_units,
                base_uri=base,
            )
            node["props"].update(pg.flat_props)

            if cfg.properties_level > 1:
                result.prop_nodes.extend(pg.property_nodes)
                result.prop_rels.extend(pg.property_rels)

        result.add_node(node)
        result.add_rel(make_relationship(container_uri, rel_type, elem_uri))

        # Hosted elements (doors/windows in walls) → HAS_SUB_ELEMENT
        for fill, host_uri in get_hosted_elements(elem, base, hier):
            process_element(fill, host_uri, "HAS_SUB_ELEMENT", parent_uri=host_uri)

        # Aggregated sub-elements → HAS_SUB_ELEMENT
        for sub, par_uri in get_aggregated_sub_elements(elem, base, hier):
            process_element(sub, par_uri, "HAS_SUB_ELEMENT", parent_uri=par_uri)

        return elem_uri

    # ------------------------------------------------------------------
    # IfcSite loop
    # ------------------------------------------------------------------
    sites = model.by_type("IfcSite")
    if not sites:
        logger.warning("No IfcSite found in model.")

    for site in sites:
        site_node = make_spatial_node(site, "Site", base, hier)
        if cfg.has_building_properties:
            pg = extract_properties(
                site, site_node["uri"], unit_map,
                level=cfg.properties_level, has_units=cfg.has_units, base_uri=base,
            )
            site_node["props"].update(pg.flat_props)
        result.add_node(site_node)
        site_uri = site_node["uri"]

        # ── Buildings ──────────────────────────────────────────────────
        for bld in _decomposed_objects(site):
            if not bld.is_a("IfcBuilding"):
                continue

            bld_node = make_spatial_node(bld, "Building", base, hier, site_uri)
            if cfg.has_building_properties:
                pg = extract_properties(
                    bld, bld_node["uri"], unit_map,
                    level=cfg.properties_level, has_units=cfg.has_units, base_uri=base,
                )
                bld_node["props"].update(pg.flat_props)
            result.add_node(bld_node)
            result.add_rel(make_relationship(site_uri, "HAS_BUILDING", bld_node["uri"]))
            bld_uri = bld_node["uri"]

            # ── Storeys ────────────────────────────────────────────────
            for storey in _decomposed_objects(bld):
                if not storey.is_a("IfcBuildingStorey"):
                    continue

                storey_node = make_spatial_node(storey, "Storey", base, hier, bld_uri)
                if cfg.has_building_properties:
                    pg = extract_properties(
                        storey, storey_node["uri"], unit_map,
                        level=cfg.properties_level, has_units=cfg.has_units, base_uri=base,
                    )
                    storey_node["props"].update(pg.flat_props)
                result.add_node(storey_node)
                result.add_rel(make_relationship(bld_uri, "HAS_STOREY", storey_node["uri"]))
                storey_uri = storey_node["uri"]

                # Direct storey elements
                if cfg.has_building_elements:
                    for elem in _contained_elements(storey):
                        process_element(elem, storey_uri, "CONTAINS_ELEMENT")

                # ── Spaces ─────────────────────────────────────────────
                for space in _decomposed_objects(storey):
                    if not space.is_a("IfcSpace"):
                        continue

                    space_node = make_spatial_node(space, "Space", base, hier, storey_uri)
                    if cfg.has_building_properties:
                        pg = extract_properties(
                            space, space_node["uri"], unit_map,
                            level=cfg.properties_level, has_units=cfg.has_units, base_uri=base,
                        )
                        space_node["props"].update(pg.flat_props)
                    result.add_node(space_node)
                    result.add_rel(make_relationship(storey_uri, "HAS_SPACE", space_node["uri"]))
                    space_uri = space_node["uri"]

                    # Space-contained elements
                    if cfg.has_building_elements:
                        for elem in _contained_elements(space):
                            process_element(elem, space_uri, "CONTAINS_ELEMENT")

                    # Space boundary elements (adjacent)
                    if cfg.has_building_elements:
                        for elem in _adjacent_elements(space):
                            elem_uri = build_element_uri(elem, base, hier)
                            # Don't re-create the node if already seen;
                            # just add the adjacency relationship
                            if getattr(elem, "GlobalId", None) not in result.seen_guids:
                                process_element(elem, space_uri, "ADJACENT_ELEMENT")
                            else:
                                result.add_rel(
                                    make_relationship(space_uri, "ADJACENT_ELEMENT", elem_uri)
                                )

    # ------------------------------------------------------------------
    # Orphaned elements (§6.8)
    # ------------------------------------------------------------------
    if cfg.has_non_lbd_element and cfg.has_building_elements:
        orphans = find_orphaned_elements(model, result.seen_guids)
        if orphans:
            logger.info("Processing %d orphaned elements.", len(orphans))
        for elem in orphans:
            elem_uri = build_element_uri(elem, base, hier)
            guid = getattr(elem, "GlobalId", None) or ""
            node = make_element_node(elem, base, hier)
            result.seen_guids.add(guid)
            if cfg.has_building_properties:
                pg = extract_properties(
                    elem, elem_uri, unit_map,
                    level=cfg.properties_level, has_units=cfg.has_units, base_uri=base,
                )
                node["props"].update(pg.flat_props)
            result.add_node(node)
            # No spatial relationship — orphaned

    logger.info(
        "Traversal complete: %d nodes, %d relationships, %d elements seen.",
        len(result.nodes), len(result.rels), len(result.seen_guids),
    )
    return result


# ---------------------------------------------------------------------------
# Spatial navigation helpers (IFC2x3 and IFC4 compatible)
# ---------------------------------------------------------------------------

def _decomposed_objects(spatial_element) -> list:
    """
    Return child objects via IsDecomposedBy.
    Works for both IFC2X3 (IfcRelDecomposes) and IFC4 (IfcRelAggregates).
    ifcopenshell exposes both via the IsDecomposedBy inverse attribute.
    """
    objects = []
    is_decomposed_by = getattr(spatial_element, "IsDecomposedBy", None) or []
    for rel in is_decomposed_by:
        related = getattr(rel, "RelatedObjects", None) or []
        objects.extend(related)
    return objects


def _contained_elements(spatial_element) -> list:
    """
    Return elements contained in a spatial structure element via
    IfcRelContainedInSpatialStructure (ContainsElements inverse attribute).
    """
    elements = []
    contains = getattr(spatial_element, "ContainsElements", None) or []
    for rel in contains:
        related = getattr(rel, "RelatedElements", None) or []
        elements.extend(related)
    return elements


def _adjacent_elements(space) -> list:
    """
    Return elements that bound a space via IfcRelSpaceBoundary
    (BoundedBy inverse attribute).
    """
    elements = []
    bounded_by = getattr(space, "BoundedBy", None) or []
    for rel in bounded_by:
        elem = getattr(rel, "RelatedBuildingElement", None)
        if elem is not None:
            elements.append(elem)
    return elements
