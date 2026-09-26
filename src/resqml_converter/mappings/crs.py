"""CRS conversion between RESQML 2.0.1 and 2.2.

Strict XSD-compliant approach: In RESQML 2.2, CRS is modeled as EML 2.3
LocalEngineeringCompoundCrs which decomposes a flat LocalDepth3dCrs into:
  - LocalEngineering2dCrs (horizontal: origin, rotation, projected CRS ref)
  - VerticalCrs (vertical datum reference)
  - LocalEngineeringCompoundCrs (combines them with vertical axis direction)

DOR qualified_type for CRS in 2.2 is 'eml23.LocalEngineeringCompoundCrs'.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any, List, Optional

from energyml.eml.v2_0 import commonv2 as eml20
from energyml.eml.v2_3 import commonv2 as eml23
from energyml.resqml.v2_0_1 import resqmlv2 as r201
from energyml.resqml.v2_2 import resqmlv2 as r22
from energyml.utils.introspection import get_obj_uuid

from resqml_converter.mappings.base import ConversionContext, registry
from resqml_converter.mappings.common import (
    convert_citation_201_to_23,
    convert_citation_23_to_201,
    SCHEMA_VERSION_22,
    SCHEMA_VERSION_EML23,
    SCHEMA_VERSION_201,
    SCHEMA_VERSION_EML20,
)

# Deterministic namespace for CRS sub-object UUIDs
_CRS_NS = _uuid.UUID("b7c1e3a0-4f2d-4a8b-9c1e-d5f6a7b8c9d0")


def _sub_uuid(parent_uuid: str, suffix: str) -> str:
    """Deterministic UUID for a CRS sub-object derived from parent UUID."""
    return str(_uuid.uuid5(_CRS_NS, f"{parent_uuid}:{suffix}"))


# ─── 2.0.1 -> 2.2 CRS ───────────────────────────────────────────────────────
# Decompose LocalDepth3dCrs / LocalTime3dCrs into EML 2.3 compound CRS.

@registry.register_201_to_22(r"LocalDepth3[dD][Cc]rs")
def convert_local_depth_3d_crs_to_22(obj: r201.LocalDepth3DCrs, ctx: ConversionContext) -> Any:
    """Decompose LocalDepth3dCrs into EML 2.3 LocalEngineeringCompoundCrs."""
    return _decompose_crs_201_to_22(obj, ctx, is_time=False)


@registry.register_201_to_22(r"LocalTime3[dD][Cc]rs")
def convert_local_time_3d_crs_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """Decompose LocalTime3dCrs into EML 2.3 LocalEngineeringCompoundCrs."""
    return _decompose_crs_201_to_22(obj, ctx, is_time=True)


def _decompose_crs_201_to_22(obj: Any, ctx: ConversionContext, is_time: bool) -> eml23.LocalEngineeringCompoundCrs:
    """Convert a flat 2.0.1 LocalDepth/Time3dCrs into compound EML 2.3 CRS objects."""
    parent_uuid = get_obj_uuid(obj)
    title = obj.citation.title if obj.citation else "Local CRS"

    # ── 1. Build VerticalCrs ──
    vert_uuid = _sub_uuid(parent_uuid, "vert")
    vert_epsg = _extract_vertical_epsg(obj)
    vertical_crs = eml23.VerticalCrs(
        citation=eml23.Citation(
            title=f"{title} (Vertical)",
            originator="resqml-converter",
            creation=obj.citation.creation if obj.citation else "2025-01-01T00:00:00Z",
            format="EML v2.3",
        ),
        uuid=vert_uuid,
        schema_version=SCHEMA_VERSION_EML23,
        direction=eml23.VerticalDirection.DOWN if getattr(obj, 'zincreasing_downward', True) else eml23.VerticalDirection.UP,
        abstract_vertical_crs=eml23.VerticalEpsgCrs(epsg_code=vert_epsg),
        uom=_uom_str(getattr(obj, 'vertical_uom', None), is_time),
    )
    ctx.register(vert_uuid, vertical_crs)

    # ── 2. Build LocalEngineering2dCrs ──
    twod_uuid = _sub_uuid(parent_uuid, "2d")
    proj_epsg = _extract_projected_epsg(obj)
    axis_order = getattr(obj, 'projected_axis_order', None)
    areal_rotation = getattr(obj, 'areal_rotation', None)
    azimuth_val = areal_rotation.value if areal_rotation else 0.0

    # Determine axis directions from axis order
    dir1, dir2 = _axis_order_to_directions(axis_order)

    proj_uom_str = _uom_str(getattr(obj, 'projected_uom', None), False)

    local_2d_crs = eml23.LocalEngineering2DCrs(
        citation=eml23.Citation(
            title=f"{title} (2D)",
            originator="resqml-converter",
            creation=obj.citation.creation if obj.citation else "2025-01-01T00:00:00Z",
            format="EML v2.3",
        ),
        uuid=twod_uuid,
        schema_version=SCHEMA_VERSION_EML23,
        azimuth=eml23.PlaneAngleMeasureExt(value=azimuth_val, uom="dega"),
        azimuth_reference=eml23.NorthReferenceKind.GRID_NORTH,
        origin_projected_coordinate1=getattr(obj, 'xoffset', 0.0) or 0.0,
        origin_projected_coordinate2=getattr(obj, 'yoffset', 0.0) or 0.0,
        horizontal_axes=eml23.HorizontalAxes(
            direction1=dir1,
            direction2=dir2,
            uom=proj_uom_str,
            is_time=False,
        ),
        origin_projected_crs=eml23.ProjectedCrs(
            citation=eml23.Citation(title=f"EPSG:{proj_epsg}", originator="resqml-converter", creation=obj.citation.creation if obj.citation else "2025-01-01T00:00:00Z", format="EML v2.3"),
            uuid=_sub_uuid(parent_uuid, "proj"),
            schema_version=SCHEMA_VERSION_EML23,
            axis_order=eml23.AxisOrder2D.EASTING_NORTHING if dir1 == eml23.AxisDirectionKind.EAST else eml23.AxisOrder2D.NORTHING_EASTING,
            abstract_projected_crs=eml23.ProjectedEpsgCrs(epsg_code=proj_epsg),
            uom=proj_uom_str,
        ),
    )
    ctx.register(twod_uuid, local_2d_crs)

    # ── 3. Build LocalEngineeringCompoundCrs ──
    vert_uom_str = _uom_str(getattr(obj, 'vertical_uom', None), is_time)
    compound_crs = eml23.LocalEngineeringCompoundCrs(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=parent_uuid,
        schema_version=SCHEMA_VERSION_EML23,
        vertical_crs=eml23.DataObjectReference(
            uuid=vert_uuid,
            title=f"{title} (Vertical)",
            qualified_type="eml23.VerticalCrs",
        ),
        origin_vertical_coordinate=getattr(obj, 'zoffset', 0.0) or 0.0,
        vertical_axis=eml23.VerticalAxis(
            direction=eml23.VerticalDirection.DOWN if getattr(obj, 'zincreasing_downward', True) else eml23.VerticalDirection.UP,
            uom=vert_uom_str,
            is_time=is_time,
        ),
        local_engineering2d_crs=eml23.DataObjectReference(
            uuid=twod_uuid,
            title=f"{title} (2D)",
            qualified_type="eml23.LocalEngineering2dCrs",
        ),
    )
    return compound_crs


# ─── 2.2 -> 2.0.1 CRS ───────────────────────────────────────────────────────

@registry.register_22_to_201(r"LocalDepth3[dD][Cc]rs")
def convert_local_depth_3d_crs_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """LocalDepth3dCrs from 2.2 back to 2.0.1 - just update schema_version."""
    obj.schema_version = SCHEMA_VERSION_201
    return obj


@registry.register_22_to_201(r"LocalTime3[dD][Cc]rs")
def convert_local_time_3d_crs_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """LocalTime3dCrs from 2.2 back to 2.0.1."""
    obj.schema_version = SCHEMA_VERSION_201
    return obj


@registry.register_22_to_201(r"LocalEngineeringCompoundCrs")
def convert_compound_crs_to_201(obj: eml23.LocalEngineeringCompoundCrs, ctx: ConversionContext) -> Any:
    """Convert EML 2.3 LocalEngineeringCompoundCrs back to LocalDepth3dCrs (2.0.1)."""
    uuid = get_obj_uuid(obj)

    vert_ref = obj.vertical_crs
    twod_ref = obj.local_engineering2d_crs
    vert_obj = ctx.get_source(vert_ref.uuid) if vert_ref else None
    twod_obj = ctx.get_source(twod_ref.uuid) if twod_ref else None

    z_down = True
    if obj.vertical_axis:
        z_down = obj.vertical_axis.direction == eml23.VerticalDirection.DOWN

    xoffset = 0.0
    yoffset = 0.0
    areal_rotation_val = 0.0
    projected_uom = r201.LengthUom.M
    axis_order = r201.AxisOrder2D.EASTING_NORTHING
    projected_crs_val = None

    if twod_obj:
        xoffset = getattr(twod_obj, 'origin_projected_coordinate1', 0.0) or 0.0
        yoffset = getattr(twod_obj, 'origin_projected_coordinate2', 0.0) or 0.0
        if twod_obj.azimuth:
            areal_rotation_val = twod_obj.azimuth.value or 0.0
        if twod_obj.horizontal_axes:
            uom_str = twod_obj.horizontal_axes.uom or "m"
            projected_uom = _parse_length_uom_201(uom_str)
            axis_order = _dirs_to_axis_order(
                twod_obj.horizontal_axes.direction1,
                twod_obj.horizontal_axes.direction2,
            )
        if twod_obj.origin_projected_crs:
            projected_crs_val = _convert_projected_crs_23_to_201(twod_obj.origin_projected_crs)

    vertical_uom = r201.LengthUom.M
    vertical_crs_val = None
    if obj.vertical_axis and obj.vertical_axis.uom:
        vertical_uom = _parse_length_uom_201(obj.vertical_axis.uom)
    if vert_obj:
        vertical_crs_val = _convert_vertical_crs_23_to_201(vert_obj)

    return r201.LocalDepth3DCrs(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=uuid,
        schema_version=SCHEMA_VERSION_201,
        xoffset=xoffset,
        yoffset=yoffset,
        zoffset=obj.origin_vertical_coordinate or 0.0,
        zincreasing_downward=z_down,
        projected_axis_order=axis_order,
        projected_uom=projected_uom,
        vertical_uom=vertical_uom,
        areal_rotation=r201.PlaneAngleMeasure(value=areal_rotation_val, uom=r201.PlaneAngleUom.DEGA),
        projected_crs=projected_crs_val or eml20.ProjectedCrsEpsgCode(epsg_code=32631),
        vertical_crs=vertical_crs_val or eml20.VerticalCrsEpsgCode(epsg_code=5714),
    )


@registry.register_22_to_201(r"VerticalCrs")
def convert_vertical_crs_to_201(obj: eml23.VerticalCrs, ctx: ConversionContext) -> None:
    """VerticalCrs gets folded into LocalDepth3dCrs - skip."""
    return None


@registry.register_22_to_201(r"LocalEngineering2[dD][Cc]rs")
def convert_2d_crs_to_201(obj: eml23.LocalEngineering2DCrs, ctx: ConversionContext) -> None:
    """LocalEngineering2dCrs gets folded into LocalDepth3dCrs - skip."""
    return None


# ─── Helper Functions ─────────────────────────────────────────────────────────

def _extract_projected_epsg(obj: Any) -> int:
    """Extract projected EPSG code from a 2.0.1 CRS object, defaulting to 32631 (WGS84 UTM31N)."""
    pc = getattr(obj, 'projected_crs', None)
    if pc:
        epsg = getattr(pc, 'epsg_code', None)
        if epsg and epsg > 0:
            return epsg
    return 32631  # WGS 84 / UTM zone 31N (default for NCS)


def _extract_vertical_epsg(obj: Any) -> int:
    """Extract vertical EPSG code from a 2.0.1 CRS object, defaulting to 5714 (MSL height)."""
    vc = getattr(obj, 'vertical_crs', None)
    if vc:
        epsg = getattr(vc, 'epsg_code', None)
        if epsg and epsg > 0:
            return epsg
    return 5714  # MSL height


def _uom_str(uom: Any, is_time: bool) -> str:
    """Convert UOM enum to string for EML 2.3."""
    if uom is None:
        return "s" if is_time else "m"
    if hasattr(uom, 'value'):
        return str(uom.value)
    return str(uom)


def _axis_order_to_directions(axis_order: Any) -> tuple:
    """Convert 2.0.1 AxisOrder2D to EML 2.3 direction pair."""
    if axis_order and hasattr(axis_order, 'value'):
        val = axis_order.value
    else:
        val = str(axis_order) if axis_order else "easting northing"
    val_lower = val.lower().replace("_", " ") if val else "easting northing"
    if "northing" in val_lower and val_lower.index("northing") < val_lower.index("easting"):
        return (eml23.AxisDirectionKind.NORTH, eml23.AxisDirectionKind.EAST)
    return (eml23.AxisDirectionKind.EAST, eml23.AxisDirectionKind.NORTH)


def _convert_vertical_crs_23_to_201(vert_obj: Any) -> Any:
    abs_crs = getattr(vert_obj, 'abstract_vertical_crs', None)
    if abs_crs and hasattr(abs_crs, 'epsg_code'):
        return eml20.VerticalCrsEpsgCode(epsg_code=abs_crs.epsg_code)
    return eml20.VerticalCrsEpsgCode(epsg_code=5714)


def _convert_projected_crs_23_to_201(proj_obj: Any) -> Any:
    abs_crs = getattr(proj_obj, 'abstract_projected_crs', None)
    if abs_crs and hasattr(abs_crs, 'epsg_code'):
        return eml20.ProjectedCrsEpsgCode(epsg_code=abs_crs.epsg_code)
    return eml20.ProjectedCrsEpsgCode(epsg_code=32631)


def _dirs_to_axis_order(dir1: Any, dir2: Any) -> r201.AxisOrder2D:
    if dir1 == eml23.AxisDirectionKind.EAST:
        return r201.AxisOrder2D.EASTING_NORTHING
    elif dir1 == eml23.AxisDirectionKind.NORTH:
        return r201.AxisOrder2D.NORTHING_EASTING
    return r201.AxisOrder2D.EASTING_NORTHING


def _parse_length_uom_201(uom_str: Any) -> r201.LengthUom:
    """Parse a UOM string or enum into the 2.0.1 LengthUom enum."""
    if hasattr(uom_str, 'value'):
        uom_str = uom_str.value
    uom_str = str(uom_str).lower()
    uom_map = {"m": r201.LengthUom.M, "ft": r201.LengthUom.FT, "km": r201.LengthUom.KM}
    return uom_map.get(uom_str, r201.LengthUom.M)
