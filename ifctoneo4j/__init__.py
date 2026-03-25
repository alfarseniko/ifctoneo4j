"""ifctoneo4j — IFC to LBD Neo4j converter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

_DEFAULT_BASE_URI = "https://linkedbuildingdata.org/building#"


@dataclass
class ParseResult:
    """
    Returned by :func:`ifctoneo4j.parse`.  Pass to :func:`ifctoneo4j.write`.

    Attributes
    ----------
    node_count : int    — total nodes (spatial + elements)
    rel_count  : int    — total relationships
    element_count : int — unique IFC elements processed
    """

    _traversal: Any  # converters.spatial.TraversalResult
    _cfg: Any        # config.ConversionConfig

    @property
    def node_count(self) -> int:
        return len(self._traversal.nodes)

    @property
    def rel_count(self) -> int:
        return len(self._traversal.rels)

    @property
    def element_count(self) -> int:
        return len(self._traversal.seen_guids)

    def __repr__(self) -> str:
        return (
            f"ParseResult(nodes={self.node_count}, "
            f"rels={self.rel_count}, "
            f"elements={self.element_count})"
        )


def parse(
    ifc_path: str,
    *,
    properties_level: int = 1,
    include_units: bool = False,
    base_uri: str = _DEFAULT_BASE_URI,
) -> ParseResult:
    """
    Load an IFC file and traverse the spatial hierarchy.

    No database connection required.

    Parameters
    ----------
    ifc_path : str
        Path to an ``.ifc`` or ``.ifczip`` file.
    properties_level : int
        ``1`` — flat key/value properties on each node (default).
        ``2`` — separate OPM PropertyNode per property.
        ``3`` — OPM PropertyNode + versioned StateNode with timestamp.
    include_units : bool
        Attach QUDT unit URIs to numeric properties (default ``False``).
    base_uri : str
        URI prefix used for all node identifiers.

    Returns
    -------
    ParseResult
        Inspect with ``.node_count``, ``.rel_count``, ``.element_count``.
        Pass to :func:`write` to push to Neo4j.

    Example
    -------
    >>> import ifctoneo4j
    >>> result = ifctoneo4j.parse("model.ifc")
    >>> print(result)
    ParseResult(nodes=187, rels=186, elements=93)
    """
    from .core.ifc_loader import open_ifc
    from .config import ConversionConfig
    from .converters.spatial import traverse

    loaded = open_ifc(ifc_path)
    cfg = ConversionConfig(
        properties_level=properties_level,
        has_units=include_units,
        base_uri=base_uri,
    )
    traversal = traverse(loaded, cfg)
    return ParseResult(_traversal=traversal, _cfg=cfg)


def write(
    result: ParseResult,
    *,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    database: str = "neo4j",
    clear_db: bool = False,
    batch_size: int = 500,
) -> dict[str, int]:
    """
    Write a :class:`ParseResult` to Neo4j.

    Parameters
    ----------
    result : ParseResult
        From :func:`parse`.
    neo4j_uri : str
        Bolt URI, e.g. ``"bolt://localhost:7687"`` or
        ``"neo4j+s://xxxx.databases.neo4j.io"`` for AuraDB.
    neo4j_user : str
        Neo4j username.
    neo4j_password : str
        Neo4j password.
    database : str
        Target database name (default ``"neo4j"``).
    clear_db : bool
        Delete all existing data before writing (default ``False``).
    batch_size : int
        Rows per Neo4j transaction (default ``500``).

    Returns
    -------
    dict[str, int]
        ``{"nodes": N, "rels": M, "prop_nodes": P}``

    Example
    -------
    >>> ifctoneo4j.write(
    ...     result,
    ...     neo4j_uri="bolt://localhost:7687",
    ...     neo4j_user="neo4j",
    ...     neo4j_password="secret",
    ... )
    {'nodes': 187, 'rels': 186, 'prop_nodes': 0}
    """
    from neo4j import GraphDatabase
    from .neo4j.writer import Neo4jWriter
    from .neo4j.schema import drop_all_data

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        if clear_db:
            drop_all_data(driver, database)
        with Neo4jWriter(driver, database=database, batch_size=batch_size) as writer:
            writer.setup()
            counts = writer.write(result._traversal, base_uri=result._cfg.base_uri)
    finally:
        driver.close()

    return counts
