use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use serde::de::{self, DeserializeSeed, Deserializer, MapAccess, SeqAccess, Visitor};
use serde::Serialize;
use serde_json::Value;

mod deep_structure;
use deep_structure::{JpegLimits, JpegStructureParser, PdfStructureParser};

// ================================================================
// MODELOS DE SAÍDA
// ================================================================

#[derive(Debug, Serialize)]
struct JsonField {
    path: String,
    key: String,
    value: Value,
    value_type: String,
    category: String,
}

#[derive(Debug, Serialize)]
struct JsonParseResult {
    is_valid: bool,
    streaming_used: bool,
    root_type: String,

    total_fields: usize,
    displayed_fields: usize,
    truncated: bool,

    fields: Vec<JsonField>,

    error_message: String,
}

// ================================================================
// ACUMULADOR
// ================================================================

struct JsonAccumulator {
    fields: Vec<JsonField>,
    total_fields: usize,
    max_fields: usize,
    truncated: bool,
    root_type: String,
}

impl JsonAccumulator {
    fn new(max_fields: usize) -> Self {
        Self {
            fields: Vec::new(),
            total_fields: 0,
            max_fields,
            truncated: false,
            root_type: String::new(),
        }
    }

    fn set_root_type(&mut self, path: &str, value_type: &str) {
        if path == "root" && self.root_type.is_empty() {
            self.root_type = value_type.to_string();
        }
    }

    fn add_field(&mut self, path: String, value: Value, value_type: &str) {
        self.set_root_type(&path, value_type);

        self.total_fields += 1;

        if self.fields.len() >= self.max_fields {
            self.truncated = true;
            return;
        }

        let key = extract_key(&path);
        let category = classify_key(&key);

        self.fields.push(JsonField {
            path,
            key,
            value,
            value_type: value_type.to_string(),
            category,
        });
    }

    fn into_result(self) -> JsonParseResult {
        JsonParseResult {
            is_valid: true,
            streaming_used: true,

            root_type: if self.root_type.is_empty() {
                "unknown".to_string()
            } else {
                self.root_type
            },

            total_fields: self.total_fields,
            displayed_fields: self.fields.len(),
            truncated: self.truncated,

            fields: self.fields,

            error_message: String::new(),
        }
    }
}

// ================================================================
// DESERIALIZAÇÃO INCREMENTAL
// ================================================================

struct JsonNodeSeed<'a> {
    path: String,
    accumulator: &'a mut JsonAccumulator,
}

impl<'de, 'a> DeserializeSeed<'de> for JsonNodeSeed<'a> {
    type Value = ();

    fn deserialize<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
    where
        D: Deserializer<'de>,
    {
        deserializer.deserialize_any(JsonNodeVisitor {
            path: self.path,
            accumulator: self.accumulator,
        })
    }
}

struct JsonNodeVisitor<'a> {
    path: String,
    accumulator: &'a mut JsonAccumulator,
}

impl<'de, 'a> Visitor<'de> for JsonNodeVisitor<'a> {
    type Value = ();

    fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
        formatter.write_str("qualquer valor JSON válido")
    }

    fn visit_map<M>(self, mut map: M) -> Result<Self::Value, M::Error>
    where
        M: MapAccess<'de>,
    {
        self.accumulator.set_root_type(&self.path, "object");

        while let Some(key) = map.next_key::<String>()? {
            let child_path = format!("{}.{}", self.path, key,);

            map.next_value_seed(JsonNodeSeed {
                path: child_path,
                accumulator: &mut *self.accumulator,
            })?;
        }

        Ok(())
    }

    fn visit_seq<S>(self, mut sequence: S) -> Result<Self::Value, S::Error>
    where
        S: SeqAccess<'de>,
    {
        self.accumulator.set_root_type(&self.path, "array");

        let mut index = 0usize;

        loop {
            let child_path = format!("{}[{}]", self.path, index,);

            let has_value = sequence.next_element_seed(JsonNodeSeed {
                path: child_path,
                accumulator: &mut *self.accumulator,
            })?;

            if has_value.is_none() {
                break;
            }

            index += 1;
        }

        Ok(())
    }

    fn visit_bool<E>(self, value: bool) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        self.accumulator
            .add_field(self.path, Value::Bool(value), "boolean");

        Ok(())
    }

    fn visit_i64<E>(self, value: i64) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        self.accumulator
            .add_field(self.path, Value::Number(value.into()), "integer");

        Ok(())
    }

    fn visit_u64<E>(self, value: u64) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        self.accumulator
            .add_field(self.path, Value::Number(value.into()), "integer");

        Ok(())
    }

    fn visit_f64<E>(self, value: f64) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        let number =
            serde_json::Number::from_f64(value).ok_or_else(|| E::custom("Número JSON inválido"))?;

        self.accumulator
            .add_field(self.path, Value::Number(number), "number");

        Ok(())
    }

    fn visit_str<E>(self, value: &str) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        self.accumulator
            .add_field(self.path, Value::String(value.to_string()), "string");

        Ok(())
    }

    fn visit_string<E>(self, value: String) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        self.accumulator
            .add_field(self.path, Value::String(value), "string");

        Ok(())
    }

    fn visit_none<E>(self) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        self.accumulator.add_field(self.path, Value::Null, "null");

        Ok(())
    }

    fn visit_unit<E>(self) -> Result<Self::Value, E>
    where
        E: de::Error,
    {
        self.accumulator.add_field(self.path, Value::Null, "null");

        Ok(())
    }

    fn visit_some<D>(self, deserializer: D) -> Result<Self::Value, D::Error>
    where
        D: Deserializer<'de>,
    {
        JsonNodeSeed {
            path: self.path,
            accumulator: self.accumulator,
        }
        .deserialize(deserializer)
    }
}

// ================================================================
// CLASSIFICAÇÃO
// ================================================================

fn normalize_key(key: &str) -> String {
    key.trim()
        .to_lowercase()
        .chars()
        .filter(|character| character.is_ascii_alphanumeric() || *character == '_')
        .collect()
}

fn extract_key(path: &str) -> String {
    let last_part = path.rsplit('.').next().unwrap_or(path);

    if let Some(index_position) = last_part.find('[') {
        let key = &last_part[..index_position];

        if key.is_empty() {
            return "item".to_string();
        }

        return key.to_string();
    }

    last_part.to_string()
}

fn classify_key(key: &str) -> String {
    let normalized = normalize_key(key);

    let device_keys = [
        "device",
        "devicemodel",
        "device_model",
        "model",
        "manufacturer",
        "brand",
        "platform",
        "os",
        "operatingsystem",
        "versionname",
        "androidversion",
    ];

    let browser_keys = [
        "browser",
        "useragent",
        "user_agent",
        "browsername",
        "browserversion",
        "navigator",
    ];

    let location_keys = [
        "lat",
        "latitude",
        "lon",
        "lng",
        "longitude",
        "originlocation",
        "locationsource",
        "location_source",
        "gps",
        "geolocation",
    ];

    let network_keys = [
        "ip",
        "ipaddress",
        "ip_address",
        "ipv4",
        "ipv6",
        "asn",
        "isp",
        "proxy",
        "vpn",
        "tor",
    ];

    let document_keys = [
        "cpf",
        "cnpj",
        "document",
        "documentnumber",
        "document_number",
        "proposal",
        "contract",
        "contractid",
        "contract_id",
    ];

    let date_keys = [
        "date",
        "datetime",
        "timestamp",
        "createdat",
        "created_at",
        "updatedat",
        "updated_at",
        "signingtime",
        "signing_time",
    ];

    let hash_keys = [
        "hash", "md5", "sha1", "sha224", "sha256", "sha384", "sha512", "checksum", "digest",
    ];

    let person_keys = [
        "name",
        "fullname",
        "full_name",
        "customername",
        "customer_name",
        "email",
        "phone",
        "telephone",
        "mobile",
    ];

    let technical_keys = [
        "memoryinfo",
        "memory",
        "architecture",
        "arch",
        "version",
        "versionname",
        "build",
        "sdk",
    ];

    if device_keys.contains(&normalized.as_str()) {
        return "device".to_string();
    }

    if browser_keys.contains(&normalized.as_str()) {
        return "browser".to_string();
    }

    if location_keys.contains(&normalized.as_str()) {
        return "location".to_string();
    }

    if network_keys.contains(&normalized.as_str()) {
        return "network".to_string();
    }

    if document_keys.contains(&normalized.as_str()) {
        return "document".to_string();
    }

    if date_keys.contains(&normalized.as_str()) {
        return "date".to_string();
    }

    if hash_keys.contains(&normalized.as_str()) {
        return "hash".to_string();
    }

    if person_keys.contains(&normalized.as_str()) {
        return "person".to_string();
    }

    if technical_keys.contains(&normalized.as_str()) {
        return "technical".to_string();
    }

    "other".to_string()
}

// ================================================================
// PARSERS
// ================================================================

fn parse_regular_json(path: &Path, max_fields: usize) -> Result<JsonParseResult, String> {
    let file =
        File::open(path).map_err(|error| format!("Não foi possível abrir o JSON: {}", error))?;

    let reader = BufReader::new(file);

    let mut deserializer = serde_json::Deserializer::from_reader(reader);

    let mut accumulator = JsonAccumulator::new(max_fields);

    JsonNodeSeed {
        path: "root".to_string(),
        accumulator: &mut accumulator,
    }
    .deserialize(&mut deserializer)
    .map_err(|error| format!("JSON inválido: {}", error))?;

    deserializer
        .end()
        .map_err(|error| format!("Conteúdo adicional após o JSON: {}", error))?;

    Ok(accumulator.into_result())
}

fn parse_json_lines(path: &Path, max_fields: usize) -> Result<JsonParseResult, String> {
    let file = File::open(path)
        .map_err(|error| format!("Não foi possível abrir o JSON Lines: {}", error))?;

    let reader = BufReader::new(file);

    let mut accumulator = JsonAccumulator::new(max_fields);

    accumulator.root_type = "json_lines".to_string();

    for (line_index, line_result) in reader.lines().enumerate() {
        let line = line_result
            .map_err(|error| format!("Falha ao ler a linha {}: {}", line_index + 1, error))?;

        let normalized_line = line.trim();

        if normalized_line.is_empty() {
            continue;
        }

        let mut deserializer = serde_json::Deserializer::from_str(normalized_line);

        JsonNodeSeed {
            path: format!("line_{}", line_index + 1,),
            accumulator: &mut accumulator,
        }
        .deserialize(&mut deserializer)
        .map_err(|error| format!("JSON inválido na linha {}: {}", line_index + 1, error))?;

        deserializer.end().map_err(|error| {
            format!("Conteúdo adicional na linha {}: {}", line_index + 1, error)
        })?;
    }

    Ok(accumulator.into_result())
}

// ================================================================
// FUNÇÃO EXPOSTA AO PYTHON
// ================================================================

#[pyfunction(signature = (path, max_fields=10_000))]
fn parse_json_file(path: &str, max_fields: usize) -> PyResult<String> {
    if max_fields == 0 {
        return Err(PyValueError::new_err("max_fields deve ser maior que zero."));
    }

    let file_path = Path::new(path);

    if !file_path.exists() {
        return Err(PyValueError::new_err(format!(
            "Arquivo não encontrado: {}",
            path
        )));
    }

    if !file_path.is_file() {
        return Err(PyValueError::new_err(
            "O caminho informado não representa um arquivo.",
        ));
    }

    let extension = file_path
        .extension()
        .and_then(|value| value.to_str())
        .unwrap_or("")
        .to_lowercase();

    let parse_result = match extension.as_str() {
        "jsonl" | "ndjson" => parse_json_lines(file_path, max_fields),

        "json" => parse_regular_json(file_path, max_fields),

        _ => {
            return Err(PyValueError::new_err(
                "Extensão não suportada. Use JSON, JSONL ou NDJSON.",
            ));
        }
    };

    let result = parse_result.map_err(PyRuntimeError::new_err)?;

    serde_json::to_string(&result).map_err(|error| {
        PyRuntimeError::new_err(format!("Falha ao serializar o resultado: {}", error))
    })
}

#[pyclass(name = "DeepStructureSession")]
struct PyDeepStructureSession {
    parsed: deep_structure::ParsedStructure,
    max_decoded_stream_bytes: usize,
    preview_limits: deep_structure::PreviewLimits,
    max_embedded_file_bytes: usize,
    max_preview_cache_bytes: usize,
    preview_cache: std::sync::Mutex<(std::collections::HashMap<String, Vec<u8>>, usize)>,
}

#[pymethods]
impl PyDeepStructureSession {
    fn report_json(&self) -> PyResult<String> {
        serde_json::to_string(&self.parsed.report)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    fn get_object(&self, object_id: &str) -> PyResult<String> {
        let id = parse_pdf_object_id(object_id)?;
        let normalized = format!("{}_{}", id.0, id.1);
        let object = self
            .parsed
            .report
            .objects
            .iter()
            .find(|item| item.id == normalized)
            .ok_or_else(|| PyValueError::new_err(format!("PDF object not found: {object_id}")))?;
        serde_json::to_string(object).map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    fn get_raw_object(&self, object_id: &str) -> PyResult<Vec<u8>> {
        let id = parse_pdf_object_id(object_id)?;
        let normalized = format!("{}_{}", id.0, id.1);
        let object = self
            .parsed
            .report
            .objects
            .iter()
            .find(|item| item.id == normalized)
            .ok_or_else(|| PyValueError::new_err(format!("PDF object not found: {object_id}")))?;
        let start = object.offset.ok_or_else(|| {
            PyRuntimeError::new_err(format!("Raw bytes are unavailable for object {object_id}"))
        })? as usize;
        let length = object.raw_length.ok_or_else(|| {
            PyRuntimeError::new_err(format!("Raw length is unavailable for object {object_id}"))
        })? as usize;
        let end = start
            .checked_add(length)
            .filter(|end| *end <= self.parsed.source_data.len())
            .ok_or_else(|| {
                PyRuntimeError::new_err(format!("Raw object range is invalid: {object_id}"))
            })?;
        Ok(self.parsed.source_data[start..end].to_vec())
    }

    fn get_raw_stream(&self, object_id: &str) -> PyResult<Vec<u8>> {
        let id = parse_pdf_object_id(object_id)?;
        let stream = self
            .parsed
            .document
            .get_object(id)
            .ok()
            .and_then(|object| object.as_stream().ok())
            .ok_or_else(|| PyValueError::new_err(format!("PDF stream not found: {object_id}")))?;
        Ok(stream.content.clone())
    }

    fn get_decoded_stream(&self, object_id: &str) -> PyResult<Vec<u8>> {
        let id = parse_pdf_object_id(object_id)?;
        let stream = self
            .parsed
            .document
            .get_object(id)
            .ok()
            .and_then(|object| object.as_stream().ok())
            .ok_or_else(|| PyValueError::new_err(format!("PDF stream not found: {object_id}")))?;
        stream
            .decompressed_content_with_limit(self.max_decoded_stream_bytes)
            .map_err(|error| {
                PyRuntimeError::new_err(format!("Unable to decode stream {object_id}: {error}"))
            })
    }

    fn get_visual_asset(&self, object_id: &str) -> PyResult<String> {
        let id = parse_pdf_object_id(object_id)?;
        let result = deep_structure::visual_asset(&self.parsed.document, id, self.preview_limits)
            .map_err(PyRuntimeError::new_err)?;
        serde_json::to_string(&result.asset)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    fn get_preview(&self, object_id: &str) -> PyResult<Vec<u8>> {
        let id = parse_pdf_object_id(object_id)?;
        let key = format!("preview:{}_{}", id.0, id.1);
        if let Some(bytes) = self
            .preview_cache
            .lock()
            .map_err(|_| PyRuntimeError::new_err("Preview cache lock failed"))?
            .0
            .get(&key)
            .cloned()
        {
            return Ok(bytes);
        }
        let result = deep_structure::visual_asset(&self.parsed.document, id, self.preview_limits)
            .map_err(PyRuntimeError::new_err)?;
        let bytes = result.bytes.ok_or_else(|| {
            PyRuntimeError::new_err(
                result
                    .asset
                    .warnings
                    .first()
                    .map(|warning| warning.message.clone())
                    .unwrap_or_else(|| "Preview is unavailable".into()),
            )
        })?;
        self.cache_preview(key, &bytes)?;
        Ok(bytes)
    }

    fn get_composite_preview(&self, object_id: &str) -> PyResult<Vec<u8>> {
        let id = parse_pdf_object_id(object_id)?;
        let key = format!("composite:{}_{}", id.0, id.1);
        if let Some(bytes) = self
            .preview_cache
            .lock()
            .map_err(|_| PyRuntimeError::new_err("Preview cache lock failed"))?
            .0
            .get(&key)
            .cloned()
        {
            return Ok(bytes);
        }
        let bytes =
            deep_structure::composite_preview(&self.parsed.document, id, self.preview_limits)
                .map_err(PyRuntimeError::new_err)?;
        self.cache_preview(key, &bytes)?;
        Ok(bytes)
    }

    fn get_embedded_file(&self, object_id: &str) -> PyResult<Vec<u8>> {
        let bytes = self.get_decoded_stream(object_id)?;
        if bytes.len() > self.max_embedded_file_bytes {
            return Err(PyRuntimeError::new_err(
                "Embedded file exceeds configured size limit",
            ));
        }
        Ok(bytes)
    }

    fn get_metadata_text(&self, object_id: &str) -> PyResult<String> {
        let bytes = self.get_decoded_stream(object_id)?;
        Ok(String::from_utf8_lossy(&bytes).into_owned())
    }
}

impl PyDeepStructureSession {
    fn cache_preview(&self, key: String, bytes: &[u8]) -> PyResult<()> {
        if bytes.len() > self.max_preview_cache_bytes {
            return Ok(());
        }
        let mut cache = self
            .preview_cache
            .lock()
            .map_err(|_| PyRuntimeError::new_err("Preview cache lock failed"))?;
        if cache.1.saturating_add(bytes.len()) > self.max_preview_cache_bytes {
            cache.0.clear();
            cache.1 = 0;
        }
        cache.1 = cache.1.saturating_add(bytes.len());
        cache.0.insert(key, bytes.to_vec());
        Ok(())
    }
}

fn parse_pdf_object_id(value: &str) -> PyResult<(u32, u16)> {
    let normalized = value.strip_prefix("pdf_object_").unwrap_or(value);
    let parts = normalized.split('_').collect::<Vec<_>>();
    if parts.len() != 2 {
        return Err(PyValueError::new_err(
            "object_id must use '<number>_<generation>' or 'pdf_object_<number>_<generation>'",
        ));
    }
    let number = parts[0]
        .parse()
        .map_err(|_| PyValueError::new_err("invalid object number"))?;
    let generation = parts[1]
        .parse()
        .map_err(|_| PyValueError::new_err("invalid generation number"))?;
    Ok((number, generation))
}

#[pyfunction(signature = (path, max_file_bytes=536_870_912, max_decoded_stream_bytes=67_108_864, max_preview_width=16384, max_preview_height=16384, max_preview_pixels=100_000_000, max_nested_resource_depth=16, max_embedded_file_bytes=134_217_728, max_preview_cache_bytes=134_217_728))]
fn analyze_pdf(
    path: &str,
    max_file_bytes: usize,
    max_decoded_stream_bytes: usize,
    max_preview_width: u32,
    max_preview_height: u32,
    max_preview_pixels: u64,
    max_nested_resource_depth: usize,
    max_embedded_file_bytes: usize,
    max_preview_cache_bytes: usize,
) -> PyResult<PyDeepStructureSession> {
    if max_file_bytes == 0
        || max_decoded_stream_bytes == 0
        || max_preview_width == 0
        || max_preview_height == 0
        || max_preview_pixels == 0
        || max_nested_resource_depth == 0
        || max_embedded_file_bytes == 0
        || max_preview_cache_bytes == 0
    {
        return Err(PyValueError::new_err(
            "size limits must be greater than zero",
        ));
    }
    let file_path = Path::new(path);
    let metadata = std::fs::metadata(file_path)
        .map_err(|error| PyValueError::new_err(format!("Unable to inspect PDF: {error}")))?;
    if !metadata.is_file() {
        return Err(PyValueError::new_err("The supplied path is not a file"));
    }
    if metadata.len() > max_file_bytes as u64 {
        return Err(PyValueError::new_err(format!(
            "PDF exceeds configured file limit of {max_file_bytes} bytes"
        )));
    }
    let data = std::fs::read(file_path)
        .map_err(|error| PyRuntimeError::new_err(format!("Unable to read PDF: {error}")))?;
    let parsed = PdfStructureParser
        .parse_with_depth(&data, max_nested_resource_depth)
        .map_err(|error| PyRuntimeError::new_err(error.to_string()))?;
    Ok(PyDeepStructureSession {
        parsed,
        max_decoded_stream_bytes,
        preview_limits: deep_structure::PreviewLimits {
            max_width: max_preview_width,
            max_height: max_preview_height,
            max_pixels: max_preview_pixels,
            max_decoded_bytes: max_decoded_stream_bytes,
        },
        max_embedded_file_bytes,
        max_preview_cache_bytes,
        preview_cache: std::sync::Mutex::new((std::collections::HashMap::new(), 0)),
    })
}

#[pyclass(name = "JpegDeepStructureSession")]
struct PyJpegDeepStructureSession {
    parsed: deep_structure::ParsedJpeg,
    max_icc_bytes: usize,
}

#[pymethods]
impl PyJpegDeepStructureSession {
    fn report_json(&self) -> PyResult<String> {
        serde_json::to_string(&self.parsed.report)
            .map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
    fn get_segment(&self, index: usize) -> PyResult<String> {
        let item = self
            .parsed
            .report
            .segments
            .get(index)
            .ok_or_else(|| PyValueError::new_err("JPEG segment not found"))?;
        serde_json::to_string(item).map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
    fn get_segment_raw(&self, index: usize) -> PyResult<Vec<u8>> {
        let item = self
            .parsed
            .report
            .segments
            .get(index)
            .ok_or_else(|| PyValueError::new_err("JPEG segment not found"))?;
        self.range(item.offset, item.end_offset - item.offset, "segment")
    }
    fn get_scan(&self, index: usize) -> PyResult<String> {
        let item = self
            .parsed
            .report
            .scans
            .get(index)
            .ok_or_else(|| PyValueError::new_err("JPEG scan not found"))?;
        serde_json::to_string(item).map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
    fn get_scan_raw(&self, index: usize) -> PyResult<Vec<u8>> {
        let item = self
            .parsed
            .report
            .scans
            .get(index)
            .ok_or_else(|| PyValueError::new_err("JPEG scan not found"))?;
        self.range(item.data_offset, item.data_length, "scan")
    }
    fn get_exif_ifd(&self, path: &str) -> PyResult<String> {
        let item = self
            .parsed
            .report
            .exif
            .iter()
            .flat_map(|e| e.ifds.iter())
            .find(|i| i.id == path || i.kind == path)
            .ok_or_else(|| PyValueError::new_err("EXIF IFD not found"))?;
        serde_json::to_string(item).map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
    fn get_exif_entry(&self, path: &str, tag_id: u16) -> PyResult<String> {
        let ifd = self
            .parsed
            .report
            .exif
            .iter()
            .flat_map(|e| e.ifds.iter())
            .find(|i| i.id == path || i.kind == path)
            .ok_or_else(|| PyValueError::new_err("EXIF IFD not found"))?;
        let item = ifd
            .entries
            .iter()
            .find(|e| e.tag_id == tag_id)
            .ok_or_else(|| PyValueError::new_err("EXIF entry not found"))?;
        serde_json::to_string(item).map_err(|e| PyRuntimeError::new_err(e.to_string()))
    }
    fn get_visual_asset(&self, asset_id: &str) -> PyResult<Vec<u8>> {
        let a = self
            .parsed
            .report
            .visual_assets
            .iter()
            .find(|a| a.id == asset_id)
            .ok_or_else(|| PyValueError::new_err("JPEG visual asset not found"))?;
        self.range(a.offset, a.length, "visual asset")
    }
    fn get_preview(&self, asset_id: &str) -> PyResult<Vec<u8>> {
        let a = self
            .parsed
            .report
            .visual_assets
            .iter()
            .find(|a| a.id == asset_id)
            .ok_or_else(|| PyValueError::new_err("JPEG visual asset not found"))?;
        if !a.preview_available {
            return Err(PyRuntimeError::new_err(
                "Preview is unsupported for this asset",
            ));
        }
        self.range(a.offset, a.length, "preview")
    }
    fn get_xmp_text(&self, packet_id: &str) -> PyResult<String> {
        let p = self
            .parsed
            .report
            .xmp
            .iter()
            .find(|p| p.id == packet_id)
            .ok_or_else(|| PyValueError::new_err("XMP packet not found"))?;
        let bytes = self.range(p.offset, p.length, "XMP")?;
        String::from_utf8(bytes)
            .map_err(|_| PyRuntimeError::new_err("XMP packet is not valid UTF-8"))
    }
    fn get_xmp_raw(&self, packet_id: &str) -> PyResult<Vec<u8>> {
        let p = self
            .parsed
            .report
            .xmp
            .iter()
            .find(|p| p.id == packet_id)
            .ok_or_else(|| PyValueError::new_err("XMP packet not found"))?;
        self.range(p.offset, p.length, "XMP")
    }
    fn get_icc_profile(&self) -> PyResult<Vec<u8>> {
        let chunks = &self.parsed.report.icc;
        if chunks.is_empty() {
            return Err(PyValueError::new_err("ICC profile not found"));
        }
        let total = chunks[0].total_chunks;
        let mut ordered = chunks.iter().collect::<Vec<_>>();
        ordered.sort_by_key(|c| c.sequence_number);
        if ordered.len() != total as usize
            || (1..=total).any(|n| ordered.iter().filter(|c| c.sequence_number == n).count() != 1)
        {
            return Err(PyRuntimeError::new_err(
                "ICC profile chunks are incomplete or duplicated",
            ));
        }
        let size: usize = ordered.iter().map(|c| c.length as usize).sum();
        if size > self.max_icc_bytes {
            return Err(PyRuntimeError::new_err(
                "ICC profile exceeds configured size limit",
            ));
        }
        let mut out = Vec::with_capacity(size);
        for c in ordered {
            out.extend(self.range(c.offset, c.length, "ICC chunk")?);
        }
        Ok(out)
    }
    fn get_trailing_bytes(&self) -> PyResult<Vec<u8>> {
        let p = &self.parsed.report.physical_info;
        match p.trailing_bytes_offset {
            Some(o) => self.range(o, p.trailing_bytes_length, "trailing bytes"),
            None => Ok(vec![]),
        }
    }
}

impl PyJpegDeepStructureSession {
    fn range(&self, offset: u64, length: u64, label: &str) -> PyResult<Vec<u8>> {
        let start = usize::try_from(offset)
            .map_err(|_| PyRuntimeError::new_err(format!("Invalid {label} offset")))?;
        let len = usize::try_from(length)
            .map_err(|_| PyRuntimeError::new_err(format!("Invalid {label} length")))?;
        let end = start
            .checked_add(len)
            .filter(|e| *e <= self.parsed.source_data.len())
            .ok_or_else(|| PyRuntimeError::new_err(format!("Invalid {label} range")))?;
        Ok(self.parsed.source_data[start..end].to_vec())
    }
}

#[pyfunction(signature = (path, max_file_bytes=536_870_912, max_segments=100_000, max_app_payload_bytes=67_108_864, max_exif_ifds=128, max_exif_entries=100_000, max_exif_depth=16, max_icc_bytes=134_217_728, max_xmp_bytes=67_108_864, max_thumbnail_bytes=67_108_864, max_scans=4096))]
fn analyze_jpeg(
    path: &str,
    max_file_bytes: usize,
    max_segments: usize,
    max_app_payload_bytes: usize,
    max_exif_ifds: usize,
    max_exif_entries: usize,
    max_exif_depth: usize,
    max_icc_bytes: usize,
    max_xmp_bytes: usize,
    max_thumbnail_bytes: usize,
    max_scans: usize,
) -> PyResult<PyJpegDeepStructureSession> {
    let values = [
        max_file_bytes,
        max_segments,
        max_app_payload_bytes,
        max_exif_ifds,
        max_exif_entries,
        max_exif_depth,
        max_icc_bytes,
        max_xmp_bytes,
        max_thumbnail_bytes,
        max_scans,
    ];
    if values.contains(&0) {
        return Err(PyValueError::new_err(
            "size limits must be greater than zero",
        ));
    }
    let file_path = Path::new(path);
    let metadata = std::fs::metadata(file_path)
        .map_err(|e| PyValueError::new_err(format!("Unable to inspect JPEG: {e}")))?;
    if !metadata.is_file() {
        return Err(PyValueError::new_err("The supplied path is not a file"));
    }
    if metadata.len() > max_file_bytes as u64 {
        return Err(PyValueError::new_err(format!(
            "JPEG exceeds configured file limit of {max_file_bytes} bytes"
        )));
    }
    let data = std::fs::read(file_path)
        .map_err(|e| PyRuntimeError::new_err(format!("Unable to read JPEG: {e}")))?;
    let limits = JpegLimits {
        max_segments,
        max_app_payload_bytes,
        max_exif_ifds,
        max_exif_entries,
        max_exif_depth,
        max_icc_bytes,
        max_xmp_bytes,
        max_thumbnail_bytes,
        max_scans,
    };
    let parsed = JpegStructureParser
        .parse(&data, limits)
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    Ok(PyJpegDeepStructureSession {
        parsed,
        max_icc_bytes,
    })
}

#[pymodule]
fn forensihash_core(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(parse_json_file, module)?)?;

    module.add_function(wrap_pyfunction!(analyze_pdf, module)?)?;
    module.add_function(wrap_pyfunction!(analyze_jpeg, module)?)?;
    module.add_class::<PyDeepStructureSession>()?;
    module.add_class::<PyJpegDeepStructureSession>()?;

    Ok(())
}
