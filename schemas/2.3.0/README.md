# RESQML 2.3.0 XSD Schemas

RESQML 2.3.0 extends RESQML 2.2 with new data object types and enriched metadata.
It ships with EML common v2.3 (same as 2.2). All 2.2 documents remain valid
against the 2.3.0 schemas - every addition uses `minOccurs="0"` or introduces a
new top-level element.

## Schema layout

Follows the Energistics-published directory structure. RESQML schemas
(`targetNamespace=resqmlv2`) import EML common schemas (`targetNamespace=commonv2`)
via relative path `../../../common/v2.3/xsd_schemas/EmlAllObjects.xsd`.

```
2.3.0/
├── resqml/v2.3.0/xsd_schemas/       # RESQML v2.3.0 types (12 files)
│   ├── ResqmlAllObjects.xsd         # ← entry point for validation
│   ├── Interpretations.xsd          # ← SealState, TransmissibilityMultiplier
│   ├── Properties.xsd               # ← SimulationRunMetadata, SaturationFunctionSet
│   ├── Seismic.xsd                  # ← AcquisitionMethod enum
│   ├── Features.xsd, Geometry.xsd, Grids.xsd, ...
│   └── Wells.xsd
└── common/v2.3/xsd_schemas/         # EML common v2.3 types (22 files)
    ├── EmlAllObjects.xsd            # ← imported by RESQML schemas
    ├── Abstract.xsd                 # ← OSDU flattening + Extension refactor
    ├── Activities.xsd               # ← TypedValue on parameters
    ├── Collection.xsd               # ← Purpose enum + ParentCollection
    ├── CRS.xsd, Datum.xsd           # (unchanged from 2.2)
    ├── ...                          # remaining EML common XSDs
    └── PropertyKindDictionary_v2.3.xml
```

## Changes from 2.2

### 1. New data objects - `Properties.xsd` (+8,108 bytes, largest change)

Two new top-level data objects added via `substitutionGroup="eml:AbstractDataObject"`:

#### SimulationRunMetadata

Captures reservoir simulation run provenance:

```xml
<xs:complexType name="SimulationRunMetadata">
  <xs:complexContent>
    <xs:extension base="eml:AbstractObject">
      <xs:sequence>
        <xs:element name="SimulatorName"       type="eml:String256"    minOccurs="1"/>
        <xs:element name="SimulatorVersion"    type="eml:String256"    minOccurs="0"/>
        <xs:element name="RunDate"             type="xs:dateTime"      minOccurs="0"/>
        <xs:element name="RunDurationSeconds"  type="xs:double"        minOccurs="0"/>
        <xs:element name="InputCollection"     type="eml:DataObjectReference" minOccurs="0"/>
        <xs:element name="OutputCollection"    type="eml:DataObjectReference" minOccurs="0"/>
        <xs:element name="Grid"                type="eml:DataObjectReference" minOccurs="0"/>
        <xs:element name="RealizationIndex"    type="xs:nonNegativeInteger"   minOccurs="0"/>
        <xs:element name="Status"              type="resqml:SimulationRunStatus" minOccurs="0"/>
      </xs:sequence>
    </xs:extension>
  </xs:complexContent>
</xs:complexType>
```

`SimulationRunStatus` enum: `completed`, `failed`, `running`, `queued`, `cancelled`.

#### SaturationFunctionSet

Set of Kr/Pc saturation functions per SCAL region:

| Type | Description |
|------|-------------|
| `SaturationFunctionSet` | Top-level container - set of `SaturationFunction` entries |
| `SaturationFunction` | Single Kr or Pc curve with tabulated saturation and function values |
| `SaturationFunctionKind` | `relative permeability`, `capillary pressure` |
| `FluidPhase` | `water`, `oil`, `gas` |

### 2. Fault seal characterisation - `Interpretations.xsd`

Same additions as 2.0.2, applied to the 2.2+ FaultInterpretation type:

| Element | Type | Description |
|---------|------|-------------|
| `SealState` | `SealState` enum | `sealed`, `leaking`, `unknown` |
| `TransmissibilityMultiplier` | `xs:double` | 0 = sealed, 1 = open |

### 3. OSDU integration flattening - `Abstract.xsd`

The single `OSDUIntegration` container element was removed and its fields
flattened directly into `AbstractObject`:

- `LineageAssertions`, `OwnerGroup`, `ViewerGroup`, `LegalTags` (unbounded)
- `OSDUGeoJSON` (xs:string), `WGS84Latitude`, `WGS84Longitude`, `WGS84LocationMetadata`
- `GeographicContext` group reference

Also: `ExtensionNameValue` replaced by structured `Extension` element with
`Namespace` (URI), `Name`, `Value` (xs:anyType).

### 4. Typed activity parameters - `Activities.xsd`

Same `TypedValue` choice element as in 2.0.2:
`FloatValue`, `IntegerValue`, `StringValue`, `DataObjectReference`, `DateTimeValue`.

### 5. Collection hierarchy - `Collection.xsd`

| Element | Type | Description |
|---------|------|-------------|
| `Purpose` | `CollectionPurposeExt` | `gate evidence`, `working set`, `delivery package`, `scenario` |
| `ParentCollection` | `eml:DataObjectReference` | Enables hierarchical collection organisation |

### 6. Seismic acquisition - `Seismic.xsd`

New on `SeismicLatticeFeature`:

| Element | Type | Values |
|---------|------|--------|
| `AcquisitionMethod` | `SeismicAcquisitionMethodExt` | marine towed streamer, ocean bottom cable/node, land vibroseis/dynamite, VSP, crosswell |
| `CoveragePercent` | `xs:double` | 0–100 |

### Files with version-only changes

Nine files differ only in `version="2.2"` → `version="2.3.0"`:

`Features.xsd`, `Geometry.xsd`, `GraphicalInformationObject.xsd`, `Grids.xsd`,
`Representations.xsd`, `ResqmlAllObjects.xsd`, `Streamlines.xsd`,
`Structural.xsd`, `Wells.xsd`.

### Unchanged files (19)

All EML common, CRS, Datum, and supporting files are **byte-identical** between
2.2 and 2.3.0.

## New simpleTypes summary

| simpleType | File | Values |
|------------|------|--------|
| `SimulationRunStatus` | Properties.xsd | completed, failed, running, queued, cancelled |
| `SaturationFunctionKind` | Properties.xsd | relative permeability, capillary pressure |
| `FluidPhase` | Properties.xsd | water, oil, gas |
| `SealState` | Interpretations.xsd | sealed, leaking, unknown |
| `CollectionPurpose` | Collection.xsd | gate evidence, working set, delivery package, scenario |
| `SeismicAcquisitionMethod` | Seismic.xsd | marine towed streamer, ocean bottom cable/node, land vibroseis/dynamite, VSP, crosswell |

## CRS - no changes

`CRS.xsd` and `Datum.xsd` are **byte-identical** between 2.2 and 2.3.0.
See [docs/datadef/ToDo.md §8](../../../datadef/ToDo.md) for known 2.2 CRS
weaknesses that remain unaddressed in 2.3.0.

## Binary compatibility

2.3.0 is a **superset** of 2.2. The validator resolves `2.2`, `2.2.0`, `2.2.1`
to schema dir `2.2` for XSD validation. Version `2.3` and `2.3.0` use schema
dir `2.3.0`. Class loading uses `resqml220` for 2.2.x and `resqml230` for 2.3.x.

## Test coverage

Test EPC: [`tests/test_230_features.epc`](../tests/test_230_features.epc) -
3 objects (BoundaryFeature + FaultInterpretation + SimulationRunMetadata).

Key tests in [`tests/test_version_and_features.py`](../tests/test_version_and_features.py):

| Test | What it verifies |
|------|-----------------|
| `TestClassLoading::test_230_simulation_run_metadata` | `SimulationRunMetadata` class exists in `resqml230` module |
| `TestEPC230::test_version_detection` | EPC detected as version `2.3.0` |
| `TestEPC230::test_xsd_validation_passes` | All XML parts valid against 2.3.0 XSD |
| `TestEPC230::test_all_objects_parsed` | All 3 objects deserialized |
| `TestEPC230::test_simulation_metadata_parsed` | Parsed SimulationRunMetadata has correct `simulator_name` |
| `TestEPC230::test_sealstate_230_parsed` | FaultInterpretation has `seal_state == "leaking"` |
| `TestRawXsdValidation::test_230_simulation_run_metadata_valid` | Raw SimulationRunMetadata XML validates against 2.3.0 schema |
| `TestRawXsdValidation::test_230_simulation_rejected_by_22_schema` | Same XML **fails** against 2.2 schema |

Also: [`tests/test_22_compound_crs.epc`](../tests/test_22_compound_crs.epc) covers
2.2 `LocalEngineeringCompoundCrs` loading through the shared EML 2.3 types.
