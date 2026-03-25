"""
ConversionProperties — mirrors IFCtoLBD v2.44.0 ConversionProperties.java

All flags that control what gets extracted and how it is represented.
Defaults match the Java reference implementation.
"""

from dataclasses import dataclass, field


@dataclass
class ConversionConfig:
    # ── Structural output flags ──────────────────────────────────────────────
    has_building_elements: bool = True
    """Include building elements (walls, doors, slabs, MEP, etc.) in output."""

    has_building_properties: bool = True
    """Extract and attach IfcPropertySet / IfcElementQuantity data."""

    # ── Property representation level ────────────────────────────────────────
    properties_level: int = 1
    """
    Property representation complexity.
      1 (L1) — flat key/value properties on the Neo4j node itself (default)
      2 (L2) — separate Property nodes linked by relationship (OPM-style)
      3 (L3) — L2 + versioned State nodes with prov:generatedAtTime timestamp
    """

    # ── Geometry flags ────────────────────────────────────────────────────────
    has_geometry: bool = False
    """Compute 3-D bounding boxes using ifcopenshell.geom and store on nodes."""

    has_bounding_box_wkt: bool = False
    """
    When has_geometry=True, store bounding box as a 2-D WKT polygon string
    (geo:asWKT) instead of individual x-min/x-max/y-min/y-max/z-min/z-max
    properties.
    """

    has_interfaces: bool = False
    """
    Detect element interfaces by 3-D bounding-box overlap (≤ 0.05 m tolerance)
    and create :Interface nodes with INTERFACE_OF relationships.
    Requires has_geometry=True.
    """

    # ── Geolocation ───────────────────────────────────────────────────────────
    has_geolocation: bool = False
    """
    Extract IfcSite.RefLatitude / RefLongitude and attach as a WKT POINT
    geo:asWKT property on the Site node.
    """

    # ── URI / naming ──────────────────────────────────────────────────────────
    has_hierarchical_naming: bool = False
    """
    When True, the `uri` property of each node encodes the building hierarchy:
      <base>BuildingName/StoreyName/ElementName
    instead of the default GUID-based flat URI.
    """

    base_uri: str = "https://linkedbuildingdata.org/building#"
    """
    Base URI used when constructing the `uri` property stored on every node.
    Must end with '#' or '/'.
    """

    # ── Units ─────────────────────────────────────────────────────────────────
    has_units: bool = False
    """
    Read IfcUnitAssignment and store QUDT unit URIs alongside numeric property
    values.  For L1 this adds a parallel `<prop>_unit` property; for L2/L3 it
    is stored on the Property node.
    """

    # ── Completeness flags ────────────────────────────────────────────────────
    has_non_lbd_element: bool = True
    """
    When True, elements that are not reachable via the spatial hierarchy
    (orphaned elements) are still created as :Element nodes without spatial
    relationships.
    """

    # ── Output model separation ───────────────────────────────────────────────
    has_separate_building_elements_model: bool = False
    """(Reserved for future use — no effect in this Python implementation.)"""

    has_separate_properties_model: bool = False
    """(Reserved for future use — no effect in this Python implementation.)"""

    # ── Performance ───────────────────────────────────────────────────────────
    batch_size: int = 500
    """Number of Cypher parameter rows sent per transaction."""

    geometry_workers: int = 1
    """
    Number of parallel workers for ifcopenshell.geom processing.
    Set > 1 to use multiprocessing for large models.
    """

    # ── IFC OWL sameAs ────────────────────────────────────────────────────────
    export_ifc_owl: bool = False
    """
    When True, store an `ifc_guid` property on every node that can later be
    used to generate owl:sameAs links to a parallel ifcOWL graph.
    (In the Java version this adds `owl:sameAs` triples; here we store the
    GUID so downstream tools can reconstruct the link.)
    """

    def validate(self) -> None:
        """Raise ValueError for invalid combinations."""
        if self.has_interfaces and not self.has_geometry:
            raise ValueError(
                "has_interfaces=True requires has_geometry=True"
            )
        if self.properties_level not in (1, 2, 3):
            raise ValueError(
                f"properties_level must be 1, 2, or 3 (got {self.properties_level})"
            )
        if not self.base_uri.endswith(("#", "/")):
            raise ValueError(
                f"base_uri must end with '#' or '/' (got {self.base_uri!r})"
            )
