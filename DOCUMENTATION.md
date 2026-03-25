# IFC → Neo4j LBD Converter — Complete Developer Reference

A Python reimplementation of [IFCtoLBD v2.44.0](https://github.com/jyrkioraskari/IFCtoLBD) that converts IFC building models directly to a **Linked Building Data (LBD)** graph in Neo4j using **ifcopenshell** — no RDF, no Turtle files, no intermediate steps.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Installation](#2-installation)
3. [Quick Start](#3-quick-start)
4. [Architecture & Pipeline](#4-architecture--pipeline)
5. [Module Reference](#5-module-reference)
   - 5.1 [config.py — ConversionConfig](#51-configpy--conversionconfig)
   - 5.2 [product_map.py — IFC-to-Label Mapping](#52-product_mappy--ifc-to-label-mapping)
   - 5.3 [core/string_ops.py — String Utilities](#53-corestring_opspy--string-utilities)
   - 5.4 [core/ifc_loader.py — IFC File Loading](#54-coreifc_loaderpy--ifc-file-loading)
   - 5.5 [core/unit_handler.py — QUDT Unit Mapping](#55-coreunit_handlerpy--qudt-unit-mapping)
   - 5.6 [converters/elements.py — Element Classification](#56-converterselementspy--element-classification)
   - 5.7 [converters/properties.py — Property Extraction](#57-converterspropertiespy--property-extraction)
   - 5.8 [converters/spatial.py — Spatial Traversal](#58-convertersspatialpy--spatial-traversal)
   - 5.9 [geometry/bounding_box.py — Geometry & Interfaces](#59-geometrybounding_boxpy--geometry--interfaces)
   - 5.10 [neo4j/schema.py — Database Schema Setup](#510-neo4jschemappy--database-schema-setup)
   - 5.11 [neo4j/writer.py — Batched Neo4j Writes](#511-neo4jwriterpy--batched-neo4j-writes)
   - 5.12 [main.py — CLI Entry Point](#512-mainpy--cli-entry-point)
6. [Neo4j Data Model](#6-neo4j-data-model)
7. [Property Levels (L1 / L2 / L3)](#7-property-levels-l1--l2--l3)
8. [CLI Reference](#8-cli-reference)
9. [Configuration Reference](#9-configuration-reference)
10. [Using as a Python Library](#10-using-as-a-python-library)
11. [Example Cypher Queries](#11-example-cypher-queries)
12. [Running Tests](#12-running-tests)
13. [Design Decisions](#13-design-decisions)

---

## 1. Overview

This converter takes an IFC file (`.ifc` or `.ifczip`) and produces a property graph in Neo4j following the [Building Topology Ontology (BOT)](https://w3id.org/bot) schema. Element types come from three ontologies:

- **BEO** — Building Element Ontology (walls, doors, slabs, beams, …)
- **MEP** — Mechanical, Electrical & Plumbing Ontology (fans, pumps, sensors, …)
- **FURN** — Furniture Ontology (furniture, chairs, tables, …)

The spatial hierarchy produced is:

```
IfcSite  ──[HAS_BUILDING]──►  IfcBuilding
                                   └──[HAS_STOREY]──►  IfcBuildingStorey
                                                            ├──[CONTAINS_ELEMENT]──►  IfcElement
                                                            └──[HAS_SPACE]──►  IfcSpace
                                                                                  ├──[CONTAINS_ELEMENT]──►  IfcElement
                                                                                  └──[ADJACENT_ELEMENT]──►  IfcElement
```

Hosted elements (doors, windows inside walls) add `HAS_SUB_ELEMENT` relationships. Optional geometry phases add bounding boxes and `INTERFACE_OF` nodes.

---

## 2. Installation

**Minimum requirements:**
```
Python >= 3.10
ifcopenshell >= 0.7.0
neo4j >= 5.0.0
```

**Install dependencies:**
```bash
pip install ifcopenshell neo4j

# For geometry extraction and interface detection (optional):
pip install rtree numpy
```

**Clone and set up:**
```bash
git clone <repo>
cd ifc-ai-002
# The package is ifc_to_neo4j/ — no pip install needed, run with python -m
```

---

## 3. Quick Start

**Convert with Neo4j:**
```bash
python -m ifctoneo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j \
    --neo4j-password yourpassword
```

**Dry run (no Neo4j required):**
```bash
python3 test_with_real_ifc.py path/to/model.ifc
```

This prints a full summary of nodes, relationships, property keys, and sample entities without writing anything to the database.

**Neo4j AuraDB (cloud):**
```bash
python -m ifctoneo4j.main model.ifc \
    --neo4j-uri neo4j+s://YOUR-INSTANCE.databases.neo4j.io \
    --neo4j-user YOUR-USERNAME \
    --neo4j-password YOUR-PASSWORD \
    --database YOUR-DATABASE-NAME \
    --clear-db
```

---

## 4. Architecture & Pipeline

The conversion runs in four phases:

```
Phase 1: Load
  open_ifc(path) → LoadedIFC
      └── ifcopenshell.open()
      └── schema version detection (IFC2X3 vs IFC4)

Phase 2: Traverse
  traverse(loaded, cfg) → TraversalResult
      └── Walk Site → Building → Storey → Space → Elements
      └── extract_properties() per element
      └── get_hosted_elements() for doors/windows in walls
      └── get_aggregated_sub_elements() for parts
      └── find_orphaned_elements() for anything outside the hierarchy

Phase 3: Geometry (optional, cfg.has_geometry=True)
  compute_bounding_boxes(model, seen_guids) → dict[guid, BoundingBox]
  attach_geometry_to_nodes(nodes, bbox_map)
  detect_interfaces(bbox_map) → list[(guid_a, guid_b)]

Phase 4: Write
  Neo4jWriter.setup()           → CREATE CONSTRAINT + INDEX DDL
  Neo4jWriter.write(traversal)  → MERGE nodes + MERGE relationships
  Neo4jWriter.write_interfaces() → Interface nodes
```

All intermediate data is plain Python dicts and dataclasses — no RDF, no ontology tooling, no SPARQL.

---

## 5. Module Reference

### 5.1 `config.py` — ConversionConfig

Holds all conversion flags. Passed to every phase of the pipeline.

```python
from ifctoneo4j.config import ConversionConfig
```

#### `ConversionConfig` dataclass

```python
@dataclass
class ConversionConfig:
    has_building_elements:    bool  = True
    has_building_properties:  bool  = True
    properties_level:         int   = 1        # 1, 2, or 3
    has_geometry:             bool  = False
    has_bounding_box_wkt:     bool  = False
    has_interfaces:           bool  = False
    has_geolocation:          bool  = False
    has_hierarchical_naming:  bool  = False
    base_uri:                 str   = "https://linkedbuildingdata.org/building#"
    has_units:                bool  = False
    has_non_lbd_element:      bool  = True
    batch_size:               int   = 500
    geometry_workers:         int   = 1
    export_ifc_owl:           bool  = False
```

| Field | Default | Description |
|---|---|---|
| `has_building_elements` | `True` | Include building elements (walls, doors, etc.) |
| `has_building_properties` | `True` | Extract property sets |
| `properties_level` | `1` | 1=L1 flat, 2=L2 OPM nodes, 3=L3 OPM+states |
| `has_geometry` | `False` | Compute bounding boxes with `ifcopenshell.geom` |
| `has_bounding_box_wkt` | `False` | Store bbox as WKT polygon instead of 6 numbers |
| `has_interfaces` | `False` | Detect overlapping elements → Interface nodes |
| `has_geolocation` | `False` | Extract `IfcSite` lat/lon → `geo_wkt` POINT string |
| `has_hierarchical_naming` | `False` | Use name-based URIs instead of GUID-based |
| `base_uri` | `"https://linkedbuildingdata.org/building#"` | Prefix for all node URIs |
| `has_units` | `False` | Attach QUDT unit URIs to numeric properties |
| `has_non_lbd_element` | `True` | Include elements outside the spatial hierarchy |
| `batch_size` | `500` | Rows per Neo4j transaction |
| `geometry_workers` | `1` | Parallel geometry workers |

#### `ConversionConfig.validate()`

```python
cfg = ConversionConfig(has_interfaces=True, has_geometry=False)
cfg.validate()  # raises ValueError: --interfaces requires --geometry
```

Raises `ValueError` for invalid combinations:
- `has_interfaces=True` without `has_geometry=True`
- `has_bounding_box_wkt=True` without `has_geometry=True`
- `properties_level` not in `{1, 2, 3}`

**Example:**
```python
cfg = ConversionConfig(
    has_building_elements=True,
    has_building_properties=True,
    properties_level=1,
    has_geometry=False,
    has_non_lbd_element=True,
    base_uri="https://mybuilding.org/building#",
    batch_size=1000,
)
cfg.validate()
```

---

### 5.2 `product_map.py` — IFC-to-Label Mapping

Encodes the complete BEO / MEP / FURN ontology class mappings as a static Python dict. Replaces the runtime SPARQL queries over TTL files used in the Java implementation.

```python
from ifctoneo4j.product_map import get_labels, get_namespace, PRODUCT_MAP
```

#### `get_labels(ifc_entity, predefined_type=None) → list[str]`

Returns the ordered list of Neo4j label strings for an IFC element class.

| Parameter | Type | Description |
|---|---|---|
| `ifc_entity` | `str` | IFC class name as returned by `element.is_a()`, e.g. `"IfcWall"` |
| `predefined_type` | `str \| None` | Value of `element.PredefinedType`, e.g. `"SOLIDWALL"`. `None`, `"NOTDEFINED"`, `"USERDEFINED"` are ignored. |

**Returns:** `list[str]` — always starts with `"Element"`, then the specific type label, then the predefined-type subclass label if matched.

```python
get_labels("IfcWall", "SOLIDWALL")
# → ['Element', 'Wall', 'Wall_SOLIDWALL']

get_labels("IfcFan", "AXIAL")
# → ['Element', 'Fan', 'Fan_AXIAL']

get_labels("IfcWall", None)
# → ['Element', 'Wall']

get_labels("IfcWall", "NOTDEFINED")
# → ['Element', 'Wall']   (NOTDEFINED is ignored)

get_labels("IfcProxy", None)
# → ['Element']           (not in PRODUCT_MAP)
```

#### `get_namespace(ifc_entity) → str | None`

Returns the ontology namespace string for an IFC class.

```python
get_namespace("IfcWall")    # → "beo"
get_namespace("IfcFan")     # → "mep"
get_namespace("IfcChair")   # → "furn"
get_namespace("IfcProxy")   # → None
```

#### `PRODUCT_MAP` — Raw mapping dict

```python
PRODUCT_MAP["IfcWall"]
# → {"namespace": "beo", "label": "Wall", "predefined": {"SOLIDWALL": "Wall_SOLIDWALL", ...}}

PRODUCT_MAP["IfcFan"]
# → {"namespace": "mep", "label": "Fan", "predefined": {"AXIAL": "Fan_AXIAL", ...}}
```

The map covers **33 BEO classes**, **49 MEP classes**, and **3 FURN classes**, each with their full predefined-type subclass mappings.

---

### 5.3 `core/string_ops.py` — String Utilities

Exact Python reimplementation of `StringOperations.java` from IFCtoLBD v2.44.0.

```python
from ifctoneo4j.core.string_ops import to_camel_case, property_predicate, attribute_predicate, url_encode_name
```

#### `to_camel_case(name) → str`

Converts a property name string to lowerCamelCase, exactly matching the Java implementation.

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | The raw property name from an IFC property set |

**Returns:** `str` — lowerCamelCase version of the name.

**Rules:**
- Split on non-alphabetic characters (spaces, dots, numbers, etc.)
- All-uppercase tokens (e.g. `"HVAC"`, `"MEP"`) are preserved as-is
- First token is always lowercased
- Subsequent tokens are title-cased
- Accented characters are decomposed and stripped (e.g. `Å` → `A`)
- Empty tokens are filtered out

```python
to_camel_case("Is External")   # → "isExternal"
to_camel_case("Fire Rating")   # → "fireRating"
to_camel_case("Net Floor Area")# → "netFloorArea"
to_camel_case("LoadBearing")   # → "loadbearing"  (no space → treated as one token)
to_camel_case("HVAC")          # → "HVAC"          (all caps preserved)
to_camel_case("Ref. Level")    # → "refLevel"      (dot stripped)
to_camel_case("Ångström")      # → "angstrom"      (accent stripped)
to_camel_case("")              # → ""
to_camel_case("  Fire Rating  ") # → "fireRating"  (leading/trailing spaces handled)
to_camel_case("Level 2")       # → "level"         (numbers stripped)
```

#### `property_predicate(name, is_attribute=False) → str`

Builds the full Neo4j property key for a property set value.

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | Raw property name |
| `is_attribute` | `bool` | If `True`, appends `_attribute_simple` instead of `_property_simple` |

```python
property_predicate("Is External")            # → "isExternal_property_simple"
property_predicate("Fire Rating")            # → "fireRating_property_simple"
property_predicate("GlobalId", is_attribute=True)  # → "globalid_attribute_simple"
```

#### `attribute_predicate(attr_name) → str`

Converts a raw IFC attribute name to its Neo4j property key, applying special rename rules.

Special renames:
- `"name_IfcRoot"` → `"name"` (rdfs:label)
- `"tag_IfcElement"` → `"batid"`

```python
attribute_predicate("name_IfcRoot")   # → "name"
attribute_predicate("tag_IfcElement") # → "batid"
attribute_predicate("ObjectType")     # → "objecttype_attribute_simple"
```

#### `url_encode_name(name) → str`

Encodes a string for use in a URI: spaces become `_`, other unsafe characters are percent-encoded.

```python
url_encode_name("My Building")    # → "My_Building"
url_encode_name("Level1")         # → "Level1"
url_encode_name("Floor (Level 1)")# → "Floor_%28Level_1%29"
```

---

### 5.4 `core/ifc_loader.py` — IFC File Loading

```python
from ifctoneo4j.core.ifc_loader import open_ifc, log_model_summary, LoadedIFC
```

#### `LoadedIFC` dataclass

Container returned by `open_ifc()`.

```python
@dataclass
class LoadedIFC:
    model:          ifcopenshell.file  # The parsed IFC model
    path:           Path               # Absolute path to the file
    schema_raw:     str                # Raw schema string, e.g. "IFC2X3"
    schema_version: str                # Normalised version, e.g. "IFC2X3_TC1"
    is_ifc2x3:      bool               # True if IFC2x3, False if IFC4/IFC4x3
    file_name:      str                # Filename without path
```

#### `open_ifc(path) → LoadedIFC`

Opens and parses an IFC or IFCzip file using ifcopenshell.

| Parameter | Type | Description |
|---|---|---|
| `path` | `str \| Path` | Path to `.ifc` or `.ifczip` file |

**Returns:** `LoadedIFC`

**Raises:** `FileNotFoundError`, `Exception` (ifcopenshell parse errors)

```python
from ifctoneo4j.core.ifc_loader import open_ifc

loaded = open_ifc("model.ifc")
print(loaded.schema_version)  # "IFC4"
print(loaded.is_ifc2x3)       # False
print(loaded.file_name)       # "model.ifc"

# Access the raw ifcopenshell model
walls = loaded.model.by_type("IfcWall")
```

#### `log_model_summary(loaded)`

Logs a summary of the loaded model to the Python logger (INFO level): entity type counts, schema version, file size.

```python
log_model_summary(loaded)
# 10:23:45  INFO  ifc_loader — Schema: IFC4
# 10:23:45  INFO  ifc_loader — IfcWall: 42
# 10:23:45  INFO  ifc_loader — IfcDoor: 18
# ...
```

#### `normalise_schema(raw_schema) → str`

Normalises the schema string from the IFC file header.

```python
normalise_schema("IFC2X3")     # → "IFC2X3"
normalise_schema("IFC4")       # → "IFC4"
normalise_schema("IFC4X3_ADD2")# → "IFC4X3_ADD2"
```

#### `is_ifc2x3(schema_normalised) → bool`

Returns `True` for IFC2X3 schemas, `False` for IFC4 and later.

```python
is_ifc2x3("IFC2X3")    # → True
is_ifc2x3("IFC4")      # → False
is_ifc2x3("IFC4X3")    # → False
```

---

### 5.5 `core/unit_handler.py` — QUDT Unit Mapping

Builds a project-level unit map from `IfcUnitAssignment` and resolves QUDT unit URIs for property values.

```python
from ifctoneo4j.core.unit_handler import build_unit_map, get_unit_for_property
```

#### `build_unit_map(ifc_model) → dict[str, str]`

Reads `IfcProject.UnitsInContext.Units` and returns a mapping of unit type → QUDT URI.

| Parameter | Type | Description |
|---|---|---|
| `ifc_model` | `ifcopenshell.file` | The parsed IFC model |

**Returns:** `dict[str, str]` — keys are IFC unit type strings (e.g. `"LENGTHUNIT"`), values are QUDT URIs.

```python
unit_map = build_unit_map(loaded.model)
# {
#   "LENGTHUNIT":      "http://qudt.org/vocab/unit/M",
#   "AREAUNIT":        "http://qudt.org/vocab/unit/M2",
#   "VOLUMEUNIT":      "http://qudt.org/vocab/unit/M3",
#   "MASSUNIT":        "http://qudt.org/vocab/unit/KiloGM",
#   "THERMODYNAMICTEMPERATUREUNIT": "http://qudt.org/vocab/unit/DEG_C",
#   "TIMEUNIT":        "http://qudt.org/vocab/unit/SEC",
#   "PLANEANGLEUNIT":  "http://qudt.org/vocab/unit/DEG",
# }
```

If the model has no unit assignment, returns an empty dict.

#### `get_unit_for_property(unit_map, ifc_unit=None, unit_type_hint=None) → str | None`

Resolves the QUDT URI for a specific property, considering:
1. An explicit `IfcUnit` on the property (overrides project default)
2. A unit type hint (e.g. `"LENGTHUNIT"` from quantity class name)
3. Project-level default from `unit_map`

| Parameter | Type | Description |
|---|---|---|
| `unit_map` | `dict[str, str]` | From `build_unit_map()` |
| `ifc_unit` | `ifcopenshell entity \| None` | Explicit unit from `IfcPropertySingleValue.Unit` |
| `unit_type_hint` | `str \| None` | Unit type string for lookup, e.g. `"LENGTHUNIT"` |

**Returns:** `str | None` — QUDT URI or `None` if not resolvable.

```python
uri = get_unit_for_property(unit_map, unit_type_hint="LENGTHUNIT")
# → "http://qudt.org/vocab/unit/M"

uri = get_unit_for_property(unit_map, unit_type_hint="AREAUNIT")
# → "http://qudt.org/vocab/unit/M2"

uri = get_unit_for_property({})  # empty unit map
# → None
```

---

### 5.6 `converters/elements.py` — Element Classification

Handles classification of IFC elements into Neo4j labels, URI construction, and node/relationship dict creation.

```python
from ifctoneo4j.converters.elements import (
    build_element_uri,
    classify_element,
    make_spatial_node,
    make_element_node,
    make_relationship,
    get_hosted_elements,
    get_aggregated_sub_elements,
    find_orphaned_elements,
)
```

#### `build_element_uri(element, base_uri, hierarchical=False, parent_uri=None) → str`

Constructs a unique URI string for an IFC element.

| Parameter | Type | Description |
|---|---|---|
| `element` | `ifcopenshell entity` | The IFC element |
| `base_uri` | `str` | Base URI prefix |
| `hierarchical` | `bool` | Use name-based path instead of GUID-based |
| `parent_uri` | `str \| None` | Parent URI for hierarchical naming |

**Standard (GUID-based):** `<base_uri><ifcclass_lowercase>_<GlobalId>`
**Hierarchical:** `<parent_uri>/<url_encoded_name>` or `<base_uri><url_encoded_name>` if no parent

```python
BASE = "https://mybuilding.org/building#"

# Standard URI (default)
build_element_uri(wall, BASE)
# → "https://mybuilding.org/building#ifcwall_3cUkl32yn8xA7kQ..."

# Hierarchical URI
build_element_uri(wall, BASE, hierarchical=True, parent_uri=BASE + "GroundFloor")
# → "https://mybuilding.org/building#GroundFloor/North_Wall"

# Fallback if no GlobalId
build_element_uri(wall_no_guid, BASE)
# → "https://mybuilding.org/building#ifcwall_<id(element)>"
```

#### `classify_element(element) → list[str]`

Returns the full list of Neo4j labels for an IFC element using the product map.

| Parameter | Type | Description |
|---|---|---|
| `element` | `ifcopenshell entity` | The IFC element |

**Returns:** `list[str]` — ordered: `"Element"` first, then specific type, then predefined-type subclass.

```python
classify_element(wall)   # wall.is_a() == "IfcWall", wall.PredefinedType == "SOLIDWALL"
# → ['Element', 'Wall', 'Wall_SOLIDWALL']

classify_element(fan)    # fan.is_a() == "IfcFan", fan.PredefinedType == None
# → ['Element', 'Fan']

classify_element(proxy)  # proxy.is_a() == "IfcProxy"
# → ['Element']
```

#### `make_spatial_node(element, ifc_type, base_uri, hierarchical=False, parent_uri=None) → dict`

Creates a node dict for a spatial structure element (Site, Building, Storey, Space).

| Parameter | Type | Description |
|---|---|---|
| `element` | `ifcopenshell entity` | `IfcSite`, `IfcBuilding`, `IfcBuildingStorey`, or `IfcSpace` |
| `ifc_type` | `str` | Label string: `"Site"`, `"Building"`, `"Storey"`, or `"Space"` |
| `base_uri` | `str` | Base URI prefix |
| `hierarchical` | `bool` | Use hierarchical naming |
| `parent_uri` | `str \| None` | Parent URI for hierarchical naming |

**Returns:**
```python
{
    "uri":    "https://...building#ifcsite_GUID",
    "labels": ["Site"],
    "props":  {
        "globalId":   "3cUkl32yn8x...",
        "name":       "Default Site",
        "description": None,              # omitted if None
        "elevation":  0.0,                # IfcBuildingStorey only
        "ifcType":    "IfcSite",
    }
}
```

```python
site_node = make_spatial_node(ifc_site, "Site", "https://mybuilding.org/building#")
print(site_node["uri"])           # "https://mybuilding.org/building#ifcsite_SITE001"
print(site_node["labels"])        # ["Site"]
print(site_node["props"]["name"]) # "Site A"

storey_node = make_spatial_node(ifc_storey, "Storey", BASE)
print(storey_node["props"]["elevation"])  # 0.0
```

#### `make_element_node(element, base_uri, hierarchical=False, parent_uri=None) → dict`

Creates a node dict for a building element.

**Returns:** Same structure as `make_spatial_node`, but with labels from `classify_element()` and `ifcType` from `element.is_a()`.

```python
wall_node = make_element_node(ifc_wall, "https://mybuilding.org/building#")
print(wall_node["labels"])          # ['Element', 'Wall', 'Wall_SOLIDWALL']
print(wall_node["props"]["globalId"]) # "W001"
print(wall_node["props"]["name"])     # "North Wall"
print(wall_node["uri"])               # "https://...#ifcwall_W001"
```

#### `make_relationship(from_uri, rel_type, to_uri, props=None) → dict`

Creates a relationship dict.

| Parameter | Type | Description |
|---|---|---|
| `from_uri` | `str` | URI of the source node |
| `rel_type` | `str` | Relationship type string |
| `to_uri` | `str` | URI of the target node |
| `props` | `dict \| None` | Optional relationship properties |

**Returns:**
```python
{
    "from_uri": "https://...#ifcbuildingstorey_FLOOR01",
    "rel_type": "HAS_SPACE",
    "to_uri":   "https://...#ifcspace_SPACE001",
    "props":    {}
}
```

```python
rel = make_relationship(storey_uri, "HAS_SPACE", space_uri)
rel_with_props = make_relationship(elem_a, "ADJACENT_ELEMENT", elem_b, {"weight": 1.0})
```

#### `get_hosted_elements(element, base_uri, hierarchical=False) → list[tuple]`

Finds elements hosted inside another element via `IfcRelVoidsElement` → `IfcRelFillsElement`.

The typical use case is doors and windows hosted inside walls.

| Parameter | Type | Description |
|---|---|---|
| `element` | `ifcopenshell entity` | Host element (typically a wall) |
| `base_uri` | `str` | Base URI |
| `hierarchical` | `bool` | Use hierarchical naming |

**Returns:** `list[tuple[ifcopenshell entity, str]]` — list of `(fill_element, host_element_uri)` pairs.

```python
results = get_hosted_elements(ifc_wall, BASE)
for fill_element, host_uri in results:
    print(fill_element.is_a())  # "IfcDoor" or "IfcWindow"
    print(host_uri)             # URI of the wall
# Caller then calls process_element(fill, host_uri, "HAS_SUB_ELEMENT")
```

Returns `[]` if the element has no openings.

#### `get_aggregated_sub_elements(element, base_uri, hierarchical=False) → list[tuple]`

Finds sub-elements via `IfcRelAggregates` (e.g. `IfcBuildingElementPart` inside a wall).

**Returns:** `list[tuple[ifcopenshell entity, str]]` — `(sub_element, parent_uri)` pairs.

```python
results = get_aggregated_sub_elements(ifc_wall, BASE)
for sub_elem, parent_uri in results:
    print(sub_elem.is_a())  # "IfcBuildingElementPart"
```

#### `find_orphaned_elements(ifc_model, seen_guids) → list`

Scans the entire model for elements not reachable via the spatial hierarchy.

| Parameter | Type | Description |
|---|---|---|
| `ifc_model` | `ifcopenshell.file` | The parsed IFC model |
| `seen_guids` | `set[str]` | GlobalIds already processed by the traversal |

**Returns:** `list[ifcopenshell entity]` — elements with GlobalIds not in `seen_guids`.

```python
orphans = find_orphaned_elements(loaded.model, traversal.seen_guids)
print(f"Found {len(orphans)} orphaned elements")
for elem in orphans:
    print(elem.is_a(), elem.GlobalId)
```

---

### 5.7 `converters/properties.py` — Property Extraction

Extracts IFC property sets and direct attributes from elements, returning structured output for L1, L2, or L3 property representation.

```python
from ifctoneo4j.converters.properties import extract_properties, PropertyGraph, PropertyNode
```

#### `PropertyNode` dataclass

Represents a single OPM property node (used in L2 and L3 modes).

```python
@dataclass
class PropertyNode:
    uri:          str           # Unique URI for this property node
    prop_name:    str           # camelCase property name
    value:        Any           # Actual value (bool, int, float, str)
    unit_uri:     str | None    # QUDT unit URI (if has_units=True)
    state_uri:    str | None    # L3 only: URI of the PropertyStateNode
    generated_at: str | None    # L3 only: ISO-8601 timestamp string
```

#### `PropertyGraph` dataclass

Container for all graph data produced from one element's property sets.

```python
@dataclass
class PropertyGraph:
    flat_props:      dict[str, Any]           # L1: key → value
    property_nodes:  list[PropertyNode]        # L2/L3: OPM Property nodes
    property_rels:   list[tuple[str, str, str]] # L2/L3: (elem_uri, rel_type, prop_uri)
```

In L1 mode only `flat_props` is populated. In L2/L3 mode all three fields are populated.

#### `extract_properties(element, element_uri, unit_map, level=1, has_units=False, base_uri=..., timestamp=None) → PropertyGraph`

Extracts all property data from an IFC element.

| Parameter | Type | Description |
|---|---|---|
| `element` | `ifcopenshell entity` | The IFC element |
| `element_uri` | `str` | URI for this element (used as foreign key in L2/L3 rels) |
| `unit_map` | `dict[str, str]` | From `build_unit_map()` |
| `level` | `int` | 1, 2, or 3 |
| `has_units` | `bool` | Attach QUDT unit URIs |
| `base_uri` | `str` | Base URI for property node URIs |
| `timestamp` | `str \| None` | ISO-8601 datetime for L3 states. Defaults to `datetime.now()`. |

**Property sources walked (in order):**
1. `element.IsDefinedBy` → `IfcPropertySet` and `IfcElementQuantity`
2. `element.IsTypedBy` → type object's `HasPropertySets`
3. Direct IFC attributes: `Name`, `Description`, `ObjectType`, `Tag`, `PredefinedType`, `LongName`, `Elevation`

**L1 example:**
```python
unit_map = build_unit_map(loaded.model)
pg = extract_properties(ifc_wall, "https://...#ifcwall_W001", unit_map, level=1)

pg.flat_props
# {
#   "globalId":                    "3cUkl32yn8x...",
#   "name":                        "North Wall",
#   "isExternal_property_simple":  True,
#   "fireRating_property_simple":  "60 min",
#   "loadBearing_property_simple": True,
#   "objectType_attribute_simple": "Standard Wall",
# }
```

**L2 example:**
```python
pg = extract_properties(ifc_wall, wall_uri, unit_map, level=2)

pg.property_nodes[0]
# PropertyNode(
#   uri="https://...#isExternal_3cUkl32yn8x...",
#   prop_name="isExternal",
#   value=True,
#   unit_uri=None,
#   state_uri=None,
#   generated_at=None,
# )

pg.property_rels[0]
# ("https://...#ifcwall_W001", "HAS_PROPERTY_ISEXTERNAL", "https://...#isExternal_W001")
```

**L3 example:**
```python
pg = extract_properties(ifc_wall, wall_uri, unit_map, level=3,
                        timestamp="2024-01-15T10:30:00+00:00")

pg.property_nodes[0]
# PropertyNode(
#   uri="https://...#isExternal_W001",
#   prop_name="isExternal",
#   value=True,
#   unit_uri=None,
#   state_uri="https://...#state_isExternal_W001_p0",
#   generated_at="2024-01-15T10:30:00+00:00",
# )
```

**With units:**
```python
pg = extract_properties(ifc_space, space_uri, unit_map, level=1, has_units=True)

pg.flat_props
# {
#   "netFloorArea_property_simple":       42.5,
#   "netFloorArea_property_simple_unit":  "http://qudt.org/vocab/unit/M2",
#   "grossVolume_property_simple":        127.5,
#   "grossVolume_property_simple_unit":   "http://qudt.org/vocab/unit/M3",
# }
```

**Special attribute rules:**
- `Name` → `"name"` key (rdfs:label equivalent)
- `GlobalId` → `"globalId"` key (always stored as flat prop regardless of level)
- `Tag` → `"batid"` key
- `Description` → `"description"` key
- All others → `"<camelCase>_attribute_simple"`
- `RefLatitude` / `RefLongitude` / `RefElevation` → skipped (handled by geolocation phase)
- `"NOTDEFINED"` and `"$"` values are skipped

---

### 5.8 `converters/spatial.py` — Spatial Traversal

The core traversal engine. Walks the complete IFC spatial hierarchy and produces all nodes and relationships.

```python
from ifctoneo4j.converters.spatial import traverse, TraversalResult
```

#### `TraversalResult` dataclass

```python
@dataclass
class TraversalResult:
    nodes:      list[dict]    # All node dicts (spatial + element)
    rels:       list[dict]    # All relationship dicts
    seen_guids: set[str]      # GlobalIds of all processed elements
    prop_nodes: list          # list[PropertyNode] for L2/L3
    prop_rels:  list[tuple]   # L2/L3 element→property relationships
```

**Methods:**

`add_node(node)` — Appends a node dict and records its `globalId` in `seen_guids`.

`add_rel(rel)` — Appends a relationship dict.

#### `traverse(ifc_loaded, cfg) → TraversalResult`

Walks the complete IFC spatial hierarchy.

| Parameter | Type | Description |
|---|---|---|
| `ifc_loaded` | `LoadedIFC` | From `open_ifc()` |
| `cfg` | `ConversionConfig` | Conversion configuration |

**Returns:** `TraversalResult`

**Traversal order:**
1. `model.by_type("IfcSite")` — all sites
2. Per site: `IsDecomposedBy` → `IfcBuilding`
3. Per building: `IsDecomposedBy` → `IfcBuildingStorey`
4. Per storey: `ContainsElements` → direct storey elements
5. Per storey: `IsDecomposedBy` → `IfcSpace`
6. Per space: `ContainsElements` → space elements
7. Per space: `BoundedBy` → adjacent boundary elements
8. Per element: recurse into hosted elements (`HasOpenings` → `HasFillings`)
9. Per element: recurse into aggregated sub-elements (`IsDecomposedBy`)
10. Orphan scan: `model.by_type("IfcElement")` minus `seen_guids`

**Deduplication:** Elements shared between multiple spaces (via `ADJACENT_ELEMENT`) are only created once; only the relationship is added for subsequent references.

```python
from ifctoneo4j.core.ifc_loader import open_ifc
from ifctoneo4j.config import ConversionConfig
from ifctoneo4j.converters.spatial import traverse

loaded = open_ifc("model.ifc")
cfg = ConversionConfig(
    has_building_elements=True,
    has_building_properties=True,
    properties_level=1,
)

result = traverse(loaded, cfg)

print(f"Nodes:         {len(result.nodes)}")
print(f"Relationships: {len(result.rels)}")
print(f"Elements seen: {len(result.seen_guids)}")

# Inspect a node
wall_nodes = [n for n in result.nodes if "Wall" in n.get("labels", [])]
print(wall_nodes[0])
# {
#   "uri": "https://...#ifcwall_W001",
#   "labels": ["Element", "Wall"],
#   "props": {
#     "globalId": "W001",
#     "name": "North Wall",
#     "isExternal_property_simple": True,
#   }
# }

# Inspect a relationship
print(result.rels[0])
# {
#   "from_uri": "https://...#ifcsite_SITE001",
#   "rel_type": "HAS_BUILDING",
#   "to_uri":   "https://...#ifcbuilding_BLD001",
#   "props":    {}
# }
```

**Internal helper functions (not public API):**

- `_decomposed_objects(spatial_element)` — Returns objects via `IsDecomposedBy`. Works for both IFC2X3 (`IfcRelDecomposes`) and IFC4 (`IfcRelAggregates`).
- `_contained_elements(spatial_element)` — Returns elements via `ContainsElements` → `RelatedElements`.
- `_adjacent_elements(space)` — Returns elements via `BoundedBy` → `RelatedBuildingElement`.

---

### 5.9 `geometry/bounding_box.py` — Geometry & Interfaces

Optional geometry phase. Requires `ifcopenshell.geom` (bundled with ifcopenshell) and optionally `rtree` for interface detection.

```python
from ifctoneo4j.geometry.bounding_box import (
    BoundingBox,
    compute_bounding_boxes,
    attach_geometry_to_nodes,
    detect_interfaces,
    extract_geolocation,
    INTERFACE_TOLERANCE,
)
```

`INTERFACE_TOLERANCE = 0.05` metres — default expansion for interface detection.

#### `BoundingBox` dataclass

```python
@dataclass
class BoundingBox:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float
```

**Methods:**

`expanded(tol) → BoundingBox` — Returns a copy expanded by `tol` in all 6 directions.
```python
bb = BoundingBox(0, 5, 1, 4, 0, 3)
bb.expanded(0.05)
# → BoundingBox(x_min=-0.05, x_max=5.05, y_min=0.95, y_max=4.05, z_min=-0.05, z_max=3.05)
```

`to_props() → dict` — Returns flat property dict for Neo4j.
```python
bb.to_props()
# → {"bbox_x_min": 0.0, "bbox_x_max": 5.0, "bbox_y_min": 1.0, "bbox_y_max": 4.0,
#    "bbox_z_min": 0.0, "bbox_z_max": 3.0}
```

`to_wkt_polygon() → str` — Returns 2D footprint as WKT polygon (X/Y plane).
```python
bb.to_wkt_polygon()
# → "POLYGON((0.0 1.0, 5.0 1.0, 5.0 4.0, 0.0 4.0, 0.0 1.0))"
```

#### `compute_bounding_boxes(ifc_model, seen_guids=None) → dict[str, BoundingBox]`

Computes bounding boxes for all IFC elements using `ifcopenshell.geom`.

| Parameter | Type | Description |
|---|---|---|
| `ifc_model` | `ifcopenshell.file` | The parsed IFC model |
| `seen_guids` | `set[str] \| None` | Only process these GUIDs. `None` processes all. |

**Returns:** `dict[str, BoundingBox]` — mapping of GlobalId → BoundingBox. Elements with no geometry (e.g. abstract elements) are omitted.

Requires `ifcopenshell.geom` and `numpy`. Returns `{}` with a logged error if unavailable.

```python
bbox_map = compute_bounding_boxes(loaded.model, traversal.seen_guids)
print(f"Got bboxes for {len(bbox_map)} elements")

bb = bbox_map["3cUkl32yn8xA7kQ..."]
print(f"Wall height: {bb.z_max - bb.z_min:.2f}m")
```

#### `attach_geometry_to_nodes(nodes, bbox_map, as_wkt=False) → None`

Mutates node dicts in-place to add bounding box data.

| Parameter | Type | Description |
|---|---|---|
| `nodes` | `list[dict]` | Node dicts from traversal (modified in-place) |
| `bbox_map` | `dict[str, BoundingBox]` | From `compute_bounding_boxes()` |
| `as_wkt` | `bool` | If `True`, adds `bbox_wkt` polygon. If `False`, adds 6 individual properties. |

```python
# Mode A: WKT polygon (as_wkt=True)
attach_geometry_to_nodes(result.nodes, bbox_map, as_wkt=True)
# node["props"]["bbox_wkt"] → "POLYGON((...))"

# Mode B: Individual properties (as_wkt=False, default)
attach_geometry_to_nodes(result.nodes, bbox_map, as_wkt=False)
# node["props"]["bbox_x_min"] → 0.0
# node["props"]["bbox_x_max"] → 5.0
# node["props"]["bbox_y_min"] → 1.0  ... etc.
```

#### `detect_interfaces(bbox_map, tolerance=0.05) → list[tuple[str, str]]`

Detects pairs of elements whose bounding boxes overlap (within `tolerance`) using an RTree spatial index.

| Parameter | Type | Description |
|---|---|---|
| `bbox_map` | `dict[str, BoundingBox]` | From `compute_bounding_boxes()` |
| `tolerance` | `float` | Expansion distance in metres. Default `0.05`. |

**Returns:** `list[tuple[str, str]]` — unique, order-independent pairs of `(guid_a, guid_b)`.

Requires `rtree`. Returns `[]` with a logged error if unavailable.

```python
interfaces = detect_interfaces(bbox_map, tolerance=0.05)
print(f"Found {len(interfaces)} element interfaces")

for guid_a, guid_b in interfaces[:3]:
    print(f"Interface: {guid_a} ↔ {guid_b}")
```

#### `extract_geolocation(site) → str | None`

Reads `IfcSite.RefLatitude` and `RefLongitude` and converts to a WKT POINT string.

IFC stores coordinates as `IfcCompoundPlaneAngleMeasure`: a 4-element sequence of `(degrees, minutes, seconds, millionths_of_seconds)`.

| Parameter | Type | Description |
|---|---|---|
| `site` | `ifcopenshell entity` | An `IfcSite` entity |

**Returns:** `str | None` — `"POINT (<lon> <lat>)"` or `None` if data unavailable.

```python
wkt = extract_geolocation(ifc_site)
# → "POINT (-6.25 53.333333)"  (longitude first, per WKT convention)

# None if coordinates not set
wkt = extract_geolocation(site_without_coords)
# → None
```

---

### 5.10 `neo4j/schema.py` — Database Schema Setup

Creates Neo4j constraints and indexes. Run once before the first write.

```python
from ifctoneo4j.neo4j.schema import setup_schema, drop_all_data
```

#### `setup_schema(driver, database="neo4j") → None`

Creates uniqueness constraints on `uri` for all label types, and indexes on `globalId` and `ifcType`.

All DDL uses `IF NOT EXISTS` for idempotent re-runs.

| Parameter | Type | Description |
|---|---|---|
| `driver` | `neo4j.Driver` | Connected Neo4j driver |
| `database` | `str` | Target database name |

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
setup_schema(driver, database="neo4j")
# Creates constraints: unique_site_uri, unique_building_uri, unique_element_uri, ...
# Creates indexes: idx_site_globalid, idx_element_ifctype, ...
driver.close()
```

Constraints created for these labels:
- Spatial: `Site`, `Building`, `Storey`, `Space`
- BEO: `Element`, `Wall`, `Door`, `Slab`, `Beam`, `Column`, `Roof`, `Stair`, `Window`, ... (33 types)
- MEP: `Fan`, `Pump`, `Sensor`, `Valve`, `Boiler`, `Chiller`, ... (49 types)
- Optional: `Interface`, `PropertyNode`, `PropertyStateNode`

#### `drop_all_data(driver, database="neo4j") → None`

Deletes ALL nodes and relationships from the database.

**Use with caution — intended for development/testing only.**

```python
drop_all_data(driver, database="neo4j")
# Runs: MATCH (n) DETACH DELETE n
```

---

### 5.11 `neo4j/writer.py` — Batched Neo4j Writes

```python
from ifctoneo4j.neo4j.writer import (
    Neo4jWriter,
    write_nodes,
    write_relationships,
    write_property_nodes,
    write_interface_nodes,
)
```

#### `Neo4jWriter` class

High-level orchestrator. Manages driver lifecycle and writes a complete `TraversalResult`.

```python
class Neo4jWriter:
    def __init__(self, driver, database="neo4j", batch_size=500): ...
    def setup(self) -> None: ...
    def write(self, traversal_result, base_uri=...) -> dict[str, int]: ...
    def write_interfaces(self, interfaces, base_uri) -> int: ...
    def close(self) -> None: ...
    # Context manager: __enter__ / __exit__ (calls close)
```

**`setup()`** — Calls `setup_schema()` to create constraints and indexes.

**`write(traversal_result, base_uri) → dict[str, int]`** — Writes nodes and relationships in separate transactions. Returns count dict: `{"nodes": N, "rels": M, "prop_nodes": P}`.

**`write_interfaces(interfaces, base_uri) → int`** — Creates `:Interface` nodes and `INTERFACE_OF` relationships.

**`close()`** — Closes the Neo4j driver.

```python
from neo4j import GraphDatabase
from ifctoneo4j.neo4j.writer import Neo4jWriter

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))

with Neo4jWriter(driver, database="neo4j", batch_size=500) as writer:
    writer.setup()                          # DDL: constraints + indexes
    counts = writer.write(result)           # Write nodes + rels
    print(f"Nodes:    {counts['nodes']}")
    print(f"Rels:     {counts['rels']}")
    print(f"PropNodes:{counts.get('prop_nodes', 0)}")

    if interfaces:
        n = writer.write_interfaces(interfaces, cfg.base_uri)
        print(f"Interfaces: {n}")
```

#### `write_nodes(session, nodes, batch_size=500) → int`

Writes node dicts to Neo4j using `MERGE` on `uri`.

- Groups nodes by label set to generate efficient per-label-set Cypher
- Backtick-escapes labels to handle underscores and special characters
- Sanitises all property values (none → skipped, non-scalar → `str()`)

**Cypher pattern:**
```cypher
UNWIND $rows AS row
MERGE (n:`Element`:`Wall`:`Wall_SOLIDWALL` {uri: row.uri})
SET n += row.props
SET n.uri = row.uri
```

```python
with driver.session(database="neo4j") as session:
    with session.begin_transaction() as tx:
        n = write_nodes(tx, result.nodes, batch_size=500)
        print(f"Wrote {n} nodes")
```

#### `write_relationships(session, rels, batch_size=500) → int`

Writes relationship dicts using `MERGE`.

- Groups by `rel_type` for batching
- Sanitises relationship type name (spaces and hyphens → underscore, uppercase)

**Cypher pattern:**
```cypher
UNWIND $rows AS row
MATCH (a {uri: row.from_uri})
MATCH (b {uri: row.to_uri})
MERGE (a)-[r:`HAS_SPACE`]->(b)
SET r += row.props
```

```python
with driver.session(database="neo4j") as session:
    with session.begin_transaction() as tx:
        n = write_relationships(tx, result.rels, batch_size=500)
        print(f"Wrote {n} relationships")
```

#### `write_property_nodes(session, prop_nodes, prop_rels, batch_size=500) → int`

Writes OPM-style `PropertyNode` and `PropertyStateNode` records (L2/L3 modes).

- Creates `:PropertyNode` nodes with `propName`, `value`, `unitUri`
- For L3: creates `:PropertyStateNode` nodes with `value`, `generatedAt`, `unitUri`; links via `HAS_STATE`
- Links elements to property nodes via `HAS_PROPERTY`

```python
with driver.session(database="neo4j") as session:
    with session.begin_transaction() as tx:
        n = write_property_nodes(tx, result.prop_nodes, result.prop_rels)
        print(f"Wrote {n} property nodes")
```

#### `write_interface_nodes(session, interfaces, base_uri, batch_size=500) → int`

Creates `:Interface` nodes and `INTERFACE_OF` relationships for each overlapping element pair.

**Cypher pattern:**
```cypher
UNWIND $rows AS row
MERGE (i:`Interface` {uri: row.iface_uri})
WITH i, row
MATCH (a {uri: row.uri_a})
MATCH (b {uri: row.uri_b})
MERGE (a)-[:INTERFACE_OF]->(i)
MERGE (b)-[:INTERFACE_OF]->(i)
```

---

### 5.12 `main.py` — CLI Entry Point

The CLI orchestrates all four phases: load, traverse, geometry (optional), write.

```python
# Entry point: python -m ifctoneo4j.main
from ifctoneo4j.main import run, build_parser, main
```

#### `build_parser() → argparse.ArgumentParser`

Returns the argument parser with all CLI flags.

#### `run(args) → int`

Executes the full conversion pipeline. Returns `0` on success, `1` on error.

Internally calls:
1. `open_ifc(args.ifc_file)`
2. `traverse(loaded, cfg)`
3. (optional) `compute_bounding_boxes()`, `attach_geometry_to_nodes()`, `detect_interfaces()`
4. (optional) `extract_geolocation()` per site
5. `GraphDatabase.driver()` with connectivity verification
6. `drop_all_data()` if `--clear-db`
7. `Neo4jWriter.setup()`, `Neo4jWriter.write()`, `Neo4jWriter.write_interfaces()`

#### `main() → None`

Entry point called by `python -m ifctoneo4j.main`. Parses args, sets up logging, calls `run()`, and exits with its return code.

---

## 6. Neo4j Data Model

### Node Labels

| Label | Source Ontology | Description |
|---|---|---|
| `Site` | BOT | `IfcSite` — top of spatial hierarchy |
| `Building` | BOT | `IfcBuilding` |
| `Storey` | BOT | `IfcBuildingStorey` |
| `Space` | BOT | `IfcSpace` |
| `Element` | BOT | Any `IfcElement` — always applied |
| `Wall`, `Door`, `Slab`, `Beam`, `Column`, … | BEO | Specific building element type |
| `Wall_SOLIDWALL`, `Fan_AXIAL`, … | BEO/MEP | Predefined-type subclass |
| `Fan`, `Pump`, `Sensor`, `Valve`, `Boiler`, … | MEP | MEP distribution element type |
| `Furniture`, `Chair`, `Table` | FURN | Furnishing element type |
| `Interface` | BOT | Element interface (geometry overlap) |
| `PropertyNode` | OPM | Property value node (L2/L3) |
| `PropertyStateNode` | OPM | Versioned property state (L3 only) |

### Relationship Types

| Relationship | BOT Mapping | Description |
|---|---|---|
| `HAS_BUILDING` | `bot:hasBuilding` | Site → Building |
| `HAS_STOREY` | `bot:hasStorey` | Building → Storey |
| `HAS_SPACE` | `bot:hasSpace` | Storey → Space |
| `CONTAINS_ELEMENT` | `bot:containsElement` | Storey/Space → Element |
| `ADJACENT_ELEMENT` | `bot:adjacentElement` | Space → bounding Element |
| `HAS_SUB_ELEMENT` | `bot:hasSubElement` | Host element → hosted/sub element |
| `INTERFACE_OF` | `bot:interfaceOf` | Element → Interface node |
| `HAS_PROPERTY` | — | Element → PropertyNode (L2/L3) |
| `HAS_STATE` | `opm:hasPropertyState` | PropertyNode → StateNode (L3) |

### Node Properties

Every node has:
- `uri` — unique identifier (indexed, uniqueness constraint)
- `globalId` — IFC GlobalId (indexed)

Spatial nodes additionally have:
- `name`, `description`, `ifcType`
- `elevation` (Storey only)
- `geo_wkt` (Site only, if `--geolocation`)

Element nodes additionally have:
- `name`, `description`, `ifcType`, `batid` (if Tag present)
- `<camelCase>_property_simple` — one per property set value (L1)
- `<camelCase>_attribute_simple` — for IFC attributes
- `bbox_x_min`, `bbox_x_max`, … (if `--geometry`)
- `bbox_wkt` (if `--geometry --wkt-bbox`)

---

## 7. Property Levels (L1 / L2 / L3)

### L1 — Flat Properties (default)

Properties are stored directly on the element node as `<camelCase>_property_simple`:

```cypher
(:Wall {
  uri: "https://...#ifcwall_W001",
  globalId: "W001",
  name: "North Wall",
  isExternal_property_simple: true,
  fireRating_property_simple: "60 min",
  loadBearing_property_simple: true,
  netFloorArea_property_simple: 42.5,
  netFloorArea_property_simple_unit: "http://qudt.org/vocab/unit/M2"  // if --units
})
```

### L2 — OPM Property Nodes

Separate `PropertyNode` for each value, linked by `HAS_PROPERTY`:

```cypher
(:Wall)-[:HAS_PROPERTY {name: "HAS_PROPERTY_ISEXTERNAL"}]->
    (:PropertyNode {
      uri: "https://...#isExternal_W001",
      propName: "isExternal",
      value: true,
      unitUri: null
    })
```

### L3 — OPM with Versioned States

Each `PropertyNode` additionally links to a `PropertyStateNode` with a timestamp:

```cypher
(:Wall)-[:HAS_PROPERTY]->
    (:PropertyNode {propName: "isExternal"})-[:HAS_STATE]->
    (:PropertyStateNode {
      uri: "https://...#state_isExternal_W001_p0",
      value: true,
      generatedAt: "2024-01-15T10:30:00+00:00",
      unitUri: null
    })
```

---

## 8. CLI Reference

```
usage: ifc_to_neo4j [-h]
                    [--neo4j-uri URI] [--neo4j-user USER] [--neo4j-password PW]
                    [--database DB]
                    [--base-uri URI]
                    [--properties-level {1,2,3}]
                    [--units]
                    [--hierarchical-naming]
                    [--no-elements] [--no-properties] [--no-orphans]
                    [--geometry] [--wkt-bbox] [--interfaces]
                    [--geolocation] [--geometry-workers N]
                    [--batch-size N]
                    [--clear-db]
                    [-v]
                    ifc_file
```

### Positional Arguments

| Argument | Description |
|---|---|
| `ifc_file` | Path to the `.ifc` or `.ifczip` file |

### Neo4j Connection

| Flag | Default | Description |
|---|---|---|
| `--neo4j-uri` | `bolt://localhost:7687` | Neo4j Bolt URI. Use `neo4j+s://` for AuraDB. |
| `--neo4j-user` | `neo4j` | Username |
| `--neo4j-password` | `neo4j` | Password |
| `--database` | `neo4j` | Target database name (important for AuraDB) |

### Conversion Options

| Flag | Default | Description |
|---|---|---|
| `--base-uri` | `https://linkedbuildingdata.org/building#` | URI prefix for all nodes |
| `--properties-level` | `1` | Property level: 1=flat, 2=OPM nodes, 3=OPM+states |
| `--units` | off | Attach QUDT unit URIs to numeric properties |
| `--hierarchical-naming` | off | Name-based URIs instead of GUID-based |
| `--no-elements` | off | Skip all building elements |
| `--no-properties` | off | Skip property set extraction |
| `--no-orphans` | off | Skip elements outside the spatial hierarchy |

### Geometry Options

| Flag | Default | Description |
|---|---|---|
| `--geometry` | off | Compute bounding boxes (requires `ifcopenshell.geom`) |
| `--wkt-bbox` | off | Store bbox as WKT polygon (requires `--geometry`) |
| `--interfaces` | off | Detect element interfaces (requires `--geometry`) |
| `--geolocation` | off | Extract site lat/lon as WKT POINT |
| `--geometry-workers` | `1` | Parallel workers for geometry computation |

### Performance Options

| Flag | Default | Description |
|---|---|---|
| `--batch-size` | `500` | Rows per Neo4j transaction |

### Database Management

| Flag | Description |
|---|---|
| `--clear-db` | Delete ALL existing data before importing (destructive!) |
| `-v` / `--verbose` | Enable debug logging |

### Common Usage Examples

```bash
# Minimal: spatial hierarchy only
python -m ifctoneo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j --neo4j-password secret \
    --no-elements --no-properties

# Full L1 with all elements and properties (default)
python -m ifctoneo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j --neo4j-password secret

# With geometry, bounding boxes, and interface detection
python -m ifctoneo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j --neo4j-password secret \
    --geometry --interfaces

# L2 OPM property nodes with QUDT units
python -m ifctoneo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j --neo4j-password secret \
    --properties-level 2 --units

# Full L3 with geometry, units, hierarchical naming
python -m ifctoneo4j.main model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j --neo4j-password secret \
    --properties-level 3 --units \
    --geometry --geolocation \
    --hierarchical-naming

# AuraDB cloud instance, clear first, large batch
python -m ifctoneo4j.main big-model.ifc \
    --neo4j-uri neo4j+s://9e65deb7.databases.neo4j.io \
    --neo4j-user myuser --neo4j-password mypassword \
    --database mydb \
    --clear-db --batch-size 1000
```

---

## 9. Configuration Reference

The same configuration that drives the CLI can be used programmatically via `ConversionConfig`:

```python
from ifctoneo4j.config import ConversionConfig

# Spatial hierarchy only (no elements, no properties)
cfg = ConversionConfig(
    has_building_elements=False,
    has_building_properties=False,
)

# Full L1 conversion (default settings)
cfg = ConversionConfig()

# L2 with units
cfg = ConversionConfig(
    properties_level=2,
    has_units=True,
)

# With geometry and interface detection
cfg = ConversionConfig(
    has_geometry=True,
    has_interfaces=True,
    has_bounding_box_wkt=True,
)
cfg.validate()  # → raises ValueError if has_geometry=False but has_interfaces=True

# Custom base URI
cfg = ConversionConfig(
    base_uri="https://mycompany.com/building/ProjectAlpha#",
)

# Hierarchical naming (name-based URIs)
cfg = ConversionConfig(
    has_hierarchical_naming=True,
)
# → URIs like "https://...#Site_A/Building_B/Ground_Floor/North_Wall"
#   instead of "https://...#ifcwall_3cUkl32yn8x..."
```

---

## 10. Using as a Python Library

The converter can be used programmatically without the CLI:

```python
from ifctoneo4j.core.ifc_loader import open_ifc
from ifctoneo4j.config import ConversionConfig
from ifctoneo4j.converters.spatial import traverse

# --- Load ---
loaded = open_ifc("path/to/model.ifc")

# --- Configure ---
cfg = ConversionConfig(
    has_building_elements=True,
    has_building_properties=True,
    properties_level=1,
    base_uri="https://myproject.org/building#",
)

# --- Traverse (no Neo4j needed) ---
result = traverse(loaded, cfg)

# Inspect results
for node in result.nodes:
    if "Wall" in node.get("labels", []):
        print(node["props"].get("name"), node["props"].get("isExternal_property_simple"))

for rel in result.rels:
    if rel["rel_type"] == "HAS_SPACE":
        print(f"  {rel['from_uri']} → {rel['to_uri']}")
```

**Writing to Neo4j manually:**
```python
from neo4j import GraphDatabase
from ifctoneo4j.neo4j.writer import Neo4jWriter
from ifctoneo4j.neo4j.schema import drop_all_data

driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "password"),
)

# Optional: clear existing data
drop_all_data(driver, database="neo4j")

with Neo4jWriter(driver, database="neo4j", batch_size=500) as writer:
    writer.setup()                               # Create constraints + indexes
    counts = writer.write(result, cfg.base_uri)  # MERGE nodes + rels
    print(counts)
    # → {"nodes": 187, "rels": 186, "prop_nodes": 0}
```

**With geometry:**
```python
from ifctoneo4j.geometry.bounding_box import (
    compute_bounding_boxes,
    attach_geometry_to_nodes,
    detect_interfaces,
)

bbox_map = compute_bounding_boxes(loaded.model, result.seen_guids)
attach_geometry_to_nodes(result.nodes, bbox_map, as_wkt=False)

interfaces = detect_interfaces(bbox_map, tolerance=0.05)

# Convert guid pairs to uri pairs
guid_to_uri = {
    n["props"]["globalId"]: n["uri"]
    for n in result.nodes if "globalId" in n.get("props", {})
}
uri_interfaces = [
    (guid_to_uri[a], guid_to_uri[b])
    for a, b in interfaces
    if a in guid_to_uri and b in guid_to_uri
]

with Neo4jWriter(driver) as writer:
    writer.setup()
    writer.write(result)
    writer.write_interfaces(uri_interfaces, cfg.base_uri)
```

**Dry run (no Neo4j):**
```python
# Full pipeline without writing to any database
loaded = open_ifc("model.ifc")
cfg = ConversionConfig()
result = traverse(loaded, cfg)

print(f"Nodes: {len(result.nodes)}")
print(f"Rels:  {len(result.rels)}")

# Count by label
from collections import Counter
label_counts = Counter(
    lbl
    for node in result.nodes
    for lbl in node.get("labels", [])
)
for label, count in label_counts.most_common(10):
    print(f"  {label}: {count}")
```

---

## 11. Example Cypher Queries

```cypher
// All walls on the ground floor
MATCH (s:Storey {name: 'Ground Floor'})-[:CONTAINS_ELEMENT]->(w:Wall)
RETURN w.name, w.globalId, w.isExternal_property_simple

// Full spatial hierarchy
MATCH path = (site:Site)-[:HAS_BUILDING]->(:Building)-[:HAS_STOREY]->(:Storey)-[:HAS_SPACE]->(:Space)
RETURN path

// All spaces and their element counts
MATCH (sp:Space)-[:CONTAINS_ELEMENT]->(e:Element)
RETURN sp.name AS space, count(e) AS elementCount
ORDER BY elementCount DESC

// Doors hosted in walls
MATCH (w:Wall)-[:HAS_SUB_ELEMENT]->(d:Door)
RETURN w.name AS wall, d.name AS door, d.globalId

// External load-bearing walls
MATCH (w:Wall)
WHERE w.isExternal_property_simple = true
  AND w.loadBearing_property_simple = true
RETURN w.name, w.globalId

// Space floor areas
MATCH (sp:Space)
WHERE sp.netFloorArea_property_simple IS NOT NULL
RETURN sp.name, toFloat(sp.netFloorArea_property_simple) AS area_m2
ORDER BY area_m2 DESC

// All MEP sensors
MATCH (s:Sensor)
RETURN s.name, s.globalId, labels(s) AS types

// Elements by storey
MATCH (st:Storey)-[:CONTAINS_ELEMENT]->(e:Element)
RETURN st.name AS storey, labels(e) AS types, count(e) AS count
ORDER BY st.name, count DESC

// Interface pairs (requires --geometry --interfaces)
MATCH (a:Element)-[:INTERFACE_OF]->(i:Interface)<-[:INTERFACE_OF]-(b:Element)
WHERE id(a) < id(b)
RETURN a.name, b.name, i.uri

// L2/L3: all property nodes for a specific element
MATCH (w:Wall {globalId: '3cUkl32yn8xA7kQ...'})-[:HAS_PROPERTY]->(p:PropertyNode)
RETURN p.propName, p.value, p.unitUri
ORDER BY p.propName

// L3: property history (all states)
MATCH (w:Wall)-[:HAS_PROPERTY]->(p:PropertyNode {propName: 'isExternal'})
      -[:HAS_STATE]->(s:PropertyStateNode)
RETURN w.name, s.value, s.generatedAt
ORDER BY s.generatedAt

// Elements with site geolocation (requires --geolocation)
MATCH (site:Site)
WHERE site.geo_wkt IS NOT NULL
RETURN site.name, site.geo_wkt
```

---

## 12. Running Tests

The test suite has 142 tests covering all modules. No Neo4j connection or IFC file is required — all IFC entities are mocked.

```bash
# From the ifc-ai-002 directory
python -m pytest ifc_to_neo4j/tests/ -v

# With coverage report
python -m pytest ifc_to_neo4j/tests/ --cov=ifc_to_neo4j --cov-report=term-missing

# Run a specific test file
python -m pytest ifc_to_neo4j/tests/test_string_ops.py -v
python -m pytest ifc_to_neo4j/tests/test_elements.py -v
python -m pytest ifc_to_neo4j/tests/test_properties.py -v
python -m pytest ifc_to_neo4j/tests/test_bounding_box.py -v
python -m pytest ifc_to_neo4j/tests/test_product_map.py -v
python -m pytest ifc_to_neo4j/tests/test_unit_handler.py -v
```

### Test files

| File | What it tests |
|---|---|
| `test_string_ops.py` | `to_camel_case()`, `property_predicate()`, `attribute_predicate()`, `url_encode_name()` |
| `test_product_map.py` | `get_labels()`, `get_namespace()` for BEO/MEP/FURN classes |
| `test_unit_handler.py` | `build_unit_map()`, `get_unit_for_property()` |
| `test_properties.py` | `extract_properties()` for L1/L2/L3, value type handling |
| `test_elements.py` | `build_element_uri()`, `classify_element()`, node/rel builders, hosted/sub-element detection |
| `test_bounding_box.py` | `BoundingBox` methods, `extract_geolocation()` |

### Dry-run test with a real IFC file

```bash
python3 test_with_real_ifc.py path/to/model.ifc
```

Output includes node/relationship counts, label distribution, property keys, and sample nodes. No database required.

---

## 13. Design Decisions

### No RDF / No Turtle / No SPARQL

The Java IFCtoLBD uses Apache Jena to load BEO/MEP/FURN ontology TTL files, then runs SPARQL queries to build the `ifcowl_product_map` at startup. This is replaced with a static 636-line Python dict (`product_map.py`), which is:
- Deterministic and version-controlled
- Zero external dependencies for the mapping
- ~100x faster to initialise

### GlobalId Used Directly

Java IFCtoLBD decompresses IFC GlobalIds from their base64-encoded form to UUIDs. ifcopenshell returns the `GlobalId` attribute as the original string (e.g. `"3cUkl32yn8xA7kQ..."`) — no decompression needed.

### EXPRESS Type Unwrapping

IFC property values are typed scalars (`IfcLabel`, `IfcBoolean`, `IfcReal`, …). Java uses Jena/OWL to unwrap these; ifcopenshell exposes them with a `.wrappedValue` attribute, handled in `_extract_value()`.

### IFC2x3 vs IFC4 Compatibility

The main schema difference is the relationship class name for aggregation: `IfcRelDecomposes` (IFC2x3) vs `IfcRelAggregates` (IFC4). ifcopenshell exposes both via the same `IsDecomposedBy` inverse attribute, making the Python code schema-agnostic.

### Multi-Label Neo4j Nodes

Neo4j supports multiple labels per node (`Wall:Element:Wall_SOLIDWALL`). Labels cannot be parameterised in Cypher, so node groups are batched by label set and a dynamic Cypher string is built per group with backtick-escaped labels.

### Idempotent Writes

All writes use `MERGE` on `uri`, making re-runs safe. Re-importing the same IFC file updates all properties without creating duplicates.

### Orphaned Elements

IFC models sometimes contain elements that are not connected to any spatial structure. These are found by comparing `model.by_type("IfcElement")` against the `seen_guids` set built during traversal. Orphans are added as nodes without any spatial relationship, allowing them to be queried in Neo4j.
