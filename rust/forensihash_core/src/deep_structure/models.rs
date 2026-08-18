use lopdf::Document;
use serde::Serialize;
use std::collections::BTreeMap;

pub const CONTRACT_VERSION: &str = "1.2";

#[derive(Debug, Clone, Serialize)]
pub struct ParserWarning {
    pub code: String,
    pub message: String,
    pub object_id: Option<String>,
    pub offset: Option<u64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PhysicalInfo {
    pub file_size: u64,
    pub magic_bytes_hex: String,
    pub pdf_version: Option<String>,
    pub header_offset: Option<u64>,
    pub eof_count: usize,
    pub eof_offsets: Vec<u64>,
    pub startxref_offsets: Vec<u64>,
    pub bytes_after_last_eof: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ReferenceEdge {
    pub source: String,
    pub target: String,
    pub relation: String,
    pub path: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct PdfValue {
    pub kind: String,
    pub value: Option<String>,
    pub reference: Option<String>,
    pub items: Vec<PdfValue>,
    pub entries: BTreeMap<String, PdfValue>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ObjectRecord {
    pub id: String,
    pub object_number: u32,
    pub generation_number: u16,
    pub object_type: String,
    pub subtype: Option<String>,
    pub offset: Option<u64>,
    pub raw_length: Option<u64>,
    pub is_stream: bool,
    pub dictionary: BTreeMap<String, PdfValue>,
    pub references: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct StreamRecord {
    pub object_id: String,
    pub filters: Vec<String>,
    pub declared_length: Option<i64>,
    pub raw_length: u64,
    pub decoded_length: Option<u64>,
    pub raw_available: bool,
    pub decoded_available: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct XrefSection {
    pub kind: String,
    pub offset: Option<u64>,
    pub prev: Option<i64>,
    pub xref_stm: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct TrailerInfo {
    pub root: Option<String>,
    pub info: Option<String>,
    pub size: Option<i64>,
    pub id: Option<String>,
    pub encrypt: Option<String>,
    pub prev: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct CatalogInfo {
    pub object_id: Option<String>,
    pub pages: Option<String>,
    pub metadata: Option<String>,
    pub acro_form: Option<String>,
    pub names: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct PageRecord {
    pub page_number: usize,
    pub object_id: String,
    pub parent: Option<String>,
    pub media_box: Option<String>,
    pub crop_box: Option<String>,
    pub rotate: Option<i64>,
    pub resources: Option<String>,
    pub contents: Option<String>,
    pub content_object_ids: Vec<String>,
    pub annots: Option<String>,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct PageTreeInfo {
    pub root_object_id: Option<String>,
    pub declared_count: Option<i64>,
    pub effective_count: usize,
    pub pages: Vec<PageRecord>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ResourceRecord {
    pub page_object_id: String,
    pub category: String,
    pub name: String,
    pub object_id: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ImageRecord {
    pub object_id: String,
    pub width: Option<i64>,
    pub height: Option<i64>,
    pub bits_per_component: Option<i64>,
    pub color_space: Option<String>,
    pub filters: Vec<String>,
    pub raw_size: u64,
    pub decoded_size: Option<u64>,
    pub mask: Option<String>,
    pub soft_mask: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "snake_case")]
#[allow(dead_code)]
pub enum PreviewKind {
    Image,
    Page,
    Thumbnail,
    EmbeddedFile,
    Unknown,
}

#[derive(Debug, Clone, Serialize)]
pub struct PreviewableAsset {
    pub id: String,
    pub kind: PreviewKind,
    pub object_id: String,
    pub media_type: Option<String>,
    pub previewable: bool,
    pub direct_preview: bool,
    pub preview_available: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct VisualWarning {
    pub code: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct PreviewProvenance {
    pub source_object_id: String,
    pub source_filter: Option<String>,
    pub transformation: String,
    pub reconstructed: bool,
    pub mime_type: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct VisualAsset {
    pub id: String,
    pub source_object_id: String,
    pub kind: String,
    pub width: Option<u32>,
    pub height: Option<u32>,
    pub bits_per_component: Option<u8>,
    pub color_space: Option<String>,
    pub filters: Vec<String>,
    pub mime_type: Option<String>,
    pub source_encoding: Option<String>,
    pub preview_encoding: Option<String>,
    pub status: String,
    pub preview_available: bool,
    pub reconstructed: bool,
    pub image_mask: bool,
    pub has_mask: bool,
    pub mask_object_id: Option<String>,
    pub soft_mask_object_id: Option<String>,
    pub byte_length: Option<u64>,
    pub warnings: Vec<VisualWarning>,
    pub provenance: PreviewProvenance,
}

#[derive(Debug, Clone, Serialize)]
pub struct VisualResourceUsage {
    pub page_object_id: String,
    pub container_object_id: String,
    pub resource_name: String,
    pub object_id: String,
    pub kind: String,
    pub path: String,
    pub depth: usize,
    pub declared: bool,
    pub invoked_by_do: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct FormRecord {
    pub object_id: String,
    pub bbox: Option<PdfValue>,
    pub matrix: Option<PdfValue>,
    pub resources: Option<PdfValue>,
    pub group: Option<PdfValue>,
    pub content_available: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct EmbeddedFileRecord {
    pub id: String,
    pub filename: Option<String>,
    pub unicode_filename: Option<String>,
    pub mime_type: Option<String>,
    pub size: Option<i64>,
    pub object_id: String,
    pub stream_available: bool,
    pub warnings: Vec<VisualWarning>,
}

#[derive(Debug, Clone, Serialize)]
pub struct MetadataRecord {
    pub object_id: String,
    pub subtype: Option<String>,
    pub raw_available: bool,
    pub decoded_available: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct AnnotationRecord {
    pub object_id: String,
    pub page_object_ids: Vec<String>,
    pub subtype: Option<String>,
    pub properties: BTreeMap<String, PdfValue>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SignatureRecord {
    pub object_id: String,
    pub properties: BTreeMap<String, PdfValue>,
}

#[derive(Debug, Clone, Serialize)]
pub struct Occurrence {
    pub name: String,
    pub count: usize,
}

#[derive(Debug, Clone, Serialize, Default)]
pub struct StructureSummary {
    pub object_count: usize,
    pub page_count: usize,
    pub stream_count: usize,
    pub image_count: usize,
    pub font_count: usize,
    pub annotation_count: usize,
    pub embedded_file_count: usize,
    pub signature_dictionary_count: usize,
    pub revision_count: usize,
    pub unique_image_objects: usize,
    pub image_references: usize,
    pub unique_font_objects: usize,
    pub font_references: usize,
    pub pages_with_annotations: usize,
    pub unique_annotation_objects: usize,
    pub annotation_references: usize,
    pub visual_resource_references: usize,
    pub invoked_xobject_usages: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct StructureReport {
    pub format: String,
    pub contract_version: String,
    pub parser: String,
    pub physical: PhysicalInfo,
    pub summary: StructureSummary,
    pub objects: Vec<ObjectRecord>,
    pub references: Vec<ReferenceEdge>,
    pub xref: Vec<XrefSection>,
    pub trailer: TrailerInfo,
    pub catalog: CatalogInfo,
    pub page_tree: PageTreeInfo,
    pub resources: Vec<ResourceRecord>,
    pub streams: Vec<StreamRecord>,
    pub images: Vec<ImageRecord>,
    pub embedded_items: Vec<String>,
    pub previewable_assets: Vec<PreviewableAsset>,
    pub visual_resources: Vec<VisualResourceUsage>,
    pub forms: Vec<FormRecord>,
    pub embedded_files: Vec<EmbeddedFileRecord>,
    pub metadata_streams: Vec<MetadataRecord>,
    pub annotations: Vec<AnnotationRecord>,
    pub signatures: Vec<SignatureRecord>,
    pub occurrences: Vec<Occurrence>,
    pub parser_warnings: Vec<ParserWarning>,
}

pub struct ParsedStructure {
    pub report: StructureReport,
    pub document: Document,
    pub source_data: Vec<u8>,
}
