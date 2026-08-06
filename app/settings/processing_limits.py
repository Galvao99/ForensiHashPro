from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class ProcessingLimits:
    max_file_size_bytes: int = 2 * 1024 * 1024 * 1024
    max_pdf_pages: int = 1000
    max_image_width: int = 30_000
    max_image_height: int = 30_000
    max_image_pixels: int = 100_000_000
    max_estimated_memory_bytes: int = 1024 * 1024 * 1024
    ocr_timeout_seconds: int = 120
    external_tool_timeout_seconds: int = 60
    max_external_output_bytes: int = 10 * 1024 * 1024
    max_pdf_objects: int = 1_000_000
    max_binary_strings: int = 1000
    max_archive_depth: int = 10
    max_archive_entries: int = 10_000
    max_expanded_bytes: int = 4 * 1024 * 1024 * 1024

    def validate(self) -> None:
        for item in fields(self):
            name = item.name
            value = getattr(self, name)
            if value <= 0:
                raise ValueError(f"{name} deve ser maior que zero.")
