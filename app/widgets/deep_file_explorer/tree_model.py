from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from app.deep_structure.models import JpegStructureReport, ObjectRecord, StructureReport


@dataclass(slots=True)
class StructureTreeNode:
    label: str
    kind: str
    object_id: str | None = None
    payload: Any = None
    parent: StructureTreeNode | None = None
    children: list[StructureTreeNode] = field(default_factory=list)
    lazy_kind: str | None = None
    loaded: bool = True
    id: str = ""
    segment_index: int | None = None
    path: str | None = None
    preview_asset_id: str | None = None
    capabilities: frozenset[str] = frozenset({"summary"})

    def add(self, node: StructureTreeNode) -> StructureTreeNode:
        node.parent = self
        if not node.id:
            node.id = f"{self.id}/{node.kind}:{len(self.children)}"
        self.children.append(node)
        return node


class StructureTreeModel(QAbstractItemModel):
    NodeRole = Qt.UserRole + 1
    SearchRole = Qt.UserRole + 2

    def __init__(self, report: StructureReport | JpegStructureReport | None = None) -> None:
        super().__init__()
        self.report = report
        self.root = StructureTreeNode("root", "root", id="root")
        self._object_nodes: dict[str, list[StructureTreeNode]] = {}
        if report is not None:
            if isinstance(report, JpegStructureReport):
                self._build_jpeg(report)
            else:
                self._build(report)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        node = self._node(parent)
        return len(node.children)

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        parent_node = self._node(parent)
        if row < 0 or row >= len(parent_node.children) or column != 0:
            return QModelIndex()
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node: StructureTreeNode = index.internalPointer()
        parent = node.parent
        if parent is None or parent is self.root or parent.parent is None:
            return QModelIndex()
        return self.createIndex(parent.parent.children.index(parent), 0, parent)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid():
            return None
        node: StructureTreeNode = index.internalPointer()
        if role == Qt.DisplayRole:
            return node.label
        if role == self.NodeRole:
            return node
        if role == self.SearchRole:
            return f"{node.label} {node.kind} {node.object_id or ''}"
        if role == Qt.ToolTipRole and node.object_id:
            return f"Objeto PDF {self.reference_label(node.object_id)}"
        return None

    def canFetchMore(self, parent: QModelIndex) -> bool:
        node = self._node(parent)
        return node.lazy_kind is not None and not node.loaded

    def fetchMore(self, parent: QModelIndex) -> None:
        node = self._node(parent)
        if node.lazy_kind != "objects" or node.loaded or self.report is None:
            return
        objects = list(self.report.objects)
        if objects:
            self.beginInsertRows(parent, 0, len(objects) - 1)
            for record in objects:
                child = self._object_node(record)
                child.parent = node
                node.children.append(child)
            node.loaded = True
            self.endInsertRows()
        else:
            node.loaded = True

    def node_from_index(self, index: QModelIndex) -> StructureTreeNode | None:
        return index.internalPointer() if index.isValid() else None

    def indexes_for_object(self, object_id: str) -> list[QModelIndex]:
        return [self._index_for_node(node) for node in self._object_nodes.get(object_id, [])]

    def index_for_node_id(self, node_id: str) -> QModelIndex:
        return next((self._index_for_node(node) for node in self._walk(self.root) if node.id == node_id), QModelIndex())

    def page_index(self, page_number: int) -> QModelIndex:
        for node in self._walk(self.root):
            if node.kind == "page" and node.payload.get("page_number") == page_number:
                return self._index_for_node(node)
        return QModelIndex()

    @staticmethod
    def reference_label(object_id: str) -> str:
        parts = object_id.split("_")
        return f"{parts[0]} {parts[1]} R" if len(parts) == 2 else object_id

    def _build(self, report: StructureReport) -> None:
        pdf = self.root.add(StructureTreeNode(f"PDF {report.physical.pdf_version or ''}".strip(), "pdf", id="pdf"))
        physical = pdf.add(StructureTreeNode("Physical Structure", "physical", payload=report.physical))
        physical.add(StructureTreeNode("Header and version", "properties", payload=report.physical))
        physical.add(StructureTreeNode("startxref", "properties", payload={"offsets": report.physical.startxref_offsets}))
        physical.add(StructureTreeNode("EOF markers", "properties", payload={"count": report.physical.eof_count,
                                                                              "offsets": report.physical.eof_offsets}))
        physical.add(StructureTreeNode("Trailing bytes", "properties",
                                       payload={"length": report.physical.bytes_after_last_eof}))
        pdf.add(StructureTreeNode("Trailer", "properties", payload=report.trailer))
        catalog_id = report.catalog.get("object_id")
        pdf.add(StructureTreeNode(self._with_ref("Catalog", catalog_id), "catalog", catalog_id, report.catalog))

        pages_parent = pdf.add(StructureTreeNode(f"Pages ({report.summary.page_count})", "pages"))
        pages = report.page_tree.get("pages", [])
        for page in pages:
            page_id = page.get("object_id")
            page_node = pages_parent.add(StructureTreeNode(
                self._with_ref(f"Page {page.get('page_number', len(pages_parent.children) + 1)}", page_id),
                "page", page_id, page,
            ))
            page_node.add(StructureTreeNode("Properties", "properties", page_id, page))
            contents = page_node.add(StructureTreeNode(
                f"Contents ({len(page.get('content_object_ids', []))})", "contents", payload=page,
            ))
            for content_id in page.get("content_object_ids", []):
                contents.add(self._reference_node("Content Stream", content_id, "stream"))
            resources = page_node.add(StructureTreeNode("Resources", "resources", page_id, page))
            self._add_page_resources(resources, page_id, report)
            page_annotations = [a for a in report.annotations if page_id in a.get("page_object_ids", [])]
            annots = page_node.add(StructureTreeNode(f"Annotations ({len(page_annotations)})", "annotations"))
            for annotation in page_annotations:
                self._add_record(annots, annotation.get("subtype") or "Annotation", "annotation", annotation)

        objects = pdf.add(StructureTreeNode(
            f"Objects ({report.summary.object_count})", "objects", lazy_kind="objects", loaded=False,
        ))
        objects.children.clear()
        visual = pdf.add(StructureTreeNode(f"Visual Assets ({len(report.previewable_assets)})", "visual_assets"))
        for asset in report.previewable_assets:
            object_id = asset.get("object_id")
            node = visual.add(StructureTreeNode(
                self._with_ref(asset.get("kind", "Asset").title(), object_id), "resource_image",
                object_id, asset, preview_asset_id=object_id,
                capabilities=frozenset({"summary", "preview", "raw", "hex"}),
            ))
            self._track(node)
        self._add_collection(pdf, "Embedded Files", "embedded", report.embedded_files, "filename")
        self._add_collection(pdf, "Metadata", "metadata", report.metadata_streams, "subtype")
        self._add_collection(pdf, "Annotations", "annotation", report.annotations, "subtype")
        signatures = self._add_collection(pdf, "Signatures", "signature", report.signatures, None)
        if signatures.children:
            signatures.children[0].label += " — dados exclusivamente estruturais"
        occurrences = pdf.add(StructureTreeNode(f"Occurrences ({len(report.occurrences)})", "occurrences"))
        for item in report.occurrences:
            occurrences.add(StructureTreeNode(f"{item['name']}  {item['count']}", "occurrence", payload=item))

    def _build_jpeg(self, report: JpegStructureReport) -> None:
        physical = report.physical_info
        jpeg = self.root.add(StructureTreeNode("JPEG", "jpeg", id="jpeg"))
        physical_node = jpeg.add(StructureTreeNode("Physical Structure", "physical", payload=physical))
        for label, payload in (
            ("File Size", {"bytes": physical.file_size}), ("SOI", {"offset": physical.soi_offset}),
            ("EOI", {"offset": physical.eoi_offset}),
        ):
            physical_node.add(StructureTreeNode(label, "properties", payload=payload))
        trailing_caps = {"summary"}
        if physical.trailing_bytes_length:
            trailing_caps.update({"raw", "hex"})
        physical_node.add(StructureTreeNode(
            f"Trailing Bytes ({physical.trailing_bytes_length})", "jpeg_trailing", payload={
                "offset": physical.trailing_bytes_offset, "length": physical.trailing_bytes_length,
            }, capabilities=frozenset(trailing_caps), id="jpeg/trailing",
        ))

        segments_node = jpeg.add(StructureTreeNode(f"Segments ({len(report.segments)})", "jpeg_segments"))
        scans_by_sos = {scan.get("sos_segment_index"): scan for scan in report.scans}
        for segment in report.segments:
            qualifier = ""
            metadata = segment.metadata or {}
            if metadata.get("identifier"):
                qualifier = f" — {metadata['identifier']}"
            elif metadata.get("kind"):
                qualifier = f" — {str(metadata['kind']).upper()}"
            node = segments_node.add(StructureTreeNode(
                f"#{segment.index} {segment.marker_name}{qualifier}", "jpeg_segment", payload=segment,
                segment_index=segment.index, path=f"Segments/{segment.index}", id=f"jpeg/segment/{segment.index}",
                capabilities=frozenset({"summary", "raw", "hex"}),
            ))
            scan = scans_by_sos.get(segment.index)
            if scan is not None:
                node.add(StructureTreeNode(
                    f"Scan Data #{scan['index']} ({scan['data_length']} bytes)", "jpeg_scan", payload=scan,
                    path=f"Scans/{scan['index']}", id=f"jpeg/scan/{scan['index']}",
                    capabilities=frozenset({"summary", "raw", "hex"}),
                ))
            self._add_jpeg_segment_details(node, segment.index, report)

        self._jpeg_collection(jpeg, "Frames", "jpeg_frame", report.frames)
        scans = self._jpeg_collection(jpeg, "Scans", "jpeg_scan", report.scans)
        for index, node in enumerate(scans.children):
            node.id = f"jpeg/scans/{index}"; node.capabilities = frozenset({"summary", "raw", "hex"})

        exif_root = jpeg.add(StructureTreeNode(f"EXIF ({len(report.exif)})", "jpeg_exif_group"))
        for block_index, block in enumerate(report.exif):
            block_node = exif_root.add(StructureTreeNode(
                f"APP1 / EXIF #{block_index}", "jpeg_exif", payload=block,
                segment_index=block.get("segment_index"), id=f"jpeg/exif/{block_index}",
            ))
            block_node.add(StructureTreeNode("TIFF Header", "properties", payload={
                "byte_order": block.get("byte_order"), "tiff_offset": block.get("tiff_offset"),
            }))
            for ifd in block.get("ifds", []):
                ifd_node = block_node.add(StructureTreeNode(
                    ifd.get("kind", "IFD"), "jpeg_exif_ifd", payload=ifd,
                    segment_index=block.get("segment_index"), path=ifd.get("kind"),
                    id=f"jpeg/exif/{block_index}/ifd/{ifd.get('id', ifd.get('kind'))}",
                ))
                for entry in ifd.get("entries", []):
                    name = entry.get("tag_name") or f"0x{entry.get('tag_id', 0):04X}"
                    entry_payload = {**entry, "ifd": ifd.get("kind"),
                                     "segment_index": block.get("segment_index")}
                    target_kind = {0x8769: "ExifIFD", 0x8825: "GPSIFD", 0xA005: "InteroperabilityIFD"}.get(
                        entry.get("tag_id")
                    )
                    if target_kind:
                        entry_payload["structural_target_id"] = f"jpeg/exif/{block_index}/ifd/{target_kind}"
                    ifd_node.add(StructureTreeNode(
                        name, "jpeg_exif_entry", payload=entry_payload,
                        segment_index=block.get("segment_index"), path=entry.get("path"),
                        id=f"{ifd_node.id}/tag/{entry.get('tag_id')}", capabilities=frozenset({"summary", "decoded"}),
                    ))

        xmp_root = self._jpeg_collection(jpeg, "XMP", "jpeg_xmp", report.xmp)
        for index, node in enumerate(xmp_root.children):
            node.id=f"jpeg/xmp/{index}"; node.capabilities=frozenset({"summary", "raw", "text", "hex"})
        icc_root = self._jpeg_collection(jpeg, "ICC", "jpeg_icc_chunk", report.icc)
        if icc_root.children:
            icc_root.capabilities=frozenset({"summary", "raw", "hex"}); icc_root.id="jpeg/icc/profile"
        assets = jpeg.add(StructureTreeNode(f"Visual Assets ({len(report.visual_assets)})", "jpeg_assets"))
        for asset in report.visual_assets:
            assets.add(StructureTreeNode(
                asset.get("kind", "Visual Asset"), "jpeg_asset", payload=asset,
                preview_asset_id=asset.get("id"), id=f"jpeg/asset/{asset.get('id')}",
                capabilities=frozenset({"summary", "preview", "raw", "hex"}),
            ))
        comments = self._jpeg_collection(jpeg, "Comments", "jpeg_comment", report.comments)
        for node in comments.children: node.capabilities=frozenset({"summary", "text"})
        self._jpeg_collection(jpeg, "Warnings", "jpeg_warning", report.warnings)

    def _add_jpeg_segment_details(self, parent: StructureTreeNode, segment_index: int,
                                  report: JpegStructureReport) -> None:
        for label, kind, records in (
            ("Quantization Tables", "jpeg_dqt", report.quantization_tables),
            ("Huffman Tables", "jpeg_dht", report.huffman_tables),
            ("Frames", "jpeg_frame", report.frames),
        ):
            selected = [item for item in records if item.get("segment_index") == segment_index]
            if selected:
                group = parent.add(StructureTreeNode(f"{label} ({len(selected)})", f"{kind}_group"))
                for index, item in enumerate(selected):
                    table_id = item.get("table_id", index)
                    group.add(StructureTreeNode(f"{label.rstrip('s')} {table_id}", kind, payload=item))
        for index, block in enumerate(report.exif):
            if block.get("segment_index") == segment_index:
                parent.add(StructureTreeNode("EXIF structure →", "structural_link",
                                             payload={"structural_target_id": f"jpeg/exif/{index}"}))
        for index, packet in enumerate(report.xmp):
            if packet.get("segment_index") == segment_index:
                parent.add(StructureTreeNode("XMP packet →", "structural_link",
                                             payload={"structural_target_id": f"jpeg/xmp/{index}"}))
        if any(chunk.get("segment_index") == segment_index for chunk in report.icc):
            parent.add(StructureTreeNode("ICC profile →", "structural_link",
                                         payload={"structural_target_id": "jpeg/icc/profile"}))

    def _jpeg_collection(self, parent: StructureTreeNode, title: str, kind: str,
                         records: tuple[Any, ...]) -> StructureTreeNode:
        group = parent.add(StructureTreeNode(f"{title} ({len(records)})", f"{kind}_group"))
        for index, record in enumerate(records):
            payload = record if isinstance(record, dict) else record
            group.add(StructureTreeNode(f"{title.rstrip('s')} #{index}", kind, payload=payload,
                                        id=f"jpeg/{kind}/{index}"))
        return group

    def _add_page_resources(self, parent: StructureTreeNode, page_id: str, report: StructureReport) -> None:
        usages = [item for item in report.visual_resources if item.get("page_object_id") == page_id]
        images = parent.add(StructureTreeNode("Images", "resource_group"))
        forms = parent.add(StructureTreeNode("Forms", "resource_group"))
        other = parent.add(StructureTreeNode("Other", "resource_group"))
        roots = [item for item in usages if item.get("container_object_id") == page_id]
        for usage in roots:
            target = forms if usage.get("kind") == "form" else images if usage.get("kind") in {"image", "thumbnail"} else other
            self._add_visual_usage(target, usage, usages, report, set())
        for group in (images, forms, other):
            if not group.children:
                parent.children.remove(group)

    def _add_visual_usage(self, parent: StructureTreeNode, usage: dict[str, Any],
                          usages: list[dict[str, Any]], report: StructureReport,
                          ancestors: set[str]) -> None:
        object_id = usage["object_id"]
        status = "invoked" if usage.get("invoked_by_do") else "declared"
        label = f"/{usage.get('resource_name', '?')} → {self.reference_label(object_id)}  [{status}]"
        node = parent.add(StructureTreeNode(label, f"resource_{usage.get('kind', 'unknown')}", object_id, usage))
        node.path = usage.get("path")
        caps = {"summary", "raw", "hex"}
        if usage.get("kind") in {"image", "thumbnail"}:
            caps.add("preview"); node.preview_asset_id = object_id
        if usage.get("kind") == "form":
            caps.add("decoded")
        node.capabilities = frozenset(caps)
        self._track(node)
        if usage.get("kind") in {"image", "thumbnail"}:
            image = next((item for item in report.images if item.get("object_id") == object_id), None)
            if image:
                for key, child_label in (("mask", "Mask"), ("soft_mask", "SMask")):
                    mask_id = image.get(key)
                    if mask_id and "_" in str(mask_id):
                        node.add(self._reference_node(child_label, str(mask_id), "resource_mask"))
        if usage.get("kind") != "form":
            return
        form = next((item for item in report.forms if item.get("object_id") == object_id), None)
        if form:
            node.add(StructureTreeNode("Properties", "properties", object_id, form))
            node.add(StructureTreeNode("Content Stream", "stream", object_id, form))
        if object_id in ancestors:
            node.add(StructureTreeNode(f"↗ Referência cíclica para {self.reference_label(object_id)}", "reference", object_id))
            return
        nested = [item for item in usages if item.get("container_object_id") == object_id]
        if nested:
            resources = node.add(StructureTreeNode("Resources", "resources", object_id))
            next_ancestors = ancestors | {object_id}
            for child in nested:
                self._add_visual_usage(resources, child, usages, report, next_ancestors)

    def _add_collection(self, parent: StructureTreeNode, title: str, kind: str,
                        records: tuple[dict[str, Any], ...], name_key: str | None) -> StructureTreeNode:
        container = parent.add(StructureTreeNode(f"{title} ({len(records)})", f"{kind}_group"))
        for record in records:
            name = str(record.get(name_key) or kind.title()) if name_key else kind.title()
            self._add_record(container, name, kind, record)
        return container

    def _add_record(self, parent: StructureTreeNode, name: str, kind: str, record: dict[str, Any]) -> None:
        object_id = record.get("object_id")
        node = parent.add(StructureTreeNode(self._with_ref(name, object_id), kind, object_id, record))
        capabilities = {"summary", "raw", "hex"} if object_id else {"summary"}
        if kind == "metadata": capabilities.update({"decoded", "text"})
        if kind == "embedded": capabilities.update({"decoded", "text"})
        node.capabilities = frozenset(capabilities)
        self._track(node)

    def _object_node(self, record: ObjectRecord) -> StructureTreeNode:
        details = record.subtype or record.object_type
        node = StructureTreeNode(
            f"{self.reference_label(record.id)} — {details}", "object", record.id, record,
        )
        capabilities = {"summary", "raw", "hex"}
        if record.is_stream: capabilities.add("decoded")
        if record.subtype == "Image": capabilities.add("preview"); node.preview_asset_id = record.id
        node.capabilities = frozenset(capabilities)
        node.id = f"pdf/object/{record.id}"
        self._track(node)
        return node

    def _reference_node(self, label: str, object_id: str, kind: str) -> StructureTreeNode:
        node = StructureTreeNode(self._with_ref(label, object_id), kind, object_id)
        caps = {"summary", "raw", "hex"}
        if kind in {"stream", "resource_mask"}: caps.add("decoded")
        node.capabilities = frozenset(caps)
        node.id = f"pdf/reference/{kind}/{object_id}/{len(self._object_nodes.get(object_id, []))}"
        self._track(node)
        return node

    def _track(self, node: StructureTreeNode) -> None:
        if node.object_id:
            self._object_nodes.setdefault(node.object_id, []).append(node)

    def _with_ref(self, label: str, object_id: str | None) -> str:
        return f"{label} [{self.reference_label(object_id)}]" if object_id else label

    def _node(self, index: QModelIndex) -> StructureTreeNode:
        return index.internalPointer() if index.isValid() else self.root

    def _index_for_node(self, node: StructureTreeNode) -> QModelIndex:
        if node.parent is None or node.parent is self.root:
            return QModelIndex()
        return self.createIndex(node.parent.children.index(node), 0, node)

    def _walk(self, node: StructureTreeNode):
        for child in node.children:
            yield child
            yield from self._walk(child)
