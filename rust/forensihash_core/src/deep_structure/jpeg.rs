use super::jpeg_models::*;
use super::StructureError;
use serde_json::{json, Value};
use std::collections::HashSet;

const XMP_HEADER: &[u8] = b"http://ns.adobe.com/xap/1.0/\0";
const EXT_XMP_HEADER: &[u8] = b"http://ns.adobe.com/xmp/extension/\0";
const ICC_HEADER: &[u8] = b"ICC_PROFILE\0";

#[derive(Debug, Clone, Copy)]
pub struct JpegLimits {
    pub max_segments: usize,
    pub max_app_payload_bytes: usize,
    pub max_exif_ifds: usize,
    pub max_exif_entries: usize,
    pub max_exif_depth: usize,
    pub max_icc_bytes: usize,
    pub max_xmp_bytes: usize,
    pub max_thumbnail_bytes: usize,
    pub max_scans: usize,
}

impl Default for JpegLimits {
    fn default() -> Self {
        Self {
            max_segments: 100_000,
            max_app_payload_bytes: 64 << 20,
            max_exif_ifds: 128,
            max_exif_entries: 100_000,
            max_exif_depth: 16,
            max_icc_bytes: 128 << 20,
            max_xmp_bytes: 64 << 20,
            max_thumbnail_bytes: 64 << 20,
            max_scans: 4096,
        }
    }
}

pub struct JpegStructureParser;

impl JpegStructureParser {
    pub fn supports(&self, data: &[u8]) -> bool {
        data.len() >= 4 && data.starts_with(&[0xff, 0xd8]) && data[2] == 0xff
    }

    pub fn parse(&self, data: &[u8], limits: JpegLimits) -> Result<ParsedJpeg, StructureError> {
        if !self.supports(data) {
            return Err(StructureError("JPEG SOI/marker structure not found".into()));
        }
        let mut state = State::new(data, limits);
        state.walk()?;
        Ok(ParsedJpeg {
            report: state.report(),
            source_data: data.to_vec(),
        })
    }
}

struct State<'a> {
    data: &'a [u8],
    limits: JpegLimits,
    pos: usize,
    segments: Vec<JpegSegment>,
    scans: Vec<JpegScan>,
    frames: Vec<JpegFrame>,
    dqt: Vec<QuantizationTable>,
    dht: Vec<HuffmanTable>,
    exif: Vec<ExifInfo>,
    xmp: Vec<XmpPacket>,
    icc: Vec<IccChunk>,
    assets: Vec<JpegVisualAsset>,
    comments: Vec<JpegComment>,
    warnings: Vec<JpegWarning>,
    eoi: Option<usize>,
}

impl<'a> State<'a> {
    fn new(data: &'a [u8], limits: JpegLimits) -> Self {
        Self {
            data,
            limits,
            pos: 0,
            segments: vec![],
            scans: vec![],
            frames: vec![],
            dqt: vec![],
            dht: vec![],
            exif: vec![],
            xmp: vec![],
            icc: vec![],
            assets: vec![JpegVisualAsset {
                id: "jpeg_main".into(),
                kind: "main_image".into(),
                media_type: Some("image/jpeg".into()),
                offset: 0,
                length: data.len() as u64,
                preview_available: true,
                provenance: "original_file_bytes".into(),
            }],
            comments: vec![],
            warnings: vec![],
            eoi: None,
        }
    }

    fn warn(&mut self, code: &str, message: impl Into<String>, offset: Option<usize>) {
        self.warnings.push(JpegWarning {
            code: code.into(),
            message: message.into(),
            offset: offset.map(|v| v as u64),
        });
    }

    fn walk(&mut self) -> Result<(), StructureError> {
        self.push_standalone(0xd8, 0);
        self.pos = 2;
        while self.pos < self.data.len() && self.eoi.is_none() {
            if self.segments.len() >= self.limits.max_segments {
                return Err(StructureError(
                    "limit_exceeded: JPEG segment count exceeds configured limit".into(),
                ));
            }
            if self.data[self.pos] != 0xff {
                self.warn(
                    "malformed_scan",
                    "non-marker byte outside entropy-coded scan",
                    Some(self.pos),
                );
                self.pos += 1;
                continue;
            }
            let marker_offset = self.pos;
            while self.pos < self.data.len() && self.data[self.pos] == 0xff {
                self.pos += 1;
            }
            if self.pos >= self.data.len() {
                self.warn(
                    "truncated_segment",
                    "marker code is missing",
                    Some(marker_offset),
                );
                break;
            }
            let marker = self.data[self.pos];
            self.pos += 1;
            if marker == 0x00 {
                self.warn(
                    "unknown_marker",
                    "stuffed byte outside scan data",
                    Some(marker_offset),
                );
                continue;
            }
            if standalone(marker) {
                self.push_standalone(marker, marker_offset);
                if marker == 0xd9 {
                    self.eoi = Some(marker_offset);
                }
                continue;
            }
            if self.pos + 2 > self.data.len() {
                self.warn(
                    "truncated_segment",
                    "segment length is truncated",
                    Some(marker_offset),
                );
                break;
            }
            let declared = be16(&self.data[self.pos..]) as usize;
            if declared < 2 {
                self.warn(
                    "invalid_segment_length",
                    format!("marker FF{marker:02X} declares length {declared}"),
                    Some(marker_offset),
                );
                break;
            }
            let payload_offset = self.pos + 2;
            let wanted_end = self
                .pos
                .checked_add(declared)
                .ok_or_else(|| StructureError("malformed: JPEG segment offset overflow".into()))?;
            let end = wanted_end.min(self.data.len());
            if wanted_end > self.data.len() {
                self.warn(
                    "truncated_segment",
                    format!("marker FF{marker:02X} extends beyond EOF"),
                    Some(marker_offset),
                );
            }
            let payload = &self.data[payload_offset..end];
            if (0xe0..=0xef).contains(&marker) && payload.len() > self.limits.max_app_payload_bytes
            {
                return Err(StructureError(
                    "limit_exceeded: JPEG APP payload exceeds configured limit".into(),
                ));
            }
            let index = self.segments.len();
            let metadata = self.interpret(index, marker, payload_offset, payload);
            self.segments.push(JpegSegment {
                index,
                marker,
                marker_hex: format!("FF{marker:02X}"),
                marker_name: marker_name(marker),
                offset: marker_offset as u64,
                marker_offset: marker_offset as u64,
                payload_offset: payload_offset as u64,
                declared_length: Some(declared as u64),
                payload_length: payload.len() as u64,
                end_offset: end as u64,
                category: category(marker).into(),
                summary: summary(marker, payload),
                metadata,
            });
            self.pos = end;
            if marker == 0xda {
                self.scan(index);
            }
            if end < wanted_end {
                break;
            }
        }
        if self.eoi.is_none() {
            self.warn("missing_eoi", "JPEG EOI marker was not found", None);
        }
        if let Some(eoi) = self.eoi {
            let trailing = eoi + 2;
            if trailing < self.data.len() {
                self.warn(
                    "trailing_bytes",
                    format!("{} bytes after EOI", self.data.len() - trailing),
                    Some(trailing),
                );
                let mut at = trailing;
                while at + 1 < self.data.len() {
                    if self.data[at..].starts_with(&[0xff, 0xd8]) {
                        self.warn(
                            "trailing_jpeg_signature",
                            "JPEG SOI signature found after EOI",
                            Some(at),
                        );
                        break;
                    }
                    at += 1;
                }
            }
        }
        self.validate_icc();
        Ok(())
    }

    fn validate_icc(&mut self) {
        if self.icc.is_empty() {
            return;
        }
        let total = self.icc[0].total_chunks;
        let size: usize = self.icc.iter().map(|chunk| chunk.length as usize).sum();
        if size > self.limits.max_icc_bytes {
            self.warn(
                "limit_exceeded",
                "ICC profile exceeds configured reconstruction limit",
                self.icc.first().map(|c| c.offset as usize),
            );
        }
        for sequence in 1..=total {
            match self
                .icc
                .iter()
                .filter(|chunk| chunk.sequence_number == sequence)
                .count()
            {
                0 => self.warn(
                    "icc_chunk_missing",
                    format!("ICC chunk {sequence} of {total} is missing"),
                    None,
                ),
                count if count > 1 => self.warn(
                    "icc_duplicate_chunk",
                    format!("ICC chunk {sequence} occurs {count} times"),
                    None,
                ),
                _ => {}
            }
        }
    }

    fn push_standalone(&mut self, marker: u8, at: usize) {
        let index = self.segments.len();
        self.segments.push(JpegSegment {
            index,
            marker,
            marker_hex: format!("FF{marker:02X}"),
            marker_name: marker_name(marker),
            offset: at as u64,
            marker_offset: at as u64,
            payload_offset: (at + 2) as u64,
            declared_length: None,
            payload_length: 0,
            end_offset: (at + 2).min(self.data.len()) as u64,
            category: category(marker).into(),
            summary: marker_name(marker),
            metadata: None,
        });
    }

    fn scan(&mut self, sos_index: usize) {
        if self.scans.len() >= self.limits.max_scans {
            self.warn(
                "limit_exceeded",
                "JPEG scan count exceeds configured limit",
                Some(self.pos),
            );
            return;
        }
        let start = self.pos;
        let mut cursor = start;
        let mut restarts = vec![];
        while cursor + 1 < self.data.len() {
            if self.data[cursor] != 0xff {
                cursor += 1;
                continue;
            }
            let ff = cursor;
            while cursor < self.data.len() && self.data[cursor] == 0xff {
                cursor += 1;
            }
            if cursor >= self.data.len() {
                break;
            }
            let code = self.data[cursor];
            if code == 0x00 {
                cursor += 1;
                continue;
            }
            if (0xd0..=0xd7).contains(&code) {
                restarts.push(RestartMarker {
                    marker: code,
                    marker_name: marker_name(code),
                    offset: ff as u64,
                });
                cursor += 1;
                continue;
            }
            self.pos = ff;
            break;
        }
        if cursor + 1 >= self.data.len() {
            self.pos = self.data.len();
        }
        self.scans.push(JpegScan {
            index: self.scans.len(),
            sos_segment_index: sos_index,
            data_offset: start as u64,
            data_length: self.pos.saturating_sub(start) as u64,
            restart_markers: restarts,
            end_offset: self.pos as u64,
        });
    }

    fn interpret(
        &mut self,
        index: usize,
        marker: u8,
        offset: usize,
        payload: &[u8],
    ) -> Option<Value> {
        if is_sof(marker) {
            self.parse_sof(index, marker, offset, payload)
        } else if marker == 0xdb {
            self.parse_dqt(index, offset, payload)
        } else if marker == 0xc4 {
            self.parse_dht(index, offset, payload)
        } else if marker == 0xe0 {
            self.parse_app0(index, offset, payload)
        } else if marker == 0xe1 {
            self.parse_app1(index, offset, payload)
        } else if marker == 0xe2 {
            self.parse_app2(index, offset, payload)
        } else if marker == 0xed {
            self.parse_app13(payload)
        } else if marker == 0xee {
            self.parse_app14(payload)
        } else if marker == 0xfe {
            self.parse_comment(index, offset, payload)
        } else {
            None
        }
    }

    fn parse_sof(&mut self, index: usize, marker: u8, _offset: usize, p: &[u8]) -> Option<Value> {
        if p.len() < 6 {
            self.warn("truncated_segment", "SOF payload is truncated", None);
            return None;
        }
        let count = p[5] as usize;
        if p.len() < 6 + count * 3 {
            self.warn("truncated_segment", "SOF components are truncated", None);
            return None;
        }
        let components = (0..count)
            .map(|n| {
                let at = 6 + n * 3;
                FrameComponent {
                    component_id: p[at],
                    horizontal_sampling_factor: p[at + 1] >> 4,
                    vertical_sampling_factor: p[at + 1] & 15,
                    quantization_table_selector: p[at + 2],
                }
            })
            .collect();
        let frame = JpegFrame {
            segment_index: index,
            marker,
            frame_type: frame_type(marker),
            precision: p[0],
            height: be16(&p[1..]),
            width: be16(&p[3..]),
            number_of_components: p[5],
            components,
        };
        let value = json!({"frame_type":frame.frame_type,"precision":frame.precision,"width":frame.width,"height":frame.height,"number_of_components":frame.number_of_components});
        self.frames.push(frame);
        Some(value)
    }

    fn parse_dqt(&mut self, index: usize, offset: usize, p: &[u8]) -> Option<Value> {
        let mut at = 0;
        let mut ids = vec![];
        while at < p.len() {
            let info = p[at];
            at += 1;
            let bytes = if info >> 4 == 0 { 1 } else { 2 };
            let need = 64 * bytes;
            if at + need > p.len() {
                self.warn(
                    "truncated_segment",
                    "DQT table is truncated",
                    Some(offset + at),
                );
                break;
            }
            let values = (0..64)
                .map(|n| {
                    if bytes == 1 {
                        p[at + n] as u16
                    } else {
                        be16(&p[at + n * 2..])
                    }
                })
                .collect();
            self.dqt.push(QuantizationTable {
                segment_index: index,
                table_id: info & 15,
                precision_bits: (bytes * 8) as u8,
                values,
                offset: (offset + at - 1) as u64,
            });
            ids.push(info & 15);
            at += need;
        }
        Some(json!({"table_ids":ids}))
    }

    fn parse_dht(&mut self, index: usize, offset: usize, p: &[u8]) -> Option<Value> {
        let mut at = 0;
        let mut ids = vec![];
        while at < p.len() {
            if at + 17 > p.len() {
                self.warn(
                    "truncated_segment",
                    "DHT header is truncated",
                    Some(offset + at),
                );
                break;
            }
            let info = p[at];
            let counts = p[at + 1..at + 17].to_vec();
            let total: usize = counts.iter().map(|v| *v as usize).sum();
            if at + 17 + total > p.len() {
                self.warn(
                    "truncated_segment",
                    "DHT symbols are truncated",
                    Some(offset + at),
                );
                break;
            }
            self.dht.push(HuffmanTable {
                segment_index: index,
                class: if info >> 4 == 0 {
                    "dc".into()
                } else {
                    "ac".into()
                },
                table_id: info & 15,
                counts,
                symbols: p[at + 17..at + 17 + total].to_vec(),
                symbol_count: total,
                offset: (offset + at) as u64,
            });
            ids.push(info & 15);
            at += 17 + total;
        }
        Some(json!({"table_ids":ids}))
    }

    fn parse_app0(&mut self, index: usize, offset: usize, p: &[u8]) -> Option<Value> {
        if p.starts_with(b"JFIF\0") && p.len() >= 14 {
            let tw = p[12] as usize;
            let th = p[13] as usize;
            let len = tw
                .saturating_mul(th)
                .saturating_mul(3)
                .min(p.len().saturating_sub(14));
            if len > 0 {
                self.assets.push(JpegVisualAsset {
                    id: format!("jfif_thumbnail_{index}"),
                    kind: "jfif_rgb_thumbnail".into(),
                    media_type: None,
                    offset: (offset + 14) as u64,
                    length: len as u64,
                    preview_available: false,
                    provenance: format!("segment:{index}:APP0/JFIF"),
                });
            }
            Some(
                json!({"identifier":"JFIF","version_major":p[5],"version_minor":p[6],"density_units":p[7],"x_density":be16(&p[8..]),"y_density":be16(&p[10..]),"thumbnail_width":p[12],"thumbnail_height":p[13],"thumbnail_offset":offset+14,"thumbnail_length":len}),
            )
        } else if p.starts_with(b"JFXX\0") && p.len() >= 6 {
            let ext = p[5];
            let len = p.len() - 6;
            let jpeg = ext == 0x10 && p[6..].starts_with(&[0xff, 0xd8]);
            self.assets.push(JpegVisualAsset {
                id: format!("jfxx_thumbnail_{index}"),
                kind: "jfxx_thumbnail".into(),
                media_type: if jpeg {
                    Some("image/jpeg".into())
                } else {
                    None
                },
                offset: (offset + 6) as u64,
                length: len as u64,
                preview_available: jpeg,
                provenance: format!("segment:{index}:APP0/JFXX"),
            });
            Some(
                json!({"identifier":"JFXX","extension_code":ext,"thumbnail_offset":offset+6,"thumbnail_length":len}),
            )
        } else {
            None
        }
    }

    fn parse_app1(&mut self, index: usize, offset: usize, p: &[u8]) -> Option<Value> {
        if p.starts_with(b"Exif\0\0") {
            match parse_exif(
                p,
                offset,
                index,
                self.limits,
                &mut self.warnings,
                &mut self.assets,
            ) {
                Some(info) => {
                    let n = info.ifds.len();
                    self.exif.push(info);
                    Some(json!({"kind":"exif","ifd_count":n}))
                }
                None => None,
            }
        } else if p.starts_with(XMP_HEADER) {
            let body = &p[XMP_HEADER.len()..];
            if body.len() > self.limits.max_xmp_bytes {
                self.warn(
                    "limit_exceeded",
                    "XMP packet exceeds configured limit",
                    Some(offset),
                );
                return Some(json!({"kind":"xmp","available":false}));
            }
            let id = format!("xmp_{index}");
            self.xmp.push(XmpPacket {
                id: id.clone(),
                segment_index: index,
                offset: (offset + XMP_HEADER.len()) as u64,
                length: body.len() as u64,
                kind: "standard".into(),
                utf8_valid: std::str::from_utf8(body).is_ok(),
            });
            Some(
                json!({"kind":"xmp","id":id,"namespace":String::from_utf8_lossy(XMP_HEADER).trim_end_matches('\0')}),
            )
        } else if p.starts_with(EXT_XMP_HEADER) {
            self.warn(
                "extended_xmp_partial",
                "Extended XMP chunk inventoried; reconstruction is deferred",
                Some(offset),
            );
            let id = format!("extended_xmp_{index}");
            self.xmp.push(XmpPacket {
                id: id.clone(),
                segment_index: index,
                offset: (offset + EXT_XMP_HEADER.len()) as u64,
                length: (p.len() - EXT_XMP_HEADER.len()) as u64,
                kind: "extended_partial".into(),
                utf8_valid: false,
            });
            Some(json!({"kind":"extended_xmp","id":id,"status":"partial"}))
        } else {
            None
        }
    }

    fn parse_app2(&mut self, index: usize, offset: usize, p: &[u8]) -> Option<Value> {
        if p.starts_with(ICC_HEADER) && p.len() >= 14 {
            let c = IccChunk {
                sequence_number: p[12],
                total_chunks: p[13],
                segment_index: index,
                offset: (offset + 14) as u64,
                length: (p.len() - 14) as u64,
            };
            let value = json!({"kind":"icc_profile","sequence_number":c.sequence_number,"total_chunks":c.total_chunks});
            self.icc.push(c);
            Some(value)
        } else {
            None
        }
    }
    fn parse_app13(&self, p: &[u8]) -> Option<Value> {
        p.starts_with(b"Photoshop 3.0\0")
            .then(|| json!({"identifier":"Photoshop 3.0","irb_inventory":"deferred"}))
    }
    fn parse_app14(&self, p: &[u8]) -> Option<Value> {
        (p.starts_with(b"Adobe")&&p.len()>=12).then(||json!({"identifier":"Adobe","version":be16(&p[5..]),"flags0":be16(&p[7..]),"flags1":be16(&p[9..]),"color_transform":p[11]}))
    }
    fn parse_comment(&mut self, index: usize, offset: usize, p: &[u8]) -> Option<Value> {
        let text = std::str::from_utf8(p).ok().map(str::to_owned).or_else(|| {
            p.iter()
                .all(|b| b.is_ascii())
                .then(|| String::from_utf8_lossy(p).into_owned())
        });
        self.comments.push(JpegComment {
            segment_index: index,
            offset: offset as u64,
            length: p.len() as u64,
            text: text.clone(),
        });
        Some(json!({"text":text,"raw_available":true}))
    }

    fn report(self) -> JpegStructureReport {
        let trailing_offset = self.eoi.map(|v| v + 2).filter(|v| *v < self.data.len());
        JpegStructureReport {
            format: "jpeg".into(),
            structure_version: JPEG_CONTRACT_VERSION.into(),
            parser: "forensihash-jpeg-structural-v1".into(),
            physical_info: JpegPhysicalInfo {
                file_size: self.data.len() as u64,
                soi_offset: 0,
                eoi_offset: self.eoi.map(|v| v as u64),
                trailing_bytes_offset: trailing_offset.map(|v| v as u64),
                trailing_bytes_length: trailing_offset.map_or(0, |v| (self.data.len() - v) as u64),
                segment_count: self.segments.len(),
                scan_count: self.scans.len(),
            },
            segments: self.segments,
            scans: self.scans,
            frames: self.frames,
            quantization_tables: self.dqt,
            huffman_tables: self.dht,
            exif: self.exif,
            xmp: self.xmp,
            icc: self.icc,
            visual_assets: self.assets,
            comments: self.comments,
            warnings: self.warnings,
            capabilities: JpegCapabilities {
                segment_raw: true,
                scan_raw: true,
                exif_navigation: true,
                xmp_text: true,
                icc_reconstruction: true,
                lazy_visual_assets: true,
            },
        }
    }
}

fn parse_exif(
    p: &[u8],
    base: usize,
    segment_index: usize,
    limits: JpegLimits,
    warnings: &mut Vec<JpegWarning>,
    assets: &mut Vec<JpegVisualAsset>,
) -> Option<ExifInfo> {
    let t = &p[6..];
    if t.len() < 8 {
        warnings.push(w(
            "invalid_exif_tiff_header",
            "EXIF TIFF header is truncated",
            base + 6,
        ));
        return None;
    }
    let le = match &t[..2] {
        b"II" => true,
        b"MM" => false,
        _ => {
            warnings.push(w(
                "invalid_exif_tiff_header",
                "EXIF byte order is invalid",
                base + 6,
            ));
            return None;
        }
    };
    if u16at(t, 2, le) != Some(42) {
        warnings.push(w(
            "invalid_exif_tiff_header",
            "EXIF TIFF magic is not 42",
            base + 8,
        ));
        return None;
    }
    let first = u32at(t, 4, le)?;
    let mut ifds = vec![];
    let mut queue = vec![(first, "IFD0".to_string(), 0usize)];
    let mut seen = HashSet::new();
    let mut entries_total: usize = 0;
    let mut thumbnail: (Option<u32>, Option<u32>) = (None, None);
    while let Some((rel, kind, depth)) = queue.pop() {
        if rel == 0 {
            continue;
        }
        if depth > limits.max_exif_depth || ifds.len() >= limits.max_exif_ifds {
            warnings.push(w(
                "limit_exceeded",
                "EXIF IFD limit exceeded",
                base + 6 + rel as usize,
            ));
            break;
        }
        if !seen.insert(rel) {
            warnings.push(w(
                "ifd_cycle",
                "EXIF IFD cycle detected",
                base + 6 + rel as usize,
            ));
            continue;
        }
        let at = rel as usize;
        if at + 2 > t.len() {
            warnings.push(w(
                "ifd_offset_out_of_bounds",
                "EXIF IFD offset is outside TIFF payload",
                base + 6 + at,
            ));
            continue;
        }
        let count = u16at(t, at, le)? as usize;
        if entries_total.saturating_add(count) > limits.max_exif_entries {
            warnings.push(w(
                "limit_exceeded",
                "EXIF entry limit exceeded",
                base + 6 + at,
            ));
            break;
        }
        let mut entries = vec![];
        for n in 0..count {
            let e = at + 2 + n * 12;
            if e + 12 > t.len() {
                warnings.push(w(
                    "ifd_offset_out_of_bounds",
                    "EXIF entry extends outside TIFF payload",
                    base + 6 + e,
                ));
                break;
            }
            let tag = u16at(t, e, le)?;
            let typ = u16at(t, e + 2, le)?;
            let cnt = u32at(t, e + 4, le)?;
            let vo = u32at(t, e + 8, le)?;
            let unit = type_size(typ);
            let size = (cnt as usize).checked_mul(unit).unwrap_or(usize::MAX);
            let raw_rel = if size <= 4 { e + 8 } else { vo as usize };
            let decoded = decode_tiff(t, raw_rel, typ, cnt, le);
            let path = format!("{kind}/0x{tag:04X}");
            entries.push(ExifEntry {
                tag_id: tag,
                tag_name: tag_name(tag).map(str::to_owned),
                value_type: typ,
                count: cnt,
                value_or_offset: vo,
                decoded_value: decoded,
                raw_value_location: (base + 6 + raw_rel) as u64,
                path,
            });
            match tag {
                0x8769 => queue.push((vo, "ExifIFD".into(), depth + 1)),
                0x8825 => queue.push((vo, "GPSIFD".into(), depth + 1)),
                0xA005 => queue.push((vo, "InteroperabilityIFD".into(), depth + 1)),
                0x0201 if kind == "IFD1" => thumbnail.0 = Some(vo),
                0x0202 if kind == "IFD1" => thumbnail.1 = Some(vo),
                _ => {}
            }
        }
        entries_total += entries.len();
        let next_at = at + 2 + count * 12;
        let next = u32at(t, next_at, le).unwrap_or(0);
        if kind == "IFD0" && next != 0 {
            queue.push((next, "IFD1".into(), depth));
        }
        ifds.push(ExifIfd {
            id: kind.clone(),
            kind,
            offset_relative_to_tiff: rel,
            absolute_offset: (base + 6 + at) as u64,
            entries,
            next_ifd_offset: next,
        });
    }
    if let (Some(off), Some(len)) = thumbnail {
        let start = base + 6 + off as usize;
        if len as usize <= limits.max_thumbnail_bytes
            && start
                .checked_add(len as usize)
                .is_some_and(|end| end <= base + p.len())
        {
            let valid = p
                .get(6 + off as usize..)
                .is_some_and(|v| v.starts_with(&[0xff, 0xd8]));
            assets.push(JpegVisualAsset {
                id: format!("exif_thumbnail_{segment_index}"),
                kind: "exif_thumbnail".into(),
                media_type: valid.then(|| "image/jpeg".into()),
                offset: start as u64,
                length: len as u64,
                preview_available: valid,
                provenance: format!("segment:{segment_index}:APP1/EXIF/IFD1"),
            });
        }
    }
    Some(ExifInfo {
        segment_index,
        byte_order: if le {
            "little_endian".into()
        } else {
            "big_endian".into()
        },
        tiff_offset: (base + 6) as u64,
        ifds,
    })
}

fn decode_tiff(t: &[u8], at: usize, typ: u16, count: u32, le: bool) -> Value {
    let n = count as usize;
    match typ {
        1 | 7 => t
            .get(at..at.saturating_add(n))
            .map(|v| json!(v))
            .unwrap_or(Value::Null),
        2 => t
            .get(at..at.saturating_add(n))
            .and_then(|v| std::str::from_utf8(v).ok())
            .map(|v| json!(v.trim_end_matches('\0')))
            .unwrap_or(Value::Null),
        3 => (0..n)
            .map(|i| u16at(t, at + i * 2, le))
            .collect::<Option<Vec<_>>>()
            .map_or(Value::Null, |v| json!(v)),
        4 => (0..n)
            .map(|i| u32at(t, at + i * 4, le))
            .collect::<Option<Vec<_>>>()
            .map_or(Value::Null, |v| json!(v)),
        5 => (0..n)
            .map(|i| Some([u32at(t, at + i * 8, le)?, u32at(t, at + i * 8 + 4, le)?]))
            .collect::<Option<Vec<_>>>()
            .map_or(Value::Null, |v| json!(v)),
        _ => Value::Null,
    }
}
fn w(code: &str, message: &str, offset: usize) -> JpegWarning {
    JpegWarning {
        code: code.into(),
        message: message.into(),
        offset: Some(offset as u64),
    }
}
fn type_size(t: u16) -> usize {
    match t {
        1 | 2 | 6 | 7 => 1,
        3 | 8 => 2,
        4 | 9 | 11 => 4,
        5 | 10 | 12 => 8,
        _ => 0,
    }
}
fn u16at(d: &[u8], at: usize, le: bool) -> Option<u16> {
    let b = d.get(at..at + 2)?;
    Some(if le {
        u16::from_le_bytes([b[0], b[1]])
    } else {
        be16(b)
    })
}
fn u32at(d: &[u8], at: usize, le: bool) -> Option<u32> {
    let b = d.get(at..at + 4)?;
    Some(if le {
        u32::from_le_bytes([b[0], b[1], b[2], b[3]])
    } else {
        u32::from_be_bytes([b[0], b[1], b[2], b[3]])
    })
}
fn be16(d: &[u8]) -> u16 {
    u16::from_be_bytes([d[0], d[1]])
}
fn standalone(m: u8) -> bool {
    matches!(m, 0x01 | 0xd8 | 0xd9 | 0xd0..=0xd7)
}
fn is_sof(m: u8) -> bool {
    matches!(m,0xc0..=0xc3|0xc5..=0xc7|0xc9..=0xcb|0xcd..=0xcf)
}
fn marker_name(m: u8) -> String {
    match m {
        0x01 => "TEM".into(),
        0xc0 => "SOF0".into(),
        0xc1 => "SOF1".into(),
        0xc2 => "SOF2".into(),
        0xc3 => "SOF3".into(),
        0xc4 => "DHT".into(),
        0xc5..=0xc7 | 0xc9..=0xcb | 0xcd..=0xcf => format!("SOF{}", m - 0xc0),
        0xd0..=0xd7 => format!("RST{}", m - 0xd0),
        0xd8 => "SOI".into(),
        0xd9 => "EOI".into(),
        0xda => "SOS".into(),
        0xdb => "DQT".into(),
        0xdd => "DRI".into(),
        0xe0..=0xef => format!("APP{}", m - 0xe0),
        0xfe => "COM".into(),
        _ => format!("UNKNOWN_FF{m:02X}"),
    }
}
fn category(m: u8) -> &'static str {
    match m {
        0xd8 | 0xd9 => "boundary",
        0xda => "scan",
        0xc0..=0xcf => "coding",
        0xdb | 0xdd => "table",
        0xe0..=0xef => "application",
        0xfe => "comment",
        0xd0..=0xd7 => "restart",
        _ => "unknown_reserved",
    }
}
fn frame_type(m: u8) -> String {
    match m {
        0xc0 => "baseline_dct",
        0xc1 => "extended_sequential_dct",
        0xc2 => "progressive_dct",
        0xc3 => "lossless_sequential",
        0xc5 => "differential_sequential_dct",
        0xc6 => "differential_progressive_dct",
        0xc7 => "differential_lossless",
        0xc9 => "extended_sequential_dct_arithmetic",
        0xca => "progressive_dct_arithmetic",
        0xcb => "lossless_arithmetic",
        0xcd => "differential_sequential_dct_arithmetic",
        0xce => "differential_progressive_dct_arithmetic",
        0xcf => "differential_lossless_arithmetic",
        _ => "reserved",
    }
    .into()
}
fn summary(m: u8, p: &[u8]) -> String {
    format!("{}; {} payload bytes", marker_name(m), p.len())
}
fn tag_name(t: u16) -> Option<&'static str> {
    match t {
        0x010F => Some("Make"),
        0x0110 => Some("Model"),
        0x0112 => Some("Orientation"),
        0x0131 => Some("Software"),
        0x0132 => Some("DateTime"),
        0x8769 => Some("ExifIFDPointer"),
        0x8825 => Some("GPSInfoIFDPointer"),
        0xA005 => Some("InteroperabilityIFDPointer"),
        0x0201 => Some("JPEGInterchangeFormat"),
        0x0202 => Some("JPEGInterchangeFormatLength"),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn segment(marker: u8, p: &[u8]) -> Vec<u8> {
        let mut v = vec![0xff, marker];
        v.extend_from_slice(&((p.len() + 2) as u16).to_be_bytes());
        v.extend_from_slice(p);
        v
    }
    #[test]
    fn baseline_scan_stuffing_restart_and_trailing() {
        let mut d = vec![0xff, 0xd8];
        d.extend(segment(0xc0, &[8, 0, 1, 0, 1, 1, 1, 0x11, 0]));
        d.extend(segment(0xda, &[1, 1, 0, 0, 63, 0]));
        d.extend([1, 0xff, 0, 2, 0xff, 0xd0, 3, 0xff, 0xd9, 9, 8]);
        let p = JpegStructureParser
            .parse(&d, JpegLimits::default())
            .unwrap();
        assert_eq!(p.report.scans[0].restart_markers.len(), 1);
        assert_eq!(p.report.physical_info.trailing_bytes_length, 2);
        assert_eq!(p.report.frames[0].frame_type, "baseline_dct");
    }
    #[test]
    fn multiple_scans() {
        let mut d = vec![0xff, 0xd8];
        d.extend(segment(0xda, &[1, 1, 0, 0, 0, 0]));
        d.extend([1, 0xff]);
        d.extend(segment(0xda, &[1, 1, 0, 1, 63, 0]));
        d.extend([2, 0xff, 0xd9]);
        let p = JpegStructureParser
            .parse(&d, JpegLimits::default())
            .unwrap();
        assert_eq!(p.report.scans.len(), 2);
    }
    #[test]
    fn non_jpeg_rejected() {
        assert!(JpegStructureParser
            .parse(b"not jpeg", JpegLimits::default())
            .is_err());
    }

    #[test]
    fn tables_jfif_comment_adobe_xmp_and_icc_are_inventory() {
        let mut d = vec![0xff, 0xd8];
        d.extend(segment(0xe0, b"JFIF\0\x01\x02\x01\0\x48\0\x48\0\0"));
        let mut dqt = vec![0];
        dqt.extend(0u8..64);
        dqt.push(1);
        dqt.extend(64u8..128);
        d.extend(segment(0xdb, &dqt));
        let mut dht = vec![0];
        dht.extend([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        dht.push(7);
        dht.push(0x11);
        dht.extend([1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);
        dht.push(8);
        d.extend(segment(0xc4, &dht));
        d.extend(segment(0xfe, b"technical comment"));
        d.extend(segment(0xee, b"Adobe\0\x64\0\x01\0\x02\x01"));
        let mut xmp = XMP_HEADER.to_vec();
        xmp.extend(b"<x:xmpmeta/>");
        d.extend(segment(0xe1, &xmp));
        let mut icc1 = ICC_HEADER.to_vec();
        icc1.extend([1, 2]);
        icc1.extend(b"abc");
        d.extend(segment(0xe2, &icc1));
        let mut icc2 = ICC_HEADER.to_vec();
        icc2.extend([2, 2]);
        icc2.extend(b"def");
        d.extend(segment(0xe2, &icc2));
        d.extend([0xff, 0xd9]);
        let p = JpegStructureParser
            .parse(&d, JpegLimits::default())
            .unwrap();
        assert_eq!(p.report.quantization_tables.len(), 2);
        assert_eq!(p.report.huffman_tables.len(), 2);
        assert_eq!(
            p.report.comments[0].text.as_deref(),
            Some("technical comment")
        );
        assert_eq!(p.report.xmp.len(), 1);
        assert_eq!(p.report.icc.len(), 2);
        assert!(p.report.segments.iter().any(|s| s
            .metadata
            .as_ref()
            .is_some_and(|m| m.get("identifier") == Some(&json!("Adobe")))));
    }

    fn exif_payload(le: bool, cycle: bool) -> Vec<u8> {
        let mut p = b"Exif\0\0".to_vec();
        p.extend(if le { *b"II" } else { *b"MM" });
        let u16b = |v: u16| if le { v.to_le_bytes() } else { v.to_be_bytes() };
        let u32b = |v: u32| if le { v.to_le_bytes() } else { v.to_be_bytes() };
        p.extend(u16b(42));
        p.extend(u32b(8));
        p.extend(u16b(1));
        p.extend(u16b(0x0112));
        p.extend(u16b(3));
        p.extend(u32b(1));
        p.extend(u16b(1));
        p.extend([0, 0]);
        p.extend(u32b(if cycle { 8 } else { 0 }));
        p
    }

    #[test]
    fn exif_little_and_big_endian_are_structural() {
        for le in [true, false] {
            let mut d = vec![0xff, 0xd8];
            d.extend(segment(0xe1, &exif_payload(le, false)));
            d.extend([0xff, 0xd9]);
            let p = JpegStructureParser
                .parse(&d, JpegLimits::default())
                .unwrap();
            assert_eq!(
                p.report.exif[0].ifds[0].entries[0].tag_name.as_deref(),
                Some("Orientation")
            );
            assert_eq!(
                p.report.exif[0].byte_order,
                if le { "little_endian" } else { "big_endian" }
            );
        }
    }

    #[test]
    fn exif_cycle_and_bad_offset_are_warnings() {
        let mut d = vec![0xff, 0xd8];
        d.extend(segment(0xe1, &exif_payload(true, true)));
        d.extend([0xff, 0xd9]);
        let p = JpegStructureParser
            .parse(&d, JpegLimits::default())
            .unwrap();
        assert!(p.report.warnings.iter().any(|w| w.code == "ifd_cycle"));
        let mut bad = b"Exif\0\0II\x2a\0".to_vec();
        bad.extend(999u32.to_le_bytes());
        let mut d = vec![0xff, 0xd8];
        d.extend(segment(0xe1, &bad));
        d.extend([0xff, 0xd9]);
        let p = JpegStructureParser
            .parse(&d, JpegLimits::default())
            .unwrap();
        assert!(p
            .report
            .warnings
            .iter()
            .any(|w| w.code == "ifd_offset_out_of_bounds"));
    }

    #[test]
    fn missing_eoi_truncated_and_invalid_lengths_are_neutral_warnings() {
        let p = JpegStructureParser
            .parse(&[0xff, 0xd8, 0xff, 0xe1, 0, 10, 1], JpegLimits::default())
            .unwrap();
        let codes = p
            .report
            .warnings
            .iter()
            .map(|w| w.code.as_str())
            .collect::<Vec<_>>();
        assert!(codes.contains(&"truncated_segment"));
        assert!(codes.contains(&"missing_eoi"));
        let p = JpegStructureParser
            .parse(&[0xff, 0xd8, 0xff, 0xe1, 0, 1], JpegLimits::default())
            .unwrap();
        assert!(p
            .report
            .warnings
            .iter()
            .any(|w| w.code == "invalid_segment_length"));
    }

    #[test]
    fn app_and_scan_limits_are_enforced() {
        let mut d = vec![0xff, 0xd8];
        d.extend(segment(0xe1, b"12345"));
        d.extend([0xff, 0xd9]);
        let mut limits = JpegLimits::default();
        limits.max_app_payload_bytes = 4;
        assert!(JpegStructureParser.parse(&d, limits).is_err());
        let mut d = vec![0xff, 0xd8];
        d.extend(segment(0xda, &[1, 1, 0, 0, 0, 0]));
        d.extend([1, 0xff]);
        d.extend(segment(0xda, &[1, 1, 0, 1, 63, 0]));
        d.extend([2, 0xff, 0xd9]);
        let mut limits = JpegLimits::default();
        limits.max_scans = 1;
        let p = JpegStructureParser.parse(&d, limits).unwrap();
        assert!(p.report.warnings.iter().any(|w| w.code == "limit_exceeded"));
    }

    #[test]
    fn incomplete_duplicate_icc_and_extended_xmp_are_reported() {
        let mut d = vec![0xff, 0xd8];
        for _ in 0..2 {
            let mut icc = ICC_HEADER.to_vec();
            icc.extend([1, 2]);
            icc.push(1);
            d.extend(segment(0xe2, &icc));
        }
        let mut x = EXT_XMP_HEADER.to_vec();
        x.extend(b"chunk");
        d.extend(segment(0xe1, &x));
        d.extend([0xff, 0xd9]);
        let p = JpegStructureParser
            .parse(&d, JpegLimits::default())
            .unwrap();
        let codes = p
            .report
            .warnings
            .iter()
            .map(|w| w.code.as_str())
            .collect::<Vec<_>>();
        assert!(codes.contains(&"icc_duplicate_chunk"));
        assert!(codes.contains(&"icc_chunk_missing"));
        assert!(codes.contains(&"extended_xmp_partial"));
    }
}
