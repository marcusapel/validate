"""Common EML object mappings: Citation, DataObjectReference, arrays, namespaces.

Handles the fundamental differences between EML 2.0 and EML 2.3.
"""

from __future__ import annotations

from typing import Any, Optional, Type

from energyml.eml.v2_0 import commonv2 as eml20
from energyml.eml.v2_3 import commonv2 as eml23
from energyml.resqml.v2_0_1 import resqmlv2 as r201
from energyml.resqml.v2_2 import resqmlv2 as r22
from energyml.utils.introspection import (
    get_obj_uuid,
    get_qualified_type_from_class,
    get_class_fields,
    get_content_type_from_class,
    get_class_from_qualified_type,
    get_classes_matching_name,
)
from energyml.utils.epc_utils import copy_attributes
from energyml.utils.manager import get_classes_matching_name as mgr_get_classes

from resqml_converter.mappings.base import ConversionContext


# ─── Namespace & Version Constants ────────────────────────────────────────────

RESQML_201_NS = "http://www.energistics.org/energyml/data/resqmlv2"
RESQML_22_NS = "http://www.energistics.org/energyml/data/resqmlv2"
EML_20_NS = "http://www.energistics.org/energyml/data/commonv2"
EML_23_NS = "http://www.energistics.org/energyml/data/commonv2"

SCHEMA_VERSION_201 = "2.0"
SCHEMA_VERSION_22 = "2.2"
SCHEMA_VERSION_EML20 = "2.0"
SCHEMA_VERSION_EML23 = "2.3"

# Module mapping for class lookup
MODULES_201 = [r201, eml20]
MODULES_22 = [r22, eml23]


# ─── Citation Conversion ──────────────────────────────────────────────────────

def convert_citation_201_to_23(cit: Optional[eml20.Citation]) -> Optional[eml23.Citation]:
    """Convert EML 2.0 Citation to EML 2.3 Citation."""
    if cit is None:
        return None
    return eml23.Citation(
        title=cit.title,
        originator=cit.originator,
        creation=cit.creation,
        format=cit.format,
        editor=getattr(cit, 'editor', None),
        description=getattr(cit, 'description', None),
    )


def convert_citation_23_to_201(cit: Optional[eml23.Citation]) -> Optional[eml20.Citation]:
    """Convert EML 2.3 Citation to EML 2.0 Citation."""
    if cit is None:
        return None
    return eml20.Citation(
        title=cit.title,
        originator=cit.originator,
        creation=cit.creation,
        format=cit.format,
        editor=getattr(cit, 'editor', None),
        description=getattr(cit, 'description', None),
    )


# ─── DataObjectReference Conversion ──────────────────────────────────────────

def convert_dor_201_to_23(
    dor: Optional[eml20.DataObjectReference],
    ctx: ConversionContext,
) -> Optional[eml23.DataObjectReference]:
    """Convert EML 2.0 DataObjectReference to EML 2.3 DataObjectReference.

    EML 2.0 uses content_type; EML 2.3 uses qualified_type.
    """
    if dor is None:
        return None

    # Map content_type to qualified_type
    qualified_type = _content_type_to_qualified_type_22(dor.content_type)

    return eml23.DataObjectReference(
        uuid=dor.uuid,
        title=dor.title,
        qualified_type=qualified_type,
        object_version=getattr(dor, 'object_version', None),
    )


def convert_dor_23_to_201(
    dor: Optional[eml23.DataObjectReference],
    ctx: ConversionContext,
) -> Optional[eml20.DataObjectReference]:
    """Convert EML 2.3 DataObjectReference to EML 2.0 DataObjectReference.

    EML 2.3 uses qualified_type; EML 2.0 uses content_type.
    """
    if dor is None:
        return None

    # Map qualified_type back to content_type
    content_type = _qualified_type_to_content_type_201(dor.qualified_type)

    return eml20.DataObjectReference(
        uuid=dor.uuid,
        title=dor.title,
        content_type=content_type,
        version_string=getattr(dor, 'object_version', None),
    )


# ─── Array Conversion (HDF5 references) ──────────────────────────────────────

# URI written into every 2.2 ExternalDataArrayPart. convert_epc() overrides this
# to the actual output HDF5 file name so the references resolve.
EXTERNAL_H5_URI = "data.h5"


def convert_hdf5_dataset_to_external_array(
    hdf_ds: Any,
    hdf_proxy_uuid: Optional[str] = None,
) -> Optional[eml23.ExternalDataArray]:
    """Convert RESQML 2.0.1 Hdf5Dataset to EML 2.3 ExternalDataArray."""
    if hdf_ds is None:
        return None
    path = hdf_ds.path_in_hdf_file if hasattr(hdf_ds, 'path_in_hdf_file') else None
    if path is None:
        return None
    # In 2.2, HDF5 is referenced via ExternalDataArrayPart with a URI
    return eml23.ExternalDataArray(
        external_data_array_part=[
            eml23.ExternalDataArrayPart(
                path_in_external_file=path,
                uri=EXTERNAL_H5_URI,
                count=[1],
                start_index=[0],
            )
        ]
    )


def convert_external_array_to_hdf5_dataset(
    ext_arr: Any,
    hdf_proxy_ref: Optional[eml20.DataObjectReference] = None,
) -> Optional[Any]:
    """Convert EML 2.3 ExternalDataArray to RESQML 2.0.1 Hdf5Dataset."""
    if ext_arr is None:
        return None
    parts = getattr(ext_arr, 'external_data_array_part', None)
    if not parts:
        return None
    path = parts[0].path_in_external_file if parts else None
    if path is None:
        return None
    return r201.Hdf5Dataset(
        path_in_hdf_file=path,
        hdf_proxy=hdf_proxy_ref,
    )


# ─── Integer/Float Array Conversion ──────────────────────────────────────────

def convert_int_hdf5_array_to_ext(arr: Any) -> Optional[Any]:
    """Convert IntegerHdf5Array (2.0.1) to IntegerExternalArray (2.2/EML2.3)."""
    if arr is None:
        return None
    if hasattr(arr, 'values') and hasattr(arr.values, 'path_in_hdf_file'):
        ext = convert_hdf5_dataset_to_external_array(arr.values)
        null_value = getattr(arr, 'null_value', -1)
        return eml23.IntegerExternalArray(
            values=ext,
            null_value=null_value,
            count_per_value=1,
            array_integer_type=eml23.IntegerType.ARRAY_OF_INT32_LE,
        )
    return None


def convert_float_hdf5_array_to_ext(arr: Any) -> Optional[Any]:
    """Convert DoubleHdf5Array (2.0.1) to FloatingPointExternalArray (2.2/EML2.3)."""
    if arr is None:
        return None
    if hasattr(arr, 'values') and hasattr(arr.values, 'path_in_hdf_file'):
        ext = convert_hdf5_dataset_to_external_array(arr.values)
        return eml23.FloatingPointExternalArray(
            values=ext,
            count_per_value=1,
            array_floating_point_type=eml23.FloatingPointType.ARRAY_OF_DOUBLE64_LE,
        )
    return None


def convert_int_ext_array_to_hdf5(arr: Any, hdf_proxy_ref: Any) -> Optional[Any]:
    """Convert IntegerExternalArray (EML2.3) to IntegerHdf5Array (2.0.1)."""
    if arr is None:
        return None
    ext = getattr(arr, 'values', None)
    hdf_ds = convert_external_array_to_hdf5_dataset(ext, hdf_proxy_ref)
    if hdf_ds is None:
        return None
    null_value = getattr(arr, 'null_value', -1)
    return r201.IntegerHdf5Array(values=hdf_ds, null_value=null_value)


def convert_float_ext_array_to_hdf5(arr: Any, hdf_proxy_ref: Any) -> Optional[Any]:
    """Convert FloatingPointExternalArray (EML2.3) to DoubleHdf5Array (2.0.1)."""
    if arr is None:
        return None
    ext = getattr(arr, 'values', None)
    hdf_ds = convert_external_array_to_hdf5_dataset(ext, hdf_proxy_ref)
    if hdf_ds is None:
        return None
    return r201.DoubleHdf5Array(values=hdf_ds)


# ─── Point3D Array Conversion ────────────────────────────────────────────────

def convert_point3d_hdf5_to_ext(pts: Any) -> Optional[Any]:
    """Convert Point3dHdf5Array to Point3dExternalArray."""
    if pts is None:
        return None
    coords = getattr(pts, 'coordinates', None)
    if coords is None:
        return None
    ext = convert_hdf5_dataset_to_external_array(coords)
    return r22.Point3DExternalArray(coordinates=ext)


def convert_point3d_ext_to_hdf5(pts: Any, hdf_proxy_ref: Any) -> Optional[Any]:
    """Convert Point3dExternalArray to Point3dHdf5Array."""
    if pts is None:
        return None
    coords = getattr(pts, 'coordinates', None)
    if coords is None:
        return None
    hdf_ds = convert_external_array_to_hdf5_dataset(coords, hdf_proxy_ref)
    return r201.Point3DHdf5Array(coordinates=hdf_ds)


# ─── Constant Array Passthrough ───────────────────────────────────────────────

def convert_bool_constant_201_to_23(arr: Any) -> Optional[Any]:
    """Convert BooleanConstantArray between versions."""
    if arr is None:
        return None
    return eml23.BooleanConstantArray(
        value=arr.value,
        count=arr.count,
    )


def convert_bool_constant_23_to_201(arr: Any) -> Optional[Any]:
    """Convert BooleanConstantArray from 2.3 to 2.0."""
    if arr is None:
        return None
    return r201.BooleanConstantArray(
        value=arr.value,
        count=arr.count,
    )


# ─── Content-Type / Qualified-Type Mapping ────────────────────────────────────

# Map of 2.0.1 type names to 2.2 type names
_TYPE_NAME_MAP_201_TO_22 = {
    "GeneticBoundaryFeature": "BoundaryFeature",
    "TectonicBoundaryFeature": "BoundaryFeature",
    "OrganizationFeature": "Model",
    "GeologicUnitFeature": "RockVolumeFeature",
    "StratigraphicUnitFeature": "RockVolumeFeature",
    "GeobodyFeature": "BoundaryFeature",
    "FluidBoundaryFeature": "BoundaryFeature",
    "FrontierFeature": "CulturalFeature",
    "RockFluidUnitFeature": "RockVolumeFeature",
    "SeismicLineFeature": "ShotPointLineFeature",
    "Grid2DRepresentation": "Grid2dRepresentation",
    "Grid2dRepresentation": "Grid2dRepresentation",
    "Grid2DSetRepresentation": "RepresentationSetRepresentation",
    "LocalDepth3DCrs": "LocalDepth3dCrs",
    "LocalDepth3dCrs": "LocalDepth3dCrs",
    "LocalTime3DCrs": "LocalTime3dCrs",
    "LocalTime3dCrs": "LocalTime3dCrs",
    "EpcExternalPartReference": "EpcExternalPartReference",
    "obj_EpcExternalPartReference": "EpcExternalPartReference",
    "WellboreMarkerFrameRepresentation": "WellboreFrameRepresentation",
    "DeviationSurveyRepresentation": "WellboreTrajectoryRepresentation",
    "RedefinedGeometryRepresentation": "SubRepresentation",
    "StratigraphicOccurrenceInterpretation": "GeologicUnitOccurrenceInterpretation",
    "GlobalChronostratigraphicColumn": "StratigraphicColumn",
    # Properties
    "CategoricalProperty": "DiscreteProperty",
    "ContinuousProperty": "ContinuousProperty",
    "DiscreteProperty": "DiscreteProperty",
    "ContinuousPropertySeries": "ContinuousProperty",
    "DiscretePropertySeries": "DiscreteProperty",
    "CategoricalPropertySeries": "DiscreteProperty",
    "CommentPropertySeries": "CommentProperty",
    "PropertyKind": "PropertyKind",
}

_TYPE_NAME_MAP_22_TO_201 = {
    "BoundaryFeature": "GeneticBoundaryFeature",  # Default; may need context
    "Model": "OrganizationFeature",
    "RockVolumeFeature": "GeologicUnitFeature",
    "CulturalFeature": "FrontierFeature",
    "ShotPointLineFeature": "SeismicLineFeature",
    "CmpLineFeature": "SeismicLineFeature",
    "Grid2dRepresentation": "Grid2DRepresentation",
    "LocalEngineeringCompoundCrs": "LocalDepth3DCrs",
    "LocalEngineering2DCrs": "LocalDepth3DCrs",
    "LocalDepth3dCrs": "LocalDepth3DCrs",
    "LocalTime3dCrs": "LocalTime3DCrs",
    "EpcExternalPartReference": "EpcExternalPartReference",
    "DiscreteProperty": "DiscreteProperty",
    "BooleanProperty": "DiscreteProperty",
    "GeologicUnitOccurrenceInterpretation": "StratigraphicOccurrenceInterpretation",
    "ReservoirCompartmentInterpretation": "GenericFeatureInterpretation",
    "VoidageGroupInterpretation": "GenericFeatureInterpretation",
    "Seismic2DPostStackRepresentation": "Grid2DRepresentation",
    "Seismic3DPostStackRepresentation": "IjkGridRepresentation",
    "SeismicWellboreFrameRepresentation": "WellboreFrameRepresentation",
    "Graph2DRepresentation": "PolylineSetRepresentation",
    "WellboreIntervalSet": "WellboreFrameRepresentation",
}


def _content_type_to_qualified_type_22(content_type: Optional[str]) -> Optional[str]:
    """Convert 2.0.1 content_type to 2.2 qualified_type string.

    Strict convention (XSD-compliant):
    - RESQML types → resqml22.X (e.g. resqml22.IjkGridRepresentation)
    - EML types → eml23.X (e.g. eml23.PropertyKind)
    - CRS types → eml23.LocalEngineeringCompoundCrs (they get decomposed)
    """
    if content_type is None:
        return None
    import re
    m = re.search(r'type=obj_(\w+)', content_type)
    type_name = m.group(1) if m else None

    if type_name is None:
        return content_type  # Can't parse, pass through

    # Map type name
    mapped_name = _TYPE_NAME_MAP_201_TO_22.get(type_name, type_name)

    # CRS types decompose into EML 2.3 compound CRS
    if mapped_name in ("LocalDepth3dCrs", "LocalTime3dCrs"):
        return "eml23.LocalEngineeringCompoundCrs"

    # EML types (PropertyKind, EpcExternalPartReference, etc.) use eml23
    if "eml" in content_type or mapped_name in ("PropertyKind", "EpcExternalPartReference"):
        return f"eml23.{mapped_name}"

    # RESQML types
    return f"resqml22.{mapped_name}"


def _qualified_type_to_content_type_201(qualified_type: Optional[str]) -> Optional[str]:
    """Convert 2.2 qualified_type to 2.0.1 content_type string."""
    if qualified_type is None:
        return None
    # Parse qualified_type: "resqml22.TypeName" or "eml23.TypeName"
    import re
    m = re.match(r'(\w+?)(\d+)\.(\w+)', qualified_type)
    if not m:
        return qualified_type

    domain = m.group(1)
    type_name = m.group(3)

    # Map type name back
    mapped_name = _TYPE_NAME_MAP_22_TO_201.get(type_name, type_name)

    if domain == "resqml":
        return f"application/x-resqml+xml;version=2.0;type=obj_{mapped_name}"
    elif domain == "eml":
        return f"application/x-eml+xml;version=2.0;type=obj_{mapped_name}"
    else:
        return f"application/x-resqml+xml;version=2.0;type=obj_{mapped_name}"


# ─── Target Class Resolution ─────────────────────────────────────────────────

def find_target_class(obj: Any, direction: str) -> Optional[Type]:
    """Find the corresponding class in the target version for generic conversion."""
    source_name = type(obj).__name__
    source_module = type(obj).__module__

    if direction == "201_to_22":
        # Map the class name to 2.2 equivalent
        mapped_name = _TYPE_NAME_MAP_201_TO_22.get(source_name, source_name)
        target_modules = MODULES_22
    else:
        mapped_name = _TYPE_NAME_MAP_22_TO_201.get(source_name, source_name)
        target_modules = MODULES_201

    # Search for the class in target modules
    for mod in target_modules:
        cls = getattr(mod, mapped_name, None)
        if cls is not None:
            return cls

    return None


def create_target_instance(target_cls: Type, source_obj: Any, ctx: ConversionContext) -> Any:
    """Create an instance of target_cls and copy compatible attributes from source."""
    # Create with minimal required fields
    target = target_cls()

    # Copy UUID (preserve identity)
    source_uuid = get_obj_uuid(source_obj)
    if source_uuid and hasattr(target, 'uuid'):
        target.uuid = source_uuid

    # Convert and set citation
    source_cit = getattr(source_obj, 'citation', None)
    if source_cit is not None:
        if ctx.direction == "201_to_22":
            target.citation = convert_citation_201_to_23(source_cit)
        else:
            target.citation = convert_citation_23_to_201(source_cit)

    # Set schema_version
    if hasattr(target, 'schema_version'):
        if ctx.direction == "201_to_22":
            target.schema_version = SCHEMA_VERSION_22 if "resqml" in type(target).__module__ else SCHEMA_VERSION_EML23
        else:
            target.schema_version = SCHEMA_VERSION_201 if "resqml" in type(target).__module__ else SCHEMA_VERSION_EML20

    # Copy attributes that exist in both with compatible types
    copy_attributes(source_obj, target, only_existing_attributes=True, ignore_case=True)

    return target


# ─── Extra Metadata / Extension Name Value ────────────────────────────────────

def convert_extra_metadata_to_extension(metadata_list: list) -> list:
    """Convert EML 2.0 extra_metadata (NameValuePair) to EML 2.3 extension_name_value."""
    result = []
    for nv in metadata_list or []:
        result.append(eml23.ExtensionNameValue(
            name=nv.name if hasattr(nv, 'name') else str(nv),
            value=eml23.StringMeasure(value=nv.value if hasattr(nv, 'value') else ""),
        ))
    return result


def convert_extension_to_extra_metadata(ext_list: list) -> list:
    """Convert EML 2.3 extension_name_value to EML 2.0 extra_metadata (NameValuePair)."""
    result = []
    for env in ext_list or []:
        result.append(eml20.NameValuePair(
            name=env.name if hasattr(env, 'name') else str(env),
            value=env.value.value if hasattr(env, 'value') and hasattr(env.value, 'value') else "",
        ))
    return result
