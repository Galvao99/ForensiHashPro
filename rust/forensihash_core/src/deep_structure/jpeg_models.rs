use serde::Serialize;
use serde_json::Value;

pub const JPEG_CONTRACT_VERSION: &str = "1.0";

#[derive(Debug, Clone, Serialize)]
pub struct JpegWarning {
    pub code: String,
    pub message: String,
    pub offset: Option<u64>,
}

#[derive(Debug, Clone, Serialize)]
pub struct JpegPhysicalInfo {
    pub file_size: u64,
    pub soi_offset: u64,
    pub eoi_offset: Option<u64>,
    pub trailing_bytes_offset: Option<u64>,
    pub trailing_bytes_length: u64,
    pub segment_count: usize,
    pub scan_count: usize,
}

#[derive(Debug, Clone, Serialize)]
pub struct JpegSegment {
    pub index: usize,
    pub marker: u8,
    pub marker_hex: String,
    pub marker_name: String,
    pub offset: u64,
    pub marker_offset: u64,
    pub payload_offset: u64,
    pub declared_length: Option<u64>,
    pub payload_length: u64,
    pub end_offset: u64,
    pub category: String,
    pub summary: String,
    pub metadata: Option<Value>,
}

#[derive(Debug, Clone, Serialize)]
pub struct RestartMarker {
    pub marker: u8,
    pub marker_name: String,
    pub offset: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct JpegScan {
    pub index: usize,
    pub sos_segment_index: usize,
    pub data_offset: u64,
    pub data_length: u64,
    pub restart_markers: Vec<RestartMarker>,
    pub end_offset: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct FrameComponent {
    pub component_id: u8,
    pub horizontal_sampling_factor: u8,
    pub vertical_sampling_factor: u8,
    pub quantization_table_selector: u8,
}

#[derive(Debug, Clone, Serialize)]
pub struct JpegFrame {
    pub segment_index: usize,
    pub marker: u8,
    pub frame_type: String,
    pub precision: u8,
    pub width: u16,
    pub height: u16,
    pub number_of_components: u8,
    pub components: Vec<FrameComponent>,
}

#[derive(Debug, Clone, Serialize)]
pub struct QuantizationTable {
    pub segment_index: usize,
    pub table_id: u8,
    pub precision_bits: u8,
    pub values: Vec<u16>,
    pub offset: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct HuffmanTable {
    pub segment_index: usize,
    pub class: String,
    pub table_id: u8,
    pub counts: Vec<u8>,
    pub symbols: Vec<u8>,
    pub symbol_count: usize,
    pub offset: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExifEntry {
    pub tag_id: u16,
    pub tag_name: Option<String>,
    pub value_type: u16,
    pub count: u32,
    pub value_or_offset: u32,
    pub decoded_value: Value,
    pub raw_value_location: u64,
    pub path: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExifIfd {
    pub id: String,
    pub kind: String,
    pub offset_relative_to_tiff: u32,
    pub absolute_offset: u64,
    pub entries: Vec<ExifEntry>,
    pub next_ifd_offset: u32,
}

#[derive(Debug, Clone, Serialize)]
pub struct ExifInfo {
    pub segment_index: usize,
    pub byte_order: String,
    pub tiff_offset: u64,
    pub ifds: Vec<ExifIfd>,
}

#[derive(Debug, Clone, Serialize)]
pub struct XmpPacket {
    pub id: String,
    pub segment_index: usize,
    pub offset: u64,
    pub length: u64,
    pub kind: String,
    pub utf8_valid: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct IccChunk {
    pub sequence_number: u8,
    pub total_chunks: u8,
    pub segment_index: usize,
    pub offset: u64,
    pub length: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct JpegVisualAsset {
    pub id: String,
    pub kind: String,
    pub media_type: Option<String>,
    pub offset: u64,
    pub length: u64,
    pub preview_available: bool,
    pub provenance: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct JpegComment {
    pub segment_index: usize,
    pub offset: u64,
    pub length: u64,
    pub text: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct JpegCapabilities {
    pub segment_raw: bool,
    pub scan_raw: bool,
    pub exif_navigation: bool,
    pub xmp_text: bool,
    pub icc_reconstruction: bool,
    pub lazy_visual_assets: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct JpegStructureReport {
    pub format: String,
    pub structure_version: String,
    pub parser: String,
    pub physical_info: JpegPhysicalInfo,
    pub segments: Vec<JpegSegment>,
    pub scans: Vec<JpegScan>,
    pub frames: Vec<JpegFrame>,
    pub quantization_tables: Vec<QuantizationTable>,
    pub huffman_tables: Vec<HuffmanTable>,
    pub exif: Vec<ExifInfo>,
    pub xmp: Vec<XmpPacket>,
    pub icc: Vec<IccChunk>,
    pub visual_assets: Vec<JpegVisualAsset>,
    pub comments: Vec<JpegComment>,
    pub warnings: Vec<JpegWarning>,
    pub capabilities: JpegCapabilities,
}

pub struct ParsedJpeg {
    pub report: JpegStructureReport,
    pub source_data: Vec<u8>,
}
