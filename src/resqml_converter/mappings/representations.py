"""Representation type mappings between RESQML 2.0.1 and 2.2.

Key changes:
- represented_interpretation (2.0.1) -> represented_object (2.2)
- HDF5 array references: Hdf5Dataset -> ExternalDataArray
- Geometry structures: Point3dHdf5Array -> Point3dExternalArray
- Grid2dRepresentation: nested Grid2dPatch geometry -> top-level geometry
- WellboreTrajectory: start_md/finish_md/md_uom -> md_interval
- Various patch_index removal (auto-indexed in 2.2)
"""

from __future__ import annotations

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
    convert_dor_201_to_23,
    convert_dor_23_to_201,
    convert_hdf5_dataset_to_external_array,
    convert_external_array_to_hdf5_dataset,
    convert_int_hdf5_array_to_ext,
    convert_float_hdf5_array_to_ext,
    convert_int_ext_array_to_hdf5,
    convert_float_ext_array_to_hdf5,
    convert_point3d_hdf5_to_ext,
    convert_point3d_ext_to_hdf5,
    convert_bool_constant_201_to_23,
    convert_bool_constant_23_to_201,
    SCHEMA_VERSION_22,
    SCHEMA_VERSION_201,
)


# ─── Geometry Conversion Helpers ──────────────────────────────────────────────

def _convert_point_geometry_201_to_22(geom: Any, ctx: ConversionContext) -> Optional[Any]:
    """Convert PointGeometry from 2.0.1 to 2.2."""
    if geom is None:
        return None
    points = _convert_points_201_to_22(geom.points, ctx) if hasattr(geom, 'points') else None
    local_crs = convert_dor_201_to_23(geom.local_crs, ctx) if hasattr(geom, 'local_crs') else None
    return r22.PointGeometry(
        local_crs=local_crs,
        points=points,
    )


def _convert_points_201_to_22(pts: Any, ctx: ConversionContext = None) -> Optional[Any]:
    """Convert any AbstractPoint3dArray from 2.0.1 to 2.2.

    Handles: Point3dHdf5Array, Point3dLatticeArray, Point3dZvalueArray,
    Point3dParametricArray, Point3dFromRepresentationLatticeArray.
    Must reconstruct as r22 classes since xsdata requires same-module types.
    """
    if pts is None:
        return None
    cls_name = type(pts).__name__

    # HDF5 → ExternalArray
    if "Hdf5" in cls_name:
        return convert_point3d_hdf5_to_ext(pts)

    # Point3DLatticeArray: origin + offset[] → origin + dimension[]
    if cls_name == "Point3DLatticeArray":
        origin = _convert_point3d(pts.origin)
        dimensions = []
        for off in (getattr(pts, 'offset', None) or getattr(pts, 'dimension', None) or []):
            # 2.0.1: Point3DOffset has .offset (Point3D) + .spacing
            # 2.2: Point3DLatticeDimension has .direction (Point3D) + .spacing
            direction_pt = getattr(off, 'offset', None) or getattr(off, 'direction', None)
            spacing_201 = getattr(off, 'spacing', None)
            spacing_22 = _convert_spacing_201_to_22(spacing_201)
            dimensions.append(r22.Point3DLatticeDimension(
                direction=_convert_point3d(direction_pt),
                spacing=spacing_22,
            ))
        return r22.Point3DLatticeArray(
            all_dimensions_are_orthogonal=getattr(pts, 'all_dimensions_are_orthogonal', None),
            origin=origin,
            dimension=dimensions,
        )

    # Point3DZvalueArray: supporting_geometry + zvalues
    if "Zvalue" in cls_name:
        supporting = _convert_points_201_to_22(getattr(pts, 'supporting_geometry', None), ctx)
        zvalues_201 = getattr(pts, 'zvalues', None)
        zvalues_22 = _convert_double_array_to_float(zvalues_201)
        return r22.Point3DZvalueArray(
            supporting_geometry=supporting,
            zvalues=zvalues_22,
        )

    # Parametric arrays - need to convert sub-arrays
    if "Parametric" in cls_name and cls_name == "Point3DParametricArray":
        params = getattr(pts, 'parameters', None)
        params_22 = _convert_double_array_to_float(params) if params else None
        pl = getattr(pts, 'parametric_lines', None)
        pl_22 = _convert_parametric_lines_201_to_22(pl, ctx) if pl else None
        line_indices = getattr(pts, 'parametric_line_indices', None)
        line_indices_22 = _convert_int_array_201_to_22(line_indices)
        return r22.Point3DParametricArray(
            parameters=params_22,
            parametric_line_indices=line_indices_22,
            truncated_line_indices=None,
            parametric_lines=pl_22,
        )

    # FromRepresentationLatticeArray
    if "FromRepresentation" in cls_name:
        return pts

    # Fallback: try HDF5 path
    ext = convert_point3d_hdf5_to_ext(pts)
    if ext:
        return ext
    return None


def _convert_point3d(pt: Any) -> Optional[Any]:
    """Convert a r201.Point3D to r22.Point3D."""
    if pt is None:
        return None
    return r22.Point3D(
        coordinate1=getattr(pt, 'coordinate1', 0.0),
        coordinate2=getattr(pt, 'coordinate2', 0.0),
        coordinate3=getattr(pt, 'coordinate3', 0.0),
    )


def _convert_spacing_201_to_22(spacing: Any) -> Optional[Any]:
    """Convert AbstractDoubleArray spacing to AbstractFloatingPointArray.

    Handles DoubleLatticeArray → FloatingPointLatticeArray,
    DoubleConstantArray → FloatingPointConstantArray.
    """
    if spacing is None:
        return None
    cls_name = type(spacing).__name__

    if "LatticeArray" in cls_name:
        # DoubleLatticeArray: start_value + offset (list of DoubleConstantArray)
        offsets_22 = []
        for off in (getattr(spacing, 'offset', []) or []):
            offsets_22.append(eml23.FloatingPointConstantArray(
                value=getattr(off, 'value', 0.0),
                count=getattr(off, 'count', 1),
            ))
        return r22.FloatingPointLatticeArray(
            start_value=getattr(spacing, 'start_value', 0.0),
            offset=offsets_22,
        )

    if "ConstantArray" in cls_name:
        return eml23.FloatingPointConstantArray(
            value=getattr(spacing, 'value', 0.0),
            count=getattr(spacing, 'count', 1),
        )

    # HDF5 double array → FloatingPointExternalArray
    if "Hdf5" in cls_name:
        ext = convert_float_hdf5_array_to_ext(spacing)
        return ext

    return None


def _convert_double_array_to_float(arr: Any) -> Optional[Any]:
    """Convert AbstractDoubleArray (2.0.1) to AbstractFloatingPointArray (2.2)."""
    if arr is None:
        return None
    cls_name = type(arr).__name__

    if "ConstantArray" in cls_name:
        return eml23.FloatingPointConstantArray(
            value=getattr(arr, 'value', 0.0),
            count=getattr(arr, 'count', 1),
        )

    if "LatticeArray" in cls_name:
        return _convert_spacing_201_to_22(arr)

    if "Hdf5" in cls_name:
        return convert_float_hdf5_array_to_ext(arr)

    return None


def _convert_parametric_lines_201_to_22(pl: Any, ctx: ConversionContext) -> Optional[Any]:
    """Convert ParametricLineArray from 2.0.1 to 2.2."""
    if pl is None:
        return None
    cpp = getattr(pl, 'control_point_parameters', None)
    cpp_22 = _convert_double_array_to_float(cpp)
    cp = getattr(pl, 'control_points', None)
    cp_22 = _convert_points_201_to_22(cp, ctx)
    lki = getattr(pl, 'line_kind_indices', None)
    lki_22 = _convert_int_array_201_to_22(lki)
    tv = getattr(pl, 'tangent_vectors', None)
    tv_22 = _convert_points_201_to_22(tv, ctx) if tv else None
    return r22.ParametricLineArray(
        control_point_parameters=cpp_22,
        control_points=cp_22,
        knot_count=getattr(pl, 'knot_count', None),
        line_kind_indices=lki_22,
        tangent_vectors=tv_22,
    )


def _convert_point_geometry_22_to_201(geom: Any, ctx: ConversionContext, hdf_proxy_ref: Any = None) -> Optional[Any]:
    """Convert PointGeometry from 2.2 to 2.0.1."""
    if geom is None:
        return None
    points = convert_point3d_ext_to_hdf5(geom.points, hdf_proxy_ref) if hasattr(geom, 'points') else None
    local_crs = convert_dor_23_to_201(geom.local_crs, ctx) if hasattr(geom, 'local_crs') else None
    return r201.PointGeometry(
        local_crs=local_crs,
        points=points,
    )


def _get_hdf_proxy_ref(ctx: ConversionContext) -> Optional[eml20.DataObjectReference]:
    """Get or create an HDF5 proxy reference for 2.0.1 output."""
    # Look for existing EpcExternalPartReference in converted objects
    for obj in ctx.converted_objects.values():
        if type(obj).__name__ == "EpcExternalPartReference":
            return eml20.DataObjectReference(
                content_type="application/x-eml+xml;version=2.0;type=obj_EpcExternalPartReference",
                title="HDF5 Proxy",
                uuid=get_obj_uuid(obj),
            )
    return None


# ─── 2.0.1 -> 2.2 Representation Mappers ─────────────────────────────────────

@registry.register_201_to_22(r"TriangulatedSetRepresentation")
def convert_triang_set_to_22(obj: r201.TriangulatedSetRepresentation, ctx: ConversionContext) -> Any:
    """TriangulatedSetRepresentation: represented_interpretation -> represented_object, array format."""
    patches = []
    for patch in getattr(obj, 'triangle_patch', []) or []:
        triangles = convert_int_hdf5_array_to_ext(patch.triangles) if hasattr(patch, 'triangles') else None
        geometry = _convert_point_geometry_201_to_22(patch.geometry, ctx) if hasattr(patch, 'geometry') else None
        patches.append(r22.TrianglePatch(
            node_count=getattr(patch, 'node_count', 0),
            triangles=triangles,
            geometry=geometry,
        ))

    return r22.TriangulatedSetRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(obj.represented_interpretation, ctx),
        surface_role=_convert_surface_role_201_to_22(getattr(obj, 'surface_role', None)),
        triangle_patch=patches or None,
    )


@registry.register_201_to_22(r"Grid2[dD]Representation")
def convert_grid2d_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """Grid2dRepresentation: nested patch -> top-level fields in 2.2."""
    patch = getattr(obj, 'grid2d_patch', None)
    fastest = getattr(patch, 'fastest_axis_count', 10) if patch else 10
    slowest = getattr(patch, 'slowest_axis_count', 10) if patch else 10
    geometry = _convert_point_geometry_201_to_22(patch.geometry, ctx) if patch and hasattr(patch, 'geometry') else None

    return r22.Grid2DRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(obj.represented_interpretation, ctx),
        surface_role=_convert_surface_role_201_to_22(getattr(obj, 'surface_role', None)),
        fastest_axis_count=fastest,
        slowest_axis_count=slowest,
        geometry=geometry,
    )


@registry.register_201_to_22(r"IjkGridRepresentation")
def convert_ijk_grid_to_22(obj: r201.IjkGridRepresentation, ctx: ConversionContext) -> Any:
    """IjkGridRepresentation: represented_interpretation -> represented_object, geometry arrays."""
    geometry = None
    if obj.geometry:
        g = obj.geometry
        points = _convert_points_201_to_22(g.points, ctx) if hasattr(g, 'points') else None
        pillar_defined = _convert_bool_array_201_to_22(
            g.pillar_geometry_is_defined
        ) if hasattr(g, 'pillar_geometry_is_defined') else None

        geometry = r22.IjkGridGeometry(
            local_crs=convert_dor_201_to_23(g.local_crs, ctx),
            points=points,
            kdirection=r22.Kdirection(g.kdirection.value) if g.kdirection else r22.Kdirection.DOWN,
            pillar_shape=r22.PillarShape(g.pillar_shape.value) if g.pillar_shape else r22.PillarShape.STRAIGHT,
            grid_is_righthanded=getattr(g, 'grid_is_righthanded', True),
            pillar_geometry_is_defined=pillar_defined,
        )

    return r22.IjkGridRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(obj.represented_interpretation, ctx),
        ni=obj.ni,
        nj=obj.nj,
        nk=obj.nk,
        radial_grid_is_complete=getattr(obj, 'radial_grid_is_complete', None),
        geometry=geometry,
    )


@registry.register_201_to_22(r"UnstructuredGridRepresentation")
def convert_unstruct_grid_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """UnstructuredGridRepresentation conversion."""
    geometry = None
    src_geom = getattr(obj, 'geometry', None)
    if src_geom:
        geometry = r22.UnstructuredGridGeometry(
            local_crs=convert_dor_201_to_23(getattr(src_geom, 'local_crs', None), ctx),
            points=convert_point3d_hdf5_to_ext(getattr(src_geom, 'points', None)),
            node_count=getattr(src_geom, 'node_count', 0),
            cell_shape=r22.CellShape(src_geom.cell_shape.value) if getattr(src_geom, 'cell_shape', None) else None,
            face_count=getattr(src_geom, 'face_count', 0),
            faces_per_cell=_convert_jagged_array_201_to_22(getattr(src_geom, 'faces_per_cell', None)),
            nodes_per_face=_convert_jagged_array_201_to_22(getattr(src_geom, 'nodes_per_face', None)),
            cell_face_is_right_handed=_convert_bool_array_201_to_22(
                getattr(src_geom, 'cell_face_is_right_handed', None)
            ),
        )

    return r22.UnstructuredGridRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        cell_count=getattr(obj, 'cell_count', 0),
        geometry=geometry,
    )


@registry.register_201_to_22(r"WellboreTrajectoryRepresentation")
def convert_wellbore_traj_to_22(obj: r201.WellboreTrajectoryRepresentation, ctx: ConversionContext) -> Any:
    """WellboreTrajectory: start_md/finish_md/md_uom/md_datum -> md_interval."""
    geometry = None
    if obj.geometry:
        g = obj.geometry
        geometry = r22.ParametricLineGeometry(
            local_crs=convert_dor_201_to_23(g.local_crs, ctx),
            control_point_parameters=convert_float_hdf5_array_to_ext(
                getattr(g, 'control_point_parameters', None)
            ),
            control_points=convert_point3d_hdf5_to_ext(getattr(g, 'control_points', None)),
            knot_count=getattr(g, 'knot_count', 0),
            line_kind_index=getattr(g, 'line_kind_index', 2),
        )

    md_uom = str(obj.md_uom.value) if obj.md_uom else "m"

    return r22.WellboreTrajectoryRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(obj.represented_interpretation, ctx),
        md_interval=r22.MdInterval(
            md_min=obj.start_md or 0.0,
            md_max=obj.finish_md or 0.0,
            uom=md_uom,
        ),
        geometry=geometry,
    )


@registry.register_201_to_22(r"WellboreFrameRepresentation")
def convert_wellbore_frame_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.WellboreFrameRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        trajectory=convert_dor_201_to_23(getattr(obj, 'trajectory', None), ctx),
        node_count=getattr(obj, 'node_count', 0),
        node_md=convert_float_hdf5_array_to_ext(getattr(obj, 'node_md', None)),
    )


@registry.register_201_to_22(r"BlockedWellboreRepresentation")
def convert_blocked_wellbore_to_22(obj: Any, ctx: ConversionContext) -> Any:
    # Convert IntervalGridCells if present
    igc = getattr(obj, 'interval_grid_cells', None)
    interval_grid_cells = None
    if igc:
        interval_grid_cells = r22.IntervalGridCells(
            cell_count=getattr(igc, 'cell_count', 0),
            grid_indices=_convert_int_array_201_to_22(getattr(igc, 'grid_indices', None)),
            cell_indices=_convert_int_array_201_to_22(getattr(igc, 'cell_indices', None)),
            local_face_pair_per_cell_indices=_convert_int_array_201_to_22(
                getattr(igc, 'local_face_pair_per_cell_indices', None)),
            grid=[convert_dor_201_to_23(g, ctx) for g in (getattr(igc, 'grid', None) or [])],
        )
    else:
        # BlockedWellbore requires IntervalGridCells in 2.2 - create minimal stub
        # Use the grid reference from the source object's Grid list
        grid_uuid = "00000000-0000-0000-0000-000000000000"
        grid_title = "Grid"
        if hasattr(obj, 'grid') and obj.grid:
            src_grid = obj.grid[0]
            grid_uuid = src_grid.uuid or grid_uuid
            grid_title = src_grid.title or grid_title
        grid_dor = eml23.DataObjectReference(
            qualified_type="resqml22.IjkGridRepresentation",
            title=grid_title,
            uuid=grid_uuid,
        )
        interval_grid_cells = r22.IntervalGridCells(
            cell_count=1,
            grid_indices=eml23.IntegerConstantArray(value=0, count=1),
            cell_indices=eml23.IntegerConstantArray(value=0, count=1),
            local_face_pair_per_cell_indices=eml23.IntegerConstantArray(value=0, count=1),
            grid=[grid_dor],
        )
    return r22.BlockedWellboreRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        trajectory=convert_dor_201_to_23(getattr(obj, 'trajectory', None), ctx),
        node_count=getattr(obj, 'node_count', 0),
        node_md=convert_float_hdf5_array_to_ext(getattr(obj, 'node_md', None)),
        interval_grid_cells=interval_grid_cells,
    )


@registry.register_201_to_22(r"PointSetRepresentation")
def convert_point_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    patches = []
    for patch in getattr(obj, 'node_patch', []) or []:
        geom = _convert_point_geometry_201_to_22(patch.geometry, ctx) if hasattr(patch, 'geometry') else None
        patches.append(geom)
    return r22.PointSetRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        node_patch_geometry=patches or None,
    )


@registry.register_201_to_22(r"PolylineRepresentation")
def convert_polyline_to_22(obj: Any, ctx: ConversionContext) -> Any:
    geometry = _convert_point_geometry_201_to_22(getattr(obj, 'node_patch', None), ctx)
    return r22.PolylineRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        is_closed=getattr(obj, 'is_closed', False),
        node_patch_geometry=geometry,
    )


@registry.register_201_to_22(r"PolylineSetRepresentation")
def convert_polyline_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    patches = []
    for patch in getattr(obj, 'line_patch', []) or []:
        geometry = _convert_point_geometry_201_to_22(getattr(patch, 'geometry', None), ctx)
        # node_count_per_polyline: convert from 2.0.1 array format to 2.2
        ncpp = _convert_int_array_201_to_22(getattr(patch, 'node_count_per_polyline', None))
        # Compute total node_count and interval_count from node_count_per_polyline
        node_count, interval_count = _compute_polyline_counts(patch, ncpp)
        patches.append(r22.PolylineSetPatch(
            node_count=max(node_count, 1),
            interval_count=max(interval_count, 1),
            node_count_per_polyline=ncpp,
            closed_polylines=_convert_bool_array_201_to_22(getattr(patch, 'closed_polylines', None)),
            geometry=geometry,
        ))
    return r22.PolylineSetRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        line_patch=patches or None,
    )


@registry.register_201_to_22(r"GridConnectionSetRepresentation")
def convert_grid_conn_to_22(obj: Any, ctx: ConversionContext) -> Any:
    grids = [convert_dor_201_to_23(g, ctx) for g in (getattr(obj, 'grid', []) or [])]
    return r22.GridConnectionSetRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        count=getattr(obj, 'count', 0),
        cell_index_pairs=convert_int_hdf5_array_to_ext(getattr(obj, 'cell_index_pairs', None)),
        grid_index_pairs=convert_int_hdf5_array_to_ext(getattr(obj, 'grid_index_pairs', None)),
        grid=grids or None,
    )


@registry.register_201_to_22(r"SealedSurfaceFrameworkRepresentation")
def convert_sealed_surface_to_22(obj: Any, ctx: ConversionContext) -> Any:
    reps = [convert_dor_201_to_23(r, ctx) for r in (getattr(obj, 'representation', []) or [])]
    return r22.SealedSurfaceFrameworkRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        is_homogeneous=getattr(obj, 'is_homogeneous', True),
        representation=reps or None,
    )


@registry.register_201_to_22(r"SubRepresentation")
def convert_sub_rep_to_22(obj: Any, ctx: ConversionContext) -> Any:
    patches = []
    for patch in getattr(obj, 'sub_representation_patch', []) or []:
        patches.append(r22.SubRepresentationPatch(
            indices=convert_int_hdf5_array_to_ext(getattr(patch, 'indices', None)),
            supporting_representation=convert_dor_201_to_23(
                getattr(patch, 'supporting_representation', None), ctx
            ),
        ))
    indexable = None
    ie = getattr(obj, 'indexable_element', None)
    if ie:
        try:
            indexable = r22.IndexableElement(ie.value)
        except (ValueError, AttributeError):
            indexable = r22.IndexableElement.CELLS
    return r22.SubRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        indexable_element=indexable,
        sub_representation_patch=patches or None,
    )


# ─── 2.2 -> 2.0.1 Representation Mappers ─────────────────────────────────────

@registry.register_22_to_201(r"TriangulatedSetRepresentation")
def convert_triang_set_to_201(obj: r22.TriangulatedSetRepresentation, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    patches = []
    for i, patch in enumerate(getattr(obj, 'triangle_patch', []) or []):
        triangles = convert_int_ext_array_to_hdf5(patch.triangles, hdf_ref) if hasattr(patch, 'triangles') else None
        geometry = _convert_point_geometry_22_to_201(patch.geometry, ctx, hdf_ref) if hasattr(patch, 'geometry') else None
        patches.append(r201.TrianglePatch(
            patch_index=i,
            count=getattr(patch, 'count', 0),
            node_count=getattr(patch, 'node_count', 0),
            triangles=triangles,
            geometry=geometry,
        ))

    return r201.TriangulatedSetRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(obj.represented_object, ctx),
        surface_role=_convert_surface_role_22_to_201(getattr(obj, 'surface_role', None)),
        triangle_patch=patches or None,
    )


@registry.register_22_to_201(r"Grid2[dD]Representation")
def convert_grid2d_to_201(obj: Any, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    geometry = _convert_point_geometry_22_to_201(getattr(obj, 'geometry', None), ctx, hdf_ref)

    return r201.Grid2DRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(obj.represented_object, ctx),
        surface_role=_convert_surface_role_22_to_201(getattr(obj, 'surface_role', None)),
        grid2d_patch=r201.Grid2DPatch(
            patch_index=0,
            fastest_axis_count=getattr(obj, 'fastest_axis_count', 10),
            slowest_axis_count=getattr(obj, 'slowest_axis_count', 10),
            geometry=geometry,
        ),
    )


@registry.register_22_to_201(r"IjkGridRepresentation")
def convert_ijk_grid_to_201(obj: r22.IjkGridRepresentation, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    geometry = None
    if obj.geometry:
        g = obj.geometry
        points = convert_point3d_ext_to_hdf5(g.points, hdf_ref) if hasattr(g, 'points') else None
        pillar_defined = convert_bool_constant_23_to_201(
            g.pillar_geometry_is_defined
        ) if hasattr(g, 'pillar_geometry_is_defined') else None

        geometry = r201.IjkGridGeometry(
            local_crs=convert_dor_23_to_201(g.local_crs, ctx),
            points=points,
            kdirection=r201.Kdirection(g.kdirection.value) if g.kdirection else r201.Kdirection.DOWN,
            pillar_shape=r201.PillarShape(g.pillar_shape.value) if g.pillar_shape else r201.PillarShape.STRAIGHT,
            grid_is_righthanded=getattr(g, 'grid_is_righthanded', True),
            pillar_geometry_is_defined=pillar_defined,
        )

    return r201.IjkGridRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(obj.represented_object, ctx),
        ni=obj.ni,
        nj=obj.nj,
        nk=obj.nk,
        radial_grid_is_complete=getattr(obj, 'radial_grid_is_complete', None),
        geometry=geometry,
    )


@registry.register_22_to_201(r"UnstructuredGridRepresentation")
def convert_unstruct_grid_to_201(obj: Any, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    geometry = None
    src_geom = getattr(obj, 'geometry', None)
    if src_geom:
        geometry = r201.UnstructuredGridGeometry(
            local_crs=convert_dor_23_to_201(getattr(src_geom, 'local_crs', None), ctx),
            points=convert_point3d_ext_to_hdf5(getattr(src_geom, 'points', None), hdf_ref),
            node_count=getattr(src_geom, 'node_count', 0),
            cell_shape=r201.CellShape(src_geom.cell_shape.value) if getattr(src_geom, 'cell_shape', None) else None,
            face_count=getattr(src_geom, 'face_count', 0),
            faces_per_cell=_convert_jagged_array_22_to_201(getattr(src_geom, 'faces_per_cell', None), hdf_ref),
            nodes_per_face=_convert_jagged_array_22_to_201(getattr(src_geom, 'nodes_per_face', None), hdf_ref),
            cell_face_is_right_handed=convert_bool_constant_23_to_201(
                getattr(src_geom, 'cell_face_is_right_handed', None)
            ),
        )

    return r201.UnstructuredGridRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        cell_count=getattr(obj, 'cell_count', 0),
        geometry=geometry,
    )


@registry.register_22_to_201(r"WellboreTrajectoryRepresentation")
def convert_wellbore_traj_to_201(obj: r22.WellboreTrajectoryRepresentation, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    geometry = None
    if obj.geometry:
        g = obj.geometry
        geometry = r201.ParametricLineGeometry(
            local_crs=convert_dor_23_to_201(g.local_crs, ctx),
            control_point_parameters=convert_float_ext_array_to_hdf5(
                getattr(g, 'control_point_parameters', None), hdf_ref
            ),
            control_points=convert_point3d_ext_to_hdf5(getattr(g, 'control_points', None), hdf_ref),
            knot_count=getattr(g, 'knot_count', 0),
            line_kind_index=getattr(g, 'line_kind_index', 2),
        )

    # Extract from md_interval
    start_md = 0.0
    finish_md = 0.0
    md_uom = r201.LengthUom.M
    md_datum = None
    if obj.md_interval:
        start_md = obj.md_interval.md_min or 0.0
        finish_md = obj.md_interval.md_max or 0.0
        md_datum = convert_dor_23_to_201(getattr(obj.md_interval, 'datum', None), ctx)
        uom_str = getattr(obj.md_interval, 'uom', 'm') or 'm'
        md_uom = _parse_length_uom(uom_str)

    return r201.WellboreTrajectoryRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(obj.represented_object, ctx),
        start_md=start_md,
        finish_md=finish_md,
        md_uom=md_uom,
        md_datum=md_datum,
        geometry=geometry,
    )


@registry.register_22_to_201(r"WellboreFrameRepresentation")
def convert_wellbore_frame_to_201(obj: Any, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    return r201.WellboreFrameRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        trajectory=convert_dor_23_to_201(getattr(obj, 'trajectory', None), ctx),
        node_count=getattr(obj, 'node_count', 0),
        node_md=convert_float_ext_array_to_hdf5(getattr(obj, 'node_md', None), hdf_ref),
    )


@registry.register_22_to_201(r"BlockedWellboreRepresentation")
def convert_blocked_wellbore_to_201(obj: Any, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    return r201.BlockedWellboreRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        trajectory=convert_dor_23_to_201(getattr(obj, 'trajectory', None), ctx),
        node_count=getattr(obj, 'node_count', 0),
        node_md=convert_float_ext_array_to_hdf5(getattr(obj, 'node_md', None), hdf_ref),
    )


@registry.register_22_to_201(r"PointSetRepresentation")
def convert_point_set_to_201(obj: Any, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    patches = []
    for geom in getattr(obj, 'node_patch_geometry', []) or []:
        patches.append(r201.NodePatch(
            patch_index=len(patches),
            geometry=_convert_point_geometry_22_to_201(geom, ctx, hdf_ref),
        ))
    return r201.PointSetRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        node_patch=patches or None,
    )


@registry.register_22_to_201(r"PolylineRepresentation")
def convert_polyline_to_201(obj: Any, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    geometry = _convert_point_geometry_22_to_201(getattr(obj, 'node_patch_geometry', None), ctx, hdf_ref)
    return r201.PolylineRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        is_closed=getattr(obj, 'is_closed', False),
        node_patch=geometry,
    )


@registry.register_22_to_201(r"PolylineSetRepresentation")
def convert_polyline_set_to_201(obj: Any, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    patches = []
    for patch in getattr(obj, 'line_patch', []) or []:
        geometry = _convert_point_geometry_22_to_201(getattr(patch, 'geometry', None), ctx, hdf_ref)
        patches.append(r201.PolylineSetPatch(
            patch_index=len(patches),
            node_count=getattr(patch, 'node_count', 0),
            geometry=geometry,
        ))
    return r201.PolylineSetRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        line_patch=patches or None,
    )


@registry.register_22_to_201(r"GridConnectionSetRepresentation")
def convert_grid_conn_to_201(obj: Any, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    grids = [convert_dor_23_to_201(g, ctx) for g in (getattr(obj, 'grid', []) or [])]
    return r201.GridConnectionSetRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        count=getattr(obj, 'count', 0),
        cell_index_pairs=convert_int_ext_array_to_hdf5(getattr(obj, 'cell_index_pairs', None), hdf_ref),
        grid_index_pairs=convert_int_ext_array_to_hdf5(getattr(obj, 'grid_index_pairs', None), hdf_ref),
        grid=grids or None,
    )


@registry.register_22_to_201(r"SealedSurfaceFrameworkRepresentation")
def convert_sealed_surface_to_201(obj: Any, ctx: ConversionContext) -> Any:
    reps = [convert_dor_23_to_201(r, ctx) for r in (getattr(obj, 'representation', []) or [])]
    return r201.SealedSurfaceFrameworkRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        is_homogeneous=getattr(obj, 'is_homogeneous', True),
        representation=reps or None,
    )


@registry.register_22_to_201(r"SubRepresentation")
def convert_sub_rep_to_201(obj: Any, ctx: ConversionContext) -> Any:
    hdf_ref = _get_hdf_proxy_ref(ctx)
    patches = []
    for patch in getattr(obj, 'sub_representation_patch', []) or []:
        patches.append(r201.SubRepresentationPatch(
            patch_index=len(patches),
            indices=convert_int_ext_array_to_hdf5(getattr(patch, 'indices', None), hdf_ref),
            supporting_representation=convert_dor_23_to_201(
                getattr(patch, 'supporting_representation', None), ctx
            ),
        ))
    indexable = None
    ie = getattr(obj, 'indexable_element', None)
    if ie:
        try:
            indexable = r201.IndexableElements(ie.value)
        except (ValueError, AttributeError):
            indexable = r201.IndexableElements.CELLS
    return r201.SubRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        indexable_element=indexable,
        sub_representation_patch=patches or None,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _convert_surface_role_201_to_22(role: Any) -> Optional[Any]:
    if role is None:
        return None
    try:
        return r22.SurfaceRole(role.value)
    except (ValueError, AttributeError):
        return r22.SurfaceRole.MAP


def _convert_surface_role_22_to_201(role: Any) -> Optional[Any]:
    if role is None:
        return None
    try:
        return r201.SurfaceRole(role.value)
    except (ValueError, AttributeError):
        return r201.SurfaceRole.MAP


def _convert_jagged_array_201_to_22(ja: Any) -> Optional[Any]:
    """Convert JaggedArray from 2.0.1 to 2.2 format."""
    if ja is None:
        return None
    elements = convert_int_hdf5_array_to_ext(getattr(ja, 'elements', None))
    cum_length = convert_int_hdf5_array_to_ext(getattr(ja, 'cumulative_length', None))
    return r22.JaggedArray(elements=elements, cumulative_length=cum_length)


def _convert_jagged_array_22_to_201(ja: Any, hdf_ref: Any) -> Optional[Any]:
    """Convert JaggedArray from 2.2 to 2.0.1 format."""
    if ja is None:
        return None
    elements = convert_int_ext_array_to_hdf5(getattr(ja, 'elements', None), hdf_ref)
    cum_length = convert_int_ext_array_to_hdf5(getattr(ja, 'cumulative_length', None), hdf_ref)
    return r201.JaggedArray(elements=elements, cumulative_length=cum_length)


def _parse_length_uom(uom_str) -> r201.LengthUom:
    if hasattr(uom_str, 'value'):
        uom_str = uom_str.value
    uom_str = str(uom_str).lower()
    uom_map = {"m": r201.LengthUom.M, "ft": r201.LengthUom.FT, "km": r201.LengthUom.KM}
    return uom_map.get(uom_str, r201.LengthUom.M)


def _convert_int_array_201_to_22(arr: Any) -> Optional[Any]:
    """Convert a 2.0.1 integer array (Hdf5 or constant) to 2.2 format."""
    if arr is None:
        return None
    # If it's an HDF5 array, convert to external
    ext = convert_int_hdf5_array_to_ext(arr)
    if ext:
        return ext
    # If it's an integer constant array, preserve it
    if hasattr(arr, 'value') and hasattr(arr, 'count'):
        return eml23.IntegerConstantArray(value=arr.value, count=arr.count)
    return arr


def _convert_bool_array_201_to_22(arr: Any) -> Optional[Any]:
    """Convert a 2.0.1 boolean array to 2.2 format."""
    if arr is None:
        return None
    # BooleanConstantArray
    if hasattr(arr, 'value') and hasattr(arr, 'count'):
        return eml23.BooleanConstantArray(value=arr.value, count=arr.count)
    # BooleanHdf5Array → BooleanExternalArray
    if hasattr(arr, 'values') and hasattr(arr.values, 'path_in_hdf_file'):
        ext_arr = convert_hdf5_dataset_to_external_array(arr.values)
        if ext_arr:
            return eml23.BooleanExternalArray(
                count_per_value=1,
                values=ext_arr,
            )
    return None


def _compute_polyline_counts(patch: Any, ncpp: Any) -> tuple:
    """Compute node_count and interval_count from a 2.0.1 PolylineSetPatch.

    Returns (node_count, interval_count).
    node_count = sum of all nodes across polylines.
    interval_count = node_count - num_polylines (for open) or node_count (closed).
    """
    # Try to get from geometry points count
    geom = getattr(patch, 'geometry', None)
    if geom:
        points = getattr(geom, 'points', None)
        if points:
            # Hdf5 arrays don't have inline count info easily;
            # use node_count_per_polyline if available
            pass

    # If we have a constant array for ncpp
    if ncpp and hasattr(ncpp, 'value') and hasattr(ncpp, 'count'):
        # IntegerConstantArray: all polylines same length
        total_nodes = ncpp.value * ncpp.count
        num_polylines = ncpp.count
        return (total_nodes, total_nodes - num_polylines)

    # Fallback: use a minimum valid value
    # The actual count comes from HDF5 at runtime; set placeholder > 0
    return (1, 1)
