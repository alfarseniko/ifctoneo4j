"""
main.py — IFC to Neo4j LBD Converter  (CLI entry point)

Usage examples
--------------
# Basic conversion with defaults
python -m ifc_to_neo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j \
    --neo4j-password secret

# With geometry and geolocation
python -m ifc_to_neo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j --neo4j-password secret \
    --geometry --geolocation --wkt-bbox

# L2 properties with units, hierarchical naming
python -m ifc_to_neo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j --neo4j-password secret \
    --properties-level 2 --units --hierarchical-naming

# Clear database first, then import
python -m ifc_to_neo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j --neo4j-password secret \
    --clear-db
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet the neo4j driver's verbose connection logs unless in verbose mode
    if not verbose:
        logging.getLogger("neo4j").setLevel(logging.WARNING)


def _build_config(args) -> "ConversionConfig":
    from .config import ConversionConfig

    cfg = ConversionConfig(
        has_building_elements=not args.no_elements,
        has_building_properties=not args.no_properties,
        properties_level=args.properties_level,
        has_geometry=args.geometry,
        has_bounding_box_wkt=args.wkt_bbox,
        has_interfaces=args.interfaces,
        has_geolocation=args.geolocation,
        has_hierarchical_naming=args.hierarchical_naming,
        base_uri=args.base_uri,
        has_units=args.units,
        has_non_lbd_element=not args.no_orphans,
        batch_size=args.batch_size,
        geometry_workers=args.geometry_workers,
    )
    cfg.validate()
    return cfg


def run(args) -> int:
    """Execute the conversion pipeline. Returns exit code."""
    logger = logging.getLogger("ifc_to_neo4j")

    # ── Imports ──────────────────────────────────────────────────────────────
    try:
        from neo4j import GraphDatabase
    except ImportError:
        logger.error(
            "neo4j Python driver not installed. Run: pip install neo4j"
        )
        return 1

    from .config import ConversionConfig
    from .core.ifc_loader import open_ifc, log_model_summary
    from .converters.spatial import traverse
    from .neo4j.writer import Neo4jWriter

    # ── Configuration ─────────────────────────────────────────────────────────
    cfg = _build_config(args)
    logger.info("Configuration: %s", cfg)

    # ── Load IFC ──────────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    logger.info("Loading IFC file: %s", args.ifc_file)
    try:
        loaded = open_ifc(args.ifc_file)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1
    except Exception as exc:
        logger.error("Failed to open IFC file: %s", exc)
        return 1

    log_model_summary(loaded)
    t_load = time.perf_counter() - t0
    logger.info("IFC loaded in %.1fs", t_load)

    # ── Spatial traversal ────────────────────────────────────────────────────
    t1 = time.perf_counter()
    logger.info("Starting spatial hierarchy traversal …")
    traversal = traverse(loaded, cfg)
    t_traverse = time.perf_counter() - t1
    logger.info(
        "Traversal complete in %.1fs — %d nodes, %d relationships",
        t_traverse, len(traversal.nodes), len(traversal.rels),
    )

    # ── Geometry (optional) ───────────────────────────────────────────────────
    interfaces: list[tuple[str, str]] = []
    if cfg.has_geometry:
        t2 = time.perf_counter()
        logger.info("Computing bounding boxes …")
        from .geometry.bounding_box import (
            compute_bounding_boxes, attach_geometry_to_nodes, detect_interfaces
        )
        bbox_map = compute_bounding_boxes(loaded.model, traversal.seen_guids)
        attach_geometry_to_nodes(traversal.nodes, bbox_map, as_wkt=cfg.has_bounding_box_wkt)
        logger.info("Bounding boxes computed in %.1fs", time.perf_counter() - t2)

        if cfg.has_interfaces:
            t3 = time.perf_counter()
            logger.info("Detecting element interfaces …")
            # Convert guid pairs to URI pairs
            guid_interfaces = detect_interfaces(bbox_map)
            base = cfg.base_uri
            # Build a guid→uri map for quick lookup
            guid_to_uri: dict[str, str] = {}
            for node in traversal.nodes:
                g = node.get("props", {}).get("globalId")
                if g:
                    guid_to_uri[g] = node["uri"]
            for guid_a, guid_b in guid_interfaces:
                uri_a = guid_to_uri.get(guid_a)
                uri_b = guid_to_uri.get(guid_b)
                if uri_a and uri_b:
                    interfaces.append((uri_a, uri_b))
            logger.info(
                "Interface detection complete in %.1fs — %d interfaces",
                time.perf_counter() - t3, len(interfaces),
            )

    # ── Geolocation (optional) ────────────────────────────────────────────────
    if cfg.has_geolocation:
        from .geometry.bounding_box import extract_geolocation
        for node in traversal.nodes:
            if "Site" in node.get("labels", []):
                guid = node.get("props", {}).get("globalId")
                if guid:
                    try:
                        site_entity = loaded.model.by_guid(guid)
                        wkt = extract_geolocation(site_entity)
                        if wkt:
                            node["props"]["geo_wkt"] = wkt
                            logger.info("Geolocation attached to site %s: %s", guid, wkt)
                    except Exception as exc:
                        logger.warning("Geolocation failed for site %s: %s", guid, exc)

    # ── Neo4j connection ──────────────────────────────────────────────────────
    logger.info("Connecting to Neo4j at %s …", args.neo4j_uri)
    try:
        driver = GraphDatabase.driver(
            args.neo4j_uri,
            auth=(args.neo4j_user, args.neo4j_password),
        )
        driver.verify_connectivity()
        logger.info("Neo4j connection OK.")
    except Exception as exc:
        logger.error("Failed to connect to Neo4j: %s", exc)
        return 1

    # ── Write to Neo4j ────────────────────────────────────────────────────────
    t4 = time.perf_counter()
    try:
        with Neo4jWriter(driver, database=args.database, batch_size=cfg.batch_size) as writer:

            # Clear database if requested
            if args.clear_db:
                logger.warning("Clearing all data from database '%s' …", args.database)
                from .neo4j.schema import drop_all_data
                drop_all_data(driver, args.database)

            # Ensure schema constraints / indexes
            logger.info("Setting up Neo4j schema …")
            writer.setup()

            # Write nodes + relationships
            logger.info("Writing graph to Neo4j …")
            counts = writer.write(traversal, base_uri=cfg.base_uri)

            # Write interface nodes
            if interfaces:
                logger.info("Writing %d interface pairs …", len(interfaces))
                n_ifaces = writer.write_interfaces(interfaces, cfg.base_uri)
                counts["interfaces"] = n_ifaces

    except Exception as exc:
        logger.error("Neo4j write failed: %s", exc)
        return 1

    t_total = time.perf_counter() - t0
    logger.info(
        "Done in %.1fs — nodes:%d  rels:%d  prop_nodes:%d  interfaces:%d",
        t_total,
        counts.get("nodes", 0),
        counts.get("rels", 0),
        counts.get("prop_nodes", 0),
        counts.get("interfaces", 0),
    )
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ifc_to_neo4j",
        description=(
            "Convert an IFC building model to a Linked Building Data (LBD) "
            "graph in Neo4j.  Uses ifcopenshell for IFC parsing — no RDF or "
            "intermediate turtle files required."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Positional
    p.add_argument(
        "ifc_file",
        help="Path to the IFC or IFCzip file to convert.",
    )

    # Neo4j connection
    neo = p.add_argument_group("Neo4j connection")
    neo.add_argument("--neo4j-uri",      default="bolt://localhost:7687",
                     help="Neo4j Bolt URI.")
    neo.add_argument("--neo4j-user",     default="neo4j",
                     help="Neo4j username.")
    neo.add_argument("--neo4j-password", default="neo4j",
                     help="Neo4j password.")
    neo.add_argument("--database",       default="neo4j",
                     help="Target Neo4j database name.")

    # Conversion flags
    conv = p.add_argument_group("Conversion options")
    conv.add_argument("--base-uri",     default="https://linkedbuildingdata.org/building#",
                      help="Base URI for node identifiers.")
    conv.add_argument("--properties-level", type=int, default=1, choices=[1, 2, 3],
                      help="Property representation level (1=flat, 2=OPM nodes, 3=OPM+states).")
    conv.add_argument("--units",            action="store_true",
                      help="Attach QUDT unit URIs to numeric properties.")
    conv.add_argument("--hierarchical-naming", action="store_true",
                      help="Use name-based hierarchical URIs instead of GUID-based.")
    conv.add_argument("--no-elements",      action="store_true",
                      help="Skip building elements (spatial hierarchy only).")
    conv.add_argument("--no-properties",    action="store_true",
                      help="Skip property set extraction.")
    conv.add_argument("--no-orphans",       action="store_true",
                      help="Skip elements outside the spatial hierarchy.")

    # Geometry flags
    geom = p.add_argument_group("Geometry options")
    geom.add_argument("--geometry",      action="store_true",
                      help="Compute bounding boxes using ifcopenshell.geom.")
    geom.add_argument("--wkt-bbox",      action="store_true",
                      help="Store bounding box as WKT polygon instead of 6 numeric properties.")
    geom.add_argument("--interfaces",    action="store_true",
                      help="Detect and create bot:Interface nodes (requires --geometry).")
    geom.add_argument("--geolocation",   action="store_true",
                      help="Extract IfcSite lat/lon and store as geo:asWKT POINT.")
    geom.add_argument("--geometry-workers", type=int, default=1,
                      help="Number of parallel geometry processing workers.")

    # Performance
    perf = p.add_argument_group("Performance options")
    perf.add_argument("--batch-size", type=int, default=500,
                      help="Number of nodes/rels per Neo4j transaction batch.")

    # Database management
    db = p.add_argument_group("Database management")
    db.add_argument("--clear-db", action="store_true",
                    help="Delete all existing data before importing (DESTRUCTIVE).")

    # Logging
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Enable debug logging.")

    return p


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()
    _setup_logging(args.verbose)
    sys.exit(run(args))


if __name__ == "__main__":
    main()
