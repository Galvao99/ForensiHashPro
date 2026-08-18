"""Local diagnostic dump for the public Deep File Structure API."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.deep_structure import DeepFileStructureEngine  # noqa: E402


def _summary(report: object) -> str:
    physical = report.physical
    summary = report.summary
    return "\n".join(
        (
            f"Format: {report.format}",
            f"Version: {physical.pdf_version or 'unknown'}",
            f"Size: {physical.file_size:,} bytes",
            "",
            f"Objects: {summary.object_count}",
            f"Pages: {summary.page_count}",
            f"Streams: {summary.stream_count}",
            f"Unique image objects: {summary.unique_image_objects}",
            f"Image references: {summary.image_references}",
            f"Unique font objects: {summary.unique_font_objects}",
            f"Font references: {summary.font_references}",
            f"Annotations: {summary.annotation_count}",
            f"Embedded files: {summary.embedded_file_count}",
            f"Signature dictionaries: {summary.signature_dictionary_count}",
            f"Visual resource references: {summary.visual_resource_references}",
            f"Invoked XObject usages: {summary.invoked_xobject_usages}",
            "",
            f"EOF markers: {physical.eof_count}",
            f"Bytes after final EOF: {physical.bytes_after_last_eof}",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump a neutral PDF StructureReport")
    parser.add_argument("pdf", type=Path, help="Local PDF path")
    parser.add_argument("--output", type=Path, help="Write readable JSON to this path")
    parser.add_argument("--summary", action="store_true", help="Print only structural counts")
    arguments = parser.parse_args()

    report = DeepFileStructureEngine().analyze_pdf(arguments.pdf).report
    if arguments.summary:
        rendered = _summary(report)
    else:
        rendered = json.dumps(asdict(report), ensure_ascii=False, indent=2)
    if arguments.output:
        arguments.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
