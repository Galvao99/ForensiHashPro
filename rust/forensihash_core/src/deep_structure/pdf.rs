use super::models::*;
use super::{StructureError, StructureParser};
use lopdf::{Dictionary, Document, Object, ObjectId};
use std::collections::{BTreeMap, HashMap};
use std::path::Path;

pub struct PdfStructureParser;

impl StructureParser for PdfStructureParser {
    fn supports(&self, data: &[u8]) -> bool {
        find_all(data, b"%PDF-")
            .first()
            .is_some_and(|offset| *offset < 1024)
    }

    fn parse(&self, _path: &Path, data: &[u8]) -> Result<ParsedStructure, StructureError> {
        if !self.supports(data) {
            return Err(StructureError(
                "PDF header not found in the first 1024 bytes".into(),
            ));
        }
        self.parse_with_depth(data, 16)
    }
}

impl PdfStructureParser {
    pub fn parse_with_depth(
        &self,
        data: &[u8],
        max_nested_resource_depth: usize,
    ) -> Result<ParsedStructure, StructureError> {
        if !self.supports(data) {
            return Err(StructureError(
                "PDF header not found in the first 1024 bytes".into(),
            ));
        }
        let document = Document::load_mem(data)
            .map_err(|error| StructureError(format!("Unable to parse PDF structure: {error}")))?;
        let report = build_report(data, &document, max_nested_resource_depth);
        Ok(ParsedStructure {
            report,
            document,
            source_data: data.to_vec(),
        })
    }
}

fn build_report(
    data: &[u8],
    document: &Document,
    max_nested_resource_depth: usize,
) -> StructureReport {
    let header_offset = find_all(data, b"%PDF-")
        .into_iter()
        .find(|value| *value < 1024);
    let eof_offsets = find_all(data, b"%%EOF");
    let startxref_offsets = parse_startxrefs(data);
    let last_eof_end = eof_offsets
        .last()
        .map(|offset| offset + 5)
        .unwrap_or(data.len());
    let physical = PhysicalInfo {
        file_size: data.len() as u64,
        magic_bytes_hex: data
            .iter()
            .take(8)
            .map(|byte| format!("{byte:02X}"))
            .collect::<Vec<_>>()
            .join(" "),
        pdf_version: header_offset.and_then(|offset| parse_version(data, offset)),
        header_offset: header_offset.map(|value| value as u64),
        eof_count: eof_offsets.len(),
        eof_offsets: eof_offsets.iter().map(|value| *value as u64).collect(),
        startxref_offsets,
        bytes_after_last_eof: data.len().saturating_sub(last_eof_end) as u64,
    };

    let object_offsets = scan_object_offsets(data);
    let mut occurrences = HashMap::<String, usize>::new();
    let mut objects = Vec::new();
    let mut references = Vec::new();
    let mut streams = Vec::new();
    let mut images = Vec::new();
    let mut previews = Vec::new();
    let mut warnings = Vec::new();

    for (&id, object) in &document.objects {
        let source = object_id(id);
        let dictionary = object_dictionary(object);
        let object_type = dictionary
            .and_then(|dict| name(dict, b"Type"))
            .unwrap_or_else(|| object_kind(object));
        let subtype = dictionary.and_then(|dict| name(dict, b"Subtype"));
        if let Some(dict) = dictionary {
            count_dictionary(dict, &mut occurrences);
        }
        let mut object_refs = Vec::new();
        collect_references(object, "", &source, &mut object_refs, &mut references);
        let offset = object_offsets.get(&id).copied();
        let raw_length = offset.and_then(|start| raw_object_length(data, start));
        objects.push(ObjectRecord {
            id: source.clone(),
            object_number: id.0,
            generation_number: id.1,
            object_type: object_type.clone(),
            subtype: subtype.clone(),
            offset: offset.map(|v| v as u64),
            raw_length: raw_length.map(|v| v as u64),
            is_stream: matches!(object, Object::Stream(_)),
            dictionary: dictionary.map(dictionary_view).unwrap_or_default(),
            references: object_refs,
        });
        if let Object::Stream(stream) = object {
            let filters = filter_names(&stream.dict);
            let decoded_available = filters.iter().all(|filter| supported_filter(filter));
            streams.push(StreamRecord {
                object_id: source.clone(),
                filters: filters.clone(),
                declared_length: integer(&stream.dict, b"Length"),
                raw_length: stream.content.len() as u64,
                decoded_length: None,
                raw_available: true,
                decoded_available,
            });
            if subtype.as_deref() == Some("Image") {
                let mut media_type = preview_media_type(&filters);
                let direct_preview = media_type.is_some();
                let reconstructable = (filters.is_empty()
                    || filters
                        .iter()
                        .all(|filter| filter == "/FlateDecode" || filter == "/Fl"))
                    && integer(&stream.dict, b"BitsPerComponent") == Some(8)
                    && matches!(
                        name_value(&stream.dict, b"ColorSpace").as_deref(),
                        Some("DeviceGray" | "DeviceRGB" | "DeviceCMYK")
                    )
                    && integer(&stream.dict, b"Width").is_some_and(|value| value > 0)
                    && integer(&stream.dict, b"Height").is_some_and(|value| value > 0);
                if reconstructable {
                    media_type = Some("image/png".into());
                }
                images.push(ImageRecord {
                    object_id: source.clone(),
                    width: integer(&stream.dict, b"Width"),
                    height: integer(&stream.dict, b"Height"),
                    bits_per_component: integer(&stream.dict, b"BitsPerComponent"),
                    color_space: value(&stream.dict, b"ColorSpace"),
                    filters: filters.clone(),
                    raw_size: stream.content.len() as u64,
                    decoded_size: None,
                    mask: value(&stream.dict, b"Mask"),
                    soft_mask: value(&stream.dict, b"SMask"),
                });
                previews.push(PreviewableAsset {
                    id: format!("pdf_object_{}_{}", id.0, id.1),
                    kind: PreviewKind::Image,
                    object_id: source,
                    media_type,
                    previewable: true,
                    direct_preview,
                    preview_available: direct_preview || reconstructable,
                });
            }
        }
    }
    objects.sort_by_key(|item| (item.object_number, item.generation_number));
    let known_ids = objects
        .iter()
        .map(|item| item.id.as_str())
        .collect::<std::collections::HashSet<_>>();
    for edge in &references {
        if !known_ids.contains(edge.target.as_str()) {
            warnings.push(ParserWarning {
                code: "missing_reference".into(),
                message: format!(
                    "Reference {} points to missing object {}",
                    edge.path, edge.target
                ),
                object_id: Some(edge.source.clone()),
                offset: None,
            });
        }
    }

    let trailer = trailer_info(&document.trailer);
    let catalog = catalog_info(document, &document.trailer);
    let page_tree = page_tree(document, &catalog);
    let resources = resources(document, &page_tree.pages);
    let visual_resources = visual_resources(document, &page_tree.pages, max_nested_resource_depth);
    let forms = form_records(document);
    let embedded_files = embedded_file_records(document);
    for usage in visual_resources
        .iter()
        .filter(|usage| usage.kind == "thumbnail")
    {
        if let Some(asset) = previews
            .iter_mut()
            .find(|asset| asset.object_id == usage.object_id)
        {
            asset.kind = PreviewKind::Thumbnail;
        }
    }
    for embedded in &embedded_files {
        previews.push(PreviewableAsset {
            id: embedded.id.clone(),
            kind: PreviewKind::EmbeddedFile,
            object_id: embedded.object_id.clone(),
            media_type: embedded.mime_type.clone(),
            previewable: false,
            direct_preview: false,
            preview_available: false,
        });
    }
    let metadata_streams = metadata_records(document);
    let annotations = annotation_records(document, &page_tree.pages);
    let signatures = signature_records(document);
    let xref = xref_sections(data, document);
    let pages_with_annotations = page_tree
        .pages
        .iter()
        .filter(|page| page.annots.is_some())
        .count();
    let annotation_references = annotations
        .iter()
        .map(|item| item.page_object_ids.len())
        .sum();
    let embedded_items = objects
        .iter()
        .filter(|item| {
            item.object_type == "EmbeddedFile" || item.subtype.as_deref() == Some("EmbeddedFile")
        })
        .map(|item| item.id.clone())
        .collect::<Vec<_>>();
    let signature_count = objects
        .iter()
        .filter(|item| item.object_type == "Sig" || item.subtype.as_deref() == Some("Sig"))
        .count();
    let font_references = resources
        .iter()
        .filter(|item| item.category == "Font")
        .count();
    let image_references = resources
        .iter()
        .filter(|item| item.category == "XObject")
        .filter_map(|item| item.object_id.as_ref())
        .filter(|id| images.iter().any(|image| &image.object_id == *id))
        .count();
    let unique_font_objects = resources
        .iter()
        .filter(|item| item.category == "Font")
        .filter_map(|item| item.object_id.as_ref())
        .collect::<std::collections::HashSet<_>>()
        .len();
    let summary = StructureSummary {
        object_count: objects.len(),
        page_count: page_tree.effective_count,
        stream_count: streams.len(),
        image_count: images.len(),
        font_count: unique_font_objects,
        annotation_count: annotations.len(),
        embedded_file_count: embedded_items.len(),
        signature_dictionary_count: signature_count,
        revision_count: eof_offsets.len(),
        unique_image_objects: images.len(),
        image_references,
        unique_font_objects,
        font_references,
        pages_with_annotations,
        unique_annotation_objects: annotations.len(),
        annotation_references,
        visual_resource_references: visual_resources.len(),
        invoked_xobject_usages: visual_resources
            .iter()
            .filter(|item| item.invoked_by_do)
            .count(),
    };
    if eof_offsets.is_empty() {
        warnings.push(warning("eof_not_found", "No %%EOF marker was found"));
    }
    for declared in &physical.startxref_offsets {
        if *declared >= physical.file_size {
            warnings.push(ParserWarning {
                code: "invalid_xref_offset".into(),
                message: format!("startxref offset {declared} is outside the file"),
                object_id: None,
                offset: Some(*declared),
            });
        }
    }
    if physical.bytes_after_last_eof > 0 {
        warnings.push(warning(
            "bytes_after_last_eof",
            &format!(
                "{} bytes exist after the last %%EOF marker",
                physical.bytes_after_last_eof
            ),
        ));
    }

    let mut occurrence_list = occurrences
        .into_iter()
        .map(|(name, count)| Occurrence { name, count })
        .collect::<Vec<_>>();
    occurrence_list.sort_by(|a, b| a.name.cmp(&b.name));
    StructureReport {
        format: "PDF".into(),
        contract_version: CONTRACT_VERSION.into(),
        parser: "lopdf+bounded_physical_scan".into(),
        physical,
        summary,
        objects,
        references,
        xref,
        trailer,
        catalog,
        page_tree,
        resources,
        streams,
        images,
        embedded_items,
        previewable_assets: previews,
        visual_resources,
        forms,
        embedded_files,
        metadata_streams,
        annotations,
        signatures,
        occurrences: occurrence_list,
        parser_warnings: warnings,
    }
}

fn object_id(id: ObjectId) -> String {
    format!("{}_{}", id.0, id.1)
}
fn ref_string(id: ObjectId) -> String {
    format!("{} {} R", id.0, id.1)
}
fn object_dictionary(object: &Object) -> Option<&Dictionary> {
    match object {
        Object::Dictionary(dict) => Some(dict),
        Object::Stream(stream) => Some(&stream.dict),
        _ => None,
    }
}
fn name(dict: &Dictionary, key: &[u8]) -> Option<String> {
    dict.get(key)
        .ok()?
        .as_name()
        .ok()
        .map(|v| String::from_utf8_lossy(v).into_owned())
}
fn integer(dict: &Dictionary, key: &[u8]) -> Option<i64> {
    dict.get(key).ok()?.as_i64().ok()
}
fn value(dict: &Dictionary, key: &[u8]) -> Option<String> {
    dict.get(key).ok().map(object_value)
}
fn object_kind(object: &Object) -> String {
    match object {
        Object::Null => "Null",
        Object::Boolean(_) => "Boolean",
        Object::Integer(_) | Object::Real(_) => "Number",
        Object::Name(_) => "Name",
        Object::String(_, _) => "String",
        Object::Array(_) => "Array",
        Object::Dictionary(_) => "Dictionary",
        Object::Stream(_) => "Stream",
        Object::Reference(_) => "Reference",
    }
    .into()
}
fn object_value(object: &Object) -> String {
    match object {
        Object::Reference(id) => ref_string(*id),
        Object::Name(v) => format!("/{}", String::from_utf8_lossy(v)),
        Object::Integer(v) => v.to_string(),
        Object::Real(v) => v.to_string(),
        Object::Boolean(v) => v.to_string(),
        Object::Null => "null".into(),
        Object::String(v, _) => format!("({} bytes)", v.len()),
        Object::Array(v) => format!(
            "[{}]",
            v.iter().map(object_value).collect::<Vec<_>>().join(" ")
        ),
        Object::Dictionary(v) => format!("<<{} entries>>", v.len()),
        Object::Stream(v) => format!("stream({} bytes)", v.content.len()),
    }
}
fn pdf_value(object: &Object) -> PdfValue {
    let empty = || PdfValue {
        kind: String::new(),
        value: None,
        reference: None,
        items: Vec::new(),
        entries: BTreeMap::new(),
    };
    match object {
        Object::Null => PdfValue {
            kind: "null".into(),
            ..empty()
        },
        Object::Boolean(value) => PdfValue {
            kind: "boolean".into(),
            value: Some(value.to_string()),
            ..empty()
        },
        Object::Integer(value) => PdfValue {
            kind: "integer".into(),
            value: Some(value.to_string()),
            ..empty()
        },
        Object::Real(value) => PdfValue {
            kind: "real".into(),
            value: Some(value.to_string()),
            ..empty()
        },
        Object::Name(value) => PdfValue {
            kind: "name".into(),
            value: Some(format!("/{}", String::from_utf8_lossy(value))),
            ..empty()
        },
        Object::String(value, format) => PdfValue {
            kind: match format {
                lopdf::StringFormat::Literal => "string",
                lopdf::StringFormat::Hexadecimal => "hex_string",
            }
            .into(),
            value: Some(match format {
                lopdf::StringFormat::Literal => String::from_utf8_lossy(value).into_owned(),
                lopdf::StringFormat::Hexadecimal => {
                    value.iter().map(|byte| format!("{byte:02X}")).collect()
                }
            }),
            ..empty()
        },
        Object::Array(items) => PdfValue {
            kind: "array".into(),
            items: items.iter().map(pdf_value).collect(),
            ..empty()
        },
        Object::Dictionary(dict) => PdfValue {
            kind: "dictionary".into(),
            entries: dictionary_view(dict),
            ..empty()
        },
        Object::Stream(stream) => PdfValue {
            kind: "stream".into(),
            entries: dictionary_view(&stream.dict),
            ..empty()
        },
        Object::Reference(id) => PdfValue {
            kind: "reference".into(),
            reference: Some(object_id(*id)),
            value: Some(ref_string(*id)),
            ..empty()
        },
    }
}
fn dictionary_view(dict: &Dictionary) -> BTreeMap<String, PdfValue> {
    dict.iter()
        .map(|(key, value)| {
            (
                format!("/{}", String::from_utf8_lossy(key)),
                pdf_value(value),
            )
        })
        .collect()
}

fn collect_references(
    object: &Object,
    path: &str,
    source: &str,
    targets: &mut Vec<String>,
    edges: &mut Vec<ReferenceEdge>,
) {
    match object {
        Object::Reference(id) => {
            let target = object_id(*id);
            targets.push(target.clone());
            edges.push(ReferenceEdge {
                source: source.into(),
                target,
                relation: path
                    .rsplit('/')
                    .next()
                    .unwrap_or(path)
                    .split('[')
                    .next()
                    .unwrap_or(path)
                    .into(),
                path: if path.is_empty() {
                    "/".into()
                } else {
                    path.into()
                },
            });
        }
        Object::Array(items) => {
            for (index, item) in items.iter().enumerate() {
                collect_references(item, &format!("{path}[{index}]"), source, targets, edges);
            }
        }
        Object::Dictionary(dict) => {
            for (key, item) in dict.iter() {
                collect_references(
                    item,
                    &format!("{path}/{}", String::from_utf8_lossy(key)),
                    source,
                    targets,
                    edges,
                );
            }
        }
        Object::Stream(stream) => {
            for (key, item) in stream.dict.iter() {
                collect_references(
                    item,
                    &format!("{path}/{}", String::from_utf8_lossy(key)),
                    source,
                    targets,
                    edges,
                );
            }
        }
        _ => {}
    }
}

fn count_dictionary(dict: &Dictionary, counts: &mut HashMap<String, usize>) {
    for (key, object) in dict.iter() {
        *counts
            .entry(format!("/{}", String::from_utf8_lossy(key)))
            .or_default() += 1;
        count_names(object, counts);
    }
}
fn count_names(object: &Object, counts: &mut HashMap<String, usize>) {
    match object {
        Object::Name(v) => {
            *counts
                .entry(format!("/{}", String::from_utf8_lossy(v)))
                .or_default() += 1
        }
        Object::Array(v) => {
            for item in v {
                count_names(item, counts);
            }
        }
        Object::Dictionary(v) => count_dictionary(v, counts),
        _ => {}
    }
}
fn filter_names(dict: &Dictionary) -> Vec<String> {
    match dict.get(b"Filter") {
        Ok(Object::Name(v)) => vec![format!("/{}", String::from_utf8_lossy(v))],
        Ok(Object::Array(v)) => v
            .iter()
            .filter_map(|o| o.as_name().ok())
            .map(|v| format!("/{}", String::from_utf8_lossy(v)))
            .collect(),
        _ => vec![],
    }
}
fn supported_filter(filter: &str) -> bool {
    matches!(
        filter,
        "/FlateDecode"
            | "/Fl"
            | "/LZWDecode"
            | "/LZW"
            | "/ASCII85Decode"
            | "/A85"
            | "/ASCIIHexDecode"
            | "/AHx"
            | "/RunLengthDecode"
            | "/RL"
            | "/DCTDecode"
            | "/DCT"
            | "/JPXDecode"
            | "/CCITTFaxDecode"
            | "/CCF"
    )
}

fn trailer_info(dict: &Dictionary) -> TrailerInfo {
    TrailerInfo {
        root: value(dict, b"Root"),
        info: value(dict, b"Info"),
        size: integer(dict, b"Size"),
        id: value(dict, b"ID"),
        encrypt: value(dict, b"Encrypt"),
        prev: integer(dict, b"Prev"),
    }
}
fn catalog_info(document: &Document, trailer: &Dictionary) -> CatalogInfo {
    let root = trailer
        .get(b"Root")
        .ok()
        .and_then(|o| o.as_reference().ok());
    let dict = root.and_then(|id| document.get_dictionary(id).ok());
    CatalogInfo {
        object_id: root.map(object_id),
        pages: dict.and_then(|v| value(v, b"Pages")),
        metadata: dict.and_then(|v| value(v, b"Metadata")),
        acro_form: dict.and_then(|v| value(v, b"AcroForm")),
        names: dict.and_then(|v| value(v, b"Names")),
    }
}
fn page_tree(document: &Document, catalog: &CatalogInfo) -> PageTreeInfo {
    let root = catalog.pages.as_deref().and_then(parse_reference);
    let declared_count = root
        .and_then(|id| document.get_dictionary(id).ok())
        .and_then(|d| integer(d, b"Count"));
    let pages = document
        .get_pages()
        .into_iter()
        .enumerate()
        .filter_map(|(index, (_, id))| {
            let dict = document.get_dictionary(id).ok()?;
            Some(PageRecord {
                page_number: index + 1,
                object_id: object_id(id),
                parent: value(dict, b"Parent"),
                media_box: value(dict, b"MediaBox"),
                crop_box: value(dict, b"CropBox"),
                rotate: integer(dict, b"Rotate"),
                resources: value(dict, b"Resources"),
                contents: value(dict, b"Contents"),
                content_object_ids: dict
                    .get(b"Contents")
                    .ok()
                    .map(content_references)
                    .unwrap_or_default(),
                annots: value(dict, b"Annots"),
            })
        })
        .collect::<Vec<_>>();
    PageTreeInfo {
        root_object_id: root.map(object_id),
        declared_count,
        effective_count: pages.len(),
        pages,
    }
}
fn content_references(object: &Object) -> Vec<String> {
    match object {
        Object::Reference(id) => vec![object_id(*id)],
        Object::Array(items) => items
            .iter()
            .filter_map(|item| item.as_reference().ok())
            .map(object_id)
            .collect(),
        _ => Vec::new(),
    }
}
fn resources(document: &Document, pages: &[PageRecord]) -> Vec<ResourceRecord> {
    let mut result = Vec::new();
    for page in pages {
        let Some(page_id) = parse_object_id(&page.object_id) else {
            continue;
        };
        let Ok(page_dict) = document.get_dictionary(page_id) else {
            continue;
        };
        let Some(resource_dict) = resolve_dictionary(document, page_dict.get(b"Resources").ok())
        else {
            continue;
        };
        for category in [
            b"Font".as_slice(),
            b"XObject",
            b"ExtGState",
            b"ColorSpace",
            b"Pattern",
            b"Shading",
            b"Properties",
        ] {
            let Some(category_dict) =
                resolve_dictionary(document, resource_dict.get(category).ok())
            else {
                continue;
            };
            for (name, object) in category_dict.iter() {
                result.push(ResourceRecord {
                    page_object_id: page.object_id.clone(),
                    category: String::from_utf8_lossy(category).into_owned(),
                    name: String::from_utf8_lossy(name).into_owned(),
                    object_id: object.as_reference().ok().map(object_id),
                });
            }
        }
    }
    result
}
fn resolve_dictionary<'a>(
    document: &'a Document,
    object: Option<&'a Object>,
) -> Option<&'a Dictionary> {
    match object? {
        Object::Dictionary(dict) => Some(dict),
        Object::Reference(id) => document.get_dictionary(*id).ok(),
        _ => None,
    }
}

fn visual_resources(
    document: &Document,
    pages: &[PageRecord],
    max_depth: usize,
) -> Vec<VisualResourceUsage> {
    let mut result = Vec::new();
    for page in pages {
        let Some(page_id) = parse_object_id(&page.object_id) else {
            continue;
        };
        let Ok(page_dict) = document.get_dictionary(page_id) else {
            continue;
        };
        let invoked = page
            .content_object_ids
            .iter()
            .filter_map(|id| parse_object_id(id))
            .flat_map(|id| invoked_names(document, id))
            .collect::<std::collections::HashSet<_>>();
        let mut visited = std::collections::HashSet::new();
        if let Some(resource_dict) = resolve_dictionary(document, page_dict.get(b"Resources").ok())
        {
            walk_xobjects(
                document,
                &page.object_id,
                &page.object_id,
                resource_dict,
                "/Resources/XObject",
                0,
                max_depth,
                &invoked,
                &mut visited,
                &mut result,
            );
        }
        if let Ok(Object::Reference(thumb_id)) = page_dict.get(b"Thumb") {
            result.push(VisualResourceUsage {
                page_object_id: page.object_id.clone(),
                container_object_id: page.object_id.clone(),
                resource_name: "Thumb".into(),
                object_id: object_id(*thumb_id),
                kind: "thumbnail".into(),
                path: "/Thumb".into(),
                depth: 0,
                declared: true,
                invoked_by_do: false,
            });
        }
    }
    result
}

#[allow(clippy::too_many_arguments)]
fn walk_xobjects(
    document: &Document,
    page_id: &str,
    container_id: &str,
    resources: &Dictionary,
    base_path: &str,
    depth: usize,
    max_depth: usize,
    invoked: &std::collections::HashSet<String>,
    visited: &mut std::collections::HashSet<ObjectId>,
    result: &mut Vec<VisualResourceUsage>,
) {
    if depth > max_depth {
        return;
    }
    let Some(xobjects) = resolve_dictionary(document, resources.get(b"XObject").ok()) else {
        return;
    };
    for (name_bytes, object) in xobjects.iter() {
        let Ok(id) = object.as_reference() else {
            continue;
        };
        let name = String::from_utf8_lossy(name_bytes).into_owned();
        let subtype = document
            .get_object(id)
            .ok()
            .and_then(object_dictionary)
            .and_then(|dict| name_value(dict, b"Subtype"))
            .unwrap_or_else(|| "Unknown".into());
        let path = format!("{base_path}/{name}");
        result.push(VisualResourceUsage {
            page_object_id: page_id.into(),
            container_object_id: container_id.into(),
            resource_name: name.clone(),
            object_id: object_id(id),
            kind: subtype.to_lowercase(),
            path: path.clone(),
            depth,
            declared: true,
            invoked_by_do: invoked.contains(&name),
        });
        if subtype == "Form" && depth < max_depth && visited.insert(id) {
            if let Ok(stream) = document.get_object(id).and_then(Object::as_stream) {
                let nested_invoked = invoked_names(document, id)
                    .into_iter()
                    .collect::<std::collections::HashSet<_>>();
                if let Some(nested_resources) =
                    resolve_dictionary(document, stream.dict.get(b"Resources").ok())
                {
                    walk_xobjects(
                        document,
                        page_id,
                        &object_id(id),
                        nested_resources,
                        &format!("{path}/Resources/XObject"),
                        depth + 1,
                        max_depth,
                        &nested_invoked,
                        visited,
                        result,
                    );
                }
            }
            visited.remove(&id);
        }
    }
}

fn invoked_names(document: &Document, id: ObjectId) -> Vec<String> {
    let Some(stream) = document
        .get_object(id)
        .ok()
        .and_then(|object| object.as_stream().ok())
    else {
        return Vec::new();
    };
    let Ok(decoded) = stream.decompressed_content_with_limit(16 * 1024 * 1024) else {
        return Vec::new();
    };
    let Ok(content) = lopdf::content::Content::decode(&decoded) else {
        return Vec::new();
    };
    content
        .operations
        .into_iter()
        .filter(|operation| operation.operator == "Do")
        .filter_map(|operation| {
            operation
                .operands
                .first()
                .and_then(|operand| operand.as_name().ok())
                .map(|value| String::from_utf8_lossy(value).into_owned())
        })
        .collect()
}

fn form_records(document: &Document) -> Vec<FormRecord> {
    document
        .objects
        .iter()
        .filter_map(|(&id, object)| {
            let stream = object.as_stream().ok()?;
            (name_value(&stream.dict, b"Subtype").as_deref() == Some("Form")).then(|| FormRecord {
                object_id: object_id(id),
                bbox: stream.dict.get(b"BBox").ok().map(pdf_value),
                matrix: stream.dict.get(b"Matrix").ok().map(pdf_value),
                resources: stream.dict.get(b"Resources").ok().map(pdf_value),
                group: stream.dict.get(b"Group").ok().map(pdf_value),
                content_available: true,
            })
        })
        .collect()
}

fn embedded_file_records(document: &Document) -> Vec<EmbeddedFileRecord> {
    let mut names = HashMap::<ObjectId, (Option<String>, Option<String>)>::new();
    for object in document.objects.values() {
        collect_file_specs(document, object, &mut names);
    }
    document
        .objects
        .iter()
        .filter_map(|(&id, object)| {
            let stream = object.as_stream().ok()?;
            (name_value(&stream.dict, b"Type").as_deref() == Some("EmbeddedFile")).then(|| {
                let (filename, unicode_filename) = names.remove(&id).unwrap_or_default();
                EmbeddedFileRecord {
                    id: format!("embedded_{}_{}", id.0, id.1),
                    filename,
                    unicode_filename,
                    mime_type: name_value(&stream.dict, b"Subtype")
                        .map(|value| value.replace('#', "/")),
                    size: integer(&stream.dict, b"Size"),
                    object_id: object_id(id),
                    stream_available: true,
                    warnings: Vec::new(),
                }
            })
        })
        .collect()
}

fn collect_file_specs(
    document: &Document,
    object: &Object,
    names: &mut HashMap<ObjectId, (Option<String>, Option<String>)>,
) {
    match object {
        Object::Dictionary(dict) => {
            if let Some(ef) = resolve_dictionary(document, dict.get(b"EF").ok()) {
                let id = [b"F".as_slice(), b"UF"]
                    .into_iter()
                    .find_map(|key| ef.get(key).ok().and_then(|value| value.as_reference().ok()));
                if let Some(id) = id {
                    names.insert(id, (pdf_string(dict, b"F"), pdf_string(dict, b"UF")));
                }
            }
            for (_, value) in dict.iter() {
                collect_file_specs(document, value, names);
            }
        }
        Object::Array(items) => {
            for item in items {
                collect_file_specs(document, item, names);
            }
        }
        Object::Stream(stream) => {
            collect_file_specs(document, &Object::Dictionary(stream.dict.clone()), names)
        }
        _ => {}
    }
}

fn metadata_records(document: &Document) -> Vec<MetadataRecord> {
    document
        .objects
        .iter()
        .filter_map(|(&id, object)| {
            let stream = object.as_stream().ok()?;
            (name_value(&stream.dict, b"Type").as_deref() == Some("Metadata")).then(|| {
                MetadataRecord {
                    object_id: object_id(id),
                    subtype: name_value(&stream.dict, b"Subtype"),
                    raw_available: true,
                    decoded_available: true,
                }
            })
        })
        .collect()
}

fn annotation_records(document: &Document, pages: &[PageRecord]) -> Vec<AnnotationRecord> {
    let mut page_map = HashMap::<ObjectId, Vec<String>>::new();
    for page in pages {
        let Some(page_id) = parse_object_id(&page.object_id) else {
            continue;
        };
        let Ok(dict) = document.get_dictionary(page_id) else {
            continue;
        };
        if let Ok(Object::Array(items)) = dict.get(b"Annots") {
            for item in items {
                if let Ok(id) = item.as_reference() {
                    page_map.entry(id).or_default().push(page.object_id.clone());
                }
            }
        }
    }
    page_map
        .into_iter()
        .filter_map(|(id, pages)| {
            let dict = document.get_dictionary(id).ok()?;
            let keys: [&[u8]; 7] = [
                b"Subtype",
                b"Rect",
                b"Contents",
                b"Name",
                b"FS",
                b"A",
                b"AA",
            ];
            Some(AnnotationRecord {
                object_id: object_id(id),
                page_object_ids: pages,
                subtype: name_value(dict, b"Subtype"),
                properties: keys
                    .into_iter()
                    .filter_map(|key| {
                        dict.get(key).ok().map(|value| {
                            (
                                format!("/{}", String::from_utf8_lossy(key)),
                                pdf_value(value),
                            )
                        })
                    })
                    .collect(),
            })
        })
        .collect()
}

fn signature_records(document: &Document) -> Vec<SignatureRecord> {
    document
        .objects
        .iter()
        .filter_map(|(&id, object)| {
            let dict = object_dictionary(object)?;
            (name_value(dict, b"Type").as_deref() == Some("Sig")).then(|| {
                let keys: [&[u8]; 9] = [
                    b"Type",
                    b"Filter",
                    b"SubFilter",
                    b"ByteRange",
                    b"Contents",
                    b"M",
                    b"Name",
                    b"Reason",
                    b"Location",
                ];
                SignatureRecord {
                    object_id: object_id(id),
                    properties: keys
                        .into_iter()
                        .filter_map(|key| {
                            dict.get(key).ok().map(|value| {
                                (
                                    format!("/{}", String::from_utf8_lossy(key)),
                                    pdf_value(value),
                                )
                            })
                        })
                        .collect(),
                }
            })
        })
        .collect()
}

fn name_value(dict: &Dictionary, key: &[u8]) -> Option<String> {
    dict.get(key)
        .ok()?
        .as_name()
        .ok()
        .map(|value| String::from_utf8_lossy(value).into_owned())
}
fn pdf_string(dict: &Dictionary, key: &[u8]) -> Option<String> {
    dict.get(key)
        .ok()?
        .as_str()
        .ok()
        .map(|value| String::from_utf8_lossy(value).into_owned())
}

fn xref_sections(data: &[u8], document: &Document) -> Vec<XrefSection> {
    let mut sections = find_all(data, b"xref")
        .into_iter()
        .filter(|offset| {
            *offset == 0 || data.get(offset.saturating_sub(5)..*offset) != Some(b"start")
        })
        .map(|offset| XrefSection {
            kind: "table".into(),
            offset: Some(offset as u64),
            prev: document
                .trailer
                .get(b"Prev")
                .ok()
                .and_then(|v| v.as_i64().ok()),
            xref_stm: document
                .trailer
                .get(b"XRefStm")
                .ok()
                .and_then(|v| v.as_i64().ok()),
        })
        .collect::<Vec<_>>();
    for (&id, object) in &document.objects {
        if object_dictionary(object)
            .and_then(|d| name(d, b"Type"))
            .as_deref()
            == Some("XRef")
        {
            sections.push(XrefSection {
                kind: "stream".into(),
                offset: None,
                prev: object_dictionary(object).and_then(|d| integer(d, b"Prev")),
                xref_stm: Some(id.0 as i64),
            });
        }
    }
    sections
}
fn warning(code: &str, message: &str) -> ParserWarning {
    ParserWarning {
        code: code.into(),
        message: message.into(),
        object_id: None,
        offset: None,
    }
}
fn preview_media_type(filters: &[String]) -> Option<String> {
    if filters.iter().any(|v| v == "/DCTDecode") {
        Some("image/jpeg".into())
    } else if filters.iter().any(|v| v == "/JPXDecode") {
        Some("image/jp2".into())
    } else {
        None
    }
}

fn find_all(data: &[u8], needle: &[u8]) -> Vec<usize> {
    if needle.is_empty() {
        return vec![];
    }
    data.windows(needle.len())
        .enumerate()
        .filter_map(|(index, value)| (value == needle).then_some(index))
        .collect()
}
fn parse_version(data: &[u8], offset: usize) -> Option<String> {
    let start = offset + 5;
    let end = data[start..]
        .iter()
        .position(|v| !v.is_ascii_digit() && *v != b'.')
        .map(|v| start + v)
        .unwrap_or(data.len());
    (end > start).then(|| String::from_utf8_lossy(&data[start..end]).into_owned())
}
fn parse_startxrefs(data: &[u8]) -> Vec<u64> {
    find_all(data, b"startxref")
        .into_iter()
        .filter_map(|offset| {
            let tail = &data[offset + 9..];
            let start = tail.iter().position(|v| !v.is_ascii_whitespace())?;
            let digits = &tail[start..];
            let end = digits
                .iter()
                .position(|v| !v.is_ascii_digit())
                .unwrap_or(digits.len());
            std::str::from_utf8(&digits[..end]).ok()?.parse().ok()
        })
        .collect()
}
fn scan_object_offsets(data: &[u8]) -> HashMap<ObjectId, usize> {
    let mut result = HashMap::new();
    for (index, _) in data.windows(4).enumerate().filter(|(_, v)| *v == b" obj") {
        let prefix = &data[..index];
        let line_start = prefix
            .iter()
            .rposition(|v| *v == b'\n' || *v == b'\r')
            .map(|v| v + 1)
            .unwrap_or(0);
        let tokens = String::from_utf8_lossy(&data[line_start..index])
            .split_whitespace()
            .filter_map(|v| v.parse::<u32>().ok())
            .collect::<Vec<_>>();
        if tokens.len() >= 2 {
            result.insert(
                (tokens[tokens.len() - 2], tokens[tokens.len() - 1] as u16),
                line_start,
            );
        }
    }
    result
}
fn raw_object_length(data: &[u8], start: usize) -> Option<usize> {
    let relative = find_all(&data[start..], b"endobj").first().copied()?;
    Some(relative + 6)
}
fn parse_reference(value: &str) -> Option<ObjectId> {
    let parts = value.split_whitespace().collect::<Vec<_>>();
    if parts.len() != 3 || parts[2] != "R" {
        return None;
    }
    Some((parts[0].parse().ok()?, parts[1].parse().ok()?))
}
fn parse_object_id(value: &str) -> Option<ObjectId> {
    let parts = value.split('_').collect::<Vec<_>>();
    if parts.len() != 2 {
        return None;
    }
    Some((parts[0].parse().ok()?, parts[1].parse().ok()?))
}

#[cfg(test)]
mod tests {
    use super::*;
    use lopdf::{dictionary, SaveOptions, Stream};

    fn sample_pdf(page_count: usize, image: bool) -> Vec<u8> {
        let mut document = Document::with_version("1.7");
        let pages_id = document.new_object_id();
        let catalog_id =
            document.add_object(dictionary! { "Type" => "Catalog", "Pages" => pages_id });
        let mut kids = Vec::new();
        let image_id = image.then(|| {
            let mut stream = Stream::new(
                dictionary! {
                "Type" => "XObject", "Subtype" => "Image", "Width" => 32,
                    "Height" => 1, "BitsPerComponent" => 8, "ColorSpace" => "DeviceRGB"
                },
                [255, 0, 0].repeat(32),
            );
            stream.compress().expect("compress image");
            document.add_object(stream)
        });
        for _ in 0..page_count {
            let content_id = document.add_object(Stream::new(dictionary! {}, b"BT ET".to_vec()));
            let resources = image_id
                .map(|id| {
                    Object::Dictionary(dictionary! {
                        "XObject" => Object::Dictionary(dictionary! { "Im1" => id })
                    })
                })
                .unwrap_or_else(|| Object::Dictionary(dictionary! {}));
            let page_id = document.add_object(dictionary! {
                "Type" => "Page", "Parent" => pages_id, "MediaBox" => vec![0.into(), 0.into(), 100.into(), 100.into()],
                "Contents" => content_id, "Resources" => resources
            });
            kids.push(page_id.into());
        }
        document.objects.insert(
            pages_id,
            Object::Dictionary(dictionary! {
                "Type" => "Pages", "Kids" => kids, "Count" => page_count as i64
            }),
        );
        document.trailer.set("Root", catalog_id);
        let mut bytes = Vec::new();
        document.save_to(&mut bytes).expect("save PDF");
        bytes
    }

    #[test]
    fn multipage_tree_and_cyclic_references_are_finite() {
        let bytes = sample_pdf(2, false);
        let parsed = PdfStructureParser
            .parse(Path::new("sample.pdf"), &bytes)
            .expect("parse");
        assert_eq!(parsed.report.summary.page_count, 2);
        assert_eq!(parsed.report.page_tree.declared_count, Some(2));
        assert!(parsed
            .report
            .references
            .iter()
            .any(|edge| edge.relation == "Parent"));
        assert!(parsed.report.references.len() < 100);
    }

    #[test]
    fn compressed_image_is_inventory_and_payload_is_decodable() {
        let bytes = sample_pdf(1, true);
        let parsed = PdfStructureParser
            .parse(Path::new("image.pdf"), &bytes)
            .expect("parse");
        assert_eq!(parsed.report.summary.image_count, 1);
        let image = &parsed.report.images[0];
        assert_eq!((image.width, image.height), (Some(32), Some(1)));
        let id = parse_object_id(&image.object_id).expect("object id");
        let stream = parsed.document.get_object(id).unwrap().as_stream().unwrap();
        assert_eq!(
            stream.decompressed_content_with_limit(1024).unwrap(),
            [255, 0, 0].repeat(32)
        );
        let preview = crate::deep_structure::visual_asset(
            &parsed.document,
            id,
            crate::deep_structure::PreviewLimits {
                max_width: 100,
                max_height: 100,
                max_pixels: 10_000,
                max_decoded_bytes: 1024,
            },
        )
        .unwrap();
        assert!(preview
            .bytes
            .as_deref()
            .is_some_and(|bytes| bytes.starts_with(b"\x89PNG")));
    }

    #[test]
    fn physical_scan_reports_incremental_markers_and_trailing_bytes_neutrally() {
        let mut bytes = sample_pdf(1, false);
        bytes.extend_from_slice(b"\n%%EOFtail");
        let parsed = PdfStructureParser
            .parse(Path::new("incremental.pdf"), &bytes)
            .expect("parse");
        assert_eq!(parsed.report.physical.eof_count, 2);
        assert_eq!(parsed.report.physical.bytes_after_last_eof, 4);
        assert_eq!(parsed.report.summary.revision_count, 2);
    }

    #[test]
    fn malformed_pdf_returns_controlled_error() {
        let error = PdfStructureParser
            .parse(Path::new("broken.pdf"), b"%PDF-1.7\n1 0 obj\n<<")
            .err();
        assert!(error.is_some());
    }

    #[test]
    fn semantic_paths_preserve_nested_resources_and_multiple_contents() {
        let mut document = Document::with_version("1.7");
        let pages_id = document.new_object_id();
        let image_id = document.add_object(Stream::new(dictionary! {
            "Type" => "XObject", "Subtype" => "Image", "Width" => 2, "Height" => 3,
            "BitsPerComponent" => 8, "ColorSpace" => "DeviceRGB", "Mask" => (98, 0), "SMask" => (99, 0)
        }, vec![0; 18]));
        let form_id = document.add_object(Stream::new(dictionary! {
            "Type" => "XObject", "Subtype" => "Form", "BBox" => vec![0.into(), 0.into(), 10.into(), 10.into()]
        }, b"q Q".to_vec()));
        let font_id = document.add_object(
            dictionary! { "Type" => "Font", "Subtype" => "Type1", "BaseFont" => "Helvetica" },
        );
        let first_content = document.add_object(Stream::new(dictionary! {}, b"q".to_vec()));
        let second_content = document.add_object(Stream::new(dictionary! {}, b"Q".to_vec()));
        let annotation_id =
            document.add_object(dictionary! { "Type" => "Annot", "Subtype" => "Text" });
        let page_id = document.add_object(dictionary! {
            "Type" => "Page", "Parent" => pages_id,
            "MediaBox" => vec![0.into(), 0.into(), 100.into(), 100.into()],
            "Contents" => vec![first_content.into(), second_content.into()],
            "Annots" => vec![annotation_id.into()],
            "Resources" => Object::Dictionary(dictionary! {
                "Font" => Object::Dictionary(dictionary! { "F1" => font_id }),
                "XObject" => Object::Dictionary(dictionary! { "Im1" => image_id, "Fm1" => form_id })
            })
        });
        document.objects.insert(
            pages_id,
            Object::Dictionary(dictionary! {
                "Type" => "Pages", "Kids" => vec![page_id.into()], "Count" => 1
            }),
        );
        let metadata_id = document.add_object(Stream::new(
            dictionary! { "Type" => "Metadata", "Subtype" => "XML" },
            b"<x:xmpmeta/>".to_vec(),
        ));
        let embedded_id = document.add_object(Stream::new(
            dictionary! { "Type" => "EmbeddedFile" },
            b"attachment".to_vec(),
        ));
        let signature_id =
            document.add_object(dictionary! { "Type" => "Sig", "Filter" => "Adobe.PPKLite" });
        let acroform_id = document.add_object(dictionary! { "Fields" => Vec::<Object>::new() });
        let catalog_id = document.add_object(dictionary! {
            "Type" => "Catalog", "Pages" => pages_id, "Metadata" => metadata_id, "AcroForm" => acroform_id,
            "Names" => Object::Dictionary(dictionary! { "EmbeddedFiles" => embedded_id }), "Perms" => signature_id
        });
        document.trailer.set("Root", catalog_id);
        let mut bytes = Vec::new();
        document.save_to(&mut bytes).unwrap();
        let parsed = PdfStructureParser
            .parse(Path::new("semantic.pdf"), &bytes)
            .unwrap();

        let page = &parsed.report.page_tree.pages[0];
        assert_eq!(
            page.content_object_ids,
            vec![object_id(first_content), object_id(second_content)]
        );
        assert!(parsed
            .report
            .references
            .iter()
            .any(|edge| edge.source == object_id(page_id)
                && edge.target == object_id(image_id)
                && edge.path == "/Resources/XObject/Im1"));
        assert!(parsed
            .report
            .references
            .iter()
            .any(|edge| edge.source == object_id(image_id)
                && edge.target == "99_0"
                && edge.path == "/SMask"));
        assert_eq!(
            parsed
                .report
                .resources
                .iter()
                .filter(|item| item.page_object_id == object_id(page_id))
                .count(),
            3
        );
        assert_eq!(parsed.report.summary.unique_image_objects, 1);
        assert_eq!(parsed.report.summary.image_references, 1);
        assert_eq!(parsed.report.summary.unique_font_objects, 1);
        assert_eq!(parsed.report.summary.font_references, 1);
        assert_eq!(parsed.report.summary.embedded_file_count, 1);
        assert_eq!(parsed.report.summary.signature_dictionary_count, 1);
        assert!(parsed
            .report
            .parser_warnings
            .iter()
            .any(|warning| warning.code == "missing_reference"));
        let width = &parsed
            .report
            .objects
            .iter()
            .find(|item| item.id == object_id(image_id))
            .unwrap()
            .dictionary["/Width"];
        assert_eq!(width.kind, "integer");
        assert_eq!(width.value.as_deref(), Some("2"));
    }

    #[test]
    fn reused_image_distinguishes_unique_object_from_references() {
        let bytes = sample_pdf(3, true);
        let parsed = PdfStructureParser
            .parse(Path::new("reuse.pdf"), &bytes)
            .unwrap();
        assert_eq!(parsed.report.summary.unique_image_objects, 1);
        assert_eq!(parsed.report.summary.image_references, 3);
        assert_eq!(parsed.report.summary.image_count, 1);
    }

    #[test]
    fn xref_and_object_stream_document_is_supported() {
        let mut document = Document::load_mem(&sample_pdf(1, false)).unwrap();
        let options = SaveOptions::builder()
            .use_object_streams(true)
            .use_xref_streams(true)
            .build();
        let mut bytes = Vec::new();
        document.save_with_options(&mut bytes, options).unwrap();
        let parsed = PdfStructureParser
            .parse(Path::new("streams.pdf"), &bytes)
            .unwrap();
        assert_eq!(parsed.report.summary.page_count, 1);
        assert!(parsed
            .report
            .xref
            .iter()
            .any(|section| section.kind == "stream"));
    }

    #[test]
    fn contract_golden_core_fields_are_stable() {
        let parsed = PdfStructureParser
            .parse(Path::new("golden.pdf"), &sample_pdf(1, false))
            .unwrap();
        let value = serde_json::to_value(&parsed.report).unwrap();
        assert_eq!(value["contract_version"], "1.2");
        assert_eq!(value["format"], "PDF");
        assert_eq!(value["summary"]["page_count"], 1);
        assert_eq!(value["summary"]["unique_image_objects"], 0);
        assert_eq!(
            value["page_tree"]["pages"][0]["content_object_ids"]
                .as_array()
                .unwrap()
                .len(),
            1
        );
    }

    #[test]
    fn malformed_variants_never_panic() {
        let cases: [&[u8]; 3] = [
            b"%PDF-1.7\n1 0 obj\n<<",
            b"%PDF-1.7\n1 0 obj\n<< /Length 10 >>\nstream\nbroken\n%%EOF",
            b"%PDF-1.7\nstartxref\n999999\n%%EOF",
        ];
        for bytes in cases {
            let outcome = std::panic::catch_unwind(|| {
                PdfStructureParser.parse(Path::new("malformed.pdf"), bytes)
            });
            assert!(outcome.is_ok());
        }
    }

    #[test]
    fn nested_forms_map_declared_and_invoked_visual_resources() {
        let mut document = Document::with_version("1.7");
        let pages_id = document.new_object_id();
        let image_id = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Image", "Width" => 1, "Height" => 1, "BitsPerComponent" => 8, "ColorSpace" => "DeviceGray" }, vec![0]));
        let form_two_id = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Form", "BBox" => vec![0.into(),0.into(),1.into(),1.into()], "Resources" => Object::Dictionary(dictionary! { "XObject" => Object::Dictionary(dictionary! { "Im1" => image_id }) }) }, b"/Im1 Do".to_vec()));
        let form_one_id = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Form", "BBox" => vec![0.into(),0.into(),1.into(),1.into()], "Resources" => Object::Dictionary(dictionary! { "XObject" => Object::Dictionary(dictionary! { "Fm2" => form_two_id }) }) }, b"/Fm2 Do".to_vec()));
        let unused_id = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Image", "Width" => 1, "Height" => 1, "BitsPerComponent" => 8, "ColorSpace" => "DeviceGray" }, vec![255]));
        let content_id = document.add_object(Stream::new(dictionary! {}, b"/Fm1 Do".to_vec()));
        let page_id = document.add_object(dictionary! { "Type" => "Page", "Parent" => pages_id, "MediaBox" => vec![0.into(),0.into(),10.into(),10.into()], "Contents" => content_id, "Resources" => Object::Dictionary(dictionary! { "XObject" => Object::Dictionary(dictionary! { "Fm1" => form_one_id, "Unused" => unused_id }) }) });
        document.objects.insert(
            pages_id,
            Object::Dictionary(
                dictionary! { "Type" => "Pages", "Kids" => vec![page_id.into()], "Count" => 1 },
            ),
        );
        let catalog_id =
            document.add_object(dictionary! { "Type" => "Catalog", "Pages" => pages_id });
        document.trailer.set("Root", catalog_id);
        let mut bytes = Vec::new();
        document.save_to(&mut bytes).unwrap();
        let parsed = PdfStructureParser.parse_with_depth(&bytes, 8).unwrap();
        assert!(parsed
            .report
            .visual_resources
            .iter()
            .any(|usage| usage.object_id == object_id(image_id)
                && usage.path
                    == "/Resources/XObject/Fm1/Resources/XObject/Fm2/Resources/XObject/Im1"
                && usage.invoked_by_do));
        assert!(parsed
            .report
            .visual_resources
            .iter()
            .any(|usage| usage.object_id == object_id(unused_id) && !usage.invoked_by_do));
        assert_eq!(parsed.report.forms.len(), 2);
    }

    #[test]
    fn nested_resource_depth_limit_is_enforced() {
        let mut document = Document::with_version("1.7");
        let pages_id = document.new_object_id();
        let image_id = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Image", "Width" => 1, "Height" => 1, "BitsPerComponent" => 8, "ColorSpace" => "DeviceGray" }, vec![0]));
        let inner = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Form", "BBox" => vec![0.into(),0.into(),1.into(),1.into()], "Resources" => Object::Dictionary(dictionary! { "XObject" => Object::Dictionary(dictionary! { "Im" => image_id }) }) }, b"/Im Do".to_vec()));
        let outer = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Form", "BBox" => vec![0.into(),0.into(),1.into(),1.into()], "Resources" => Object::Dictionary(dictionary! { "XObject" => Object::Dictionary(dictionary! { "Inner" => inner }) }) }, b"/Inner Do".to_vec()));
        let content = document.add_object(Stream::new(dictionary! {}, b"/Outer Do".to_vec()));
        let page = document.add_object(dictionary! { "Type" => "Page", "Parent" => pages_id, "MediaBox" => vec![0.into(),0.into(),1.into(),1.into()], "Contents" => content, "Resources" => Object::Dictionary(dictionary! { "XObject" => Object::Dictionary(dictionary! { "Outer" => outer }) }) });
        document.objects.insert(
            pages_id,
            Object::Dictionary(
                dictionary! { "Type" => "Pages", "Kids" => vec![page.into()], "Count" => 1 },
            ),
        );
        let root = document.add_object(dictionary! { "Type" => "Catalog", "Pages" => pages_id });
        document.trailer.set("Root", root);
        let mut bytes = Vec::new();
        document.save_to(&mut bytes).unwrap();
        let parsed = PdfStructureParser.parse_with_depth(&bytes, 1).unwrap();
        assert!(!parsed
            .report
            .visual_resources
            .iter()
            .any(|usage| usage.object_id == object_id(image_id)));
    }

    #[test]
    fn thumbnail_embedded_metadata_annotations_and_signature_are_inventory() {
        let mut document = Document::with_version("1.7");
        let pages_id = document.new_object_id();
        let thumb = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Image", "Width" => 1, "Height" => 1, "BitsPerComponent" => 8, "ColorSpace" => "DeviceGray" }, vec![10]));
        let embedded = document.add_object(Stream::new(
            dictionary! { "Type" => "EmbeddedFile", "Subtype" => "text#2Fplain", "Size" => 7 },
            b"payload".to_vec(),
        ));
        let filespec = document.add_object(dictionary! { "Type" => "Filespec", "F" => Object::string_literal("note.txt"), "UF" => Object::string_literal("nota.txt"), "EF" => Object::Dictionary(dictionary! { "F" => embedded }) });
        let metadata = document.add_object(Stream::new(
            dictionary! { "Type" => "Metadata", "Subtype" => "XML" },
            b"<xmp/>".to_vec(),
        ));
        let annot_one = document.add_object(dictionary! { "Type" => "Annot", "Subtype" => "Text", "Rect" => vec![0.into(),0.into(),1.into(),1.into()], "Contents" => Object::string_literal("one") });
        let annot_two = document.add_object(dictionary! { "Type" => "Annot", "Subtype" => "FileAttachment", "Rect" => vec![1.into(),1.into(),2.into(),2.into()], "FS" => filespec });
        let signature = document.add_object(dictionary! { "Type" => "Sig", "Filter" => "Adobe.PPKLite", "SubFilter" => "adbe.pkcs7.detached", "ByteRange" => vec![0.into(),1.into(),2.into(),3.into()] });
        let page = document.add_object(dictionary! { "Type" => "Page", "Parent" => pages_id, "MediaBox" => vec![0.into(),0.into(),10.into(),10.into()], "Thumb" => thumb, "Annots" => vec![annot_one.into(), annot_two.into()] });
        document.objects.insert(
            pages_id,
            Object::Dictionary(
                dictionary! { "Type" => "Pages", "Kids" => vec![page.into()], "Count" => 1 },
            ),
        );
        let root = document.add_object(dictionary! { "Type" => "Catalog", "Pages" => pages_id, "Metadata" => metadata, "Names" => Object::Dictionary(dictionary! { "EmbeddedFiles" => filespec }), "Perms" => signature });
        document.trailer.set("Root", root);
        let mut bytes = Vec::new();
        document.save_to(&mut bytes).unwrap();
        let parsed = PdfStructureParser.parse_with_depth(&bytes, 8).unwrap();
        assert!(parsed
            .report
            .visual_resources
            .iter()
            .any(|usage| usage.kind == "thumbnail" && usage.object_id == object_id(thumb)));
        assert_eq!(
            parsed.report.embedded_files[0].filename.as_deref(),
            Some("note.txt")
        );
        assert_eq!(
            parsed.report.embedded_files[0].unicode_filename.as_deref(),
            Some("nota.txt")
        );
        assert_eq!(parsed.report.metadata_streams.len(), 1);
        assert_eq!(parsed.report.annotations.len(), 2);
        assert_eq!(parsed.report.summary.pages_with_annotations, 1);
        assert_eq!(parsed.report.summary.annotation_references, 2);
        assert_eq!(parsed.report.signatures.len(), 1);
    }

    #[test]
    fn cyclic_form_resources_do_not_recurse_forever() {
        let mut document = Document::with_version("1.7");
        let pages_id = document.new_object_id();
        let form_id = document.new_object_id();
        document.objects.insert(form_id, Object::Stream(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Form", "BBox" => vec![0.into(),0.into(),1.into(),1.into()], "Resources" => Object::Dictionary(dictionary! { "XObject" => Object::Dictionary(dictionary! { "Self" => form_id }) }) }, b"/Self Do".to_vec())));
        let content = document.add_object(Stream::new(dictionary! {}, b"/Fm Do".to_vec()));
        let page=document.add_object(dictionary! { "Type" => "Page", "Parent" => pages_id, "MediaBox" => vec![0.into(),0.into(),1.into(),1.into()], "Contents" => content, "Resources" => Object::Dictionary(dictionary! { "XObject" => Object::Dictionary(dictionary! { "Fm" => form_id }) }) });
        document.objects.insert(
            pages_id,
            Object::Dictionary(
                dictionary! { "Type" => "Pages", "Kids" => vec![page.into()], "Count" => 1 },
            ),
        );
        let root = document.add_object(dictionary! { "Type" => "Catalog", "Pages" => pages_id });
        document.trailer.set("Root", root);
        let mut bytes = Vec::new();
        document.save_to(&mut bytes).unwrap();
        let parsed = PdfStructureParser.parse_with_depth(&bytes, 16).unwrap();
        assert!(parsed.report.visual_resources.len() < 10);
    }
}
