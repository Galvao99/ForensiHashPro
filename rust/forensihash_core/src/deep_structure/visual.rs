use super::models::{PreviewProvenance, VisualAsset, VisualWarning};
use lopdf::{Document, Object, ObjectId, Stream};

#[derive(Debug, Clone, Copy)]
pub struct PreviewLimits {
    pub max_width: u32,
    pub max_height: u32,
    pub max_pixels: u64,
    pub max_decoded_bytes: usize,
}

pub struct PreviewResult {
    pub asset: VisualAsset,
    pub bytes: Option<Vec<u8>>,
}

pub fn visual_asset(
    document: &Document,
    id: ObjectId,
    limits: PreviewLimits,
) -> Result<PreviewResult, String> {
    let stream = document
        .get_object(id)
        .ok()
        .and_then(|object| object.as_stream().ok())
        .ok_or_else(|| format!("PDF image stream not found: {}_{}", id.0, id.1))?;
    if name(stream, b"Subtype").as_deref() != Some("Image") {
        return Err(format!("PDF object is not an image: {}_{}", id.0, id.1));
    }
    let object_id = format!("{}_{}", id.0, id.1);
    let width = integer(stream, b"Width").and_then(|value| u32::try_from(value).ok());
    let height = integer(stream, b"Height").and_then(|value| u32::try_from(value).ok());
    let bits = integer(stream, b"BitsPerComponent").and_then(|value| u8::try_from(value).ok());
    let color_space = color_space(document, stream);
    let filters = filters(stream);
    let mask_object_id = reference(stream, b"Mask");
    let soft_mask_object_id = reference(stream, b"SMask");
    let image_mask = boolean(stream, b"ImageMask").unwrap_or(false);
    let mut warnings = Vec::new();

    let direct = filters.iter().find_map(|filter| match filter.as_str() {
        "/DCTDecode" => Some(("image/jpeg", "JPEG")),
        "/JPXDecode" => Some(("image/jp2", "JPEG2000")),
        _ => None,
    });
    let (status, mime_type, encoding, reconstructed, transformation, bytes) =
        if let Some((mime, encoding)) = direct {
            (
                "direct",
                Some(mime.into()),
                Some(encoding.into()),
                false,
                "none".into(),
                Some(stream.content.clone()),
            )
        } else if filters.is_empty()
            || filters
                .iter()
                .all(|filter| filter == "/FlateDecode" || filter == "/Fl")
        {
            match reconstruct_png(
                stream,
                width,
                height,
                bits,
                color_space.as_deref(),
                image_mask,
                limits,
            ) {
                Ok(bytes) => (
                    "reconstructed",
                    Some("image/png".into()),
                    Some("PNG".into()),
                    true,
                    if color_space.as_deref() == Some("/DeviceCMYK") {
                        "cmyk_to_rgb_png".into()
                    } else {
                        "decoded_pixels_to_png".into()
                    },
                    Some(bytes),
                ),
                Err(message) => {
                    warnings.push(VisualWarning {
                        code: "preview_unsupported".into(),
                        message,
                    });
                    ("unsupported", None, None, false, "none".into(), None)
                }
            }
        } else {
            warnings.push(VisualWarning {
                code: "filter_unsupported".into(),
                message: format!(
                    "Preview is not supported for filters {}",
                    filters.join(", ")
                ),
            });
            ("unsupported", None, None, false, "none".into(), None)
        };
    let byte_length = bytes.as_ref().map(|value| value.len() as u64);
    let provenance_mime_type = mime_type.clone();
    let source_filter = filters.first().cloned();
    Ok(PreviewResult {
        asset: VisualAsset {
            id: format!("visual_{object_id}"),
            source_object_id: object_id.clone(),
            kind: if image_mask {
                "image_mask".into()
            } else {
                "image".into()
            },
            width,
            height,
            bits_per_component: bits,
            color_space,
            filters,
            mime_type,
            source_encoding: source_filter.clone(),
            preview_encoding: encoding,
            status: status.into(),
            preview_available: bytes.is_some(),
            reconstructed,
            image_mask,
            has_mask: mask_object_id.is_some(),
            mask_object_id,
            soft_mask_object_id,
            byte_length,
            warnings,
            provenance: PreviewProvenance {
                source_object_id: object_id,
                source_filter,
                transformation,
                reconstructed,
                mime_type: provenance_mime_type,
            },
        },
        bytes,
    })
}

pub fn composite_preview(
    document: &Document,
    id: ObjectId,
    limits: PreviewLimits,
) -> Result<Vec<u8>, String> {
    let main_stream = document
        .get_object(id)
        .ok()
        .and_then(|object| object.as_stream().ok())
        .ok_or("Main image stream not found")?;
    let mask_id = main_stream
        .dict
        .get(b"SMask")
        .ok()
        .and_then(|value| value.as_reference().ok())
        .ok_or("Image has no indirect /SMask")?;
    let (width, height) = dimensions(main_stream)?;
    let main = decoded_pixels(main_stream, limits)?;
    let mask_stream = document
        .get_object(mask_id)
        .ok()
        .and_then(|object| object.as_stream().ok())
        .ok_or("Soft mask stream not found")?;
    let (mask_width, mask_height) = dimensions(mask_stream)?;
    if (width, height) != (mask_width, mask_height) {
        return Err("Soft mask dimensions do not match the image".into());
    }
    if color_space(document, main_stream).as_deref() != Some("/DeviceRGB")
        || color_space(document, mask_stream).as_deref() != Some("/DeviceGray")
    {
        return Err("Composite preview currently requires DeviceRGB plus DeviceGray SMask".into());
    }
    let mask = decoded_pixels(mask_stream, limits)?;
    if main.len() != (width as usize) * (height as usize) * 3
        || mask.len() != (width as usize) * (height as usize)
    {
        return Err("Decoded image or mask length is inconsistent".into());
    }
    let mut rgba = Vec::with_capacity((width as usize) * (height as usize) * 4);
    for (pixel, alpha) in main.chunks_exact(3).zip(mask) {
        rgba.extend_from_slice(pixel);
        rgba.push(alpha);
    }
    encode_png(width, height, png::ColorType::Rgba, &rgba)
}

fn reconstruct_png(
    stream: &Stream,
    width: Option<u32>,
    height: Option<u32>,
    bits: Option<u8>,
    space: Option<&str>,
    image_mask: bool,
    limits: PreviewLimits,
) -> Result<Vec<u8>, String> {
    let width = width.ok_or("Image width is missing or invalid")?;
    let height = height.ok_or("Image height is missing or invalid")?;
    validate_dimensions(width, height, limits)?;
    if bits != Some(8) {
        return Err(format!(
            "Preview supports BitsPerComponent=8; found {:?}",
            bits
        ));
    }
    if let Some(predictor) = predictor(stream) {
        if predictor != 1 && !(10..=15).contains(&predictor) {
            return Err(format!("Preview does not support Predictor {predictor}"));
        }
    }
    let decoded = decoded_pixels(stream, limits)?;
    if image_mask {
        return Err("8-bit ImageMask preview is not supported".into());
    }
    match space {
        Some("/DeviceGray") => {
            validate_and_encode(width, height, 1, png::ColorType::Grayscale, &decoded)
        }
        Some("/DeviceRGB") => validate_and_encode(width, height, 3, png::ColorType::Rgb, &decoded),
        Some("/DeviceCMYK") => {
            let expected = checked_len(width, height, 4)?;
            if decoded.len() != expected {
                return Err(format!(
                    "Decoded CMYK length {} differs from expected {expected}",
                    decoded.len()
                ));
            }
            let mut rgb = Vec::with_capacity(checked_len(width, height, 3)?);
            for pixel in decoded.chunks_exact(4) {
                let c = pixel[0] as u16;
                let m = pixel[1] as u16;
                let y = pixel[2] as u16;
                let k = pixel[3] as u16;
                rgb.push(255u16.saturating_sub((c + k).min(255)) as u8);
                rgb.push(255u16.saturating_sub((m + k).min(255)) as u8);
                rgb.push(255u16.saturating_sub((y + k).min(255)) as u8);
            }
            encode_png(width, height, png::ColorType::Rgb, &rgb)
        }
        other => Err(format!(
            "Preview does not support ColorSpace {}",
            other.unwrap_or("missing")
        )),
    }
}

fn decoded_pixels(stream: &Stream, limits: PreviewLimits) -> Result<Vec<u8>, String> {
    stream
        .decompressed_content_with_limit(limits.max_decoded_bytes)
        .map_err(|error| format!("Unable to decode image stream: {error}"))
}
fn validate_and_encode(
    width: u32,
    height: u32,
    channels: usize,
    color: png::ColorType,
    data: &[u8],
) -> Result<Vec<u8>, String> {
    let expected = checked_len(width, height, channels)?;
    if data.len() != expected {
        return Err(format!(
            "Decoded pixel length {} differs from expected {expected}",
            data.len()
        ));
    }
    encode_png(width, height, color, data)
}
fn encode_png(
    width: u32,
    height: u32,
    color: png::ColorType,
    data: &[u8],
) -> Result<Vec<u8>, String> {
    let mut output = Vec::new();
    {
        let mut encoder = png::Encoder::new(&mut output, width, height);
        encoder.set_color(color);
        encoder.set_depth(png::BitDepth::Eight);
        let mut writer = encoder.write_header().map_err(|error| error.to_string())?;
        writer
            .write_image_data(data)
            .map_err(|error| error.to_string())?;
    }
    Ok(output)
}
fn validate_dimensions(width: u32, height: u32, limits: PreviewLimits) -> Result<(), String> {
    if width == 0 || height == 0 || width > limits.max_width || height > limits.max_height {
        return Err(format!(
            "Image dimensions {width}x{height} exceed configured limits"
        ));
    }
    let pixels = u64::from(width)
        .checked_mul(u64::from(height))
        .ok_or("Image pixel count overflow")?;
    if pixels > limits.max_pixels {
        return Err(format!(
            "Image pixel count {pixels} exceeds configured limit"
        ));
    }
    Ok(())
}
fn checked_len(width: u32, height: u32, channels: usize) -> Result<usize, String> {
    (width as usize)
        .checked_mul(height as usize)
        .and_then(|value| value.checked_mul(channels))
        .ok_or("Image byte length overflow".into())
}
fn dimensions(stream: &Stream) -> Result<(u32, u32), String> {
    Ok((
        u32::try_from(integer(stream, b"Width").ok_or("Missing Width")?)
            .map_err(|_| "Invalid Width")?,
        u32::try_from(integer(stream, b"Height").ok_or("Missing Height")?)
            .map_err(|_| "Invalid Height")?,
    ))
}
fn integer(stream: &Stream, key: &[u8]) -> Option<i64> {
    stream.dict.get(key).ok()?.as_i64().ok()
}
fn boolean(stream: &Stream, key: &[u8]) -> Option<bool> {
    stream.dict.get(key).ok()?.as_bool().ok()
}
fn name(stream: &Stream, key: &[u8]) -> Option<String> {
    stream
        .dict
        .get(key)
        .ok()?
        .as_name()
        .ok()
        .map(|value| String::from_utf8_lossy(value).into_owned())
}
fn reference(stream: &Stream, key: &[u8]) -> Option<String> {
    stream
        .dict
        .get(key)
        .ok()?
        .as_reference()
        .ok()
        .map(|id| format!("{}_{}", id.0, id.1))
}
fn color_space(document: &Document, stream: &Stream) -> Option<String> {
    color_space_object(document, stream.dict.get(b"ColorSpace").ok()?)
}
fn color_space_object(document: &Document, object: &Object) -> Option<String> {
    match object {
        Object::Name(value) => Some(format!("/{}", String::from_utf8_lossy(value))),
        Object::Reference(id) => document
            .get_object(*id)
            .ok()
            .and_then(|value| color_space_object(document, value)),
        Object::Array(items) => items
            .first()
            .and_then(|value| color_space_object(document, value)),
        other => Some(format!("{other:?}")),
    }
}
fn filters(stream: &Stream) -> Vec<String> {
    stream
        .filters()
        .unwrap_or_default()
        .into_iter()
        .map(|value| format!("/{}", String::from_utf8_lossy(&value)))
        .collect()
}
fn predictor(stream: &Stream) -> Option<i64> {
    match stream.dict.get(b"DecodeParms").ok()? {
        Object::Dictionary(dict) => dict.get(b"Predictor").ok()?.as_i64().ok(),
        Object::Array(items) => items
            .iter()
            .find_map(|item| item.as_dict().ok()?.get(b"Predictor").ok()?.as_i64().ok()),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use lopdf::{dictionary, Stream};

    fn limits() -> PreviewLimits {
        PreviewLimits {
            max_width: 100,
            max_height: 100,
            max_pixels: 10_000,
            max_decoded_bytes: 1024 * 1024,
        }
    }
    fn image_document(
        space: &str,
        pixels: Vec<u8>,
        width: i64,
        height: i64,
    ) -> (Document, ObjectId) {
        let mut document = Document::with_version("1.7");
        let mut stream = Stream::new(
            dictionary! { "Type" => "XObject", "Subtype" => "Image", "Width" => width, "Height" => height, "BitsPerComponent" => 8, "ColorSpace" => space },
            pixels,
        );
        stream.compress().unwrap();
        let id = document.add_object(stream);
        (document, id)
    }
    fn decode_png(bytes: &[u8]) -> (png::OutputInfo, Vec<u8>) {
        let decoder = png::Decoder::new(std::io::Cursor::new(bytes));
        let mut reader = decoder.read_info().unwrap();
        let mut output = vec![0; reader.output_buffer_size().unwrap()];
        let info = reader.next_frame(&mut output).unwrap();
        output.truncate(info.buffer_size());
        (info, output)
    }

    #[test]
    fn dct_preview_is_byte_preserving_and_direct() {
        let mut document = Document::with_version("1.7");
        let jpeg = b"\xff\xd8\xffsynthetic-jpeg\xff\xd9".to_vec();
        let id = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Image", "Width" => 1, "Height" => 1, "BitsPerComponent" => 8, "ColorSpace" => "DeviceRGB", "Filter" => "DCTDecode" }, jpeg.clone()));
        let result = visual_asset(&document, id, limits()).unwrap();
        assert_eq!(result.bytes.unwrap(), jpeg);
        assert_eq!(result.asset.status, "direct");
        assert!(!result.asset.reconstructed);
        assert_eq!(result.asset.mime_type.as_deref(), Some("image/jpeg"));
    }

    #[test]
    fn flate_rgb_and_gray_reconstruct_png() {
        for (space, pixels, expected_color) in [
            ("DeviceRGB", [255, 0, 0].repeat(32), png::ColorType::Rgb),
            ("DeviceGray", vec![127; 32], png::ColorType::Grayscale),
        ] {
            let (document, id) = image_document(space, pixels.clone(), 32, 1);
            let result = visual_asset(&document, id, limits()).unwrap();
            assert_eq!(result.asset.filters, vec!["/FlateDecode"]);
            let bytes = result.bytes.unwrap();
            let (info, decoded) = decode_png(&bytes);
            assert_eq!(info.color_type, expected_color);
            assert_eq!(decoded, pixels);
            assert_eq!(result.asset.status, "reconstructed");
            assert!(result.asset.reconstructed);
        }
    }

    #[test]
    fn flate_cmyk_has_documented_rgb_preview_conversion() {
        let (document, id) = image_document("DeviceCMYK", [0, 255, 255, 0].repeat(32), 32, 1);
        let result = visual_asset(&document, id, limits()).unwrap();
        let (_, decoded) = decode_png(&result.bytes.unwrap());
        assert_eq!(decoded, [255, 0, 0].repeat(32));
        assert_eq!(result.asset.provenance.transformation, "cmyk_to_rgb_png");
    }

    #[test]
    fn soft_mask_is_separate_and_composite_is_rgba() {
        let (mut document, mask_id) = image_document("DeviceGray", vec![128], 1, 1);
        let mut main = Stream::new(
            dictionary! { "Type" => "XObject", "Subtype" => "Image", "Width" => 1, "Height" => 1, "BitsPerComponent" => 8, "ColorSpace" => "DeviceRGB", "SMask" => mask_id },
            vec![10, 20, 30],
        );
        main.compress().unwrap();
        let main_id = document.add_object(main);
        let main_asset = visual_asset(&document, main_id, limits()).unwrap().asset;
        assert_eq!(
            main_asset.soft_mask_object_id,
            Some(format!("{}_{}", mask_id.0, mask_id.1))
        );
        assert!(visual_asset(&document, mask_id, limits())
            .unwrap()
            .bytes
            .is_some());
        let (_, rgba) = decode_png(&composite_preview(&document, main_id, limits()).unwrap());
        assert_eq!(rgba, vec![10, 20, 30, 128]);
    }

    #[test]
    fn unsupported_bits_and_excessive_dimensions_return_no_preview() {
        let mut document = Document::with_version("1.7");
        let id = document.add_object(Stream::new(dictionary! { "Type" => "XObject", "Subtype" => "Image", "Width" => 101, "Height" => 1, "BitsPerComponent" => 4, "ColorSpace" => "DeviceGray" }, vec![0]));
        let result = visual_asset(&document, id, limits()).unwrap();
        assert!(result.bytes.is_none());
        assert_eq!(result.asset.status, "unsupported");
        assert!(!result.asset.warnings.is_empty());
    }

    #[test]
    fn predictor_one_is_supported_and_unknown_predictor_fails_safely() {
        let (mut document, id) = image_document("DeviceRGB", vec![1, 2, 3], 1, 1);
        document.get_object_mut(id).unwrap().as_stream_mut().unwrap().dict.set("DecodeParms", dictionary! { "Predictor" => 1, "Colors" => 3, "Columns" => 1, "BitsPerComponent" => 8 });
        assert!(visual_asset(&document, id, limits())
            .unwrap()
            .bytes
            .is_some());
        document
            .get_object_mut(id)
            .unwrap()
            .as_stream_mut()
            .unwrap()
            .dict
            .set("DecodeParms", dictionary! { "Predictor" => 99 });
        let result = visual_asset(&document, id, limits()).unwrap();
        assert!(result.bytes.is_none());
        assert_eq!(result.asset.status, "unsupported");
    }

    #[test]
    fn png_predictor_twelve_is_decoded_before_preview() {
        let mut document = Document::with_version("1.7");
        let mut predicted = vec![0];
        predicted.extend(vec![7; 300]);
        let mut stream = Stream::new(
            dictionary! { "Type" => "XObject", "Subtype" => "Image", "Width" => 100, "Height" => 1, "BitsPerComponent" => 8, "ColorSpace" => "DeviceRGB" },
            predicted,
        );
        stream.compress().unwrap();
        stream.dict.set("DecodeParms", dictionary! { "Predictor" => 12, "Colors" => 3, "Columns" => 100, "BitsPerComponent" => 8 });
        let id = document.add_object(stream);
        let result = visual_asset(&document, id, limits()).unwrap();
        assert!(result.bytes.is_some(), "{:?}", result.asset.warnings);
        let (_, pixels) = decode_png(&result.bytes.unwrap());
        assert_eq!(pixels, vec![7; 300]);
    }

    #[test]
    fn decoded_byte_limit_is_enforced() {
        let (document, id) = image_document("DeviceRGB", vec![0; 300], 10, 10);
        let mut constrained = limits();
        constrained.max_decoded_bytes = 16;
        let result = visual_asset(&document, id, constrained).unwrap();
        assert!(result.bytes.is_none());
    }
}
