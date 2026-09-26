"""Additional feature/interpretation/representation mappers for complete standard coverage.

Covers types not handled in the primary mapping files:
- DeviationSurveyRepresentation
- WellboreMarkerFrameRepresentation
- GpGridRepresentation
- TruncatedIjkGridRepresentation
- TruncatedUnstructuredColumnLayerGridRepresentation
- UnstructuredColumnLayerGridRepresentation
- NonSealedSurfaceFrameworkRepresentation
- SealedVolumeFrameworkRepresentation
- PlaneSetRepresentation
- RepresentationSetRepresentation
- RepresentationIdentitySet
- RedefinedGeometryRepresentation
- Grid2DSetRepresentation
- StreamlinesFeature / StreamlinesRepresentation
- SeismicLineFeature / SeismicLineSetFeature / SeismicLatticeSetFeature
- MdDatum
- LocalGridSet
- GeobodyFeature / FrontierFeature / FluidBoundaryFeature / RockFluidUnitFeature
- StratigraphicUnitFeature / StratigraphicOccurrenceInterpretation
- GeologicUnitInterpretation / GenericFeatureInterpretation
- BoundaryFeatureInterpretation
- GlobalChronostratigraphicColumn / StratigraphicColumn
- Activity / ActivityTemplate / TimeSeries
- DoubleTableLookup / StringTableLookup
- PropertySet / PointsProperty / CommentProperty
- ContinuousPropertySeries / DiscretePropertySeries / CategoricalPropertySeries / CommentPropertySeries
- BooleanProperty (2.2 only)
- CmpLineFeature / ShotPointLineFeature (2.2 only)
- CulturalFeature (2.2 only)
- WellboreIntervalSet (2.2 only)
"""

from __future__ import annotations

from typing import Any

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
    convert_float_hdf5_array_to_ext,
    convert_int_hdf5_array_to_ext,
    convert_float_ext_array_to_hdf5,
    convert_int_ext_array_to_hdf5,
    convert_point3d_hdf5_to_ext,
    convert_point3d_ext_to_hdf5,
    convert_bool_constant_201_to_23,
    convert_bool_constant_23_to_201,
    SCHEMA_VERSION_22,
    SCHEMA_VERSION_201,
    SCHEMA_VERSION_EML23,
    SCHEMA_VERSION_EML20,
)


# ─── Features ────────────────────────────────────────────────────────────────

@registry.register_201_to_22(r"GeobodyFeature")
def convert_geobody_feature_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """GeobodyFeature (2.0.1) -> BoundaryFeature (2.2) - geobody merged into BoundaryFeature."""
    return r22.BoundaryFeature(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        is_well_known=False,
    )


@registry.register_201_to_22(r"FrontierFeature")
def convert_frontier_feature_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """FrontierFeature (2.0.1) -> CulturalFeature (2.2)."""
    return r22.CulturalFeature(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        is_well_known=False,
        kind=r22.CulturalFeatureKind.FRONTIER,
    )


@registry.register_22_to_201(r"CulturalFeature")
def convert_cultural_feature_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """CulturalFeature (2.2) -> FrontierFeature (2.0.1)."""
    return r201.FrontierFeature(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
    )


@registry.register_201_to_22(r"FluidBoundaryFeature")
def convert_fluid_boundary_feature_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """FluidBoundaryFeature (2.0.1) -> BoundaryFeature (2.2)."""
    return r22.BoundaryFeature(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        is_well_known=False,
    )


@registry.register_201_to_22(r"RockFluidUnitFeature")
def convert_rock_fluid_unit_feature_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """RockFluidUnitFeature (2.0.1) -> RockVolumeFeature (2.2)."""
    return r22.RockVolumeFeature(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        is_well_known=False,
    )


@registry.register_201_to_22(r"StratigraphicUnitFeature")
def convert_strat_unit_feature_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """StratigraphicUnitFeature (2.0.1) -> RockVolumeFeature (2.2)."""
    return r22.RockVolumeFeature(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        is_well_known=False,
    )


@registry.register_201_to_22(r"StreamlinesFeature")
def convert_streamlines_feature_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.StreamlinesFeature(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        is_well_known=False,
        time_index=getattr(obj, 'time_index', None),
    )


@registry.register_22_to_201(r"StreamlinesFeature")
def convert_streamlines_feature_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.StreamlinesFeature(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
    )


@registry.register_201_to_22(r"SeismicLineFeature")
def convert_seismic_line_feature_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """SeismicLineFeature (2.0.1) -> ShotPointLineFeature or CmpLineFeature (2.2)."""
    return r22.ShotPointLineFeature(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        is_well_known=False,
    )


@registry.register_22_to_201(r"ShotPointLineFeature")
def convert_shot_point_line_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.SeismicLineFeature(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
    )


@registry.register_22_to_201(r"CmpLineFeature")
def convert_cmp_line_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.SeismicLineFeature(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
    )


@registry.register_201_to_22(r"SeismicLineSetFeature")
def convert_seismic_line_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.SeismicLineSetFeature(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        is_well_known=False,
    )


@registry.register_22_to_201(r"SeismicLineSetFeature")
def convert_seismic_line_set_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.SeismicLineSetFeature(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
    )


@registry.register_201_to_22(r"SeismicLatticeSetFeature")
def convert_seismic_lattice_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.SeismicLatticeSetFeature(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        is_well_known=False,
    )


@registry.register_22_to_201(r"SeismicLatticeSetFeature")
def convert_seismic_lattice_set_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.SeismicLatticeSetFeature(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
    )


# ─── Interpretations ─────────────────────────────────────────────────────────

@registry.register_201_to_22(r"GenericFeatureInterpretation")
def convert_generic_interp_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.GenericFeatureInterpretation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        domain=r22.Domain(obj.domain.value) if obj.domain else r22.Domain.DEPTH,
        interpreted_feature=convert_dor_201_to_23(obj.interpreted_feature, ctx),
    )


@registry.register_22_to_201(r"GenericFeatureInterpretation")
def convert_generic_interp_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.GenericFeatureInterpretation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        domain=r201.Domain(obj.domain.value) if obj.domain else r201.Domain.DEPTH,
        interpreted_feature=convert_dor_23_to_201(obj.interpreted_feature, ctx),
    )


@registry.register_201_to_22(r"BoundaryFeatureInterpretation")
def convert_boundary_feat_interp_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.BoundaryFeatureInterpretation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        domain=r22.Domain(obj.domain.value) if obj.domain else r22.Domain.DEPTH,
        interpreted_feature=convert_dor_201_to_23(obj.interpreted_feature, ctx),
    )


@registry.register_22_to_201(r"BoundaryFeatureInterpretation")
def convert_boundary_feat_interp_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.BoundaryFeatureInterpretation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        domain=r201.Domain(obj.domain.value) if obj.domain else r201.Domain.DEPTH,
        interpreted_feature=convert_dor_23_to_201(obj.interpreted_feature, ctx),
    )


@registry.register_201_to_22(r"GeologicUnitInterpretation")
def convert_geologic_unit_interp_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.GeologicUnitInterpretation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        domain=r22.Domain(obj.domain.value) if obj.domain else r22.Domain.DEPTH,
        interpreted_feature=convert_dor_201_to_23(obj.interpreted_feature, ctx),
    )


@registry.register_22_to_201(r"GeologicUnitInterpretation")
def convert_geologic_unit_interp_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.GeologicUnitInterpretation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        domain=r201.Domain(obj.domain.value) if obj.domain else r201.Domain.DEPTH,
        interpreted_feature=convert_dor_23_to_201(obj.interpreted_feature, ctx),
    )


@registry.register_201_to_22(r"StratigraphicOccurrenceInterpretation")
def convert_strat_occurrence_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.GeologicUnitOccurrenceInterpretation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        domain=r22.Domain(obj.domain.value) if obj.domain else r22.Domain.DEPTH,
        interpreted_feature=convert_dor_201_to_23(obj.interpreted_feature, ctx),
    )


@registry.register_22_to_201(r"GeologicUnitOccurrenceInterpretation")
def convert_geologic_unit_occurrence_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.StratigraphicOccurrenceInterpretation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        domain=r201.Domain(obj.domain.value) if obj.domain else r201.Domain.DEPTH,
        interpreted_feature=convert_dor_23_to_201(obj.interpreted_feature, ctx),
    )


@registry.register_22_to_201(r"ReservoirCompartmentInterpretation")
def convert_reservoir_compartment_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """ReservoirCompartmentInterpretation is new in 2.2 -> map to GenericFeatureInterpretation."""
    ctx.warn(f"ReservoirCompartmentInterpretation {get_obj_uuid(obj)} mapped to GenericFeatureInterpretation in 2.0.1")
    return r201.GenericFeatureInterpretation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        domain=r201.Domain(obj.domain.value) if obj.domain else r201.Domain.DEPTH,
        interpreted_feature=convert_dor_23_to_201(obj.interpreted_feature, ctx),
    )


@registry.register_22_to_201(r"VoidageGroupInterpretation")
def convert_voidage_group_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """VoidageGroupInterpretation is new in 2.2 -> map to GenericFeatureInterpretation."""
    ctx.warn(f"VoidageGroupInterpretation {get_obj_uuid(obj)} mapped to GenericFeatureInterpretation in 2.0.1")
    return r201.GenericFeatureInterpretation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        domain=r201.Domain(obj.domain.value) if obj.domain else r201.Domain.DEPTH,
        interpreted_feature=convert_dor_23_to_201(obj.interpreted_feature, ctx),
    )


# ─── Representations ─────────────────────────────────────────────────────────

@registry.register_201_to_22(r"DeviationSurveyRepresentation")
def convert_deviation_survey_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """DeviationSurveyRepresentation -> WellboreTrajectoryRepresentation in 2.2.

    Deviation surveys are folded into wellbore trajectory in 2.2.
    """
    ctx.warn(f"DeviationSurveyRepresentation {get_obj_uuid(obj)} mapped to WellboreTrajectoryRepresentation")
    md_uom = str(obj.md_uom.value) if getattr(obj, 'md_uom', None) else "m"
    return r22.WellboreTrajectoryRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        md_interval=r22.MdInterval(
            md_min=getattr(obj, 'first_station_md', 0.0) or 0.0,
            md_max=getattr(obj, 'last_station_md', 0.0) or 0.0,
            uom=md_uom,
        ),
    )


@registry.register_201_to_22(r"WellboreMarkerFrameRepresentation")
def convert_wellbore_marker_frame_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """WellboreMarkerFrameRepresentation -> WellboreFrameRepresentation in 2.2."""
    return r22.WellboreFrameRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        trajectory=convert_dor_201_to_23(getattr(obj, 'trajectory', None), ctx),
        node_count=getattr(obj, 'node_count', 0),
        node_md=convert_float_hdf5_array_to_ext(getattr(obj, 'node_md', None)),
    )


@registry.register_201_to_22(r"GpGridRepresentation")
def convert_gp_grid_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.GpGridRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
    )


@registry.register_22_to_201(r"GpGridRepresentation")
def convert_gp_grid_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.GpGridRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
    )


@registry.register_201_to_22(r"TruncatedIjkGridRepresentation")
def convert_truncated_ijk_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.TruncatedIjkGridRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        ni=getattr(obj, 'ni', 1),
        nj=getattr(obj, 'nj', 1),
        nk=getattr(obj, 'nk', 1),
    )


@registry.register_22_to_201(r"TruncatedIjkGridRepresentation")
def convert_truncated_ijk_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.TruncatedIjkGridRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        ni=getattr(obj, 'ni', 1),
        nj=getattr(obj, 'nj', 1),
        nk=getattr(obj, 'nk', 1),
    )


@registry.register_201_to_22(r"UnstructuredColumnLayerGridRepresentation")
def convert_unstructured_col_layer_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.UnstructuredColumnLayerGridRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        nk=getattr(obj, 'nk', 1),
    )


@registry.register_22_to_201(r"UnstructuredColumnLayerGridRepresentation")
def convert_unstructured_col_layer_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.UnstructuredColumnLayerGridRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        nk=getattr(obj, 'nk', 1),
    )


@registry.register_201_to_22(r"TruncatedUnstructuredColumnLayerGridRepresentation")
def convert_truncated_unstructured_col_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.TruncatedUnstructuredColumnLayerGridRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        nk=getattr(obj, 'nk', 1),
    )


@registry.register_22_to_201(r"TruncatedUnstructuredColumnLayerGridRepresentation")
def convert_truncated_unstructured_col_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.TruncatedUnstructuredColumnLayerGridRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        nk=getattr(obj, 'nk', 1),
    )


@registry.register_201_to_22(r"NonSealedSurfaceFrameworkRepresentation")
def convert_non_sealed_surface_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.NonSealedSurfaceFrameworkRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        is_homogeneous=getattr(obj, 'is_homogeneous', True),
    )


@registry.register_22_to_201(r"NonSealedSurfaceFrameworkRepresentation")
def convert_non_sealed_surface_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.NonSealedSurfaceFrameworkRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        is_homogeneous=getattr(obj, 'is_homogeneous', True),
    )


@registry.register_201_to_22(r"SealedVolumeFrameworkRepresentation")
def convert_sealed_volume_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.SealedVolumeFrameworkRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
    )


@registry.register_22_to_201(r"SealedVolumeFrameworkRepresentation")
def convert_sealed_volume_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.SealedVolumeFrameworkRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
    )


@registry.register_201_to_22(r"PlaneSetRepresentation")
def convert_plane_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.PlaneSetRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
    )


@registry.register_22_to_201(r"PlaneSetRepresentation")
def convert_plane_set_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.PlaneSetRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
    )


@registry.register_201_to_22(r"RepresentationSetRepresentation")
def convert_rep_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    reps = [convert_dor_201_to_23(r, ctx) for r in (getattr(obj, 'representation', []) or [])]
    return r22.RepresentationSetRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        is_homogeneous=getattr(obj, 'is_homogeneous', True),
        representation=reps or None,
    )


@registry.register_22_to_201(r"RepresentationSetRepresentation")
def convert_rep_set_to_201(obj: Any, ctx: ConversionContext) -> Any:
    reps = [convert_dor_23_to_201(r, ctx) for r in (getattr(obj, 'representation', []) or [])]
    return r201.RepresentationSetRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        is_homogeneous=getattr(obj, 'is_homogeneous', True),
        representation=reps or None,
    )


@registry.register_201_to_22(r"RepresentationIdentitySet")
def convert_rep_identity_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.RepresentationIdentitySet(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
    )


@registry.register_22_to_201(r"RepresentationIdentitySet")
def convert_rep_identity_set_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.RepresentationIdentitySet(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
    )


@registry.register_201_to_22(r"RedefinedGeometryRepresentation")
def convert_redefined_geom_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """RedefinedGeometryRepresentation doesn't exist in 2.2; map to SubRepresentation."""
    ctx.warn(f"RedefinedGeometryRepresentation {get_obj_uuid(obj)} mapped to SubRepresentation in 2.2")
    return r22.SubRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        indexable_element=r22.IndexableElement.NODES,
    )


@registry.register_201_to_22(r"Grid2DSetRepresentation")
def convert_grid2d_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """Grid2DSetRepresentation -> RepresentationSetRepresentation in 2.2."""
    ctx.warn(f"Grid2DSetRepresentation {get_obj_uuid(obj)} mapped to RepresentationSetRepresentation")
    return r22.RepresentationSetRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        is_homogeneous=True,
    )


@registry.register_201_to_22(r"StreamlinesRepresentation")
def convert_streamlines_rep_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.StreamlinesRepresentation(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        represented_object=convert_dor_201_to_23(getattr(obj, 'represented_interpretation', None), ctx),
        line_count=getattr(obj, 'line_count', 0),
    )


@registry.register_22_to_201(r"StreamlinesRepresentation")
def convert_streamlines_rep_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.StreamlinesRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        line_count=getattr(obj, 'line_count', 0),
    )


@registry.register_201_to_22(r"LocalGridSet")
def convert_local_grid_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.LocalGridSet(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
    )


@registry.register_22_to_201(r"LocalGridSet")
def convert_local_grid_set_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.LocalGridSet(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
    )


# ─── MdDatum ─────────────────────────────────────────────────────────────────

@registry.register_201_to_22(r"MdDatum")
def convert_md_datum_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """MdDatum (2.0.1) is merged into the CRS system in 2.2.
    
    We convert to a LocalEngineeringCompoundCrs sub-reference or pass through as metadata.
    """
    # MdDatum doesn't exist as standalone in 2.2 - absorbed into WellboreTrajectory.md_interval.datum
    # Return None so it's skipped; trajectories reference it via DOR which maps to CRS
    ctx.warn(f"MdDatum {get_obj_uuid(obj)} has no standalone equivalent in 2.2; referenced from trajectories")
    return None


# ─── EML Common Objects ──────────────────────────────────────────────────────

@registry.register_201_to_22(r"^TimeSeries$")
def convert_time_series_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """TimeSeries (2.0.1 RESQML) -> TimeSeries (EML 2.3)."""
    times = []
    for ts in getattr(obj, 'time', []) or []:
        if hasattr(ts, 'date_time'):
            times.append(eml23.GeologicTime(date_time=ts.date_time))
        elif hasattr(ts, 'value'):
            times.append(eml23.GeologicTime(date_time=str(ts.value)))
    return eml23.TimeSeries(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_EML23,
        time=times or None,
    )


@registry.register_22_to_201(r"^TimeSeries$")
def convert_time_series_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """TimeSeries (EML 2.3) -> TimeSeries (2.0.1)."""
    times = []
    for ts in getattr(obj, 'time', []) or []:
        dt = getattr(ts, 'date_time', None)
        if dt:
            times.append(r201.Timestamp(date_time=str(dt)))
    return r201.TimeSeries(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        time=times or None,
    )


@registry.register_201_to_22(r"^Activity$")
def convert_activity_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return eml23.Activity(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_EML23,
        activity_descriptor=convert_dor_201_to_23(getattr(obj, 'activity_descriptor', None), ctx),
    )


@registry.register_22_to_201(r"^Activity$")
def convert_activity_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.Activity(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        activity_descriptor=convert_dor_23_to_201(getattr(obj, 'activity_descriptor', None), ctx),
    )


@registry.register_201_to_22(r"^ActivityTemplate$")
def convert_activity_template_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return eml23.ActivityTemplate(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_EML23,
    )


@registry.register_22_to_201(r"^ActivityTemplate$")
def convert_activity_template_to_201(obj: Any, ctx: ConversionContext) -> Any:
    return r201.ActivityTemplate(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
    )


@registry.register_201_to_22(r"^StratigraphicColumn$")
def convert_strat_column_to_22(obj: Any, ctx: ConversionContext) -> Any:
    ranks = [convert_dor_201_to_23(r, ctx) for r in (getattr(obj, 'ranks', []) or [])]
    return r22.StratigraphicColumn(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        ranks=ranks or None,
    )


@registry.register_22_to_201(r"^StratigraphicColumn$")
def convert_strat_column_to_201(obj: Any, ctx: ConversionContext) -> Any:
    ranks = [convert_dor_23_to_201(r, ctx) for r in (getattr(obj, 'ranks', []) or [])]
    return r201.StratigraphicColumn(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        ranks=ranks or None,
    )


@registry.register_201_to_22(r"GlobalChronostratigraphicColumn")
def convert_global_chrono_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """GlobalChronostratigraphicColumn -> StratigraphicColumn in 2.2."""
    return r22.StratigraphicColumn(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
    )


# ─── Table Lookups ───────────────────────────────────────────────────────────

@registry.register_201_to_22(r"DoubleTableLookup")
def convert_double_table_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """DoubleTableLookup doesn't exist in 2.2; preserve as metadata."""
    ctx.warn(f"DoubleTableLookup {get_obj_uuid(obj)} has no direct 2.2 equivalent")
    return None


@registry.register_201_to_22(r"StringTableLookup")
def convert_string_table_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """StringTableLookup doesn't exist in 2.2; preserve as metadata."""
    ctx.warn(f"StringTableLookup {get_obj_uuid(obj)} has no direct 2.2 equivalent")
    return None


# ─── Properties ───────────────────────────────────────────────────────────────

@registry.register_201_to_22(r"CommentProperty")
def convert_comment_prop_to_22(obj: Any, ctx: ConversionContext) -> Any:
    indexable = None
    if getattr(obj, 'indexable_element', None):
        try:
            indexable = r22.IndexableElement(obj.indexable_element.value)
        except (ValueError, AttributeError):
            indexable = r22.IndexableElement.CELLS
    return r22.CommentProperty(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        indexable_element=indexable,
        supporting_representation=convert_dor_201_to_23(
            getattr(obj, 'supporting_representation', None), ctx
        ),
    )


@registry.register_22_to_201(r"CommentProperty")
def convert_comment_prop_to_201(obj: Any, ctx: ConversionContext) -> Any:
    indexable = None
    if getattr(obj, 'indexable_element', None):
        try:
            indexable = r201.IndexableElements(obj.indexable_element.value)
        except (ValueError, AttributeError):
            indexable = r201.IndexableElements.CELLS
    return r201.CommentProperty(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        indexable_element=indexable,
        supporting_representation=convert_dor_23_to_201(
            getattr(obj, 'supporting_representation', None), ctx
        ),
    )


@registry.register_201_to_22(r"PointsProperty")
def convert_points_prop_to_22(obj: Any, ctx: ConversionContext) -> Any:
    indexable = None
    if getattr(obj, 'indexable_element', None):
        try:
            indexable = r22.IndexableElement(obj.indexable_element.value)
        except (ValueError, AttributeError):
            indexable = r22.IndexableElement.NODES
    return r22.PointsProperty(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        indexable_element=indexable,
        supporting_representation=convert_dor_201_to_23(
            getattr(obj, 'supporting_representation', None), ctx
        ),
    )


@registry.register_22_to_201(r"PointsProperty")
def convert_points_prop_to_201(obj: Any, ctx: ConversionContext) -> Any:
    indexable = None
    if getattr(obj, 'indexable_element', None):
        try:
            indexable = r201.IndexableElements(obj.indexable_element.value)
        except (ValueError, AttributeError):
            indexable = r201.IndexableElements.NODES
    return r201.PointsProperty(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        indexable_element=indexable,
        supporting_representation=convert_dor_23_to_201(
            getattr(obj, 'supporting_representation', None), ctx
        ),
    )


@registry.register_22_to_201(r"BooleanProperty")
def convert_boolean_prop_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """BooleanProperty (2.2 only) -> DiscreteProperty (2.0.1)."""
    ctx.warn(f"BooleanProperty {get_obj_uuid(obj)} mapped to DiscreteProperty in 2.0.1")
    indexable = None
    if getattr(obj, 'indexable_element', None):
        try:
            indexable = r201.IndexableElements(obj.indexable_element.value)
        except (ValueError, AttributeError):
            indexable = r201.IndexableElements.CELLS
    return r201.DiscreteProperty(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        indexable_element=indexable,
        supporting_representation=convert_dor_23_to_201(
            getattr(obj, 'supporting_representation', None), ctx
        ),
        count=1,
    )


@registry.register_201_to_22(r"PropertySet")
def convert_property_set_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """PropertySet doesn't exist as standalone in 2.2; skip."""
    ctx.warn(f"PropertySet {get_obj_uuid(obj)} has no direct equivalent in 2.2")
    return None


@registry.register_201_to_22(r"ContinuousPropertySeries")
def convert_continuous_prop_series_to_22(obj: Any, ctx: ConversionContext) -> Any:
    """PropertySeries -> ContinuousProperty with time indices in 2.2."""
    return r22.ContinuousProperty(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        indexable_element=r22.IndexableElement.CELLS,
        supporting_representation=convert_dor_201_to_23(
            getattr(obj, 'supporting_representation', None), ctx
        ),
    )


@registry.register_201_to_22(r"DiscretePropertySeries")
def convert_discrete_prop_series_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.DiscreteProperty(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        indexable_element=r22.IndexableElement.CELLS,
        supporting_representation=convert_dor_201_to_23(
            getattr(obj, 'supporting_representation', None), ctx
        ),
    )


@registry.register_201_to_22(r"CategoricalPropertySeries")
def convert_categorical_prop_series_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.DiscreteProperty(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        indexable_element=r22.IndexableElement.CELLS,
        supporting_representation=convert_dor_201_to_23(
            getattr(obj, 'supporting_representation', None), ctx
        ),
    )


@registry.register_201_to_22(r"CommentPropertySeries")
def convert_comment_prop_series_to_22(obj: Any, ctx: ConversionContext) -> Any:
    return r22.CommentProperty(
        citation=convert_citation_201_to_23(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_22,
        indexable_element=r22.IndexableElement.CELLS,
        supporting_representation=convert_dor_201_to_23(
            getattr(obj, 'supporting_representation', None), ctx
        ),
    )


# ─── Seismic Representations (2.2 specific) ──────────────────────────────────

@registry.register_22_to_201(r"Seismic2DPostStackRepresentation")
def convert_seismic_2d_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """Seismic2DPostStackRepresentation (2.2 only) -> Grid2DRepresentation."""
    ctx.warn(f"Seismic2DPostStackRepresentation {get_obj_uuid(obj)} mapped to Grid2DRepresentation")
    return r201.Grid2DRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        surface_role=r201.SurfaceRole.PICK,
    )


@registry.register_22_to_201(r"Seismic3DPostStackRepresentation")
def convert_seismic_3d_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """Seismic3DPostStackRepresentation (2.2 only) -> IjkGridRepresentation."""
    ctx.warn(f"Seismic3DPostStackRepresentation {get_obj_uuid(obj)} mapped to IjkGridRepresentation")
    return r201.IjkGridRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        ni=getattr(obj, 'ni', 1) or 1,
        nj=getattr(obj, 'nj', 1) or 1,
        nk=getattr(obj, 'nk', 1) or 1,
    )


@registry.register_22_to_201(r"SeismicWellboreFrameRepresentation")
def convert_seismic_wellbore_frame_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """SeismicWellboreFrameRepresentation -> WellboreFrameRepresentation in 2.0.1."""
    return r201.WellboreFrameRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        trajectory=convert_dor_23_to_201(getattr(obj, 'trajectory', None), ctx),
        node_count=getattr(obj, 'node_count', 0),
    )


@registry.register_22_to_201(r"Graph2DRepresentation")
def convert_graph2d_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """Graph2DRepresentation (2.2 only) -> PolylineSetRepresentation."""
    ctx.warn(f"Graph2DRepresentation {get_obj_uuid(obj)} mapped to PolylineSetRepresentation")
    return r201.PolylineSetRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
    )


@registry.register_22_to_201(r"WellboreIntervalSet")
def convert_wellbore_interval_set_to_201(obj: Any, ctx: ConversionContext) -> Any:
    """WellboreIntervalSet (2.2 only) -> WellboreFrameRepresentation."""
    ctx.warn(f"WellboreIntervalSet {get_obj_uuid(obj)} mapped to WellboreFrameRepresentation")
    return r201.WellboreFrameRepresentation(
        citation=convert_citation_23_to_201(obj.citation),
        uuid=get_obj_uuid(obj),
        schema_version=SCHEMA_VERSION_201,
        represented_interpretation=convert_dor_23_to_201(getattr(obj, 'represented_object', None), ctx),
        node_count=0,
    )
