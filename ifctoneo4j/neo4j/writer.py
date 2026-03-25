"""
writer.py — Batched Neo4j write operations

Design goals:
  • Multi-label node creation via dynamic Cypher (Neo4j does not support
    parameterising labels, so we build the label string in Python)
  • MERGE on `uri` for idempotent re-runs
  • Batched transactions (default 500 rows per commit) for performance
  • L2/L3 Property node creation and linking
  • Interface node creation (geometry phase)

Neo4j Cypher patterns used
---------------------------
Nodes:
    MERGE (n:Label1:Label2 {uri: $uri})
    SET n += $props

Relationships:
    MATCH (a {uri: $from_uri}), (b {uri: $to_uri})
    MERGE (a)-[r:REL_TYPE]->(b)

L2/L3 property nodes:
    MERGE (p:PropertyNode {uri: $uri})
    SET p += $props
    WITH p
    MATCH (e {uri: $elem_uri})
    MERGE (e)-[r:HAS_PROPERTY {name: $name}]->(p)
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Iterator, Optional

if TYPE_CHECKING:
    from neo4j import Driver, Session

from .schema import setup_schema

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Batching helper
# ---------------------------------------------------------------------------

def _chunks(lst: list, size: int) -> Iterator[list]:
    """Yield successive `size`-length chunks from lst."""
    for i in range(0, len(lst), size):
        yield lst[i: i + size]


# ---------------------------------------------------------------------------
# Label string builder
# ---------------------------------------------------------------------------

def _label_string(labels: list[str]) -> str:
    """
    Build a safe Cypher label string from a list of label names.

    Backtick-escapes each label to handle special characters (underscores,
    hyphens in predefined-type subclass labels like Wall_SOLIDWALL).

    e.g. ["Element", "Wall", "Wall_SOLIDWALL"] → "`Element`:`Wall`:`Wall_SOLIDWALL`"
    """
    return ":".join(f"`{lbl}`" for lbl in labels)


def _sanitize_props(props: dict) -> dict:
    """
    Ensure all values in props are Neo4j-compatible (string, int, float, bool,
    list of those).  Converts anything else to str.
    """
    clean = {}
    for k, v in props.items():
        if v is None:
            continue  # skip nulls
        if isinstance(v, (bool, int, float, str)):
            clean[k] = v
        elif isinstance(v, (list, tuple)):
            # Convert list elements
            clean[k] = [str(i) if not isinstance(i, (bool, int, float, str)) else i for i in v]
        else:
            clean[k] = str(v)
    return clean


# ---------------------------------------------------------------------------
# Node writer
# ---------------------------------------------------------------------------

def write_nodes(
    session: "Session",
    nodes: list[dict],
    batch_size: int = 500,
) -> int:
    """
    MERGE nodes into Neo4j in batches.

    Each node dict must have:
      "uri"    — unique identifier
      "labels" — list of Neo4j label strings
      "props"  — property dict

    Nodes with the same label set are grouped together so we can issue one
    parameterised Cypher statement per label-set batch.

    Returns the total number of nodes written.
    """
    # Group nodes by their sorted label tuple for batching
    by_labels: dict[tuple, list[dict]] = defaultdict(list)
    for node in nodes:
        key = tuple(sorted(node.get("labels", ["Element"])))
        by_labels[key].append(node)

    total = 0
    for label_tuple, group in by_labels.items():
        label_str = _label_string(list(label_tuple))
        cypher = (
            f"UNWIND $rows AS row "
            f"MERGE (n:{label_str} {{uri: row.uri}}) "
            f"SET n += row.props "
            f"SET n.uri = row.uri"
        )
        for batch in _chunks(group, batch_size):
            rows = [
                {
                    "uri":   n["uri"],
                    "props": _sanitize_props({**n.get("props", {}), "uri": n["uri"]}),
                }
                for n in batch
            ]
            try:
                session.run(cypher, rows=rows)
                total += len(batch)
                logger.debug(
                    "Wrote %d nodes with labels %s (total so far: %d)",
                    len(batch), label_str, total,
                )
            except Exception as exc:
                logger.error(
                    "Failed to write node batch (labels=%s): %s", label_str, exc
                )
                raise

    return total


# ---------------------------------------------------------------------------
# Relationship writer
# ---------------------------------------------------------------------------

def write_relationships(
    session: "Session",
    rels: list[dict],
    batch_size: int = 500,
) -> int:
    """
    MERGE relationships into Neo4j in batches.

    Each rel dict must have:
      "from_uri"  — URI of the source node
      "rel_type"  — relationship type string
      "to_uri"    — URI of the target node
      "props"     — optional property dict (can be empty)

    Returns total relationships written.
    """
    # Group by rel_type for batching
    by_type: dict[str, list[dict]] = defaultdict(list)
    for rel in rels:
        by_type[rel["rel_type"]].append(rel)

    total = 0
    for rel_type, group in by_type.items():
        # Sanitise rel_type: must be a valid Cypher identifier
        safe_type = rel_type.replace("-", "_").replace(" ", "_").upper()
        cypher = (
            f"UNWIND $rows AS row "
            f"MATCH (a {{uri: row.from_uri}}) "
            f"MATCH (b {{uri: row.to_uri}}) "
            f"MERGE (a)-[r:`{safe_type}`]->(b) "
            f"SET r += row.props"
        )
        for batch in _chunks(group, batch_size):
            rows = [
                {
                    "from_uri": r["from_uri"],
                    "to_uri":   r["to_uri"],
                    "props":    _sanitize_props(r.get("props", {})),
                }
                for r in batch
            ]
            try:
                session.run(cypher, rows=rows)
                total += len(batch)
                logger.debug(
                    "Wrote %d rels of type %s (total so far: %d)",
                    len(batch), safe_type, total,
                )
            except Exception as exc:
                logger.error(
                    "Failed to write relationship batch (type=%s): %s", safe_type, exc
                )
                raise

    return total


# ---------------------------------------------------------------------------
# L2/L3 property node writer
# ---------------------------------------------------------------------------

def write_property_nodes(
    session: "Session",
    prop_nodes: list,   # list[PropertyNode] from properties.py
    prop_rels: list,    # list[(elem_uri, rel_type, prop_uri)]
    batch_size: int = 500,
) -> int:
    """
    Write OPM-style Property nodes (L2) or Property + State nodes (L3).

    Each PropertyNode has:
      uri, prop_name, value, unit_uri, state_uri (L3), generated_at (L3)
    """
    if not prop_nodes:
        return 0

    total = 0

    # Write Property nodes
    cypher_prop = (
        "UNWIND $rows AS row "
        "MERGE (p:`PropertyNode` {uri: row.uri}) "
        "SET p.propName = row.prop_name, p.value = row.value "
        "SET p.unitUri  = CASE WHEN row.unit_uri IS NOT NULL THEN row.unit_uri ELSE p.unitUri END"
    )
    for batch in _chunks(prop_nodes, batch_size):
        rows = [
            {
                "uri":       pn.uri,
                "prop_name": pn.prop_name,
                "value":     pn.value if isinstance(pn.value, (bool, int, float, str)) else str(pn.value),
                "unit_uri":  pn.unit_uri,
            }
            for pn in batch
        ]
        session.run(cypher_prop, rows=rows)
        total += len(batch)

    # Write L3 State nodes (if any)
    state_nodes = [pn for pn in prop_nodes if pn.state_uri]
    if state_nodes:
        cypher_state = (
            "UNWIND $rows AS row "
            "MERGE (s:`PropertyStateNode` {uri: row.state_uri}) "
            "SET s.value = row.value, s.generatedAt = row.generated_at "
            "SET s.unitUri = CASE WHEN row.unit_uri IS NOT NULL THEN row.unit_uri ELSE s.unitUri END "
            "WITH s, row "
            "MATCH (p:`PropertyNode` {uri: row.prop_uri}) "
            "MERGE (p)-[:HAS_STATE]->(s)"
        )
        for batch in _chunks(state_nodes, batch_size):
            rows = [
                {
                    "state_uri":    pn.state_uri,
                    "prop_uri":     pn.uri,
                    "value":        pn.value if isinstance(pn.value, (bool, int, float, str)) else str(pn.value),
                    "generated_at": pn.generated_at,
                    "unit_uri":     pn.unit_uri,
                }
                for pn in batch
            ]
            session.run(cypher_state, rows=rows)

    # Write element → property relationships
    if prop_rels:
        cypher_link = (
            "UNWIND $rows AS row "
            "MATCH (e {uri: row.elem_uri}) "
            "MATCH (p:`PropertyNode` {uri: row.prop_uri}) "
            "MERGE (e)-[r:`HAS_PROPERTY`]->(p) "
            "SET r.name = row.rel_name"
        )
        for batch in _chunks(prop_rels, batch_size):
            rows = [
                {
                    "elem_uri": elem_uri,
                    "rel_name": rel_type,
                    "prop_uri": prop_uri,
                }
                for elem_uri, rel_type, prop_uri in batch
            ]
            session.run(cypher_link, rows=rows)

    return total


# ---------------------------------------------------------------------------
# Interface node writer (geometry phase)
# ---------------------------------------------------------------------------

def write_interface_nodes(
    session: "Session",
    interfaces: list[tuple[str, str]],  # [(elem_uri_a, elem_uri_b), ...]
    base_uri: str,
    batch_size: int = 500,
) -> int:
    """
    Create :Interface nodes and INTERFACE_OF relationships for each
    overlapping element pair.

    Parameters
    ----------
    interfaces : list of (uri_a, uri_b) pairs
    base_uri : str
    """
    if not interfaces:
        return 0

    cypher = (
        "UNWIND $rows AS row "
        "MERGE (i:`Interface` {uri: row.iface_uri}) "
        "WITH i, row "
        "MATCH (a {uri: row.uri_a}) "
        "MATCH (b {uri: row.uri_b}) "
        "MERGE (a)-[:INTERFACE_OF]->(i) "
        "MERGE (b)-[:INTERFACE_OF]->(i)"
    )

    total = 0
    for i, batch in enumerate(_chunks(list(interfaces), batch_size)):
        rows = [
            {
                "iface_uri": f"{base_uri}interface_{i}_{j}",
                "uri_a":     a,
                "uri_b":     b,
            }
            for j, (a, b) in enumerate(batch)
        ]
        session.run(cypher, rows=rows)
        total += len(batch)

    return total


# ---------------------------------------------------------------------------
# High-level orchestration
# ---------------------------------------------------------------------------

class Neo4jWriter:
    """
    High-level writer that manages the Neo4j driver and writes a complete
    TraversalResult to the database.
    """

    def __init__(
        self,
        driver: "Driver",
        database: str = "neo4j",
        batch_size: int = 500,
    ) -> None:
        self.driver    = driver
        self.database  = database
        self.batch_size = batch_size

    def setup(self) -> None:
        """Create constraints and indexes."""
        setup_schema(self.driver, self.database)

    def write(self, traversal_result, base_uri: str = "https://linkedbuildingdata.org/building#") -> dict[str, int]:
        """
        Write all nodes and relationships from a TraversalResult.

        Returns a summary dict with counts.
        """
        result = traversal_result
        counts: dict[str, int] = {}

        with self.driver.session(database=self.database) as session:
            with session.begin_transaction() as tx:
                logger.info("Writing %d nodes …", len(result.nodes))
                counts["nodes"] = write_nodes(tx, result.nodes, self.batch_size)

            logger.info("Writing %d relationships …", len(result.rels))
            with session.begin_transaction() as tx:
                counts["rels"] = write_relationships(tx, result.rels, self.batch_size)

            if result.prop_nodes:
                logger.info("Writing %d property nodes …", len(result.prop_nodes))
                with session.begin_transaction() as tx:
                    counts["prop_nodes"] = write_property_nodes(
                        tx, result.prop_nodes, result.prop_rels, self.batch_size
                    )

        logger.info(
            "Write complete — nodes:%d  rels:%d  prop_nodes:%d",
            counts.get("nodes", 0),
            counts.get("rels", 0),
            counts.get("prop_nodes", 0),
        )
        return counts

    def write_interfaces(self, interfaces: list[tuple[str, str]], base_uri: str) -> int:
        """Write interface nodes and relationships."""
        with self.driver.session(database=self.database) as session:
            with session.begin_transaction() as tx:
                return write_interface_nodes(tx, interfaces, base_uri, self.batch_size)

    def close(self) -> None:
        """Close the underlying Neo4j driver."""
        self.driver.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
