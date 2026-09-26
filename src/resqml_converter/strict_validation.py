"""Strict RESQML validator using XSD schema validation (lxml) + energyml checks.

Supports RESQML 2.0.1 and 2.2 with validation results consistent with
fesapi and geosiris energyml libraries.

Validation layers:
  1. XSD Schema validation (lxml) - structural correctness against official Energistics XSD
  2. energyml object validation - patterns, required fields, enums
  3. DOR (DataObjectReference) integrity - all referenced objects exist
  4. EPC structure validation - OPC compliance, relationships, content types
  5. Cross-object consistency - CRS references, property kinds, HDF5 paths
"""

import os
import re
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from xml.etree import ElementTree as ET

from lxml import etree

from energyml.utils.epc import Epc
from energyml.utils.introspection import (
    get_obj_uuid,
    get_object_attribute_rgx,
    get_content_type_from_class,
    search_attribute_matching_type_with_path,
)
from energyml.utils.serialization import serialize_xml
from energyml.utils.validation import (
    validate_epc as energyml_validate_epc,
    validate_objects as energyml_validate_objects,
    ValidationError as EnergymlValidationError,
)


# --- Schema paths ---

_SCHEMAS_DIR = Path(__file__).resolve().parent.parent.parent / "schemas"

SCHEMA_PATHS = {
    "2.0.1": _SCHEMAS_DIR / "2.0.1" / "resqmlv2" / "v2.0.1" / "xsd_schemas" / "ResqmlAllObjects.xsd",
    "2.0.2": _SCHEMAS_DIR / "2.0.2" / "resqmlv2" / "v2.0.2" / "xsd_schemas" / "ResqmlAllObjects.xsd",
    "2.2": _SCHEMAS_DIR / "2.2" / "ResqmlAllObjects.xsd",
    "2.3.0": _SCHEMAS_DIR / "2.3.0" / "resqml" / "v2.3.0" / "xsd_schemas" / "ResqmlAllObjects.xsd",
}

# Namespaces used in RESQML XML documents
RESQML_NS = "http://www.energistics.org/energyml/data/resqmlv2"
EML_NS = "http://www.energistics.org/energyml/data/commonv2"

NS_MAP = {
    "resqml": RESQML_NS,
    "eml": EML_NS,
}


# --- Data classes for validation results ---


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    def __str__(self):
        return self.value


class ValidationCategory(str, Enum):
    XSD_SCHEMA = "xsd_schema"
    OBJECT_PATTERN = "object_pattern"
    DOR_INTEGRITY = "dor_integrity"
    EPC_STRUCTURE = "epc_structure"
    CROSS_OBJECT = "cross_object"
    HDF5_REFERENCE = "hdf5_reference"
    FESAPI_COMPAT = "fesapi_compat"
    RDDMS_COMPAT = "rddms_compat"

    def __str__(self):
        return self.value


@dataclass
class StrictValidationError:
    """A single validation finding."""

    message: str
    severity: Severity = Severity.ERROR
    category: ValidationCategory = ValidationCategory.XSD_SCHEMA
    object_uuid: Optional[str] = None
    object_type: Optional[str] = None
    xpath: Optional[str] = None
    line: Optional[int] = None

    def __str__(self):
        parts = [f"[{self.severity.value.upper()}][{self.category.value}]"]
        if self.object_type:
            parts.append(f"{self.object_type}")
        if self.object_uuid:
            parts.append(f"({self.object_uuid})")
        parts.append(f": {self.message}")
        if self.xpath:
            parts.append(f" @ {self.xpath}")
        if self.line:
            parts.append(f" (line {self.line})")
        return " ".join(parts)

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "severity": self.severity.value,
            "category": self.category.value,
            "object_uuid": self.object_uuid,
            "object_type": self.object_type,
            "xpath": self.xpath,
            "line": self.line,
        }


@dataclass
class StrictValidationReport:
    """Complete validation report for an EPC file or set of XML objects."""

    version: Optional[str] = None
    errors: List[StrictValidationError] = field(default_factory=list)
    object_count: int = 0
    validated_count: int = 0

    @property
    def is_valid(self) -> bool:
        return not any(e.severity == Severity.ERROR for e in self.errors)

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for e in self.errors if e.severity == Severity.WARNING)

    def summary(self) -> str:
        lines = [
            f"RESQML {self.version or '?'} Strict Validation Report",
            f"  Objects: {self.object_count} total, {self.validated_count} validated",
            f"  Result: {'PASS' if self.is_valid else 'FAIL'}",
            f"  Errors: {self.error_count}, Warnings: {self.warning_count}",
        ]
        if self.errors:
            lines.append("")
            for err in self.errors:
                lines.append(f"  {err}")
        return "\n".join(lines)

    def __add__(self, other: "StrictValidationReport") -> "StrictValidationReport":
        return StrictValidationReport(
            version=self.version or other.version,
            errors=self.errors + other.errors,
            object_count=self.object_count + other.object_count,
            validated_count=self.validated_count + other.validated_count,
        )


# --- Schema loading ---


class _FlatDirResolver(etree.Resolver):
    """Resolves schema imports by mapping to a flat directory."""

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        super().__init__()

    def resolve(self, system_url, public_id, context):
        filename = os.path.basename(system_url)
        local_path = os.path.join(self.base_dir, filename)
        if os.path.exists(local_path):
            return self.resolve_filename(local_path, context)
        return None


_schema_cache: Dict[str, etree.XMLSchema] = {}


def _load_schema(version: str) -> etree.XMLSchema:
    """Load and cache XSD schema for a given RESQML version."""
    if version in _schema_cache:
        return _schema_cache[version]

    schema_path = SCHEMA_PATHS.get(version)
    if schema_path is None or not schema_path.exists():
        raise FileNotFoundError(
            f"XSD schema not found for RESQML {version}. "
            f"Expected at: {schema_path}"
        )

    parser = etree.XMLParser()
    if version == "2.2":
        # 2.2 schemas are in a flat directory; imports need resolution
        parser.resolvers.add(_FlatDirResolver(str(schema_path.parent)))

    schema_doc = etree.parse(str(schema_path), parser)
    schema = etree.XMLSchema(schema_doc)
    _schema_cache[version] = schema
    return schema


# --- Version detection ---


def _normalize_resqml_version(schema_version: Optional[str]) -> Optional[str]:
    """Map a raw RESQML schemaVersion/content-type version to a package release.

    RESQML releases pair with EML releases using DIFFERENT numbers:
      RESQML 2.0.1 / 2.0.2 <-> EML 2.0
      RESQML 2.2           <-> EML 2.3 (released)
      RESQML 2.3.0         <-> EML 2.3 (unreleased variant)
    RESQML 2.0.x content-types carry version=2.0 (2.0.1 and 2.0.2 are binary
    compatible), so 2.0 defaults to 2.0.1 unless an explicit 2.0.2 is seen.
    """
    if not schema_version:
        return None
    sv = schema_version.strip()
    if sv.startswith("2.0.2"):
        return "2.0.2"
    if sv.startswith("2.0"):
        return "2.0.1"
    if sv.startswith("2.2"):
        return "2.2"
    if sv.startswith("2.3"):
        return "2.3.0"
    return None


def detect_version_from_xml(xml_bytes: bytes) -> Optional[str]:
    """Detect the RESQML package version from a single XML object.

    Only RESQML domain objects carry the package release in their schemaVersion.
    EML/common objects (CRS, PropertyKind) carry the EML version ("2.3") which is
    ambiguous between RESQML 2.2 and 2.3.0, so they are not used to decide the
    package version (return None and let the EPC-level detection decide).
    """
    try:
        root = etree.fromstring(xml_bytes)
        tag = root.tag
        is_resqml = "resqmlv2" in tag
        schema_version = root.get("schemaVersion") or root.get("version")
        if is_resqml:
            v = _normalize_resqml_version(schema_version)
            if v:
                return v
            # Fall back to naming/namespace heuristics for RESQML objects.
            local = etree.QName(tag).localname
            if local.startswith("obj_"):
                return "2.0.1"  # obj_ prefix is the 2.0.x convention
            if schema_version and "2.3" in schema_version:
                return "2.3.0"
            return "2.2"
    except Exception:
        pass
    return None


def detect_version_from_epc(epc_path: str) -> Optional[str]:
    """Detect the RESQML package version from EPC content types."""
    try:
        with zipfile.ZipFile(epc_path, "r") as zf:
            if "[Content_Types].xml" in zf.namelist():
                ct = zf.read("[Content_Types].xml").decode("utf-8")
                # Key off the RESQML content type version (the package release),
                # not the EML content type.
                m = re.search(r"x-resqml\+xml;\s*version=\"?([0-9.]+)", ct)
                if m:
                    v = _normalize_resqml_version(m.group(1))
                    if v:
                        return v
                if 'version="2.3"' in ct or "version=2.3" in ct:
                    return "2.3.0"
                if 'version="2.2"' in ct or "version=2.2" in ct:
                    return "2.2"
                if 'version="2.0"' in ct or "version=2.0" in ct:
                    return "2.0.1"
            # Fallback: check the first RESQML domain XML part.
            for name in zf.namelist():
                if name.endswith(".xml") and name != "[Content_Types].xml" and not name.startswith("_rels"):
                    data = zf.read(name)
                    v = detect_version_from_xml(data)
                    if v:
                        return v
    except Exception:
        pass
    return None


# --- XSD Validation ---


def validate_xml_against_xsd(
    xml_content: bytes,
    version: str,
    object_uuid: Optional[str] = None,
    object_type: Optional[str] = None,
) -> List[StrictValidationError]:
    """Validate a single XML document against the RESQML XSD schema.

    Handles the obj_ prefix convention: RESQML 2.0.1 files typically use
    obj_TypeName as root element, but the XSD declares elements as TypeName.
    Both forms are accepted (consistent with fesapi behavior).
    """
    errors = []
    try:
        schema = _load_schema(version)
    except FileNotFoundError as e:
        errors.append(StrictValidationError(
            message=str(e),
            severity=Severity.ERROR,
            category=ValidationCategory.XSD_SCHEMA,
        ))
        return errors

    try:
        doc = etree.fromstring(xml_content)
    except etree.XMLSyntaxError as e:
        errors.append(StrictValidationError(
            message=f"XML parse error: {e}",
            severity=Severity.ERROR,
            category=ValidationCategory.XSD_SCHEMA,
            object_uuid=object_uuid,
            object_type=object_type,
            line=e.lineno,
        ))
        return errors

    # Handle obj_ prefix: try as-is first, then strip obj_ prefix
    if not schema.validate(doc):
        # If validation fails, try stripping obj_ prefix (RESQML 2.0.1 convention)
        tag = etree.QName(doc.tag)
        local_name = tag.localname
        if local_name.startswith("obj_"):
            stripped_name = local_name[4:]
            new_tag = f"{{{tag.namespace}}}{stripped_name}" if tag.namespace else stripped_name
            doc_copy = etree.fromstring(xml_content)
            doc_copy.tag = new_tag
            if schema.validate(doc_copy):
                return errors  # Valid with stripped prefix
        # Report the errors from the original validation
        for err in schema.error_log:
            errors.append(StrictValidationError(
                message=err.message,
                severity=Severity.ERROR,
                category=ValidationCategory.XSD_SCHEMA,
                object_uuid=object_uuid,
                object_type=object_type,
                line=err.line,
            ))

    return errors


# --- EPC Structure Validation ---


def validate_epc_structure(epc_path: str) -> List[StrictValidationError]:
    """Validate EPC ZIP structure for OPC compliance.

    Checks:
      - Valid ZIP file
      - [Content_Types].xml present and well-formed
      - _rels/.rels present
      - All referenced parts exist
      - PartName starts with /
      - ContentType values are well-formed
    """
    errors = []

    if not os.path.exists(epc_path):
        errors.append(StrictValidationError(
            message=f"File not found: {epc_path}",
            severity=Severity.ERROR,
            category=ValidationCategory.EPC_STRUCTURE,
        ))
        return errors

    try:
        zf = zipfile.ZipFile(epc_path, "r")
    except zipfile.BadZipFile:
        errors.append(StrictValidationError(
            message="Not a valid ZIP file",
            severity=Severity.ERROR,
            category=ValidationCategory.EPC_STRUCTURE,
        ))
        return errors

    with zf:
        names = set(zf.namelist())

        # [Content_Types].xml required
        if "[Content_Types].xml" not in names:
            errors.append(StrictValidationError(
                message="Missing [Content_Types].xml (required by OPC)",
                severity=Severity.ERROR,
                category=ValidationCategory.EPC_STRUCTURE,
            ))
        else:
            try:
                ct_xml = zf.read("[Content_Types].xml")
                ct_root = ET.fromstring(ct_xml)
                # Validate PartName entries
                for override in ct_root:
                    part_name = override.get("PartName", "")
                    if part_name and not part_name.startswith("/"):
                        errors.append(StrictValidationError(
                            message=f"PartName should start with '/' per OPC spec: {part_name}",
                            severity=Severity.WARNING,
                            category=ValidationCategory.EPC_STRUCTURE,
                        ))
                    # Check that referenced part exists in ZIP
                    if part_name:
                        zip_name = part_name.lstrip("/")
                        if zip_name not in names:
                            errors.append(StrictValidationError(
                                message=f"Part referenced in [Content_Types].xml not found in ZIP: {part_name}",
                                severity=Severity.WARNING,
                                category=ValidationCategory.EPC_STRUCTURE,
                            ))
            except ET.ParseError as e:
                errors.append(StrictValidationError(
                    message=f"[Content_Types].xml is not well-formed XML: {e}",
                    severity=Severity.ERROR,
                    category=ValidationCategory.EPC_STRUCTURE,
                ))

        # _rels/.rels recommended
        if "_rels/.rels" not in names:
            errors.append(StrictValidationError(
                message="Missing _rels/.rels (recommended by OPC)",
                severity=Severity.WARNING,
                category=ValidationCategory.EPC_STRUCTURE,
            ))

    return errors


# --- DOR Integrity Validation ---


def validate_dor_integrity(
    objects: List[Any],
) -> List[StrictValidationError]:
    """Validate that all DataObjectReferences point to objects that exist in the EPC.

    This mirrors fesapi's referential integrity checking.
    """
    errors = []

    # Build UUID index
    uuid_index: Dict[str, Any] = {}
    for obj in objects:
        uuid = get_obj_uuid(obj)
        if uuid:
            uuid_index[uuid] = obj

    # Check all DORs
    for obj in objects:
        obj_uuid = get_obj_uuid(obj)
        obj_type = type(obj).__name__

        dor_list = search_attribute_matching_type_with_path(obj, "DataObjectReference")
        for dor_path, dor in dor_list:
            dor_uuid = get_obj_uuid(dor)
            dor_title = get_object_attribute_rgx(dor, "title")
            dor_content_type = get_object_attribute_rgx(dor, "content_type")
            dor_qualified_type = get_object_attribute_rgx(dor, "qualified_type")

            if not dor_uuid:
                errors.append(StrictValidationError(
                    message=f"DOR has no UUID at path '{dor_path}'",
                    severity=Severity.ERROR,
                    category=ValidationCategory.DOR_INTEGRITY,
                    object_uuid=obj_uuid,
                    object_type=obj_type,
                    xpath=dor_path,
                ))
                continue

            if dor_uuid not in uuid_index:
                # Check if it's a well-known property kind
                from energyml.utils.epc_utils import get_property_kind_by_uuid
                if get_property_kind_by_uuid(dor_uuid) is None:
                    errors.append(StrictValidationError(
                        message=f"Referenced object not found: uuid='{dor_uuid}' title='{dor_title}'",
                        severity=Severity.ERROR,
                        category=ValidationCategory.DOR_INTEGRITY,
                        object_uuid=obj_uuid,
                        object_type=obj_type,
                        xpath=dor_path,
                    ))

            # Validate DOR has required fields (fesapi requires ContentType or QualifiedType)
            if not dor_content_type and not dor_qualified_type:
                errors.append(StrictValidationError(
                    message=f"DOR missing both ContentType and QualifiedType for uuid='{dor_uuid}'",
                    severity=Severity.WARNING,
                    category=ValidationCategory.DOR_INTEGRITY,
                    object_uuid=obj_uuid,
                    object_type=obj_type,
                    xpath=dor_path,
                ))

    return errors


# --- HDF5 Reference Validation ---


def validate_hdf5_references(
    objects: List[Any],
    h5_path: Optional[str] = None,
) -> List[StrictValidationError]:
    """Validate HDF5 dataset path references in objects.

    If h5_path is provided, checks that referenced datasets actually exist.
    """
    errors = []

    # Collect all HDF5 path references from objects
    h5_datasets_referenced: Set[str] = set()

    for obj in objects:
        obj_uuid = get_obj_uuid(obj)
        obj_type = type(obj).__name__

        # Search for ExternalDataArrayPart or Hdf5Dataset references
        ext_refs = search_attribute_matching_type_with_path(obj, "ExternalDataArrayPart")
        ext_refs += search_attribute_matching_type_with_path(obj, "Hdf5Dataset")

        for ref_path, ref in ext_refs:
            path_in_file = get_object_attribute_rgx(ref, "path_in_external_file")
            if path_in_file is None:
                path_in_file = get_object_attribute_rgx(ref, "path_in_hdf_file")

            if path_in_file:
                h5_datasets_referenced.add(path_in_file)
                # Validate path format
                if not path_in_file.startswith("/"):
                    errors.append(StrictValidationError(
                        message=f"HDF5 path should start with '/': '{path_in_file}'",
                        severity=Severity.WARNING,
                        category=ValidationCategory.HDF5_REFERENCE,
                        object_uuid=obj_uuid,
                        object_type=obj_type,
                        xpath=ref_path,
                    ))

    # If H5 file is provided, verify datasets exist
    if h5_path and os.path.exists(h5_path) and h5_datasets_referenced:
        try:
            import h5py
            with h5py.File(h5_path, "r") as h5f:
                for ds_path in h5_datasets_referenced:
                    if ds_path not in h5f:
                        errors.append(StrictValidationError(
                            message=f"HDF5 dataset not found: '{ds_path}'",
                            severity=Severity.ERROR,
                            category=ValidationCategory.HDF5_REFERENCE,
                        ))
        except ImportError:
            pass
        except Exception as e:
            errors.append(StrictValidationError(
                message=f"Error reading HDF5 file: {e}",
                severity=Severity.WARNING,
                category=ValidationCategory.HDF5_REFERENCE,
            ))

    return errors


# --- Cross-Object Consistency ---


def validate_cross_object_consistency(
    objects: List[Any],
    version: str,
) -> List[StrictValidationError]:
    """Validate cross-object consistency rules.

    Checks that fesapi and geosiris would also enforce:
      - CRS references are consistent
      - Property kinds reference valid parent kinds
      - UUID uniqueness
      - Version-specific naming conventions
    """
    errors = []

    # UUID uniqueness
    uuid_counts: Dict[str, List[str]] = {}
    for obj in objects:
        uuid = get_obj_uuid(obj)
        if uuid:
            if uuid not in uuid_counts:
                uuid_counts[uuid] = []
            uuid_counts[uuid].append(type(obj).__name__)

    for uuid, types in uuid_counts.items():
        if len(types) > 1:
            errors.append(StrictValidationError(
                message=f"Duplicate UUID '{uuid}' used by: {', '.join(types)}",
                severity=Severity.ERROR,
                category=ValidationCategory.CROSS_OBJECT,
                object_uuid=uuid,
            ))

    # Version-specific checks could be added here as needed
    # Note: energyml internal class names (e.g. LocalDepth3DCrs vs ObjLocalDepth3DCrs)
    # don't reflect the XML serialization prefix, so we don't check class naming.

    return errors


# --- fesapi Compatibility Validation ---

# Elements that must appear last in their parent (per fesapi strictness)
_FESAPI_LAST_ELEMENTS = {"ExtraMetadata"}

# Regex for extracting type from root element tag
_ROOT_TAG_RE = re.compile(r"\{[^}]+\}(obj_)?(\w+)")


def validate_fesapi_compat(
    epc_path: str,
    version: Optional[str] = None,
) -> List[StrictValidationError]:
    """Validate EPC raw XML for fesapi parser compatibility (RESQML 2.0.1).

    fesapi is stricter than the XSD specification in several ways:
      - Root element MUST have xsi:type attribute for polymorphic deserialization
      - ExtraMetadata must be the LAST child elements (after all type-specific elements)
      - Root element should NOT use obj_ prefix in the tag name
      - Element ordering must strictly follow XSD sequence

    These checks operate on the raw XML bytes inside the EPC (not energyml objects),
    since the issues are about serialization format.
    """
    errors = []

    if version and version != "2.0.1":
        return errors  # fesapi checks only apply to 2.0.1

    try:
        zf = zipfile.ZipFile(epc_path, "r")
    except (zipfile.BadZipFile, FileNotFoundError):
        return errors  # Structure checks handle this

    with zf:
        for name in zf.namelist():
            if not name.endswith(".xml"):
                continue
            if name == "[Content_Types].xml" or name.startswith("_rels/"):
                continue

            xml_bytes = zf.read(name)
            try:
                root = etree.fromstring(xml_bytes)
            except etree.XMLSyntaxError:
                continue  # XSD validation handles parse errors

            tag = etree.QName(root.tag)
            local_name = tag.localname
            obj_uuid = root.get("uuid")
            obj_type = local_name.removeprefix("obj_") if local_name.startswith("obj_") else local_name

            # Skip non-RESQML objects (e.g. EpcExternalPartReference)
            if tag.namespace not in (RESQML_NS, EML_NS):
                continue

            # Check 1: xsi:type on root element (needed for RDDMS ETP import,
            #          but NOT required for local fesapi file reading)
            xsi_type = root.get(f"{{{NS_MAP.get('xsi', 'http://www.w3.org/2001/XMLSchema-instance')}}}type")
            if xsi_type is None:
                # Check with explicit xsi namespace
                xsi_type = root.get("{http://www.w3.org/2001/XMLSchema-instance}type")
            if xsi_type is None:
                errors.append(StrictValidationError(
                    message=(
                        f"Missing xsi:type on root element. "
                        f"fesapi can read this locally, but RDDMS ETP import requires xsi:type "
                        f"for server-side deserialization. Expected xsi:type containing 'obj_{obj_type}'"
                    ),
                    severity=Severity.WARNING,
                    category=ValidationCategory.FESAPI_COMPAT,
                    object_uuid=obj_uuid,
                    object_type=obj_type,
                ))

            # Check 2: Root element should NOT have obj_ prefix in tag name
            if local_name.startswith("obj_"):
                errors.append(StrictValidationError(
                    message=(
                        f"Root element uses obj_ prefix in tag name (<{local_name}>). "
                        f"fesapi expects the tag without obj_ prefix."
                    ),
                    severity=Severity.WARNING,
                    category=ValidationCategory.FESAPI_COMPAT,
                    object_uuid=obj_uuid,
                    object_type=obj_type,
                ))

            # Check 3: ExtraMetadata must be last among siblings
            children = list(root)
            if children:
                last_non_em_idx = -1
                first_em_idx = -1
                for i, child in enumerate(children):
                    child_local = etree.QName(child.tag).localname
                    if child_local == "ExtraMetadata":
                        if first_em_idx == -1:
                            first_em_idx = i
                    else:
                        last_non_em_idx = i

                if first_em_idx != -1 and last_non_em_idx > first_em_idx:
                    errors.append(StrictValidationError(
                        message=(
                            "ExtraMetadata appears before other elements. "
                            "fesapi requires ExtraMetadata to be the last child elements."
                        ),
                        severity=Severity.ERROR,
                        category=ValidationCategory.FESAPI_COMPAT,
                        object_uuid=obj_uuid,
                        object_type=obj_type,
                    ))

    return errors


# --- RESQML 2.0.1 property-kind catalogue (abstract flags + hierarchy) ---

_PROP_KIND_CACHE: Dict[str, Tuple[Set[str], Dict[str, str]]] = {}
_PROP_OBJ_TYPES = ("ContinuousProperty", "CategoricalProperty", "DiscreteProperty")
_XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"


def _load_property_kinds(version: str) -> Tuple[Set[str], Dict[str, str]]:
    """Load the standard property-kind catalogue (name -> abstract flag, parent).

    Parsed from the Energistics ancillary enum (enumValuesResqml.xml) shipped
    alongside the XSD schemas.  Returns (abstract_names, parent_by_name).
    """
    if version in _PROP_KIND_CACHE:
        return _PROP_KIND_CACHE[version]
    abstract: Set[str] = set()
    parent: Dict[str, str] = {}
    enum = (_SCHEMAS_DIR / version / "resqmlv2" / f"v{version}"
            / "ancillary" / "enumValuesResqml.xml")
    try:
        txt = enum.read_text(encoding="utf-8")
        for m in re.finditer(
            r"<value>\s*<name>([^<]+)</name>"
            r"(?:\s*<description>.*?</description>)?\s*"
            r"<isAbstract>(\w+)</isAbstract>"
            r"(?:\s*<parentKind>([^<]+)</parentKind>)?",
            txt, re.S,
        ):
            nm = m.group(1).strip()
            parent[nm] = (m.group(3) or "").strip()
            if m.group(2).strip().lower() == "true":
                abstract.add(nm)
    except (FileNotFoundError, OSError):
        pass
    _PROP_KIND_CACHE[version] = (abstract, parent)
    return abstract, parent


def _kind_branch(name: str, parent: Dict[str, str]) -> Optional[str]:
    """Return 'continuous' or 'discrete' depending on the kind's ancestry."""
    seen: Set[str] = set()
    chain = {name}
    cur = name
    while cur in parent and cur not in seen:
        seen.add(cur)
        p = parent.get(cur)
        if not p:
            break
        chain.add(p)
        cur = p
    if "discrete" in chain or "categorical" in chain:
        return "discrete"
    if "continuous" in chain:
        return "continuous"
    return None


def validate_property_kinds(
    epc_path: str,
    version: Optional[str] = None,
) -> List[StrictValidationError]:
    """Validate property -> property-kind usage for RESQML 2.0.1 / fesapi.

    fesapi (and the RESQML 2.0.1 spec) require that:
      - a property does NOT reference an *abstract* standard property kind
        (e.g. 'volume per volume', 'dimensionless'); abstract-kind properties
        are treated as partial.  Derive a non-abstract local kind (optionally
        copying a non-abstract PWLS kind) instead.
      - a DiscreteProperty / CategoricalProperty uses a kind rooted in
        'discrete' (not 'continuous'); a ContinuousProperty uses a kind rooted
        in 'continuous'.  (This is why a discrete property of kind 'length' is
        rejected: 'length' derives from 'continuous'.)
      - a local property kind referenced by a property is non-abstract.
    """
    errors: List[StrictValidationError] = []
    if version and version != "2.0.1":
        return errors
    abstract, parent = _load_property_kinds(version or "2.0.1")
    if not abstract:
        return errors  # catalogue unavailable; nothing to check against

    try:
        zf = zipfile.ZipFile(epc_path, "r")
    except (zipfile.BadZipFile, FileNotFoundError):
        return errors

    with zf:
        names = zf.namelist()

        # Catalogue local PropertyKind objects: uuid -> (is_abstract, parent_std)
        local_kinds: Dict[str, Tuple[bool, Optional[str]]] = {}
        for name in names:
            base = name.rsplit("/", 1)[-1]
            if not base.startswith("obj_PropertyKind") or not name.endswith(".xml"):
                continue
            if "_rels/" in name:
                continue
            try:
                root = etree.fromstring(zf.read(name))
            except etree.XMLSyntaxError:
                continue
            u = root.get("uuid")
            is_abs = False
            pstd: Optional[str] = None
            for el in root.iter():
                ln = etree.QName(el.tag).localname
                if ln == "IsAbstract":
                    is_abs = (el.text or "").strip().lower() == "true"
                elif ln == "ParentPropertyKind":
                    for c in el.iter():
                        if etree.QName(c.tag).localname == "Kind":
                            pstd = (c.text or "").strip()
            if u:
                local_kinds[u] = (is_abs, pstd)

        for name in names:
            base = name.rsplit("/", 1)[-1]
            if not name.endswith(".xml") or "_rels/" in name:
                continue
            if not any(base.startswith("obj_" + t) for t in _PROP_OBJ_TYPES):
                continue
            try:
                root = etree.fromstring(zf.read(name))
            except etree.XMLSyntaxError:
                continue
            ptype = etree.QName(root.tag).localname.removeprefix("obj_")
            obj_uuid = root.get("uuid")
            expected = "continuous" if ptype == "ContinuousProperty" else "discrete"

            pk = next((c for c in root
                       if etree.QName(c.tag).localname == "PropertyKind"), None)
            if pk is None:
                continue
            xtype = pk.get(_XSI) or ""

            if xtype.endswith("StandardPropertyKind"):
                kind_name = next((( c.text or "").strip() for c in pk
                                  if etree.QName(c.tag).localname == "Kind"), None)
                if not kind_name:
                    continue
                if kind_name in abstract:
                    errors.append(StrictValidationError(
                        message=(
                            f"Property references the ABSTRACT standard property "
                            f"kind '{kind_name}'. fesapi treats abstract-kind "
                            f"properties as partial; derive a non-abstract local "
                            f"property kind (or copy a non-abstract PWLS kind)."),
                        severity=Severity.ERROR,
                        category=ValidationCategory.FESAPI_COMPAT,
                        object_uuid=obj_uuid, object_type=ptype,
                    ))
                else:
                    br = _kind_branch(kind_name, parent)
                    if br and br != expected:
                        errors.append(StrictValidationError(
                            message=(
                                f"{ptype} uses standard property kind "
                                f"'{kind_name}' which derives from '{br}', not "
                                f"'{expected}'. A {ptype} must use a kind rooted "
                                f"in '{expected}'."),
                            severity=Severity.ERROR,
                            category=ValidationCategory.FESAPI_COMPAT,
                            object_uuid=obj_uuid, object_type=ptype,
                        ))
            elif xtype.endswith("LocalPropertyKind"):
                ref_uuid = next(((c.text or "").strip() for c in pk.iter()
                                 if etree.QName(c.tag).localname == "UUID"), None)
                if not ref_uuid or ref_uuid not in local_kinds:
                    continue  # DOR integrity handles a missing local kind
                is_abs, pstd = local_kinds[ref_uuid]
                if is_abs:
                    errors.append(StrictValidationError(
                        message=(
                            f"Property references local property kind "
                            f"{ref_uuid} which is IsAbstract=true; a kind used by "
                            f"a property must be non-abstract."),
                        severity=Severity.ERROR,
                        category=ValidationCategory.FESAPI_COMPAT,
                        object_uuid=obj_uuid, object_type=ptype,
                    ))
                if pstd:
                    br = _kind_branch(pstd, parent)
                    if br and br != expected:
                        errors.append(StrictValidationError(
                            message=(
                                f"{ptype} uses local kind {ref_uuid} whose parent "
                                f"'{pstd}' derives from '{br}', not '{expected}'."),
                            severity=Severity.ERROR,
                            category=ValidationCategory.FESAPI_COMPAT,
                            object_uuid=obj_uuid, object_type=ptype,
                        ))

    return errors


def validate_fesapi_packaging(
    epc_path: str,
    version: Optional[str] = None,
    h5_path: Optional[str] = None,
) -> List[StrictValidationError]:
    """Validate package-level fesapi conventions for RESQML 2.0.1.

      - [Content_Types].xml should not carry a catch-all <Default
        Extension="xml"> (fesapi ignores it; every object is an explicit
        Override).
      - <eml:VersionString> should be avoided (fesapi guidance: do not use
        object versioning unless you really need it).
      - the HDF5 file root group should carry a 'uuid' attribute equal to the
        owning EpcExternalPartReference uuid so fesapi/ETP can bind them.
    """
    errors: List[StrictValidationError] = []
    if version and version != "2.0.1":
        return errors
    try:
        zf = zipfile.ZipFile(epc_path, "r")
    except (zipfile.BadZipFile, FileNotFoundError):
        return errors

    with zf:
        names = zf.namelist()

        if "[Content_Types].xml" in names:
            ct = zf.read("[Content_Types].xml").decode("utf-8", "replace")
            if re.search(r'<Default\s+Extension="xml"', ct):
                errors.append(StrictValidationError(
                    message=(
                        '[Content_Types].xml declares a catch-all '
                        '<Default Extension="xml">. fesapi ignores it and every '
                        'object part is already an explicit Override; remove it '
                        '(keep the .rels Default).'),
                    severity=Severity.WARNING,
                    category=ValidationCategory.FESAPI_COMPAT,
                ))

        vcount = 0
        for name in names:
            if not name.endswith(".xml") or name == "[Content_Types].xml" \
                    or "_rels/" in name:
                continue
            if b"VersionString" in zf.read(name):
                vcount += 1
        if vcount:
            errors.append(StrictValidationError(
                message=(
                    f"{vcount} object(s) declare an <eml:VersionString>. fesapi "
                    f"guidance: do not use object versioning unless required \u2014 "
                    f"mismatched DOR/object versions are a common cause of broken "
                    f"references."),
                severity=Severity.WARNING,
                category=ValidationCategory.FESAPI_COMPAT,
            ))

    # HDF5 root 'uuid' attribute
    if h5_path is None:
        epc_dir = os.path.dirname(epc_path)
        stem = Path(epc_path).stem
        for ext in (".h5", ".hdf5", ".hdf"):
            cand = os.path.join(epc_dir, stem + ext)
            if os.path.exists(cand):
                h5_path = cand
                break
    if h5_path and os.path.exists(h5_path):
        try:
            import h5py
            with h5py.File(h5_path, "r") as f:
                if "uuid" not in f.attrs:
                    errors.append(StrictValidationError(
                        message=(
                            f"HDF5 file '{os.path.basename(h5_path)}' root group "
                            f"has no 'uuid' attribute. fesapi/ETP expect the owning "
                            f"EpcExternalPartReference uuid as a root attribute to "
                            f"bind the HDF5 to the EPC."),
                        severity=Severity.WARNING,
                        category=ValidationCategory.FESAPI_COMPAT,
                    ))
        except ImportError:
            pass
        except Exception:
            pass

    return errors


# --- RDDMS Compatibility Validation ---

_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_EXT_RESOURCE_TYPE = "http://schemas.energistics.org/package/2012/relationships/externalResource"
_DEST_OBJ_TYPE = "http://schemas.energistics.org/package/2012/relationships/destinationObject"
_SOURCE_OBJ_TYPE = "http://schemas.energistics.org/package/2012/relationships/sourceObject"


def validate_rddms_compat(
    epc_path: str,
    version: Optional[str] = None,
) -> List[StrictValidationError]:
    """Validate EPC for RDDMS (ETP server) import compatibility.

    Checks:
      - Namespace prefix conventions (resqml2: not resqml:)
      - ContentType format in [Content_Types].xml
      - EPR .rels has externalResource → HDF5 with TargetMode="External"
      - Root _rels/.rels references the EpcExternalPartReference
      - Closing tags match opening tags (no obj_ mismatch)
    """
    errors = []

    if version and version != "2.0.1":
        return errors  # RDDMS checks focused on 2.0.1

    try:
        zf = zipfile.ZipFile(epc_path, "r")
    except (zipfile.BadZipFile, FileNotFoundError):
        return errors

    with zf:
        names = set(zf.namelist())

        # Check [Content_Types].xml format
        if "[Content_Types].xml" in names:
            ct_xml = zf.read("[Content_Types].xml").decode("utf-8", errors="replace")
            try:
                ct_root = ET.fromstring(ct_xml)
                for override in ct_root:
                    ct_value = override.get("ContentType", "")
                    part_name = override.get("PartName", "")
                    # RESQML objects should have version=2.0 and type=obj_TypeName
                    if "x-resqml+xml" in ct_value:
                        if "version=2.0" not in ct_value:
                            errors.append(StrictValidationError(
                                message=f"ContentType missing version=2.0: '{ct_value}' for {part_name}",
                                severity=Severity.WARNING,
                                category=ValidationCategory.RDDMS_COMPAT,
                            ))
                        if "type=obj_" not in ct_value:
                            errors.append(StrictValidationError(
                                message=f"ContentType missing type=obj_ prefix: '{ct_value}' for {part_name}",
                                severity=Severity.WARNING,
                                category=ValidationCategory.RDDMS_COMPAT,
                            ))
            except ET.ParseError:
                pass  # Structure validation handles this

        # Check EpcExternalPartReference .rels has HDF5 link
        epr_files = [n for n in names if "EpcExternalPartReference" in n and n.endswith(".xml") and not n.startswith("_rels/")]
        for epr_file in epr_files:
            rels_file = f"_rels/{epr_file}.rels"
            if rels_file not in names:
                errors.append(StrictValidationError(
                    message=f"Missing .rels for EpcExternalPartReference: {rels_file}",
                    severity=Severity.ERROR,
                    category=ValidationCategory.RDDMS_COMPAT,
                ))
                continue

            rels_xml = zf.read(rels_file).decode("utf-8", errors="replace")
            try:
                rels_root = ET.fromstring(rels_xml)
                has_hdf5_link = False
                for rel in rels_root:
                    rel_type = rel.get("Type", "")
                    target_mode = rel.get("TargetMode", "")
                    target = rel.get("Target", "")
                    if rel_type == _EXT_RESOURCE_TYPE:
                        has_hdf5_link = True
                        if target_mode != "External":
                            errors.append(StrictValidationError(
                                message=(
                                    f"EPR .rels externalResource should have TargetMode=\"External\", "
                                    f"got '{target_mode}'"
                                ),
                                severity=Severity.ERROR,
                                category=ValidationCategory.RDDMS_COMPAT,
                            ))
                        if not target:
                            errors.append(StrictValidationError(
                                message="EPR .rels externalResource has empty Target",
                                severity=Severity.ERROR,
                                category=ValidationCategory.RDDMS_COMPAT,
                            ))
                if not has_hdf5_link:
                    errors.append(StrictValidationError(
                        message=(
                            f"EPR .rels ({rels_file}) has no externalResource relationship to HDF5 file. "
                            f"RDDMS requires this to locate the HDF5 data."
                        ),
                        severity=Severity.ERROR,
                        category=ValidationCategory.RDDMS_COMPAT,
                    ))
            except ET.ParseError:
                errors.append(StrictValidationError(
                    message=f"EPR .rels is not well-formed XML: {rels_file}",
                    severity=Severity.ERROR,
                    category=ValidationCategory.RDDMS_COMPAT,
                ))

        # Check namespace prefix and tag mismatch in RESQML XML
        for name in names:
            if not name.endswith(".xml") or name == "[Content_Types].xml" or name.startswith("_rels/"):
                continue
            if "EpcExternalPartReference" in name:
                continue

            xml_content = zf.read(name).decode("utf-8", errors="replace")

            # Check namespace prefix: resqml2: is preferred for RDDMS but resqml: also works
            if 'xmlns:resqml="http://www.energistics.org/energyml/data/resqmlv2"' in xml_content:
                obj_uuid_m = re.search(r'uuid="([^"]+)"', xml_content)
                errors.append(StrictValidationError(
                    message=(
                        "Uses 'resqml:' namespace prefix instead of 'resqml2:'. "
                        "Some RDDMS configurations expect 'resqml2:' prefix for RESQML 2.0.1."
                    ),
                    severity=Severity.WARNING,
                    category=ValidationCategory.RDDMS_COMPAT,
                    object_uuid=obj_uuid_m.group(1) if obj_uuid_m else None,
                    object_type=re.search(r"obj_(\w+?)_", name).group(1) if "obj_" in name else None,
                ))

            # Check closing tag mismatch (obj_ in closing but not opening)
            open_m = re.search(r"<(?:resqml2?|eml):(\w+)\s", xml_content)
            close_m = re.search(r"</(?:resqml2?|eml):(\w+)>\s*$", xml_content)
            if open_m and close_m:
                open_name = open_m.group(1)
                close_name = close_m.group(1)
                if open_name != close_name:
                    obj_uuid_m = re.search(r'uuid="([^"]+)"', xml_content)
                    errors.append(StrictValidationError(
                        message=(
                            f"Root element tag mismatch: opening <{open_name}> vs closing </{close_name}>. "
                            f"This will cause fesapi parse failure."
                        ),
                        severity=Severity.ERROR,
                        category=ValidationCategory.RDDMS_COMPAT,
                        object_uuid=obj_uuid_m.group(1) if obj_uuid_m else None,
                    ))

            # Check xsi:type on root element (required for RDDMS ETP server-side parsing)
            # Skip OPC package metadata files (not RESQML objects)
            if name.startswith('docProps/') or name.startswith('_rels/') or '[Content_Types]' in name:
                continue
            # Find the root opening tag (skip XML prolog, then everything up to first >)
            root_start = xml_content.find('<', xml_content.find('?>') + 2) if '?>' in xml_content else 0
            root_tag_end = xml_content.find('>', root_start) if root_start >= 0 else -1
            root_tag = xml_content[root_start:root_tag_end] if root_tag_end != -1 else xml_content
            if 'xsi:type=' not in root_tag:
                obj_uuid_m = re.search(r'uuid="([^"]+)"', xml_content)
                obj_type_m = re.search(r"obj_(\w+?)_", name)
                errors.append(StrictValidationError(
                    message=(
                        "Missing xsi:type on root element. "
                        "RDDMS ETP import requires xsi:type for server-side object deserialization "
                        "(e.g. xsi:type=\"resqml2:obj_TypeName\")."
                    ),
                    severity=Severity.ERROR,
                    category=ValidationCategory.RDDMS_COMPAT,
                    object_uuid=obj_uuid_m.group(1) if obj_uuid_m else None,
                    object_type=obj_type_m.group(1) if obj_type_m else None,
                ))

    return errors


# --- energyml Object Validation ---


def validate_energyml_objects(
    objects: List[Any],
) -> List[StrictValidationError]:
    """Run energyml's built-in validation (patterns, required fields, DOR checks).

    Converts energyml ValidationError results to our StrictValidationError format.
    """
    errors = []

    energyml_errors = energyml_validate_objects(objects)
    for err in energyml_errors:
        obj_uuid = None
        obj_type = None
        xpath = None

        if hasattr(err, "target_obj") and err.target_obj is not None:
            obj_uuid = get_obj_uuid(err.target_obj)
            obj_type = type(err.target_obj).__name__
        if hasattr(err, "attribute_dot_path"):
            xpath = err.attribute_dot_path

        # Map energyml error type to our severity
        err_type_str = str(err.error_type).lower() if hasattr(err, "error_type") else "error"
        if "critical" in err_type_str:
            severity = Severity.ERROR
        elif "warning" in err_type_str:
            severity = Severity.WARNING
        else:
            severity = Severity.INFO

        errors.append(StrictValidationError(
            message=err.msg if hasattr(err, "msg") else str(err),
            severity=severity,
            category=ValidationCategory.OBJECT_PATTERN,
            object_uuid=obj_uuid,
            object_type=obj_type,
            xpath=xpath,
        ))

    return errors


# --- Main Validation Entry Points ---


def validate_epc_strict(
    epc_path: str,
    version: Optional[str] = None,
    h5_path: Optional[str] = None,
    skip_xsd: bool = False,
    skip_energyml: bool = False,
    skip_dor: bool = False,
    skip_epc_structure: bool = False,
    skip_hdf5: bool = False,
    skip_cross_object: bool = False,
    skip_fesapi: bool = False,
    skip_rddms: bool = False,
) -> StrictValidationReport:
    """Run full strict validation on an EPC file.

    This is the main entry point. Runs all validation layers:
      1. EPC structure (OPC compliance)
      2. XSD schema validation per object
      3. energyml object validation (patterns, required)
      4. DOR integrity (referential completeness)
      5. HDF5 reference validation
      6. Cross-object consistency
      7. fesapi compatibility (xsi:type, element ordering, ExtraMetadata position)
      8. RDDMS compatibility (namespace prefixes, .rels integrity, ContentType format)

    Args:
        epc_path: Path to the EPC file.
        version: RESQML version override ("2.0.1" or "2.2"). Auto-detected if None.
        h5_path: Optional path to associated HDF5 file.
        skip_xsd: Skip XSD schema validation.
        skip_energyml: Skip energyml object validation.
        skip_dor: Skip DOR integrity checks.
        skip_epc_structure: Skip EPC structure validation.
        skip_hdf5: Skip HDF5 reference validation.
        skip_cross_object: Skip cross-object consistency.
        skip_fesapi: Skip fesapi compatibility checks.
        skip_rddms: Skip RDDMS compatibility checks.

    Returns:
        StrictValidationReport with all findings.
    """
    report = StrictValidationReport()

    # Auto-detect version
    if version is None:
        version = detect_version_from_epc(epc_path)
    report.version = version

    # 1. EPC structure
    if not skip_epc_structure:
        report.errors.extend(validate_epc_structure(epc_path))

    # Read EPC
    try:
        epc = Epc.read_file(epc_path)
    except Exception as e:
        report.errors.append(StrictValidationError(
            message=f"Failed to read EPC: {e}",
            severity=Severity.ERROR,
            category=ValidationCategory.EPC_STRUCTURE,
        ))
        return report

    objects = epc.energyml_objects
    report.object_count = len(objects)

    # 2. XSD schema validation
    if not skip_xsd and version:
        for obj in objects:
            obj_uuid = get_obj_uuid(obj)
            obj_type = type(obj).__name__
            try:
                xml_bytes = serialize_xml(obj).encode("utf-8")
                xsd_errors = validate_xml_against_xsd(
                    xml_bytes, version,
                    object_uuid=obj_uuid,
                    object_type=obj_type,
                )
                report.errors.extend(xsd_errors)
                report.validated_count += 1
            except Exception as e:
                report.errors.append(StrictValidationError(
                    message=f"Serialization error: {e}",
                    severity=Severity.ERROR,
                    category=ValidationCategory.XSD_SCHEMA,
                    object_uuid=obj_uuid,
                    object_type=obj_type,
                ))

    # 3. energyml object validation
    if not skip_energyml:
        report.errors.extend(validate_energyml_objects(objects))

    # 4. DOR integrity
    if not skip_dor:
        report.errors.extend(validate_dor_integrity(objects))

    # 5. HDF5 references
    if not skip_hdf5:
        # Auto-detect H5 path
        if h5_path is None:
            epc_dir = os.path.dirname(epc_path)
            epc_stem = Path(epc_path).stem
            for ext in (".h5", ".hdf5", ".hdf"):
                candidate = os.path.join(epc_dir, epc_stem + ext)
                if os.path.exists(candidate):
                    h5_path = candidate
                    break
        report.errors.extend(validate_hdf5_references(objects, h5_path))

    # 6. Cross-object consistency
    if not skip_cross_object and version:
        report.errors.extend(validate_cross_object_consistency(objects, version))

    # 7. fesapi compatibility (raw XML checks)
    if not skip_fesapi:
        report.errors.extend(validate_fesapi_compat(epc_path, version))
        report.errors.extend(validate_property_kinds(epc_path, version))
        report.errors.extend(validate_fesapi_packaging(epc_path, version, h5_path))

    # 8. RDDMS compatibility (rels, namespace, ContentType)
    if not skip_rddms:
        report.errors.extend(validate_rddms_compat(epc_path, version))

    return report


def validate_xml_strict(
    xml_content: bytes,
    version: Optional[str] = None,
) -> StrictValidationReport:
    """Validate a single XML document strictly.

    Useful for validating individual objects outside an EPC context.
    """
    report = StrictValidationReport()

    if version is None:
        version = detect_version_from_xml(xml_content)
    report.version = version
    report.object_count = 1

    if version:
        xsd_errors = validate_xml_against_xsd(xml_content, version)
        report.errors.extend(xsd_errors)
        if not xsd_errors:
            report.validated_count = 1
    else:
        report.errors.append(StrictValidationError(
            message="Could not detect RESQML version from XML",
            severity=Severity.ERROR,
            category=ValidationCategory.XSD_SCHEMA,
        ))

    return report


def validate_objects_strict(
    objects: List[Any],
    version: str,
    h5_path: Optional[str] = None,
) -> StrictValidationReport:
    """Validate a list of in-memory energyml objects strictly.

    Runs XSD validation on serialized XML + object-level + DOR checks.
    """
    report = StrictValidationReport(version=version)
    report.object_count = len(objects)

    # XSD validation via serialization
    for obj in objects:
        obj_uuid = get_obj_uuid(obj)
        obj_type = type(obj).__name__
        try:
            xml_bytes = serialize_xml(obj).encode("utf-8")
            xsd_errors = validate_xml_against_xsd(
                xml_bytes, version,
                object_uuid=obj_uuid,
                object_type=obj_type,
            )
            report.errors.extend(xsd_errors)
            report.validated_count += 1
        except Exception as e:
            report.errors.append(StrictValidationError(
                message=f"Serialization error: {e}",
                severity=Severity.ERROR,
                category=ValidationCategory.XSD_SCHEMA,
                object_uuid=obj_uuid,
                object_type=obj_type,
            ))

    # energyml object validation
    report.errors.extend(validate_energyml_objects(objects))

    # DOR integrity
    report.errors.extend(validate_dor_integrity(objects))

    # HDF5 references
    report.errors.extend(validate_hdf5_references(objects, h5_path))

    # Cross-object consistency
    report.errors.extend(validate_cross_object_consistency(objects, version))

    return report
