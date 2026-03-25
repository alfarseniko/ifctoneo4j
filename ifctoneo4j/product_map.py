"""
product_map.py — IFC class → LBD label mapping

Reimplements the Java IFCtoLBD `ifcowl_product_map` that is built at runtime
by loading beo_ontology.ttl / mep_ontology.ttl / prod_furnishing.ttl and
querying rdfs:seeAlso triples.  Here we encode the same data as plain Python
dicts so no ontology tooling is required.

Structure
---------
PRODUCT_MAP : dict[str, dict]
    Keys   — IFC class name exactly as returned by ifcopenshell (e.g. "IfcWall")
    Values — {
        "namespace":  "beo" | "mep" | "furn",
        "label":      Neo4j node label for the specific type (e.g. "Wall"),
        "predefined": dict[str, str]  # PredefinedType value → specific label
    }

The base label is always added.  If the element also has a PredefinedType that
matches a key in "predefined", that label is added in addition (not instead).

Every element also receives the generic "Element" label (bot:Element) which is
applied unconditionally by the element converter regardless of this map.

Namespace Neo4j label prefixes used
-------------------------------------
  beo  → "Beo"   (Building Element Ontology)
  mep  → "Mep"   (MEP / Distribution Element Ontology)
  furn → "Furn"  (Furniture Ontology)

Source: schema sections 2.3, 2.4, 2.5 of ifc-to-lbd-schema.md
"""

from __future__ import annotations
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Internal type alias
# ---------------------------------------------------------------------------
_Entry = Dict  # {"namespace": str, "label": str, "predefined": dict[str,str]}


def _beo(label: str, predefined: Optional[dict] = None) -> _Entry:
    return {"namespace": "beo", "label": label, "predefined": predefined or {}}


def _mep(label: str, predefined: Optional[dict] = None) -> _Entry:
    return {"namespace": "mep", "label": label, "predefined": predefined or {}}


def _furn(label: str, predefined: Optional[dict] = None) -> _Entry:
    return {"namespace": "furn", "label": label, "predefined": predefined or {}}


# ---------------------------------------------------------------------------
# 2.3  Building Elements (BEO)
# ---------------------------------------------------------------------------
# Predefined-type subclasses follow the pattern  <BaseClass>_<PREDEFINED_TYPE>
# in Neo4j labels.  They are listed here exactly as they appear in beo_ontology.ttl.

_BEAM_TYPES = {
    "BEAM":      "Beam_BEAM",
    "HOLLOWCORE":"Beam_HOLLOWCORE",
    "JOIST":     "Beam_JOIST",
    "LINTEL":    "Beam_LINTEL",
    "SPANDREL":  "Beam_SPANDREL",
    "T_BEAM":    "Beam_T_BEAM",
}

_BUILDING_ELEMENT_PART_TYPES = {
    "INSULATION":    "BuildingElementPart_INSULATION",
    "PRECASTPANEL":  "BuildingElementPart_PRECASTPANEL",
}

_COLUMN_TYPES = {
    "COLUMN":   "Column_COLUMN",
    "PILASTER": "Column_PILASTER",
}

_COVERING_TYPES = {
    "CEILING":      "Covering_CEILING",
    "CLADDING":     "Covering_CLADDING",
    "FLOORING":     "Covering_FLOORING",
    "INSULATION":   "Covering_INSULATION",
    "MEMBRANE":     "Covering_MEMBRANE",
    "MOLDING":      "Covering_MOLDING",
    "ROOFING":      "Covering_ROOFING",
    "SKIRTINGBOARD":"Covering_SKIRTINGBOARD",
    "SLEEVING":     "Covering_SLEEVING",
    "WRAPPING":     "Covering_WRAPPING",
}

_DOOR_TYPES = {
    "DOOR":     "Door_DOOR",
    "GATE":     "Door_GATE",
    "TRAPDOOR": "Door_TRAPDOOR",
}

_FASTENER_TYPES = {
    "GLUE":   "Fastener_GLUE",
    "MORTAR": "Fastener_MORTAR",
    "WELD":   "Fastener_WELD",
}

_FOOTING_TYPES = {
    "CAISSON_FOUNDATION": "Footing_CAISSON_FOUNDATION",
    "FOOTING_BEAM":       "Footing_FOOTING_BEAM",
    "PAD_FOOTING":        "Footing_PAD_FOOTING",
    "PILE_CAP":           "Footing_PILE_CAP",
    "STRIP_FOOTING":      "Footing_STRIP_FOOTING",
}

_MECHANICAL_FASTENER_TYPES = {
    "ANCHORBOLT":      "MechanicalFastener_ANCHORBOLT",
    "BOLT":            "MechanicalFastener_BOLT",
    "DOWEL":           "MechanicalFastener_DOWEL",
    "NAIL":            "MechanicalFastener_NAIL",
    "NAILPLATE":       "MechanicalFastener_NAILPLATE",
    "RIVET":           "MechanicalFastener_RIVET",
    "SCREW":           "MechanicalFastener_SCREW",
    "SHEARCONNECTOR":  "MechanicalFastener_SHEARCONNECTOR",
    "STAPLE":          "MechanicalFastener_STAPLE",
    "STUDSHEARCONNECTOR": "MechanicalFastener_STUDSHEARCONNECTOR",
}

_MEMBER_TYPES = {
    "BRACE":   "Member_BRACE",
    "CHORD":   "Member_CHORD",
    "COLLAR":  "Member_COLLAR",
    "MEMBER":  "Member_MEMBER",
    "MULLION": "Member_MULLION",
    "PLATE":   "Member_PLATE",
    "POST":    "Member_POST",
    "PURLIN":  "Member_PURLIN",
    "RAFTER":  "Member_RAFTER",
    "STRINGER":"Member_STRINGER",
    "STRUT":   "Member_STRUT",
    "STUD":    "Member_STUD",
}

_PILE_TYPES = {
    "BORED":      "Pile_BORED",
    "COHESION":   "Pile_COHESION",
    "DRIVEN":     "Pile_DRIVEN",
    "FRICTION":   "Pile_FRICTION",
    "JETGROUTING":"Pile_JETGROUTING",
    "SUPPORT":    "Pile_SUPPORT",
}

_PLATE_TYPES = {
    "CURTAIN_PANEL": "Plate_CURTAIN_PANEL",
    "SHEET":         "Plate_SHEET",
}

_RAILING_TYPES = {
    "BALUSTRADE": "Railing_BALUSTRADE",
    "GUARDRAIL":  "Railing_GUARDRAIL",
    "HANDRAIL":   "Railing_HANDRAIL",
}

_ROOF_TYPES = {
    "BARREL_ROOF":      "Roof_BARREL_ROOF",
    "BUTTERFLY_ROOF":   "Roof_BUTTERFLY_ROOF",
    "DOME_ROOF":        "Roof_DOME_ROOF",
    "FLAT_ROOF":        "Roof_FLAT_ROOF",
    "FREEFORM":         "Roof_FREEFORM",
    "GAMBREL_ROOF":     "Roof_GAMBREL_ROOF",
    "GABLE_ROOF":       "Roof_GABLE_ROOF",
    "HIPPED_GABLE_ROOF":"Roof_HIPPED_GABLE_ROOF",
    "HIP_ROOF":         "Roof_HIP_ROOF",
    "MANSARD_ROOF":     "Roof_MANSARD_ROOF",
    "PAVILION_ROOF":    "Roof_PAVILION_ROOF",
    "RAINBOW_ROOF":     "Roof_RAINBOW_ROOF",
    "SHED_ROOF":        "Roof_SHED_ROOF",
}

_SLAB_TYPES = {
    "BASESLAB": "Slab_BASESLAB",
    "FLOOR":    "Slab_FLOOR",
    "LANDING":  "Slab_LANDING",
    "ROOF":     "Slab_ROOF",
}

_TRANSPORT_ELEMENT_TYPES = {
    "ELEVATOR":      "TransportElement_ELEVATOR",
    "ESCALATOR":     "TransportElement_ESCALATOR",
    "MOVINGWALKWAY": "TransportElement_MOVINGWALKWAY",
    "CRANEWAY":      "TransportElement_CRANEWAY",
    "LIFTINGGANG":   "TransportElement_LIFTINGGANG",
}

_WALL_TYPES = {
    "FREESTANDING":  "Wall_FREESTANDING",
    "MOVABLE":       "Wall_MOVABLE",
    "PARAPET":       "Wall_PARAPET",
    "PARTITIONING":  "Wall_PARTITIONING",
    "PLUMBINGWALL":  "Wall_PLUMBINGWALL",
    "POLYGONAL":     "Wall_POLYGONAL",
    "SHEAR":         "Wall_SHEAR",
    "SOLIDWALL":     "Wall_SOLIDWALL",
    "STANDARD":      "Wall_STANDARD",
    "WINDING":       "Wall_WINDING",
}

_WINDOW_TYPES = {
    "WINDOW":    "Window_WINDOW",
    "SKYLIGHT":  "Window_SKYLIGHT",
    "LIGHTDOME": "Window_LIGHTDOME",
}

# ---------------------------------------------------------------------------
# 2.4  Furnishing Elements (FURN)
# ---------------------------------------------------------------------------
_FURNITURE_TYPES = {
    "CHAIR":       "Chair",
    "TABLE":       "Table",
    "DESK":        "Desk",
    "SOFA":        "Sofa",
    "CLOSET":      "Closet",
    "FILECABINET": "FileCabinet",
    "BED":         "Bed",
    "SHELF":       "Shelf",
}

# ---------------------------------------------------------------------------
# 2.5  MEP / Distribution Elements — predefined-type subclasses follow
#       the -TYPE suffix pattern, e.g. mep:Actuator-ELECTRICACTUATOR.
#       We encode them as  ActuatorType_ELECTRICACTUATOR  etc.
# ---------------------------------------------------------------------------
_ACTUATOR_TYPES = {
    "ELECTRICACTUATOR":   "Actuator_ELECTRICACTUATOR",
    "HANDOPERATEDACTUATOR": "Actuator_HANDOPERATEDACTUATOR",
    "HYDRAULICACTUATOR":  "Actuator_HYDRAULICACTUATOR",
    "PNEUMATICACTUATOR":  "Actuator_PNEUMATICACTUATOR",
    "THERMOSTATICACTUATOR":"Actuator_THERMOSTATICACTUATOR",
}

_ALARM_TYPES = {
    "BELL":             "Alarm_BELL",
    "BREAKGLASSBUTTON": "Alarm_BREAKGLASSBUTTON",
    "LIGHT":            "Alarm_LIGHT",
    "MANUALPULLBOX":    "Alarm_MANUALPULLBOX",
    "SIREN":            "Alarm_SIREN",
    "WHISTLE":          "Alarm_WHISTLE",
}

_BOILER_TYPES = {
    "STEAM":    "Boiler_STEAM",
    "WATER":    "Boiler_WATER",
}

_CHILLER_TYPES = {
    "AIRCOOLED":   "Chiller_AIRCOOLED",
    "WATERCOOLED": "Chiller_WATERCOOLED",
    "HEATRECOVERY":"Chiller_HEATRECOVERY",
}

_COMPRESSOR_TYPES = {
    "DYNAMIC":       "Compressor_DYNAMIC",
    "RECIPROCATING": "Compressor_RECIPROCATING",
    "ROTARY":        "Compressor_ROTARY",
    "SCROLL":        "Compressor_SCROLL",
}

_CONTROLLER_TYPES = {
    "FLOATING":      "Controller_FLOATING",
    "PROGRAMMABLE":  "Controller_PROGRAMMABLE",
    "PROPORTIONAL":  "Controller_PROPORTIONAL",
    "TIMEDTWOSTEP":  "Controller_TIMEDTWOSTEP",
    "TWOSTEP":       "Controller_TWOSTEP",
}

_DAMPER_TYPES = {
    "BACKDRAFTDAMPER":   "Damper_BACKDRAFTDAMPER",
    "BALANCINGDAMPER":   "Damper_BALANCINGDAMPER",
    "BLASTDAMPER":       "Damper_BLASTDAMPER",
    "CONTROLDAMPER":     "Damper_CONTROLDAMPER",
    "FIREDAMPER":        "Damper_FIREDAMPER",
    "FIRESMOKEDAMPER":   "Damper_FIRESMOKEDAMPER",
    "FUMEHOODEXHAUST":   "Damper_FUMEHOODEXHAUST",
    "GRAVITYDAMPER":     "Damper_GRAVITYDAMPER",
    "GRAVITYRELIEF":     "Damper_GRAVITYRELIEF",
    "RELIEFDAMPER":      "Damper_RELIEFDAMPER",
    "SMOKEDAMPER":       "Damper_SMOKEDAMPER",
}

_ELECTRIC_APPLIANCE_TYPES = {
    "DISHWASHER":    "ElectricAppliance_DISHWASHER",
    "ELECTRICCOOKER":"ElectricAppliance_ELECTRICCOOKER",
    "ELECTRICHEATER":"ElectricAppliance_ELECTRICHEATER",
    "ELECTRICSTEAMER":"ElectricAppliance_ELECTRICSTEAMER",
    "FACSIMILE":     "ElectricAppliance_FACSIMILE",
    "FREESTANDINGFAN":"ElectricAppliance_FREESTANDINGFAN",
    "FREEZER":       "ElectricAppliance_FREEZER",
    "MICROWAVE":     "ElectricAppliance_MICROWAVE",
    "PHOTOCOPIER":   "ElectricAppliance_PHOTOCOPIER",
    "PRINTER":       "ElectricAppliance_PRINTER",
    "REFRIGERATOR":  "ElectricAppliance_REFRIGERATOR",
    "SCANNER":       "ElectricAppliance_SCANNER",
    "TELEPHONE":     "ElectricAppliance_TELEPHONE",
    "TUMBLEDRYER":   "ElectricAppliance_TUMBLEDRYER",
    "TV":            "ElectricAppliance_TV",
    "VENDINGMACHINE":"ElectricAppliance_VENDINGMACHINE",
    "WASHINGMACHINE":"ElectricAppliance_WASHINGMACHINE",
}

_FAN_TYPES = {
    "CENTRIFUGALFORWARDCURVED":    "Fan_CENTRIFUGALFORWARDCURVED",
    "CENTRIFUGALRADIAL":           "Fan_CENTRIFUGALRADIAL",
    "CENTRIFUGALBACKWARDINCLINEDCURVED": "Fan_CENTRIFUGALBACKWARDINCLINEDCURVED",
    "CENTRIFUGALAIRFOIL":          "Fan_CENTRIFUGALAIRFOIL",
    "AXIAL":                       "Fan_AXIAL",
    "PROPELLORAXIAL":              "Fan_PROPELLORAXIAL",
    "TUBEAXIAL":                   "Fan_TUBEAXIAL",
    "VANEAXIAL":                   "Fan_VANEAXIAL",
    "PLUGFAN":                     "Fan_PLUGFAN",
    "POWERROOF":                   "Fan_POWERROOF",
    "FANCOILUNIT":                 "Fan_FANCOILUNIT",
    "SPLITUNIT":                   "Fan_SPLITUNIT",
    "ROOFTOPUNIT":                 "Fan_ROOFTOPUNIT",
}

_FILTER_TYPES = {
    "AIRPARTICLEFILTER":    "Filter_AIRPARTICLEFILTER",
    "COMPRESSEDAIRFILTER":  "Filter_COMPRESSEDAIRFILTER",
    "ODORFILTER":           "Filter_ODORFILTER",
    "OILFILTER":            "Filter_OILFILTER",
    "STRAINER":             "Filter_STRAINER",
    "WATERFILTER":          "Filter_WATERFILTER",
}

_HEAT_EXCHANGER_TYPES = {
    "PLATE":  "HeatExchanger_PLATE",
    "SHELLANDTUBE": "HeatExchanger_SHELLANDTUBE",
    "TURNOVER": "HeatExchanger_TURNOVER",
}

_PUMP_TYPES = {
    "CIRCULATOR":       "Pump_CIRCULATOR",
    "ENDSUCTION":       "Pump_ENDSUCTION",
    "SPLITCASE":        "Pump_SPLITCASE",
    "SUBMERSIBLE":      "Pump_SUBMERSIBLE",
    "SUMPPUMP":         "Pump_SUMPPUMP",
    "VERTICALINLINE":   "Pump_VERTICALINLINE",
    "VERTICALTURBINE":  "Pump_VERTICALTURBINE",
}

_SANITARY_TERMINAL_TYPES = {
    "BATH":         "SanitaryTerminal_BATH",
    "BIDET":        "SanitaryTerminal_BIDET",
    "CISTERN":      "SanitaryTerminal_CISTERN",
    "SHOWER":       "SanitaryTerminal_SHOWER",
    "SINK":         "SanitaryTerminal_SINK",
    "SANITARYFOUNTAIN": "SanitaryTerminal_SANITARYFOUNTAIN",
    "TOILETPAN":    "SanitaryTerminal_TOILETPAN",
    "URINAL":       "SanitaryTerminal_URINAL",
    "WASHHANDBASIN":"SanitaryTerminal_WASHHANDBASIN",
    "WCSEAT":       "SanitaryTerminal_WCSEAT",
}

_SENSOR_TYPES = {
    "CO2SENSOR":           "Sensor_CO2SENSOR",
    "CONDUCTANCESENSOR":   "Sensor_CONDUCTANCESENSOR",
    "CONTACTSENSOR":       "Sensor_CONTACTSENSOR",
    "FIRESENSOR":          "Sensor_FIRESENSOR",
    "FLOWSENSOR":          "Sensor_FLOWSENSOR",
    "FROSTSENSOR":         "Sensor_FROSTSENSOR",
    "GASSENSOR":           "Sensor_GASSENSOR",
    "HEATSENSOR":          "Sensor_HEATSENSOR",
    "HUMIDITYSENSOR":      "Sensor_HUMIDITYSENSOR",
    "IDENTIFIERSENSOR":    "Sensor_IDENTIFIERSENSOR",
    "IONCONCENTRATIONSENSOR":"Sensor_IONCONCENTRATIONSENSOR",
    "LEVELSENSOR":         "Sensor_LEVELSENSOR",
    "LIGHTSENSOR":         "Sensor_LIGHTSENSOR",
    "MOISTURESENSOR":      "Sensor_MOISTURESENSOR",
    "MOVEMENTSENSOR":      "Sensor_MOVEMENTSENSOR",
    "PHSENSOR":            "Sensor_PHSENSOR",
    "PRESSURESENSOR":      "Sensor_PRESSURESENSOR",
    "RADIATIONSENSOR":     "Sensor_RADIATIONSENSOR",
    "RADIOACTIVITYSENSOR": "Sensor_RADIOACTIVITYSENSOR",
    "SMOKESENSOR":         "Sensor_SMOKESENSOR",
    "SOUNDSENSOR":         "Sensor_SOUNDSENSOR",
    "TEMPERATURESENSOR":   "Sensor_TEMPERATURESENSOR",
    "WINDSENSOR":          "Sensor_WINDSENSOR",
}

_SWITCHING_DEVICE_TYPES = {
    "CONTACTOR":         "SwitchingDevice_CONTACTOR",
    "DIMMERSWITCH":      "SwitchingDevice_DIMMERSWITCH",
    "EMERGENCYSTOP":     "SwitchingDevice_EMERGENCYSTOP",
    "KEYPAD":            "SwitchingDevice_KEYPAD",
    "MOMENTARYSWITCH":   "SwitchingDevice_MOMENTARYSWITCH",
    "SELECTORSWITCH":    "SwitchingDevice_SELECTORSWITCH",
    "STARTER":           "SwitchingDevice_STARTER",
    "SWITCHDISCONNECTOR":"SwitchingDevice_SWITCHDISCONNECTOR",
    "TOGGLESWITCH":      "SwitchingDevice_TOGGLESWITCH",
}

_TANK_TYPES = {
    "BASIN":        "Tank_BASIN",
    "BREAKPRESSURE":"Tank_BREAKPRESSURE",
    "EXPANSION":    "Tank_EXPANSION",
    "FEEDANDEXPANSION":"Tank_FEEDANDEXPANSION",
    "PRESSUREVESSEL":"Tank_PRESSUREVESSEL",
    "STORAGE":      "Tank_STORAGE",
    "VESSEL":       "Tank_VESSEL",
}

_TRANSFORMER_TYPES = {
    "CURRENT":   "Transformer_CURRENT",
    "FREQUENCY": "Transformer_FREQUENCY",
    "INVERTER":  "Transformer_INVERTER",
    "RECTIFIER": "Transformer_RECTIFIER",
    "VOLTAGE":   "Transformer_VOLTAGE",
}

_VALVE_TYPES = {
    "AIRRELEASE":       "Valve_AIRRELEASE",
    "ANTIVACUUM":       "Valve_ANTIVACUUM",
    "CHANGEOVER":       "Valve_CHANGEOVER",
    "CHECK":            "Valve_CHECK",
    "COMMISSIONING":    "Valve_COMMISSIONING",
    "DIVERTING":        "Valve_DIVERTING",
    "DRAWOFFCOCK":      "Valve_DRAWOFFCOCK",
    "DOUBLECHECK":      "Valve_DOUBLECHECK",
    "DOUBLEREGULATING": "Valve_DOUBLEREGULATING",
    "FLUSHING":         "Valve_FLUSHING",
    "GASCOCK":          "Valve_GASCOCK",
    "GASTAP":           "Valve_GASTAP",
    "ISOLATING":        "Valve_ISOLATING",
    "MIXING":           "Valve_MIXING",
    "PRESSUREREDUCING": "Valve_PRESSUREREDUCING",
    "PRESSURERELIEF":   "Valve_PRESSURERELIEF",
    "REGULATING":       "Valve_REGULATING",
    "SAFETYCUTOFF":     "Valve_SAFETYCUTOFF",
    "STEAMTRAP":        "Valve_STEAMTRAP",
    "STOPCOCK":         "Valve_STOPCOCK",
}

_WASTE_TERMINAL_TYPES = {
    "FLOORTRAP":         "WasteTerminal_FLOORTRAP",
    "FLOORWASTE":        "WasteTerminal_FLOORWASTE",
    "GULLYSUMP":         "WasteTerminal_GULLYSUMP",
    "GULLYTRAP":         "WasteTerminal_GULLYTRAP",
    "ROOFDRAIN":         "WasteTerminal_ROOFDRAIN",
    "WASTEDISPOSALUNIT": "WasteTerminal_WASTEDISPOSALUNIT",
    "WASTETRAP":         "WasteTerminal_WASTETRAP",
}

# ---------------------------------------------------------------------------
# Main mapping dictionary
# ---------------------------------------------------------------------------
PRODUCT_MAP: dict[str, _Entry] = {

    # ── BEO base elements ─────────────────────────────────────────────────────
    "IfcBuildingElement":       _beo("BuildingElement"),
    "IfcBeam":                  _beo("Beam",                  _BEAM_TYPES),
    "IfcBuildingElementPart":   _beo("BuildingElementPart",   _BUILDING_ELEMENT_PART_TYPES),
    "IfcChimney":               _beo("Chimney"),
    "IfcColumn":                _beo("Column",                _COLUMN_TYPES),
    "IfcCovering":              _beo("Covering",              _COVERING_TYPES),
    "IfcCurtainWall":           _beo("CurtainWall"),
    "IfcDiscreteAccessory":     _beo("DiscreteAccessory"),
    "IfcDoor":                  _beo("Door",                  _DOOR_TYPES),
    "IfcElementComponent":      _beo("ElementComponent"),
    "IfcFastener":              _beo("Fastener",              _FASTENER_TYPES),
    "IfcFooting":               _beo("Footing",               _FOOTING_TYPES),
    "IfcMechanicalFastener":    _beo("MechanicalFastener",    _MECHANICAL_FASTENER_TYPES),
    "IfcMember":                _beo("Member",                _MEMBER_TYPES),
    "IfcPile":                  _beo("Pile",                  _PILE_TYPES),
    "IfcPlate":                 _beo("Plate",                 _PLATE_TYPES),
    "IfcRailing":               _beo("Railing",               _RAILING_TYPES),
    "IfcRamp":                  _beo("Ramp"),
    "IfcRampFlight":            _beo("RampFlight"),
    "IfcReinforcingBar":        _beo("ReinforcingBar"),
    "IfcReinforcingElement":    _beo("ReinforcingElement"),
    "IfcReinforcingMesh":       _beo("ReinforcingMesh"),
    "IfcRoof":                  _beo("Roof",                  _ROOF_TYPES),
    "IfcShadingDevice":         _beo("ShadingDevice"),
    "IfcSlab":                  _beo("Slab",                  _SLAB_TYPES),
    "IfcStair":                 _beo("Stair"),
    "IfcStairFlight":           _beo("StairFlight"),
    "IfcTendon":                _beo("Tendon"),
    "IfcTendonAnchor":          _beo("TendonAnchor"),
    "IfcTransportElement":      _beo("TransportElement",      _TRANSPORT_ELEMENT_TYPES),
    "IfcVibrationIsolator":     _beo("VibrationIsolator"),
    "IfcWall":                  _beo("Wall",                  _WALL_TYPES),
    "IfcWallElementedCase":     _beo("WallElementedCase"),
    "IfcWindow":                _beo("Window",                _WINDOW_TYPES),

    # ── Furnishing (FURN) ─────────────────────────────────────────────────────
    "IfcFurnishingElement":     _furn("Furniture",            _FURNITURE_TYPES),
    "IfcFurniture":             _furn("Furniture",            _FURNITURE_TYPES),
    "IfcSystemFurnitureElement":_furn("Furniture"),

    # ── MEP / Distribution (MEP) ──────────────────────────────────────────────
    "IfcDistributionElement":            _mep("DistributionElement"),
    "IfcDistributionFlowElement":        _mep("DistributionFlowElement"),
    "IfcDistributionControlElement":     _mep("DistributionControlElement"),
    "IfcEnergyConversionDevice":         _mep("EnergyConversionDevice"),
    "IfcFlowController":                 _mep("FlowController"),
    "IfcFlowFitting":                    _mep("FlowFitting"),
    "IfcFlowMovingDevice":               _mep("FlowMovingDevice"),
    "IfcFlowSegment":                    _mep("FlowSegment"),
    "IfcFlowStorageDevice":              _mep("FlowStorageDevice"),
    "IfcFlowTerminal":                   _mep("FlowTerminal"),
    "IfcFlowTreatmentDevice":            _mep("FlowTreatmentDevice"),
    "IfcActuator":                       _mep("Actuator",             _ACTUATOR_TYPES),
    "IfcAirTerminal":                    _mep("AirTerminal"),
    "IfcAirTerminalBox":                 _mep("AirTerminalBox"),
    "IfcAirToAirHeatRecovery":           _mep("AirToAirHeatRecovery"),
    "IfcAlarm":                          _mep("Alarm",                _ALARM_TYPES),
    "IfcAudioVisualAppliance":           _mep("AudioVisualAppliance"),
    "IfcBoiler":                         _mep("Boiler",               _BOILER_TYPES),
    "IfcBurner":                         _mep("Burner"),
    "IfcCableCarrierFitting":            _mep("CableCarrierFitting"),
    "IfcCableCarrierSegment":            _mep("CableCarrierSegment"),
    "IfcCableFitting":                   _mep("CableFitting"),
    "IfcCableSegment":                   _mep("CableSegment"),
    "IfcChiller":                        _mep("Chiller",              _CHILLER_TYPES),
    "IfcCoil":                           _mep("Coil"),
    "IfcCommunicationsAppliance":        _mep("CommunicationsAppliance"),
    "IfcCompressor":                     _mep("Compressor",           _COMPRESSOR_TYPES),
    "IfcCondenser":                      _mep("Condenser"),
    "IfcController":                     _mep("Controller",           _CONTROLLER_TYPES),
    "IfcCooledBeam":                     _mep("CooledBeam"),
    "IfcCoolingTower":                   _mep("CoolingTower"),
    "IfcDamper":                         _mep("Damper",               _DAMPER_TYPES),
    "IfcDistributionChamberElement":     _mep("DistributionChamberElement"),
    "IfcDuctFitting":                    _mep("DuctFitting"),
    "IfcDuctSegment":                    _mep("DuctSegment"),
    "IfcDuctSilencer":                   _mep("DuctSilencer"),
    "IfcElectricAppliance":              _mep("ElectricAppliance",    _ELECTRIC_APPLIANCE_TYPES),
    "IfcElectricDistributionBoard":      _mep("ElectricDistributionBoard"),
    "IfcElectricFlowStorageDevice":      _mep("ElectricFlowStorageDevice"),
    "IfcElectricGenerator":              _mep("ElectricGenerator"),
    "IfcElectricMotor":                  _mep("ElectricMotor"),
    "IfcElectricTimeControl":            _mep("ElectricTimeControl"),
    "IfcEngine":                         _mep("Engine"),
    "IfcEvaporativeCooler":              _mep("EvaporativeCooler"),
    "IfcEvaporator":                     _mep("Evaporator"),
    "IfcFan":                            _mep("Fan",                  _FAN_TYPES),
    "IfcFilter":                         _mep("Filter",               _FILTER_TYPES),
    "IfcFireSuppressionTerminal":        _mep("FireSuppressionTerminal"),
    "IfcFlowInstrument":                 _mep("FlowInstrument"),
    "IfcFlowMeter":                      _mep("FlowMeter"),
    "IfcHeatExchanger":                  _mep("HeatExchanger",        _HEAT_EXCHANGER_TYPES),
    "IfcHumidifier":                     _mep("Humidifier"),
    "IfcInterceptor":                    _mep("Interceptor"),
    "IfcJunctionBox":                    _mep("JunctionBox"),
    "IfcLamp":                           _mep("Lamp"),
    "IfcLightFixture":                   _mep("LightFixture"),
    "IfcMedicalDevice":                  _mep("MedicalDevice"),
    "IfcMotorConnection":                _mep("MotorConnection"),
    "IfcOutlet":                         _mep("Outlet"),
    "IfcPipeFitting":                    _mep("PipeFitting"),
    "IfcPipeSegment":                    _mep("PipeSegment"),
    "IfcProtectiveDevice":               _mep("ProtectiveDevice"),
    "IfcProtectiveDeviceTrippingUnit":   _mep("ProtectiveDeviceTrippingUnit"),
    "IfcPump":                           _mep("Pump",                 _PUMP_TYPES),
    "IfcSanitaryTerminal":               _mep("SanitaryTerminal",     _SANITARY_TERMINAL_TYPES),
    "IfcSensor":                         _mep("Sensor",               _SENSOR_TYPES),
    "IfcSolarDevice":                    _mep("SolarDevice"),
    "IfcSpaceHeater":                    _mep("SpaceHeater"),
    "IfcStackTerminal":                  _mep("StackTerminal"),
    "IfcSwitchingDevice":                _mep("SwitchingDevice",      _SWITCHING_DEVICE_TYPES),
    "IfcTank":                           _mep("Tank",                 _TANK_TYPES),
    "IfcTransformer":                    _mep("Transformer",          _TRANSFORMER_TYPES),
    "IfcTubeBundle":                     _mep("TubeBundle"),
    "IfcUnitaryControlElement":          _mep("UnitaryControlElement"),
    "IfcUnitaryEquipment":               _mep("UnitaryEquipment"),
    "IfcValve":                          _mep("Valve",                _VALVE_TYPES),
    "IfcWasteTerminal":                  _mep("WasteTerminal",        _WASTE_TERMINAL_TYPES),
}


def get_labels(ifc_entity: str, predefined_type: Optional[str] = None) -> list[str]:
    """
    Return the list of Neo4j labels for a given IFC entity class name.

    Always includes "Element" (bot:Element).
    Adds the specific namespace-prefixed label if the class is in PRODUCT_MAP.
    Adds the predefined-type subclass label if predefined_type is given and
    matched.

    Parameters
    ----------
    ifc_entity : str
        IFC class name as returned by ``element.is_a()`` — e.g. "IfcWall".
    predefined_type : str | None
        Value of ``element.PredefinedType`` — e.g. "SOLIDWALL".
        ``None``, ``"NOTDEFINED"``, and ``"USERDEFINED"`` are treated as absent.

    Returns
    -------
    list[str]
        Ordered list of Neo4j label strings.  "Element" is always first.

    Examples
    --------
    >>> get_labels("IfcWall", "SOLIDWALL")
    ['Element', 'Wall', 'Wall_SOLIDWALL']
    >>> get_labels("IfcFan", "AXIAL")
    ['Element', 'Fan', 'Fan_AXIAL']
    >>> get_labels("IfcWall", None)
    ['Element', 'Wall']
    >>> get_labels("IfcProxy", None)
    ['Element']
    """
    labels: list[str] = ["Element"]

    entry = PRODUCT_MAP.get(ifc_entity)
    if entry is None:
        # Walk MRO-style: try stripping trailing digits / version suffixes.
        # ifcopenshell sometimes returns "IfcWall" for both IFC2x3 and IFC4;
        # no special handling needed here — the map keys are schema-agnostic.
        return labels

    labels.append(entry["label"])

    # Predefined-type subclass
    pt = predefined_type
    if pt and pt not in ("NOTDEFINED", "USERDEFINED", "NULL"):
        pt_upper = pt.upper()
        specific = entry["predefined"].get(pt_upper)
        if specific:
            labels.append(specific)

    return labels


def get_namespace(ifc_entity: str) -> Optional[str]:
    """Return the ontology namespace ('beo', 'mep', 'furn') for an IFC class."""
    entry = PRODUCT_MAP.get(ifc_entity)
    return entry["namespace"] if entry else None
