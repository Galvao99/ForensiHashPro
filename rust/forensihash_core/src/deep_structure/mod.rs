mod models;
mod pdf;
mod visual;

pub use models::*;
pub use pdf::PdfStructureParser;
pub use visual::{composite_preview, visual_asset, PreviewLimits};

use std::path::Path;

pub trait StructureParser {
    fn supports(&self, data: &[u8]) -> bool;
    fn parse(&self, path: &Path, data: &[u8]) -> Result<ParsedStructure, StructureError>;
}

#[derive(Debug)]
pub struct StructureError(pub String);

impl std::fmt::Display for StructureError {
    fn fmt(&self, formatter: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        formatter.write_str(&self.0)
    }
}

impl std::error::Error for StructureError {}
