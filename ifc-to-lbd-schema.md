# IFCtoLBD Conversion Schema

**Version analysed:** IFCtoLBD v2.44.0
**Source repo:** https://github.com/jyrkioraskari/IFCtoLBD
**Purpose:** Reimplementation specification for Python + ifcopenshell + Neo4j

---

## Table of Contents

1. [Namespace Reference](#1-namespace-reference)
2. [Class Mappings](#2-class-mappings)
3. [Relationship Mappings](#3-relationship-mappings)
4. [Property Handling](#4-property-handling)
5. [URI Construction](#5-uri-construction)
6. [Additional Features](#6-additional-features)
7. [Conversion Configuration Flags](#7-conversion-configuration-flags)
8. [IFC Schema Version Handling](#8-ifc-schema-version-handling)

---

## 1. Namespace Reference

| Prefix     | URI                                             | Purpose                                  |
| ---------- | ----------------------------------------------- | ---------------------------------------- |
| `bot`      | `https://w3id.org/bot#`                         | Building Topology Ontology               |
| `beo`      | `https://pi.pauwel.be/voc/buildingelement#`     | Building Element Ontology                |
| `furn`     | `http://pi.pauwel.be/voc/furniture#`            | Furniture Ontology                       |
| `mep`      | `https://pi.pauwel.be/voc/distributionelement#` | MEP/Distribution Element Ontology        |
| `props`    | `http://lbd.arch.rwth-aachen.de/props#`         | LBD Properties                           |
| `lbd`      | `https://linkedbuildingdata.org/LBD#`           | LBD geometry/bounding box                |
| `opm`      | `https://w3id.org/opm#`                         | Open Provenance Model (L2/L3 properties) |
| `prov`     | `http://www.w3.org/ns/prov#`                    | Provenance (L3 timestamps)               |
| `schema`   | `http://schema.org/`                            | Schema.org (property values in OPM)      |
| `smls`     | `https://w3id.org/def/smls-owl#`                | SMLS units                               |
| `unit`     | `http://qudt.org/vocab/unit/`                   | QUDT unit instances                      |
| `geo`      | `http://www.opengis.net/ont/geosparql#`         | GeoSPARQL                                |
| `omg`      | `https://w3id.org/omg#`                         | Ontology for Managing Geometry           |
| `fog`      | `https://w3id.org/fog#`                         | File Ontology for Geometry               |
| `ifc4-psd` | `https://www.linkedbuildingdata.net/IFC4-PSD#`  | IFC4 PSD / bSDD                          |
| `express`  | `https://w3id.org/express#`                     | EXPRESS type wrappers                    |
| `list`     | `https://w3id.org/list#`                        | RDF list traversal                       |

**Source:** `namespace/*.java` files.

---

## 2. Class Mappings

### 2.1 Mechanism

The converter builds a map (`ifcowl_product_map`) from IFC class URIs to LBD class resources at startup.

**How it works** (`IFCtoLBDConverterCore.java`, `createIfcLBDProductMapping()`):

1. Load ontology TTL files (beo, furn, mep) into a Jena `ontology_model`
2. Query every triple of the form `?lbd_class rdfs:seeAlso ?ifc_class`
3. Also expand via `?lbd_class rdfs:subClassOf ?parent` to catch indirect mappings
4. Store: `ifc_class_uri → lbd_class_resource`

**Lookup** (`getLBDProductType()`): Given a SPARQL query result for an element's `rdf:type`, look up the type URI. Returns the LBD class **only if exactly one match** is found in the map.

**Assignment** (`connectIfcContaidedElement()`):

- Always assign `bot:Element` to every building element
- Also assign the specific product type (beo/furn/mep class) if found
- If `hasNonLBDElement=true` (default), elements without a specific product type still get `bot:Element`

---

### 2.2 Spatial Hierarchy Classes

| IFC Entity          | LBD Class      | BOT Relationship              | Source                                    |
| ------------------- | -------------- | ----------------------------- | ----------------------------------------- |
| `IfcSite`           | `bot:Site`     | — (root)                      | `IFCtoLBDConverterCore.java:conversion()` |
| `IfcBuilding`       | `bot:Building` | `bot:hasBuilding` from Site   | `handle_building()`                       |
| `IfcBuildingStorey` | `bot:Storey`   | `bot:hasStorey` from Building | `conversion()`                            |
| `IfcSpace`          | `bot:Space`    | `bot:hasSpace` from Storey    | `conversion()`                            |

---

### 2.3 Building Elements (BEO) — `beo_ontology.ttl`

All map to `bot:Element` plus the specific BEO class. The `rdfs:seeAlso` links in `beo_ontology.ttl` drive the `ifcowl_product_map`.

#### Base elements

| IFC Entity               | BEO Class                 |
| ------------------------ | ------------------------- |
| `IfcBuildingElement`     | `beo:BuildingElement`     |
| `IfcBeam`                | `beo:Beam`                |
| `IfcBuildingElementPart` | `beo:BuildingElementPart` |
| `IfcChimney`             | `beo:Chimney`             |
| `IfcColumn`              | `beo:Column`              |
| `IfcCovering`            | `beo:Covering`            |
| `IfcCurtainWall`         | `beo:CurtainWall`         |
| `IfcDiscreteAccessory`   | `beo:DiscreteAccessory`   |
| `IfcDoor`                | `beo:Door`                |
| `IfcElementComponent`    | `beo:ElementComponent`    |
| `IfcFastener`            | `beo:Fastener`            |
| `IfcFooting`             | `beo:Footing`             |
| `IfcMechanicalFastener`  | `beo:MechanicalFastener`  |
| `IfcMember`              | `beo:Member`              |
| `IfcPile`                | `beo:Pile`                |
| `IfcPlate`               | `beo:Plate`               |
| `IfcRailing`             | `beo:Railing`             |
| `IfcRamp`                | `beo:Ramp`                |
| `IfcRampFlight`          | `beo:RampFlight`          |
| `IfcReinforcingBar`      | `beo:ReinforcingBar`      |
| `IfcReinforcingElement`  | `beo:ReinforcingElement`  |
| `IfcReinforcingMesh`     | `beo:ReinforcingMesh`     |
| `IfcRoof`                | `beo:Roof`                |
| `IfcShadingDevice`       | `beo:ShadingDevice`       |
| `IfcSlab`                | `beo:Slab`                |
| `IfcStair`               | `beo:Stair`               |
| `IfcStairFlight`         | `beo:StairFlight`         |
| `IfcTendon`              | `beo:Tendon`              |
| `IfcTendonAnchor`        | `beo:TendonAnchor`        |
| `IfcTransportElement`    | `beo:TransportElement`    |
| `IfcVibrationIsolator`   | `beo:VibrationIsolator`   |
| `IfcWall`                | `beo:Wall`                |
| `IfcWallElementedCase`   | `beo:WallElementedCase`   |
| `IfcWindow`              | `beo:Window`              |

#### Predefined-type subtypes (via `IfcXxxEnumType`)

Each IFC entity has predefined types that map to more specific BEO subclasses. These are `rdfs:seeAlso IfcXxxEnumType` in the ontology and matched by predefined type value.

| BEO Subclass Pattern                                                                                                                                                                                                    | Predefined Type Values       |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------- |
| `beo:Beam-BEAM`, `beo:Beam-HOLLOWCORE`, `beo:Beam-JOIST`, `beo:Beam-LINTEL`, `beo:Beam-SPANDREL`, `beo:Beam-T_BEAM`                                                                                                     | IfcBeamType predefined types |
| `beo:BuildingElementPart-INSULATION`, `beo:BuildingElementPart-PRECASTPANEL`                                                                                                                                            | IfcBuildingElementPartType   |
| `beo:Column-COLUMN`, `beo:Column-PILASTER`                                                                                                                                                                              | IfcColumnType                |
| `beo:Covering-CEILING`, `-CLADDING`, `-FLOORING`, `-INSULATION`, `-MEMBRANE`, `-MOLDING`, `-ROOFING`, `-SKIRTINGBOARD`, `-SLEEVING`, `-WRAPPING`                                                                        | IfcCoveringType              |
| `beo:Door-DOOR`, `-GATE`, `-TRAPDOOR`                                                                                                                                                                                   | IfcDoorType                  |
| `beo:Fastener-GLUE`, `-MORTAR`, `-WELD`                                                                                                                                                                                 | IfcFastenerType              |
| `beo:Footing-CAISSON_FOUNDATION`, `-FOOTING_BEAM`, `-PAD_FOOTING`, `-PILE_CAP`, `-STRIP_FOOTING`                                                                                                                        | IfcFootingType               |
| `beo:MechanicalFastener-ANCHORBOLT`, `-BOLT`, `-DOWEL`, `-NAIL`, `-NAILPLATE`, `-RIVET`, `-SCREW`, `-SHEARCONNECTOR`, `-STAPLE`, `-STUDSHEARCONNECTOR`                                                                  | IfcMechanicalFastenerType    |
| `beo:Member-BRACE`, `-CHORD`, `-COLLAR`, `-MEMBER`, `-MULLION`, `-PLATE`, `-POST`, `-PURLIN`, `-RAFTER`, `-STRINGER`, `-STRUT`, `-STUD`                                                                                 | IfcMemberType                |
| `beo:Pile-BORED`, `-COHESION`, `-DRIVEN`, `-FRICTION`, `-JETGROUTING`, `-SUPPORT`                                                                                                                                       | IfcPileType                  |
| `beo:Plate-CURTAIN_PANEL`, `-SHEET`                                                                                                                                                                                     | IfcPlateType                 |
| `beo:Railing-BALUSTRADE`, `-GUARDRAIL`, `-HANDRAIL`                                                                                                                                                                     | IfcRailingType               |
| `beo:Roof-BARREL_ROOF`, `-BUTTERFLY_ROOF`, `-DOME_ROOF`, `-FLAT_ROOF`, `-FREEFORM`, `-GAMBREL_ROOF`, `-GABLE_ROOF`, `-HIPPED_GABLE_ROOF`, `-HIP_ROOF`, `-MANSARD_ROOF`, `-PAVILION_ROOF`, `-RAINBOW_ROOF`, `-SHED_ROOF` | IfcRoofType                  |
| `beo:Slab-BASESLAB`, `-FLOOR`, `-LANDING`, `-ROOF`                                                                                                                                                                      | IfcSlabType                  |
| `beo:TransportElement-ELEVATOR`, `-ESCALATOR`, `-MOVINGWALKWAY`, `-CRANEWAY`, `-LIFTINGGANG`                                                                                                                            | IfcTransportElementType      |
| `beo:Wall-FREESTANDING`, `-MOVABLE`, `-PARAPET`, `-PARTITIONING`, `-PLUMBINGWALL`, `-POLYGONAL`, `-SHEAR`, `-SOLIDWALL`, `-STANDARD`, `-WINDING`                                                                        | IfcWallType                  |
| `beo:Window-WINDOW`, `-SKYLIGHT`, `-LIGHTDOME`                                                                                                                                                                          | IfcWindowType                |

**Source:** `beo_ontology.ttl` (rdfs:seeAlso triples), `IFCtoLBDConverterCore.java:createIfcLBDProductMapping()`

---

### 2.4 Furnishing Elements — `prod_furnishing.ttl`

| IFC Entity / Type                              | Furniture Class    |
| ---------------------------------------------- | ------------------ |
| `IfcFurnishingElement`                         | `furn:Furniture`   |
| `IfcFurnishingElement` with type `CHAIR`       | `furn:Chair`       |
| `IfcFurnishingElement` with type `TABLE`       | `furn:Table`       |
| `IfcFurnishingElement` with type `DESK`        | `furn:Desk`        |
| `IfcFurnishingElement` with type `SOFA`        | `furn:Sofa`        |
| `IfcFurnishingElement` with type `CLOSET`      | `furn:Closet`      |
| `IfcFurnishingElement` with type `FILECABINET` | `furn:FileCabinet` |
| `IfcFurnishingElement` with type `BED`         | `furn:Bed`         |
| `IfcFurnishingElement` with type `SHELF`       | `furn:Shelf`       |

**Note:** Furniture subtypes use `rdfs:seeAlso ifc:IfcFurnitureEnumType`.
**Source:** `prod_furnishing.ttl`, `IFCtoLBDConverterCore.java:readInOntologies()`

---

### 2.5 MEP / Distribution Elements — `mep_ontology.ttl`

All map to `bot:Element` plus the specific MEP class. Namespace: `https://pi.pauwel.be/voc/distributionelement#`.

| IFC Entity                        | MEP Class                          |
| --------------------------------- | ---------------------------------- |
| `IfcDistributionElement`          | `mep:DistributionElement`          |
| `IfcDistributionFlowElement`      | `mep:DistributionFlowElement`      |
| `IfcDistributionControlElement`   | `mep:DistributionControlElement`   |
| `IfcEnergyConversionDevice`       | `mep:EnergyConversionDevice`       |
| `IfcFlowController`               | `mep:FlowController`               |
| `IfcFlowFitting`                  | `mep:FlowFitting`                  |
| `IfcFlowMovingDevice`             | `mep:FlowMovingDevice`             |
| `IfcFlowSegment`                  | `mep:FlowSegment`                  |
| `IfcFlowStorageDevice`            | `mep:FlowStorageDevice`            |
| `IfcFlowTerminal`                 | `mep:FlowTerminal`                 |
| `IfcFlowTreatmentDevice`          | `mep:FlowTreatmentDevice`          |
| `IfcActuator`                     | `mep:Actuator`                     |
| `IfcAirTerminal`                  | `mep:AirTerminal`                  |
| `IfcAirTerminalBox`               | `mep:AirTerminalBox`               |
| `IfcAirToAirHeatRecovery`         | `mep:AirToAirHeatRecovery`         |
| `IfcAlarm`                        | `mep:Alarm`                        |
| `IfcAudioVisualAppliance`         | `mep:AudioVisualAppliance`         |
| `IfcBoiler`                       | `mep:Boiler`                       |
| `IfcBurner`                       | `mep:Burner`                       |
| `IfcCableCarrierFitting`          | `mep:CableCarrierFitting`          |
| `IfcCableCarrierSegment`          | `mep:CableCarrierSegment`          |
| `IfcCableFitting`                 | `mep:CableFitting`                 |
| `IfcCableSegment`                 | `mep:CableSegment`                 |
| `IfcChiller`                      | `mep:Chiller`                      |
| `IfcCoil`                         | `mep:Coil`                         |
| `IfcCommunicationsAppliance`      | `mep:CommunicationsAppliance`      |
| `IfcCompressor`                   | `mep:Compressor`                   |
| `IfcCondenser`                    | `mep:Condenser`                    |
| `IfcController`                   | `mep:Controller`                   |
| `IfcCooledBeam`                   | `mep:CooledBeam`                   |
| `IfcCoolingTower`                 | `mep:CoolingTower`                 |
| `IfcDamper`                       | `mep:Damper`                       |
| `IfcDistributionChamberElement`   | `mep:DistributionChamberElement`   |
| `IfcDuctFitting`                  | `mep:DuctFitting`                  |
| `IfcDuctSegment`                  | `mep:DuctSegment`                  |
| `IfcDuctSilencer`                 | `mep:DuctSilencer`                 |
| `IfcElectricAppliance`            | `mep:ElectricAppliance`            |
| `IfcElectricDistributionBoard`    | `mep:ElectricDistributionBoard`    |
| `IfcElectricFlowStorageDevice`    | `mep:ElectricFlowStorageDevice`    |
| `IfcElectricGenerator`            | `mep:ElectricGenerator`            |
| `IfcElectricMotor`                | `mep:ElectricMotor`                |
| `IfcElectricTimeControl`          | `mep:ElectricTimeControl`          |
| `IfcEngine`                       | `mep:Engine`                       |
| `IfcEvaporativeCooler`            | `mep:EvaporativeCooler`            |
| `IfcEvaporator`                   | `mep:Evaporator`                   |
| `IfcFan`                          | `mep:Fan`                          |
| `IfcFilter`                       | `mep:Filter`                       |
| `IfcFireSuppressionTerminal`      | `mep:FireSuppressionTerminal`      |
| `IfcFlowInstrument`               | `mep:FlowInstrument`               |
| `IfcFlowMeter`                    | `mep:FlowMeter`                    |
| `IfcHeatExchanger`                | `mep:HeatExchanger`                |
| `IfcHumidifier`                   | `mep:Humidifier`                   |
| `IfcInterceptor`                  | `mep:Interceptor`                  |
| `IfcJunctionBox`                  | `mep:JunctionBox`                  |
| `IfcLamp`                         | `mep:Lamp`                         |
| `IfcLightFixture`                 | `mep:LightFixture`                 |
| `IfcMedicalDevice`                | `mep:MedicalDevice`                |
| `IfcMotorConnection`              | `mep:MotorConnection`              |
| `IfcOutlet`                       | `mep:Outlet`                       |
| `IfcPipeFitting`                  | `mep:PipeFitting`                  |
| `IfcPipeSegment`                  | `mep:PipeSegment`                  |
| `IfcProtectiveDevice`             | `mep:ProtectiveDevice`             |
| `IfcProtectiveDeviceTrippingUnit` | `mep:ProtectiveDeviceTrippingUnit` |
| `IfcPump`                         | `mep:Pump`                         |
| `IfcSanitaryTerminal`             | `mep:SanitaryTerminal`             |
| `IfcSensor`                       | `mep:Sensor`                       |
| `IfcSolarDevice`                  | `mep:SolarDevice`                  |
| `IfcSpaceHeater`                  | `mep:SpaceHeater`                  |
| `IfcStackTerminal`                | `mep:StackTerminal`                |
| `IfcSwitchingDevice`              | `mep:SwitchingDevice`              |
| `IfcTank`                         | `mep:Tank`                         |
| `IfcTransformer`                  | `mep:Transformer`                  |
| `IfcTubeBundle`                   | `mep:TubeBundle`                   |
| `IfcUnitaryControlElement`        | `mep:UnitaryControlElement`        |
| `IfcUnitaryEquipment`             | `mep:UnitaryEquipment`             |
| `IfcValve`                        | `mep:Valve`                        |
| `IfcWasteTerminal`                | `mep:WasteTerminal`                |

Each MEP class also has predefined-type subclasses using the `-TYPE` suffix pattern (e.g., `mep:Actuator-ELECTRICACTUATOR`) linked via `rdfs:seeAlso IfcXxxEnumType`.

**Source:** `mep_ontology.ttl`, `IFCtoLBDConverterCore.java:readInOntologies()`

---

### 2.6 Fallback / Non-matched Elements

If `hasNonLBDElement=true` (the default), any IFC element that is a subclass of `IfcElement` in the ifcOWL model but has no specific product type match still receives:

- `rdf:type bot:Element`
- All property sets and attributes
- All spatial connections

This is controlled by `isIfcElement()` which walks `rdfs:subClassOf` chain looking for `IfcElement`.

**Source:** `IFCtoLBDConverterCore.java:addSingleElement()`, `isIfcElement()`

---

## 3. Relationship Mappings

### 3.1 Spatial Decomposition (Site → Building → Storey → Space)

These are traversed via IFC aggregation relationships. The property names differ between IFC versions.

#### IFC2x3 path (IfcRelDecomposes)

```
IfcSite
  INV(relatingObject_IfcRelDecomposes)
    → IfcRelDecomposes instance
      relatedObjects_IfcRelDecomposes
        → IfcBuilding

IfcBuilding
  INV(relatingObject_IfcRelDecomposes)
    → IfcRelDecomposes instance
      relatedObjects_IfcRelDecomposes
        → IfcBuildingStorey

IfcBuildingStorey
  INV(relatingObject_IfcRelDecomposes)
    → IfcRelDecomposes instance
      relatedObjects_IfcRelDecomposes
        → IfcSpace | IfcBuildingStorey (sub-storey)
```

#### IFC4+ path (IfcRelAggregates)

```
IfcSite
  INV(relatingObject_IfcRelAggregates)
    → IfcRelAggregates instance
      relatedObjects_IfcRelAggregates
        → IfcBuilding
[same pattern for Building → Storey → Space]
```

**LBD relationships produced:**

| Context           | BOT Relationship  | Source              |
| ----------------- | ----------------- | ------------------- |
| Site → Building   | `bot:hasBuilding` | `handle_building()` |
| Building → Storey | `bot:hasStorey`   | `conversion()`      |
| Storey → Space    | `bot:hasSpace`    | `conversion()`      |

**Source:** `IfcOWLUtils.java:getNextLevelPath()`, `listStoreys()`, `listStoreySpaces()`

---

### 3.2 Spatial Containment (Elements in Storeys and Spaces)

```
IfcBuildingStorey or IfcSpace
  INV(relatingStructure_IfcRelContainedInSpatialStructure)
    → IfcRelContainedInSpatialStructure instance
      relatedElements_IfcRelContainedInSpatialStructure
        → IfcElement (wall, door, slab, etc.)
```

Additionally, for spaces, the placement path is followed to determine if an element is co-located:

```
IfcSpace.objectPlacement_IfcProduct
  INV(placementRelTo_IfcLocalPlacement)
    → IfcLocalPlacement
      INV(objectPlacement_IfcProduct)
        → co-placed elements
```

**LBD relationships produced:**

| Context                    | BOT Relationship      | Source                                    |
| -------------------------- | --------------------- | ----------------------------------------- |
| Storey → contained element | `bot:containsElement` | `IFCtoLBDConverterCore.java:conversion()` |
| Space → contained element  | `bot:containsElement` | `IFCtoLBDConverterCore.java:conversion()` |

**Source:** `IfcOWLUtils.java:listContained_StoreyElements()`, `listContained_SpaceElements()`

---

### 3.3 Space Boundary (Adjacent Elements)

```
IfcSpace
  INV(relatingSpace_IfcRelSpaceBoundary)
    → IfcRelSpaceBoundary instance
      relatedBuildingElement_IfcRelSpaceBoundary
        → IfcElement (wall, slab bounding the space)
```

**LBD relationship produced:** `bot:adjacentElement`
**Source:** `IfcOWLUtils.java:listAdjacent_SpaceElements()`, `IFCtoLBDConverterCore.java:conversion()`

---

### 3.4 Hosted Elements (Openings and Fills)

**Path 1 — Openings filled by doors/windows:**

```
IfcWall (host element)
  INV(relatingBuildingElement_IfcRelVoidsElement)
    → IfcRelVoidsElement
      relatedOpeningElement_IfcRelVoidsElement
        → IfcOpeningElement
          INV(relatingOpeningElement_IfcRelFillsElement)
            → IfcRelFillsElement
              relatedBuildingElement_IfcRelFillsElement
                → IfcDoor / IfcWindow (hosted element)
```

**Path 2 — Openings via placement (alternative path):**
Same through the opening element, then via placement resolution.

**LBD relationship produced:** `bot:hasSubElement` (hosted element added as sub-element of host)
**Source:** `IfcOWLUtils.java:listHosted_Elements()`, `IFCtoLBDConverterCore.java:connectIfcContaidedElement()`

---

### 3.5 Aggregated Sub-Elements

```
IfcElement (parent)
  INV(relatingObject_IfcRelDecomposes)
    → IfcRelDecomposes / IfcRelAggregates instance
      relatedObjects_IfcRelDecomposes/IfcRelAggregates
        → IfcElement (sub-element, e.g. IfcBuildingElementPart)
```

**LBD relationship produced:** `bot:hasSubElement`
**Source:** `IfcOWLUtils.java:listAggregated_Elements()`, `IFCtoLBDConverterCore.java:connectIfcContaidedElement()`

---

### 3.6 Property Set Linkage

```
IfcElement
  INV(relatedObjects_IfcRelDefines) [IFC2x3]
  or
  INV(relatedObjects_IfcRelDefinesByProperties) [IFC4+]
    → IfcRelDefinesByProperties instance
      relatingPropertyDefinition_IfcRelDefinesByProperties
        → IfcPropertySet or IfcElementQuantity
```

**Additionally — Type object property sets:**

```
IfcElement
  ifc:relatingType_IfcRelDefinesByType
    → IfcTypeObject
      ifc:hasPropertySets_IfcTypeObject
        → IfcPropertySet
```

These produce `props:` predicate triples on the element resource (or OPM nodes for L2/L3).
**Source:** `IfcOWLUtils.java:listPropertysets()`, `getPropertySetPath()`, `getIfcTypeObjectPropertySetPath()`

---

### 3.7 Interface Detection (Optional, geometry-based)

When `hasInterfaces=true` and geometry is enabled, after all elements are processed:

```
For every pair of elements (A, B) whose bounding boxes overlap within 0.05m tolerance:
  Create bot:Interface node
  A bot:interfaceOf interface_node
  B bot:interfaceOf interface_node
```

Uses an RTree spatial index over 3D bounding boxes.

**Source:** `IFCtoLBDConverterCore.java:finish_geometry()`, `BOT.java:interfaceOf`

---

### 3.8 Complete Relationship Summary Table

| IFC Pattern                                               | LBD Relationship      | Notes                                        |
| --------------------------------------------------------- | --------------------- | -------------------------------------------- |
| IfcRelAggregates: Site → Building                         | `bot:hasBuilding`     | Site resource subject                        |
| IfcRelAggregates: Building → Storey                       | `bot:hasStorey`       | Building resource subject                    |
| IfcRelAggregates: Storey → Space                          | `bot:hasSpace`        | Storey resource subject                      |
| IfcRelContainedInSpatialStructure: Storey/Space → Element | `bot:containsElement` | Spatial container subject                    |
| IfcRelSpaceBoundary: Space → Element                      | `bot:adjacentElement` | Space resource subject                       |
| IfcRelVoidsElement + IfcRelFillsElement: Host → Fill      | `bot:hasSubElement`   | Host element subject                         |
| IfcRelDecomposes/IfcRelAggregates: Element → Sub-element  | `bot:hasSubElement`   | Parent element subject                       |
| Geometry bounding box overlap (≤0.05m)                    | `bot:interfaceOf`     | Both elements point to shared Interface node |

---

## 4. Property Handling

### 4.1 Three Complexity Levels

The converter supports three levels of property representation, selected at runtime. The default is L1.

---

### 4.2 Level 1 (L1) — Flat Key-Value

Properties are added as direct predicates on the element resource with literal values.

#### L1 Property Set Properties

For each `IfcPropertySingleValue` in a property set:

1. **Read** property name from `name_IfcPropertySingleValue → express:hasString`
2. **Read** value from `nominalValue_IfcPropertySingleValue → express:hasString/hasDouble/hasInteger/hasBoolean/hasLogical`
3. **Compute** predicate URI: `props:toCamelCase(propertyName)_property_simple`
   - Example: `IsExternal` → `http://lbd.arch.rwth-aachen.de/props#isExternal_property_simple`
4. **Add triple**: `element_resource  props:isExternal_property_simple  "true"^^xsd:boolean`

**Simplified mode** (alternative predicate): `props:toCamelCase(name.split(" ")[0])`
(strips first space and subsequent words, uses just the first token in camelCase)

#### L1 Attribute Properties

Direct IFC attributes (GlobalId, Name, ObjectType, Tag, etc.) are read and attached:

1. **Special case**: `name_IfcRoot` → `rdfs:label` (not a props: predicate)
2. **All others**: `props:toCamelCase(attrName)_attribute_simple`
   - Example: `globalId_IfcRoot` → `props:globalId_attribute_simple`
3. **Special rename**: any attribute starting with `tag_` gets renamed to `batid`

**Simplified mode attribute predicate**: `lbd:toCamelCase(attrName.split("Ifc")[0])`
(strips the "Ifc" suffix part of the attribute name and uses the LBD namespace)

**Source:** `AttributeSet.java`, `PropertySet.java` (L1 branches)

---

### 4.3 Level 2 (L2) — OPM Property Nodes

Instead of a direct literal, an intermediate `opm:Property` node is created.

**Structure for each property:**

```
element_resource
  props:toCamelCase(propertyName)  property_node

property_node
  rdf:type opm:Property
  schema:value "value"^^xsd:...
  [optional] smls:unit unit:M  (if unit known)
```

**Property node URI:** `<uriBase><propertyName>_<uncompressed_guid>`

**Source:** `PropertySet.java:writeOPM_Set()` (L2 branch), `AttributeSet.java:writeOPM_Set()`

---

### 4.4 Level 3 (L3) — OPM with Versioned States

Extends L2 by adding a `opm:CurrentPropertyState` node with a timestamp.

**Structure:**

```
element_resource
  props:toCamelCase(propertyName)  property_node

property_node
  rdf:type opm:Property
  opm:hasPropertyState  state_node

state_node
  rdf:type opm:CurrentPropertyState
  schema:value "value"^^xsd:...
  prov:generatedAtTime "2024-01-15T10:30:00"^^xsd:dateTime
  [optional] smls:unit unit:M
```

**State node URI:** `<uriBase>state_<propertyName>_<uncompressed_guid>_p<counter>` (properties)
or `<uriBase>state_<attrName>_<uncompressed_guid>_a<counter>` (attributes)

The counter increments per property so multiple states can be tracked.

**Source:** `PropertySet.java:writeOPM_Set()` (L3 branch), `AttributeSet.java:writeOPM_Set()`

---

### 4.5 Property Name Transformation — `toCamelCase()`

**Source:** `StringOperations.java:toCamelCase()`

Rules:

1. If the string is ALL UPPERCASE (e.g., `HVAC`): URL-encode it with underscores, return as-is (uppercase preserved)
2. Otherwise:
   a. Strip accent characters (decompose + remove combining marks)
   b. Split on spaces
   c. First token: lowercase all characters
   d. Subsequent tokens: capitalize first letter, lowercase rest
   e. Filter to alphabetic ASCII characters only (`filterCharacters()`)
   f. URL-encode the result
3. Handle IFC Unicode escapes: `\X\C5` → `Å` (etc.) before applying above rules

**Examples:**

- `Is External` → `isExternal`
- `Fire Rating` → `fireRating`
- `LoadBearing` → `loadbearing`
- `Ref. Level` → `refLevel` (non-alpha stripped)

---

### 4.6 IFC Quantity Sets (IfcElementQuantity)

Handled identically to property sets. Quantity types include:

- `IfcQuantityLength` → `express:hasDouble` value (length)
- `IfcQuantityArea` → `express:hasDouble` value (area)
- `IfcQuantityVolume` → `express:hasDouble` value (volume)
- `IfcQuantityCount` → `express:hasInteger` value (count)

Path to quantity values:

```
IfcElementQuantity
  quantities_IfcElementQuantity
    → IfcQuantityXxx
      name_IfcQuantityXxx → express:hasString (property name)
      xxxValue_IfcQuantityXxx → express:hasDouble/hasInteger (value)
      unit_IfcQuantityXxx (optional explicit unit)
```

**Source:** `IFCtoLBDConverterCore.java:handleUnitsAndPropertySetData()`

---

### 4.7 Unit Handling

Enabled when `hasUnits=true`.

**Step 1 — Read project units** from `IfcUnitAssignment`:

```
IfcProject
  unitsInContext_IfcProject
    → IfcUnitAssignment
      units_IfcUnitAssignment
        → IfcSIUnit (or IfcConversionBasedUnit)
          unitType_IfcNamedUnit → type (e.g., LENGTHUNIT, AREAUNIT)
          prefix_IfcSIUnit → optional prefix (MILLI, KILO, etc.)
          name_IfcSIUnit → base unit name (METRE, SQUARE_METRE, etc.)
```

**Step 2 — Map to QUDT units:**

| IFC Unit Type + Prefix | QUDT Unit      |
| ---------------------- | -------------- |
| LENGTHUNIT (no prefix) | `unit:M`       |
| LENGTHUNIT + MILLI     | `unit:MilliM`  |
| AREAUNIT (no prefix)   | `unit:M2`      |
| AREAUNIT + MILLI       | `unit:MilliM2` |
| VOLUMEUNIT (no prefix) | `unit:M3`      |
| VOLUMEUNIT + MILLI     | `unit:MilliM3` |
| PLANEANGLEUNIT         | `unit:RAD`     |

**Step 3 — Attach to properties:** For L2/L3, add `smls:unit unit:M` to the property node.
For L1, units are not attached to the literal (they are only used in L2/L3 OPM nodes).

**Per-property units:** If the `IfcPropertySingleValue` has an explicit `unit_IfcPropertySingleValue`, that overrides the project default.

**Source:** `UNIT.java`, `SMLS.java`, `IFCtoLBDConverterCore.java:handleUnitsAndPropertySetData()`, `PropertySet.java`

---

### 4.8 bSDD Integration

When a property name matches a bSDD (buildingSMART Data Dictionary) entry:

1. The property set name is matched against known IFC4 PSD definitions (`psetdef.ttl` + `pset/*.ttl`)
2. If matched: `rdfs:seeAlso <bSDD URI>` is added to the property node (L2/L3) or element (L1)
3. For "Common" property sets (e.g., `Pset_WallCommon`): the bSDD class type is added

**PSD namespace:** `https://www.linkedbuildingdata.net/IFC4-PSD#`
Properties used: `ifc4-psd:name`, `ifc4-psd:propertyDef`, `ifc4-psd:ifdguid`

**Source:** `PROPS.java`, `PropertySet.java`

---

### 4.9 EXPRESS Type Unwrapping

IFC attribute values in ifcOWL are wrapped in EXPRESS typed nodes. The converter unwraps these:

| EXPRESS Property     | XSD Type                                | When Used                        |
| -------------------- | --------------------------------------- | -------------------------------- |
| `express:hasString`  | `xsd:string`                            | IfcLabel, IfcIdentifier, IfcText |
| `express:hasDouble`  | `xsd:double`                            | IfcReal, IfcLengthMeasure, etc.  |
| `express:hasInteger` | `xsd:integer`                           | IfcInteger, IfcCountMeasure      |
| `express:hasBoolean` | `xsd:boolean`                           | IfcBoolean                       |
| `express:hasLogical` | `xsd:string` ("TRUE"/"FALSE"/"UNKNOWN") | IfcLogical                       |

**Source:** `IfcOWL.java:EXPRESS inner class`

---

## 5. URI Construction

### 5.1 Standard Element URIs (default)

**Function:** `LBD_RDF_Utils.createformattedURIRecource()`
**Source:** `LBD_RDF_Utils.java`

**Pattern:** `<uriBase><element_type_lowercase>_<uncompressed_guid>`

Where:

- `uriBase` = the base URI provided at runtime (e.g., `https://example.org/building#`); must end with `#` or `/`
- `element_type_lowercase` = the local name of the IFC OWL class, lowercased (e.g., `ifcwall` → `ifcwall`)
- `uncompressed_guid` = the element's GUID converted from IFC compressed format to standard UUID hex (see §5.3)

**Example:** `https://example.org/building#ifcwall_3cUkl32yn8xBVyoVKlVFdT`

**Fallback when no GUID:**

- For `IfcPropertySingleValue`: `<uriBase>propertySingleValue_<sequential_number>`
- For others: strip "Ifc" prefix, use `<uriBase><type_lowercase>_<local_name_of_ifcowl_resource>`

**Optional:** If `exportIfcOWL=true`, also add `owl:sameAs` triple pointing to the original ifcOWL resource.

---

### 5.2 Hierarchical Element URIs (optional)

**Function:** `LBD_RDF_Utils.createformattedHierarchicalURIRecource()`
**Source:** `LBD_RDF_Utils.java`
**Enabled when:** `hasHierarchicalNaming=true`

**Two variants:**

**Variant A — top-level** (no parent URL):
Pattern: `<uriBase><url_encoded_name>` if name available, else GUID-based fallback

**Variant B — child element** (has parent URL):
Pattern: `<parent_url>/<url_encoded_name>` if name available
Else: `<parent_url>/<type_lowercase>_<uncompressed_guid>`

This creates a human-readable URL hierarchy that mirrors the building topology.

**Example:**

- Building: `https://example.org/building#MyBuilding`
- Storey: `https://example.org/building#MyBuilding/Level1`
- Space: `https://example.org/building#MyBuilding/Level1/Room101`

---

### 5.3 GUID Compression/Decompression

**Source:** `GuidCompressor.java`

IFC uses a 22-character compressed GUID format with a custom base64-like alphabet.

**Custom alphabet (64 characters):**

```
0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$
```

(Standard digits, then uppercase, then lowercase, then `_` and `$`)

**Compression structure:**
The 22 chars are split into 6 groups: `[2][4][4][4][4][4]`
Each group decodes to a number that, concatenated, forms the 128-bit UUID.

**Decompression algorithm:**

1. For each group, convert characters using the custom alphabet (each char → 0–63)
2. Accumulate: `num = num * 64 + value`
3. Concatenate the resulting numbers as hex
4. Format as standard UUID: `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` (lowercase)

**Example:**
IFC compressed: `3cUkl32yn8xBVyoVKlVFdT`
Uncompressed UUID: `0d3c8b96-5b32-4e7b-2b56-f28f295b5664`

The **uncompressed UUID** (without hyphens, 32 hex chars) is used in element URIs.

---

### 5.4 URL Encoding for Names

**Source:** `IfcOWLUtils.java:getURLEncodedName()`

- Read name from `name_IfcRoot → express:hasString`
- Replace spaces with underscores (`_`)
- Apply `java.net.URLEncoder.encode()` for remaining special characters

---

### 5.5 URI Patterns Summary

| Node Type                 | URI Pattern                                                  |
| ------------------------- | ------------------------------------------------------------ |
| Site                      | `<base><type_lc>_<guid32>`                                   |
| Building                  | `<base><type_lc>_<guid32>`                                   |
| Storey                    | `<base><type_lc>_<guid32>`                                   |
| Space                     | `<base><type_lc>_<guid32>`                                   |
| Element                   | `<base><type_lc>_<guid32>`                                   |
| Attribute set node        | `<base>AttributeSet_<guid32>`                                |
| Property node (L2/L3)     | `<base><propertyName>_<guid32>`                              |
| Property state node (L3)  | `<base>state_<propName>_<guid32>_p<n>`                       |
| Attribute state node (L3) | `<base>state_<attrName>_<guid32>_a<n>`                       |
| Geometry node             | `<base><type_lc>_<guid32>_geometry`                          |
| Geolocation geometry      | `urn:bot:geom:pt:<guid32>`                                   |
| BOT Interface node        | Generated during finish_geometry() from pair of element URIs |

---

## 6. Additional Features

### 6.1 Geometry / Bounding Boxes

**Enabled when:** `hasGeometry=true`
**Source:** `IFCtoLBDConverterCore.java:addGeometry()`, `IFCGeometry.java`

For each element with a geometry representation, the converter:

1. Calls `IFCGeometry` (backed by IfcOpenShell) to compute the bounding box
2. Creates a `_geometry` resource: `<element_uri>_geometry`
3. Adds: `element_resource omg:hasGeometry geometry_resource`
4. Adds geometry representation in one of two modes:

**Mode A — WKT bounding box** (`hasBoundingBoxWKT=true`):

```
geometry_resource
  rdf:type omg:Geometry
  geo:asWKT "POLYGON((xmin ymin, xmax ymin, xmax ymax, xmin ymax, xmin ymin))"^^geo:wktLiteral
```

(2D footprint polygon from X/Y extents)

**Mode B — LBD BoundingBox nodes** (default when `hasBoundingBoxWKT=false`):

```
element_resource
  lbd:hasBoundingBox bbox_node

bbox_node
  lbd:x-min "x_min_value"^^xsd:double
  lbd:x-max "x_max_value"^^xsd:double
  lbd:y-min "y_min_value"^^xsd:double
  lbd:y-max "y_max_value"^^xsd:double
  lbd:z-min "z_min_value"^^xsd:double
  lbd:z-max "z_max_value"^^xsd:double
```

**OBJ export:** If geometry processing is active, also exports a base64-encoded OBJ representation:

```
geometry_resource
  fog:asObj_v3.0-obj "base64encodedOBJcontent"^^xsd:string
```

**RTree index:** All bounding boxes are added to a 3D RTree for later interface detection.

---

### 6.2 Interface Detection

**Enabled when:** `hasInterfaces=true` (requires geometry)
**Source:** `IFCtoLBDConverterCore.java:finish_geometry()`

After all elements are processed:

1. For each element, query the RTree with its bounding box expanded by 0.05m in all directions
2. For each overlapping element pair (A, B) where A ≠ B:
   - Create a `bot:Interface` resource
   - Add `A bot:interfaceOf interface_node`
   - Add `B bot:interfaceOf interface_node`
3. Also adds `lbd:containsInBoundingBox` triples for containment relationships discovered via RTree

**Note:** Interface detection is O(n²) in the worst case. The RTree limits this in practice.

---

### 6.3 Geolocation

**Enabled when:** `hasGeolocation=true`
**Source:** `IFC_Geolocation.java`, `IfcOWL_GeolocationUtil.java`

Reads from `IfcSite` instances:

```
IfcSite
  refLatitude_IfcSite
    → RDF list (list:hasContents, list:hasNext)
      → degrees, minutes, seconds, millionths_of_seconds (4 integers)

IfcSite
  refLongitude_IfcSite
    → same RDF list structure
```

**Conversion to decimal degrees:**

```
decimal = degrees + minutes/60 + seconds/3600 + millionths/3600000000
```

**WKT output:** `"POINT (<lon> <lat>)"` (longitude first — WKT convention)

**Attached to site:**

```
site_resource
  rdf:type geo:Feature

geometry_resource (URI: urn:bot:geom:pt:<guid32>)
  rdf:type geo:Geometry
  geo:asWKT "POINT (<lon> <lat>)"^^geo:wktLiteral
```

The site resource links to geometry via `omg:hasGeometry geometry_resource`.

---

### 6.4 Hierarchical Naming

**Enabled when:** `hasHierarchicalNaming=true`
**Source:** `LBD_RDF_Utils.java:createformattedHierarchicalURIRecource()`

Instead of flat GUID-based URIs, elements get URIs that reflect their position in the building hierarchy:

```
<base>BuildingName/StoreyName/SpaceName/ElementName
```

If any name is unavailable, falls back to `<parent>/<type_lc>_<guid32>`.

This produces human-readable, navigable URIs but requires that IFC elements have meaningful names.

---

### 6.5 Performance Boost Mode

**Enabled when:** `hasPerformanceBoost=true` (default)
**Source:** `IFCtoLBDConverterCore.java`

Uses Apache Jena TDB2 (on-disk triple store) instead of in-memory models for the intermediate ifcOWL representation. This reduces memory usage for large IFC files at the cost of slower I/O.

When disabled, all intermediate RDF is kept in memory (faster but uses more RAM).

---

### 6.6 Separate Output Models

Two flags control model separation:

| Flag                               | Default | Effect                                                          |
| ---------------------------------- | ------- | --------------------------------------------------------------- |
| `hasSeparateBuildingElementsModel` | `false` | When true, building elements go into a separate RDF graph/model |
| `hasSeparatePropertiesModel`       | `false` | When true, all properties go into a separate RDF graph/model    |

When false (default), everything is in a single combined model. When true, outputs are split for more targeted querying.

---

### 6.7 IFC OWL Export

**Enabled when:** `exportIfcOWL=true` (default)
Adds `owl:sameAs` from each LBD element resource to its corresponding ifcOWL resource.

This creates links between the LBD graph and the full ifcOWL representation, enabling SPARQL queries that traverse from LBD into the complete IFC data.

---

### 6.8 Non-LBD Element Handling

**Enabled when:** `hasNonLBDElement=true` (default)
Source: `IFCtoLBDConverterCore.java:addSingleElement()`

Scans ALL `globalId_IfcRoot` statements to find any IFC element not reached via the spatial hierarchy traversal. Such orphaned elements:

1. Are checked via `isIfcElement()` (walks `rdfs:subClassOf` to find `IfcElement` ancestor)
2. If confirmed as IfcElement subclass, are created with `bot:Element` type
3. Get all property sets and attributes attached
4. Are NOT connected spatially (no bot:containsElement, bot:adjacentElement, etc.)

This ensures no elements are silently dropped from the output.

---

### 6.9 .ifczip Support

**Source:** `IFCtoLBDConverter.java`

If the input file has `.ifczip` extension, the converter decompresses it in-memory before processing. The extracted `.ifc` content is piped directly into the ifcOWL converter without writing a temporary file (uses `ZipInputStream`).

---

## 7. Conversion Configuration Flags

Full list of `ConversionProperties` flags with defaults:

| Flag                               | Default | Description                                |
| ---------------------------------- | ------- | ------------------------------------------ |
| `hasBuildingElements`              | `true`  | Include building elements in output        |
| `hasSeparateBuildingElementsModel` | `false` | Elements in separate RDF model             |
| `hasBuildingProperties`            | `true`  | Include property sets                      |
| `hasSeparatePropertiesModel`       | `false` | Properties in separate RDF model           |
| `hasGeolocation`                   | `false` | Extract and attach IfcSite lat/lon         |
| `hasGeometry`                      | `false` | Compute and attach bounding boxes          |
| `exportIfcOWL`                     | `true`  | Add owl:sameAs to ifcOWL resources         |
| `hasUnits`                         | `false` | Attach QUDT units to properties            |
| `hasBoundingBoxWKT`                | `false` | Use WKT polygon for bounding box           |
| `hasHierarchicalNaming`            | `false` | Use name-based hierarchical URIs           |
| `hasPerformanceBoost`              | `true`  | Use TDB2 disk store for ifcOWL             |
| `hasNonLBDElement`                 | `true`  | Include elements outside spatial hierarchy |
| `hasInterfaces`                    | `false` | Detect bot:Interface via geometry overlap  |

**Source:** `ConversionProperties.java`

---

## 8. IFC Schema Version Handling

### 8.1 Schema Detection

**Source:** `IfcOWLUtils.java:getExpressSchema()`

Reads the `FILE_SCHEMA` line from the IFC STEP file header. Maps to the corresponding ifcOWL ontology version string:

| IFC Schema String    | ifcOWL Ontology Version |
| -------------------- | ----------------------- |
| `IFC2X3`             | `IFC2X3_TC1`            |
| `IFC4`               | `IFC4_ADD2`             |
| `IFC4x1`             | `IFC4x1`                |
| `IFC4x2` or `IFC4X2` | `IFC4x3_RC1`            |
| `IFC4x3` or `IFC4X3` | `IFC4x3_RC1`            |
| `IFC4x3_RC1`         | `IFC4x3_RC1`            |

---

### 8.2 Version-Specific Property Name Differences

The most important version-branching is in the aggregation and property definition relationships:

| Relationship               | IFC2x3 Property Name              | IFC4+ Property Name                        |
| -------------------------- | --------------------------------- | ------------------------------------------ |
| Parent in decomposition    | `relatingObject_IfcRelDecomposes` | `relatingObject_IfcRelAggregates`          |
| Children in decomposition  | `relatedObjects_IfcRelDecomposes` | `relatedObjects_IfcRelAggregates`          |
| Element → PropertySet link | `relatedObjects_IfcRelDefines`    | `relatedObjects_IfcRelDefinesByProperties` |

The converter detects the schema version and uses the correct property names throughout.

**Source:** `IfcOWLUtils.java:getNextLevelPath()`, `getPropertySetPath()`

---

### 8.3 ifcOWL Ontology Loading

**Source:** `IFCtoLBDConverterCore.java:readInOntologies()`

The converter loads the following resource files from the JAR at startup:

| Resource File                             | Purpose                                        |
| ----------------------------------------- | ---------------------------------------------- |
| `IFC2X3_TC1.ttl` / `IFC4_ADD2.ttl` / etc. | ifcOWL ontology for the detected IFC version   |
| `prod.ttl`                                | PRODUCT ontology (`https://w3id.org/product#`) |
| `prod_furnishing.ttl`                     | Furniture Ontology                             |
| `beo_ontology.ttl`                        | Building Element Ontology                      |
| `mep_ontology.ttl`                        | MEP/Distribution Element Ontology              |
| `psetdef.ttl`                             | IFC4 Property Set Definitions (bSDD)           |
| `pset/*.ttl`                              | Individual property set definition files       |

These are all loaded into `ontology_model` (Jena OntModel) which is then queried to build the `ifcowl_product_map`.

---

## 9. Complete Conversion Pipeline (for reimplementation)

The following is the logical sequence for reimplementing this converter:

### Phase 1: Setup

1. Detect IFC schema version from file header
2. Load product ontology TTL files (beo, furn, mep)
3. Build `ifc_class → lbd_class` map by reading `rdfs:seeAlso` triples
4. Parse IFC file (ifcopenshell in Python)
5. Read `IfcUnitAssignment` to build unit map (if `hasUnits=true`)
6. Set base URI (default: `https://dot.dc.rwth-aachen.de/IFCtoLBDset#`)

### Phase 2: Spatial Hierarchy Traversal

```
for site in ifc.by_type("IfcSite"):
    create bot:Site resource

    for building in site.IsDecomposedBy[*].RelatedObjects:
        create bot:Building resource
        site bot:hasBuilding building

        for storey in building.IsDecomposedBy[*].RelatedObjects:
            create bot:Storey resource
            building bot:hasStorey storey

            for element in storey.ContainsElements[*].RelatedElements:
                create element resource (bot:Element + product type)
                storey bot:containsElement element
                attach_properties(element)
                attach_hosted_elements(element)
                attach_aggregated_elements(element)

            for space in storey.IsDecomposedBy[*].RelatedObjects:
                create bot:Space resource
                storey bot:hasSpace space

                for element in space.ContainsElements[*].RelatedElements:
                    space bot:containsElement element

                for element in space.BoundedBy[*].RelatedBuildingElement:
                    space bot:adjacentElement element
```

### Phase 3: Property Attachment

```
for element in all_elements:
    for pset in element.IsDefinedBy[*].RelatingPropertyDefinition:
        if isinstance(pset, IfcPropertySet):
            for prop in pset.HasProperties:
                attach_property(element, prop.Name, prop.NominalValue, prop.Unit)
        if isinstance(pset, IfcElementQuantity):
            for qty in pset.Quantities:
                attach_property(element, qty.Name, qty.Value, qty.Unit)

    # Also type object property sets
    for rel in element.IsTypedBy:
        for pset in rel.RelatingType.HasPropertySets:
            [same as above]

    # Attributes
    attach_attributes(element)  # GlobalId, Name, ObjectType, Tag, etc.
```

### Phase 4: Optional Post-processing

- Geometry + bounding boxes (if `hasGeometry=true`)
- Interface detection via spatial overlap (if `hasInterfaces=true`)
- Geolocation from IfcSite lat/lon (if `hasGeolocation=true`)
- Orphaned element scan (if `hasNonLBDElement=true`)

---

_Document extracted from IFCtoLBD v2.44.0 Java source. All file and method references verified against source code in `IFCtoLBD/src/main/java/org/linkedbuildingdata/ifc2lbd/` and `IFCtoLBD/src/main/resources/`._
