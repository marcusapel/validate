# RESQML 2.0.2 XSD Schemas

RESQML 2.0.2 is a **backward-compatible minor release** extending RESQML 2.0.1.
All 2.0.1 documents remain valid against the 2.0.2 schemas.

## Schema layout

Follows the Energistics-published directory structure. RESQML schemas
(`targetNamespace=resqmlv2`) import EML common schemas (`targetNamespace=commonv2`)
via relative path `../../../commonv2/v2.0/xsd_schemas/AllCommonObjects.xsd`.

```
2.0.2/
├── commonv2/v2.0/xsd_schemas/   # EML common v2.0 (unchanged from 2.0.1)
│   ├── Abstract.xsd
│   ├── BaseTypes.xsd
│   ├── CRS.xsd
│   ├── MeasureType.xsd
│   ├── ObjectReference.xsd
│   ├── QuantityClass.xsd
│   └── gml/ iso/ xlink/         # GML 3.2, ISO 19115, XLink schemas
└── resqmlv2/v2.0.2/xsd_schemas/ # RESQML v2.0.2 types
    ├── Interpretations.xsd      # ← SealState, TransmissibilityMultiplier
    ├── Activities.xsd           # ← TypedValue on parameters
    ├── Wells.xsd                # ← MinIndex/MaxIndex/SampleCount
    └── ... (80 obj_*.xsd + 14 domain files)
```

## Changes from 2.0.1

### 1. Fault seal properties - `Interpretations.xsd`

Two new optional elements on `obj_FaultInterpretation` (after `ThrowInterpretation`):

| Element | Type | Description |
|---------|------|-------------|
| `SealState` | `SealState` enum | `sealed`, `leaking`, or `unknown` |
| `TransmissibilityMultiplier` | `xs:double` | 0 = fully sealed, 1 = fully open |

New `SealState` simpleType enumeration:

```xml
<xs:simpleType name="SealState">
    <xs:restriction base="xs:string">
        <xs:enumeration value="sealed"/>
        <xs:enumeration value="leaking"/>
        <xs:enumeration value="unknown"/>
    </xs:restriction>
</xs:simpleType>
```

Maps to OSDU `FaultInterpretation.IsSealed`.

### 2. Typed activity parameters - `Activities.xsd`

New `TypedValue` choice element on `AbstractParameterKey`, providing strongly-typed
values instead of the stringly-typed subclass mechanism:

```xml
<xs:element name="TypedValue" minOccurs="0" maxOccurs="1">
    <xs:complexType><xs:choice>
        <xs:element name="FloatValue"            type="xs:double"/>
        <xs:element name="IntegerValue"          type="xs:long"/>
        <xs:element name="StringValue"           type="xs:string"/>
        <xs:element name="DataObjectReference"   type="eml:DataObjectReference"/>
        <xs:element name="DateTimeValue"         type="xs:dateTime"/>
    </xs:choice></xs:complexType>
</xs:element>
```

### 3. Wellbore frame index metadata - `Wells.xsd`

Three new optional elements on the wellbore frame representation type:

| Element | Type | Purpose |
|---------|------|---------|
| `MinIndex` | `xs:long` | Min node index (0-based) → OSDU TopMeasuredDepth |
| `MaxIndex` | `xs:long` | Max node index (0-based) → OSDU BottomMeasuredDepth |
| `SampleCount` | `xs:positiveInteger` | Total sample values → OSDU SampleCount |

### Files with version-only changes

Eleven files differ only in the schema `version` attribute (`2.0.1` → `2.0.2`) and
copyright year (`2015` → `2024`):

`PropertySeries.xsd`, `ResqmlAllObjects.xsd`, `Streamlines.xsd`,
`obj_Activity.xsd`, `obj_ActivityTemplate.xsd`,
`obj_CategoricalPropertySeries.xsd`, `obj_CommentPropertySeries.xsd`,
`obj_ContinuousPropertySeries.xsd`, `obj_DiscretePropertySeries.xsd`,
`obj_StreamlinesFeature.xsd`, `obj_StreamlinesRepresentation.xsd`.

### Common objects - unchanged

`commonv2/v2.0/` is **byte-identical** between 2.0.1 and 2.0.2.

## Binary compatibility

2.0.2 is a **superset** of 2.0.1. The validator loads all 2.0.x content through
the `resqml202` xsdata module, which contains the full 2.0.2 type set.
Any 2.0.1-only document validates successfully against the 2.0.2 schemas because
every addition uses `minOccurs="0"`.

Version normalization: `2.0`, `2.0.1`, `2.0.2` → schema dir `2.0.2` for XSD
validation; class loading uses `resqml202` Python module for all.

## Test coverage

Test EPC: [`tests/test_202_sealstate.epc`](../tests/test_202_sealstate.epc) -
2 objects (TectonicBoundaryFeature + FaultInterpretation with `SealState=sealed`).

Key tests in [`tests/test_version_and_features.py`](../tests/test_version_and_features.py):

| Test | What it verifies |
|------|-----------------|
| `TestClassLoading::test_202_sealstate_on_faultinterpretation` | `SealState` attribute exists on xsdata class |
| `TestEPC202::test_version_detection` | EPC detected as version `2.0.2` |
| `TestEPC202::test_xsd_validation_passes` | All XML parts valid against 2.0.2 XSD |
| `TestEPC202::test_objects_parsed` | Both objects deserialized via `resqml202` module |
| `TestEPC202::test_sealstate_in_parsed_object` | Parsed FaultInterpretation has `seal_state == "sealed"` |
| `TestRawXsdValidation::test_202_sealstate_valid_against_202_schema` | Raw SealState XML validates against 2.0.2 schema |
| `TestRawXsdValidation::test_202_sealstate_rejected_by_201_schema` | Same XML **fails** against 2.0.1 schema |

## fesapi compatibility

fesapi v2.14.0 only fully supports 2.0.1. The 2.0.2 additions (`SealState`,
`TransmissibilityMultiplier`) are not recognized by fesapi - they trigger
`content-type-not-recognized` messages that the validator filters as benign
false positives.
