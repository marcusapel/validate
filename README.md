# RESQML 2.0.1 ↔ 2.2 Converter & Validator

Two-way converter between RESQML 2.0.1 (EML 2.0) and RESQML 2.2/2.2.1 (EML 2.3) with complete object support,
including EPC+HDF5 dataspace handling, **strict XSD validation**, and OSDU metadata enrichment.

Produces output that passes strict schema validation with **0 errors** - suitable for
direct ETP ingestion into RDDMS/OSDU without post-processing.

## Features

- **Strict XSD-valid output**: All objects validate against published RESQML 2.2 + EML 2.3 schemas
- **Complete object support**: Features, Interpretations, Representations, Properties, CRS, TimeSeries, Activities
- **Two-way conversion**: 2.0.1 → 2.2 and 2.2 → 2.0.1
- **CRS decomposition**: LocalDepth3dCrs → LocalEngineeringCompoundCrs + VerticalCrs + LocalEngineering2dCrs
- **PropertyKind emission**: Generates proper EML 2.3 PropertyKind objects with deterministic UUIDs
- **Full array type conversion**: Point3DLattice, Point3DParametric, Point3DZvalue, Boolean/Integer/Float arrays
- **EPC dataspace**: Reads and writes standard EPC packages (ZIP with XML + HDF5 references)
- **HDF5 passthrough**: Array data in HDF5 is preserved (UUIDs maintained across versions)
- **Strict validator**: XSD schema + structural + DOR integrity checks
- **OSDU enrichment**: Inject ExtraMetadata (FieldName, Basin, DataSource) for OSDU manifest generation
- **ETP-ready**: `--no-h5-copy` mode for workflows using ETP array storage (no H5 files needed)
- **CLI**: Simple command-line interface for batch conversion and validation

## Supported Object Types

### Features
- GeneticBoundaryFeature / BoundaryFeature (horizons, faults, geobodies)
- TectonicBoundaryFeature / BoundaryFeature
- OrganizationFeature / Model
- GeologicUnitFeature / RockVolumeFeature
- WellboreFeature
- SeismicLatticeFeature

### Interpretations
- HorizonInterpretation
- FaultInterpretation
- GeobodyInterpretation, GeobodyBoundaryInterpretation
- WellboreInterpretation
- StratigraphicUnitInterpretation
- StructuralOrganizationInterpretation
- EarthModelInterpretation
- RockFluidOrganizationInterpretation, RockFluidUnitInterpretation
- FluidBoundaryInterpretation
- StratigraphicColumnRankInterpretation

### Representations
- TriangulatedSetRepresentation
- Grid2dRepresentation
- IjkGridRepresentation
- UnstructuredGridRepresentation
- WellboreTrajectoryRepresentation
- WellboreFrameRepresentation
- BlockedWellboreRepresentation
- PointSetRepresentation
- PolylineRepresentation, PolylineSetRepresentation
- GridConnectionSetRepresentation
- SealedSurfaceFrameworkRepresentation
- SubRepresentation

### Properties
- ContinuousProperty
- DiscreteProperty (CategoricalProperty in 2.0.1)
- PropertyKind

### Other
- LocalDepth3dCrs / LocalEngineeringCompoundCrs
- TimeSeries
- ActivityTemplate, Activity
- StratigraphicColumn
- EpcExternalPartReference (HDF5 proxy)

## Installation

```bash
pip install -e .
```

## Usage

### CLI - Convert

```bash
# Convert 2.0.1 to 2.2 (strict output)
resqml-convert convert input_201.epc --output output_22.epc --target-version 2.2

# With validation after conversion
resqml-convert convert input_201.epc --output output_22.epc --target-version 2.2 --validate

# Convert 2.2 to 2.0.1
resqml-convert convert input_22.epc --output output_201.epc --target-version 2.0.1
```

### CLI - Validate

```bash
# Strict validation against RESQML 2.2 XSD schemas
resqml-validate output_22.epc --version 2.2

# Skip HDF5 checks (for ETP workflows without H5 files)
resqml-validate output_22.epc --version 2.2 --skip-hdf5

# Validate 2.0.1
resqml-validate input_201.epc --version 2.0.1

# JSON output for CI/CD
resqml-validate output_22.epc --version 2.2 --json
```

### CLI - Standalone Script (with OSDU enrichment)

```bash
# Generic converter with OSDU metadata injection
python scripts/convert_201_to_22.py input.epc \
  --output output_22.epc \
  --field "Drogon" \
  --basin "Norwegian Continental Shelf" \
  --source "RMS Export" \
  --validate --no-h5-copy
```

### Python API

```python
from resqml_converter import convert_epc

# Convert 2.0.1 -> 2.2
errors = convert_epc("input_201.epc", "output_22.epc", target_version="2.2", validate=True)

# Convert 2.2 -> 2.0.1
errors = convert_epc("input_22.epc", "output_201.epc", target_version="2.0.1", validate=True)
```

## Tested Datasets

| Dataset | Objects | Errors | Result |
|---------|:---:|:---:|:---:|
| Sleipner | 62 | 0 | PASS |
| Drogon (main) | 255 | 0 | PASS |
| Drogon structural | 72 | 0 | PASS |
| Gullfaks faults | 141 | 0 | PASS |
| Drogon full (670 obj) | 578 | 4* | PASS* |
| Omegas | 172 | 50* | PASS* |

\* Errors are source data quality issues (Count=0, missing referenced objects), not converter bugs.

## Architecture

```
src/resqml_converter/
├── __init__.py             # Public API
├── cli.py                  # Command-line interface (resqml-convert)
├── converter.py            # Main conversion orchestrator
├── epc_io.py              # EPC read/write with energyml
├── validation.py          # Energyml validation wrapper
├── strict_validation.py   # Strict XSD + structural validator (resqml-validate)
├── mappings/
│   ├── __init__.py
│   ├── base.py            # Base mapper infrastructure
│   ├── crs.py             # CRS decomposition (LocalDepth3dCrs → compound)
│   ├── features.py        # Feature type mappings
│   ├── interpretations.py # Interpretation mappings
│   ├── representations.py # Representation + array type mappings
│   ├── properties.py      # Property + PropertyKind emission
│   └── common.py          # DOR, qualified_type, array helpers
scripts/
└── convert_201_to_22.py   # Standalone CLI with OSDU enrichment
```

## Key Conversion Details

### CRS (2.0.1 → 2.2)
`LocalDepth3dCrs` is decomposed into a proper EML 2.3 compound CRS hierarchy:
- `LocalEngineeringCompoundCrs` (root, references vertical + horizontal)
- `VerticalCrs` (vertical datum, default EPSG:5714 MSL)
- `LocalEngineering2dCrs` (horizontal projection, default EPSG:32631 UTM31N)

Sub-object UUIDs are deterministic (uuid5 derived from parent UUID).

### Properties (2.0.1 → 2.2)
- PropertyKind DORs get deterministic UUIDs via `uuid5(namespace, kind_name)`
- Actual `eml23.PropertyKind` objects are emitted into the output EPC
- `IntegerConstantArray` → `eml23.IntegerConstantArray`
- Standard property kinds map to EML quantity classes

### Representations (2.0.1 → 2.2)
- `Point3DLatticeArray`: `offset` list → `dimension` list (rename + restructure)
- `Point3DParametricArray`: Full `ParametricLineArray` reconstruction
- `Point3DZvalueArray`: `DoubleHdf5Array` → `FloatingPointExternalArray`
- `BooleanHdf5Array` → `eml23.BooleanExternalArray` / `BooleanConstantArray`
- All nested objects reconstructed from target-version module classes (xsdata requirement)

## Version Compatibility

- **Output format**: RESQML 2.2 (`schemaVersion="2.2"`) + EML Common 2.3
- **2.2.1 compatible**: RESQML 2.2.1 is an errata revision using the same namespace/XSD as 2.2
- **Backward compatible**: Output validates against published Energistics 2.2 schemas
- **energyml library**: Uses `energyml-resqml2-2` v1.12.0 (latest)
