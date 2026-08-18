from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ParserWarning:
    code: str
    message: str
    object_id: str | None = None
    offset: int | None = None


@dataclass(frozen=True, slots=True)
class PhysicalInfo:
    file_size: int
    magic_bytes_hex: str
    pdf_version: str | None
    header_offset: int | None
    eof_count: int
    eof_offsets: tuple[int, ...]
    startxref_offsets: tuple[int, ...]
    bytes_after_last_eof: int


@dataclass(frozen=True, slots=True)
class StructureSummary:
    object_count: int
    page_count: int
    stream_count: int
    image_count: int
    font_count: int
    annotation_count: int
    embedded_file_count: int
    signature_dictionary_count: int
    revision_count: int
    unique_image_objects: int
    image_references: int
    unique_font_objects: int
    font_references: int
    pages_with_annotations: int
    unique_annotation_objects: int
    annotation_references: int
    visual_resource_references: int
    invoked_xobject_usages: int


@dataclass(frozen=True, slots=True)
class ObjectRecord:
    id: str
    object_number: int
    generation_number: int
    object_type: str
    subtype: str | None
    offset: int | None
    raw_length: int | None
    is_stream: bool
    dictionary: dict[str, Any]
    references: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StructureReport:
    format: str
    contract_version: str
    parser: str
    physical: PhysicalInfo
    summary: StructureSummary
    objects: tuple[ObjectRecord, ...]
    references: tuple[dict[str, Any], ...]
    xref: tuple[dict[str, Any], ...]
    trailer: dict[str, Any]
    catalog: dict[str, Any]
    page_tree: dict[str, Any]
    resources: tuple[dict[str, Any], ...]
    streams: tuple[dict[str, Any], ...]
    images: tuple[dict[str, Any], ...]
    embedded_items: tuple[str, ...]
    previewable_assets: tuple[dict[str, Any], ...]
    visual_resources: tuple[dict[str, Any], ...]
    forms: tuple[dict[str, Any], ...]
    embedded_files: tuple[dict[str, Any], ...]
    metadata_streams: tuple[dict[str, Any], ...]
    annotations: tuple[dict[str, Any], ...]
    signatures: tuple[dict[str, Any], ...]
    occurrences: tuple[dict[str, Any], ...]
    parser_warnings: tuple[ParserWarning, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> StructureReport:
        physical = dict(value["physical"])
        physical["eof_offsets"] = tuple(physical["eof_offsets"])
        physical["startxref_offsets"] = tuple(physical["startxref_offsets"])
        objects = []
        for item in value["objects"]:
            normalized = dict(item)
            normalized["references"] = tuple(normalized["references"])
            objects.append(ObjectRecord(**normalized))
        return cls(
            format=value["format"], contract_version=value["contract_version"], parser=value["parser"],
            physical=PhysicalInfo(**physical), summary=StructureSummary(**value["summary"]), objects=tuple(objects),
            references=tuple(value["references"]), xref=tuple(value["xref"]), trailer=value["trailer"],
            catalog=value["catalog"], page_tree=value["page_tree"], resources=tuple(value["resources"]),
            streams=tuple(value["streams"]), images=tuple(value["images"]),
            embedded_items=tuple(value["embedded_items"]), previewable_assets=tuple(value["previewable_assets"]),
            visual_resources=tuple(value["visual_resources"]), forms=tuple(value["forms"]),
            embedded_files=tuple(value["embedded_files"]), metadata_streams=tuple(value["metadata_streams"]),
            annotations=tuple(value["annotations"]), signatures=tuple(value["signatures"]),
            occurrences=tuple(value["occurrences"]),
            parser_warnings=tuple(ParserWarning(**item) for item in value["parser_warnings"]),
        )
