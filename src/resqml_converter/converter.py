"""Main conversion orchestrator: coordinates EPC I/O, object mapping, and validation."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from energyml.utils.introspection import get_obj_uuid
from energyml.utils.epc import Epc

from resqml_converter.epc_io import read_epc, write_epc, get_all_objects, detect_version, create_output_epc
from resqml_converter.validation import validate_output, ConversionValidationReport
from resqml_converter.mappings.base import ConversionContext, registry

# Import all mappers to register them
import resqml_converter.mappings.crs  # noqa: F401
import resqml_converter.mappings.features  # noqa: F401
import resqml_converter.mappings.interpretations  # noqa: F401
import resqml_converter.mappings.representations  # noqa: F401
import resqml_converter.mappings.properties  # noqa: F401
import resqml_converter.mappings.additional  # noqa: F401


# Object type ordering for conversion (features first, then interps, then reps, then props)
_CONVERSION_ORDER = [
    # EPC infrastructure
    "EpcExternalPartReference",
    # CRS
    "LocalDepth3DCrs", "LocalTime3DCrs", "LocalDepth3dCrs", "LocalTime3dCrs",
    "VerticalCrs", "LocalEngineering2DCrs", "LocalEngineeringCompoundCrs",
    "MdDatum",
    # EML common objects
    "PropertyKind", "TimeSeries", "ActivityTemplate", "Activity",
    "DoubleTableLookup", "StringTableLookup",
    # Features
    "GeneticBoundaryFeature", "TectonicBoundaryFeature", "BoundaryFeature",
    "OrganizationFeature", "Model",
    "GeologicUnitFeature", "RockVolumeFeature",
    "GeobodyFeature", "FluidBoundaryFeature", "FrontierFeature",
    "RockFluidUnitFeature", "StratigraphicUnitFeature",
    "WellboreFeature", "SeismicLatticeFeature",
    "SeismicLatticeSetFeature", "SeismicLineFeature", "SeismicLineSetFeature",
    "ShotPointLineFeature", "CmpLineFeature",
    "StreamlinesFeature", "CulturalFeature",
    # Interpretations
    "HorizonInterpretation", "FaultInterpretation",
    "GeobodyInterpretation", "GeobodyBoundaryInterpretation",
    "BoundaryFeatureInterpretation", "GenericFeatureInterpretation",
    "WellboreInterpretation",
    "GeologicUnitInterpretation",
    "StratigraphicUnitInterpretation",
    "StratigraphicOccurrenceInterpretation", "GeologicUnitOccurrenceInterpretation",
    "RockFluidUnitInterpretation", "RockFluidOrganizationInterpretation",
    "FluidBoundaryInterpretation",
    "ReservoirCompartmentInterpretation", "VoidageGroupInterpretation",
    "StructuralOrganizationInterpretation",
    "StratigraphicColumnRankInterpretation",
    "EarthModelInterpretation",
    # Representations
    "TriangulatedSetRepresentation",
    "Grid2DRepresentation", "Grid2dRepresentation", "Grid2DSetRepresentation",
    "IjkGridRepresentation", "UnstructuredGridRepresentation",
    "TruncatedIjkGridRepresentation",
    "UnstructuredColumnLayerGridRepresentation",
    "TruncatedUnstructuredColumnLayerGridRepresentation",
    "GpGridRepresentation",
    "WellboreTrajectoryRepresentation", "DeviationSurveyRepresentation",
    "WellboreFrameRepresentation", "WellboreMarkerFrameRepresentation",
    "BlockedWellboreRepresentation",
    "PointSetRepresentation",
    "PolylineRepresentation", "PolylineSetRepresentation",
    "GridConnectionSetRepresentation",
    "SealedSurfaceFrameworkRepresentation", "NonSealedSurfaceFrameworkRepresentation",
    "SealedVolumeFrameworkRepresentation",
    "PlaneSetRepresentation",
    "RepresentationSetRepresentation", "RepresentationIdentitySet",
    "RedefinedGeometryRepresentation",
    "StreamlinesRepresentation",
    "SubRepresentation",
    "Seismic2DPostStackRepresentation", "Seismic3DPostStackRepresentation",
    "SeismicWellboreFrameRepresentation",
    "Graph2DRepresentation", "WellboreIntervalSet",
    "LocalGridSet",
    # Properties
    "ContinuousProperty", "DiscreteProperty", "CategoricalProperty",
    "BooleanProperty", "CommentProperty", "PointsProperty",
    "ContinuousPropertySeries", "DiscretePropertySeries",
    "CategoricalPropertySeries", "CommentPropertySeries",
    "PropertySet",
    # Misc
    "StratigraphicColumn", "GlobalChronostratigraphicColumn",
]


def convert_epc(
    input_path: str,
    output_path: str,
    target_version: str = "2.2",
    validate: bool = False,
    copy_h5: bool = True,
) -> ConversionResult:
    """Convert an EPC file between RESQML versions.

    Args:
        input_path: Path to input EPC file.
        output_path: Path for output EPC file.
        target_version: Target version ("2.2" or "2.0.1").
        validate: Whether to validate the output.
        copy_h5: Whether to copy associated HDF5 files.

    Returns:
        ConversionResult with converted objects, warnings, and validation report.
    """
    # Read input
    epc = read_epc(input_path)
    source_version = detect_version(epc)

    # Determine direction
    if target_version in ("2.2", "22"):
        if source_version == "2.2":
            raise ValueError("Input is already RESQML 2.2")
        direction = "201_to_22"
    elif target_version in ("2.0.1", "201"):
        if source_version == "2.0.1":
            raise ValueError("Input is already RESQML 2.0.1")
        direction = "22_to_201"
    else:
        raise ValueError(f"Unsupported target version: {target_version}")

    # Get all source objects
    source_objects = get_all_objects(epc)

    # Point 2.2 array references at the (single, merged) output HDF5 file so they
    # resolve. Must be set BEFORE conversion, since URIs are written while the
    # per-type converters build ExternalDataArrayPart elements.
    if direction == "201_to_22":
        from resqml_converter.mappings import common as _common
        _common.EXTERNAL_H5_URI = Path(output_path).with_suffix(".h5").name

    # Convert
    converted, ctx = convert_objects(source_objects, direction)

    # Build output EPC
    output_epc = create_output_epc(converted)

    # Copy/merge HDF5 files alongside output
    if copy_h5:
        if direction == "201_to_22":
            _merge_h5_files(input_path, output_path)
        else:
            _copy_h5_files(input_path, output_path)

    # Write output
    write_epc(output_epc, output_path)

    # Validate if requested
    validation_report = None
    if validate:
        validation_report = validate_output(output_epc, converted)

    return ConversionResult(
        source_version=source_version,
        target_version=target_version,
        objects_converted=len(converted),
        objects_skipped=len(source_objects) - len(converted),
        warnings=ctx.warnings,
        errors=ctx.errors,
        validation_report=validation_report,
    )


def convert_objects(
    source_objects: List[Any],
    direction: str,
) -> Tuple[List[Any], ConversionContext]:
    """Convert a list of energyml objects between versions.

    Args:
        source_objects: List of source energyml dataclass objects.
        direction: "201_to_22" or "22_to_201".

    Returns:
        Tuple of (converted objects list, conversion context with warnings/errors).
    """
    ctx = ConversionContext(direction=direction)

    # Index source objects by UUID
    for obj in source_objects:
        uuid = get_obj_uuid(obj)
        if uuid:
            ctx.source_objects[uuid] = obj

    # Sort objects by conversion order
    sorted_objects = _sort_by_conversion_order(source_objects)

    # Convert each object
    converted = []
    for obj in sorted_objects:
        uuid = get_obj_uuid(obj)
        try:
            result = registry.convert(obj, ctx)
            if result is not None:
                _propagate_extra_metadata(obj, result, direction)
                ctx.register(uuid, result)
                converted.append(result)
        except Exception as e:
            ctx.error(f"Failed to convert {type(obj).__name__} ({uuid}): {e}")

    # Add any additional objects created during conversion (e.g., sub-CRSes)
    for uuid, obj in ctx.converted_objects.items():
        if obj not in converted:
            converted.append(obj)

    return converted, ctx


def _sort_by_conversion_order(objects: List[Any]) -> List[Any]:
    """Sort objects by the defined conversion order (features first, etc.)."""
    def order_key(obj):
        name = type(obj).__name__
        try:
            return _CONVERSION_ORDER.index(name)
        except ValueError:
            return len(_CONVERSION_ORDER)  # Unknown types go last

    return sorted(objects, key=order_key)


def _propagate_extra_metadata(source_obj, result_obj, direction: str) -> None:
    """Carry OSDU/ExtraMetadata across the version boundary.

    2.0.1 objects store metadata in ``extra_metadata`` (NameValuePair); 2.2/EML2.3
    objects use ``extension_name_value`` (ExtensionNameValue). The per-type
    converters rebuild objects field-by-field and drop this metadata, so we
    re-attach it generically here for every converted object.
    """
    from resqml_converter.mappings.common import (
        convert_extra_metadata_to_extension,
        convert_extension_to_extra_metadata,
    )

    if direction == "201_to_22":
        src = getattr(source_obj, "extra_metadata", None)
        if src and hasattr(result_obj, "extension_name_value"):
            existing = list(getattr(result_obj, "extension_name_value", None) or [])
            result_obj.extension_name_value = existing + convert_extra_metadata_to_extension(src)
    else:
        src = getattr(source_obj, "extension_name_value", None)
        if src and hasattr(result_obj, "extra_metadata"):
            existing = list(getattr(result_obj, "extra_metadata", None) or [])
            result_obj.extra_metadata = existing + convert_extension_to_extra_metadata(src)


def _copy_h5_files(input_path: str, output_path: str) -> None:
    input_dir = Path(input_path).parent
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all .h5 files in the input directory
    for h5_file in input_dir.glob("*.h5"):
        dest = output_dir / h5_file.name
        if not dest.exists():
            shutil.copy2(h5_file, dest)


def _merge_h5_files(input_path: str, output_path: str) -> None:
    """Merge every source HDF5 file into a single output HDF5.

    2.0.1 EPCs often split arrays across multiple HDF5 proxies (e.g. a main file
    plus a structural file). RESQML 2.2 ExternalDataArrayPart references carry one
    URI each; convert_epc() points them all at ``<output stem>.h5``, so all source
    datasets must live in that single file for the references to resolve.
    """
    import h5py

    input_dir = Path(input_path).parent
    out_h5 = Path(output_path).with_suffix(".h5")
    out_h5.parent.mkdir(parents=True, exist_ok=True)

    sources = sorted(input_dir.glob("*.h5"))
    if not sources:
        return

    def _copy_group(src_grp, dst_grp):
        for key, item in src_grp.items():
            if isinstance(item, h5py.Group):
                sub = dst_grp.require_group(key)
                _copy_group(item, sub)
            elif key not in dst_grp:  # first writer wins; avoid clobbering
                src_grp.copy(key, dst_grp, name=key)

    with h5py.File(out_h5, "w") as dst:
        for src_path in sources:
            with h5py.File(src_path, "r") as src:
                _copy_group(src, dst)


class ConversionResult:
    """Result of an EPC conversion operation."""

    def __init__(
        self,
        source_version: str,
        target_version: str,
        objects_converted: int,
        objects_skipped: int,
        warnings: List[str],
        errors: List[str],
        validation_report: Optional[ConversionValidationReport] = None,
    ):
        self.source_version = source_version
        self.target_version = target_version
        self.objects_converted = objects_converted
        self.objects_skipped = objects_skipped
        self.warnings = warnings
        self.errors = errors
        self.validation_report = validation_report

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"Conversion: RESQML {self.source_version} -> {self.target_version}",
            f"Objects converted: {self.objects_converted}",
            f"Objects skipped: {self.objects_skipped}",
        ]
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  - {w}")
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.validation_report:
            lines.append("")
            lines.append(self.validation_report.summary())
        return "\n".join(lines)
