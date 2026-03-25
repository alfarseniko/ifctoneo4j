# ifctoneo4j

Convert IFC building models to a [Linked Building Data](https://w3id.org/bot) graph in Neo4j — no RDF, no Turtle files.

---

## Install

```bash
pip install ifctoneo4j
```

This will also install `ifcopenshell` and `neo4j` automatically.

For bounding box geometry and interface detection, also install:
```bash
pip install ifctoneo4j[geometry]
```

---

## Python API

### Basic usage

```python
import ifctoneo4j

# Step 1 — parse the IFC file (no database needed)
result = ifctoneo4j.parse("model.ifc")
print(result)
# ParseResult(nodes=187, rels=186, elements=93)

# Step 2 — write to Neo4j
ifctoneo4j.write(
    result,
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="secret",
)
```

### `parse()` options

```python
result = ifctoneo4j.parse(
    "model.ifc",
    properties_level=1,   # 1 = flat props on nodes (default)
                          # 2 = separate OPM PropertyNode per value
                          # 3 = OPM + versioned StateNode with timestamp
    include_units=False,  # attach QUDT unit URIs to numeric properties
    base_uri="https://linkedbuildingdata.org/building#",  # URI prefix
)
```

### `write()` options

```python
ifctoneo4j.write(
    result,
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="secret",
    database="neo4j",   # target database name (important for AuraDB)
    clear_db=False,     # set True to wipe the database before importing
    batch_size=500,     # rows per Neo4j transaction
)
# returns {"nodes": 187, "rels": 186, "prop_nodes": 0}
```

### AuraDB (cloud)

```python
ifctoneo4j.write(
    result,
    neo4j_uri="neo4j+s://xxxxxxxx.databases.neo4j.io",
    neo4j_user="your-username",
    neo4j_password="your-password",
    database="your-database-name",
    clear_db=True,
)
```

---

## CLI

```bash
ifctoneo4j model.ifc \
    --neo4j-uri bolt://localhost:7687 \
    --neo4j-user neo4j \
    --neo4j-password secret
```

### Common flags

| Flag | Description |
|---|---|
| `--database` | Target database name (default: `neo4j`) |
| `--clear-db` | Delete all data before importing |
| `--properties-level 2` | OPM property nodes instead of flat props |
| `--units` | Attach QUDT unit URIs to numeric properties |
| `--geometry` | Compute bounding boxes |
| `--interfaces` | Detect element interfaces (requires `--geometry`) |
| `--geolocation` | Extract site lat/lon as WKT POINT |
| `--batch-size 1000` | Rows per transaction (default: 500) |
| `--no-elements` | Spatial hierarchy only, skip elements |
| `-v` | Verbose / debug logging |

```bash
# Full example with geometry and AuraDB
ifctoneo4j model.ifc \
    --neo4j-uri neo4j+s://xxxxxxxx.databases.neo4j.io \
    --neo4j-user myuser --neo4j-password mypassword \
    --database mydb \
    --clear-db --geometry --geolocation
```

---

## What gets created in Neo4j

The graph follows the [BOT](https://w3id.org/bot) spatial hierarchy:

```
Site -[HAS_BUILDING]-> Building -[HAS_STOREY]-> Storey -[HAS_SPACE]-> Space
Storey/Space -[CONTAINS_ELEMENT]-> Element
Wall -[HAS_SUB_ELEMENT]-> Door/Window
```

Element nodes get multi-label classification — a solid wall becomes `:Element:Wall:Wall_SOLIDWALL`, an axial fan becomes `:Element:Fan:Fan_AXIAL`.

Properties from IFC property sets are stored as `camelCase_property_simple` on each node:

```cypher
MATCH (w:Wall)
WHERE w.isExternal_property_simple = true
RETURN w.name, w.globalId
```
