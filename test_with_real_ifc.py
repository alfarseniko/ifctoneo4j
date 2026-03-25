"""
Dry-run test with a real IFC file — no Neo4j required.

Usage:
    python3 test_with_real_ifc.py path/to/model.ifc

Runs the full parse + traversal pipeline and prints a summary of what
would be written to Neo4j.  Useful for validating the converter against
a real file before connecting a database.
"""

import sys
import time
import logging
from collections import Counter, defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("dry_run")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_with_real_ifc.py path/to/model.ifc")
        sys.exit(1)

    ifc_path = sys.argv[1]

    # ── Phase 1: Load ─────────────────────────────────────────────────────────
    from ifctoneo4j.core.ifc_loader import open_ifc, log_model_summary
    from ifctoneo4j.config import ConversionConfig

    log.info("=" * 60)
    log.info("Loading: %s", ifc_path)
    t0 = time.perf_counter()
    loaded = open_ifc(ifc_path)
    log.info("Schema: %s → %s", loaded.schema_raw, loaded.schema_version)
    log_model_summary(loaded)
    log.info("Load time: %.2fs", time.perf_counter() - t0)

    # ── Phase 2: Traverse ─────────────────────────────────────────────────────
    cfg = ConversionConfig(
        has_building_elements=True,
        has_building_properties=True,
        properties_level=1,
        has_geometry=False,
        has_units=False,
        has_non_lbd_element=True,
    )

    from ifctoneo4j.converters.spatial import traverse

    log.info("=" * 60)
    log.info("Traversing spatial hierarchy …")
    t1 = time.perf_counter()
    result = traverse(loaded, cfg)
    elapsed = time.perf_counter() - t1
    log.info("Traversal time: %.2fs", elapsed)

    # ── Report ────────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  TRAVERSAL SUMMARY")
    print("=" * 60)
    print(f"  Total nodes        : {len(result.nodes)}")
    print(f"  Total relationships: {len(result.rels)}")
    print(f"  Elements seen      : {len(result.seen_guids)}")
    print()

    # Count by label
    label_counts: Counter = Counter()
    for node in result.nodes:
        for lbl in node.get("labels", []):
            label_counts[lbl] += 1

    print("  Node counts by label:")
    for label, count in sorted(label_counts.items(), key=lambda x: -x[1]):
        print(f"    {label:<35} {count}")

    print()

    # Count by relationship type
    rel_counts: Counter = Counter()
    for rel in result.rels:
        rel_counts[rel["rel_type"]] += 1

    print("  Relationship counts by type:")
    for rel_type, count in sorted(rel_counts.items(), key=lambda x: -x[1]):
        print(f"    {rel_type:<35} {count}")

    print()

    # Property key sample
    all_prop_keys: set = set()
    for node in result.nodes:
        all_prop_keys.update(node.get("props", {}).keys())

    prop_keys_simple = sorted(k for k in all_prop_keys if k.endswith("_property_simple"))
    prop_keys_attr   = sorted(k for k in all_prop_keys if k.endswith("_attribute_simple"))

    print(f"  Unique property keys (_property_simple): {len(prop_keys_simple)}")
    for k in prop_keys_simple[:20]:
        print(f"    {k}")
    if len(prop_keys_simple) > 20:
        print(f"    … and {len(prop_keys_simple) - 20} more")

    print()
    print(f"  Unique attribute keys (_attribute_simple): {len(prop_keys_attr)}")
    for k in prop_keys_attr[:10]:
        print(f"    {k}")

    print()

    # Sample a few nodes
    print("  Sample nodes (first 5 of each spatial type):")
    for target_label in ("Site", "Building", "Storey", "Space"):
        matches = [n for n in result.nodes if target_label in n.get("labels", [])][:5]
        for n in matches:
            name = n["props"].get("name", "(no name)")
            guid = n["props"].get("globalId", "?")
            print(f"    [{target_label}]  {name}  ({guid})")

    print()
    print("  Sample element nodes (first 10):")
    element_nodes = [
        n for n in result.nodes
        if "Element" in n.get("labels", []) and len(n["labels"]) > 1
    ][:10]
    for n in element_nodes:
        name   = n["props"].get("name", "(no name)")
        labels = ":".join(n["labels"])
        guid   = n["props"].get("globalId", "?")
        print(f"    [{labels}]  {name}  ({guid})")

    print()
    print("=" * 60)
    print("  Dry run complete — no Neo4j connection required.")
    print("  To write to Neo4j:")
    print()
    print("  python3 -m ifctoneo4j.main", ifc_path, "\\")
    print("      --neo4j-uri bolt://localhost:7687 \\")
    print("      --neo4j-user neo4j --neo4j-password yourpassword")
    print("=" * 60)


if __name__ == "__main__":
    main()
