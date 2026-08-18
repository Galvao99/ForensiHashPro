from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt

from app.deep_structure.models import ObjectRecord, StructureReport


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

    def add(self, node: StructureTreeNode) -> StructureTreeNode:
        node.parent = self
        self.children.append(node)
        return node


class StructureTreeModel(QAbstractItemModel):
    NodeRole = Qt.UserRole + 1
    SearchRole = Qt.UserRole + 2

    def __init__(self, report: StructureReport | None = None) -> None:
        super().__init__()
        self.report = report
        self.root = StructureTreeNode("root", "root")
        self._object_nodes: dict[str, list[StructureTreeNode]] = {}
        if report is not None:
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
        pdf = self.root.add(StructureTreeNode(f"PDF {report.physical.pdf_version or ''}".strip(), "pdf"))
        pdf.add(StructureTreeNode("Header", "properties", payload=report.physical))
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
        self._add_collection(pdf, "Embedded Files", "embedded", report.embedded_files, "filename")
        self._add_collection(pdf, "Metadata", "metadata", report.metadata_streams, "subtype")
        self._add_collection(pdf, "Annotations", "annotation", report.annotations, "subtype")
        signatures = self._add_collection(pdf, "Signatures", "signature", report.signatures, None)
        if signatures.children:
            signatures.children[0].label += " — dados exclusivamente estruturais"
        occurrences = pdf.add(StructureTreeNode(f"Occurrences ({len(report.occurrences)})", "occurrences"))
        for item in report.occurrences:
            occurrences.add(StructureTreeNode(f"{item['name']}  {item['count']}", "occurrence", payload=item))

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
        self._track(node)

    def _object_node(self, record: ObjectRecord) -> StructureTreeNode:
        details = record.subtype or record.object_type
        node = StructureTreeNode(
            f"{self.reference_label(record.id)} — {details}", "object", record.id, record,
        )
        self._track(node)
        return node

    def _reference_node(self, label: str, object_id: str, kind: str) -> StructureTreeNode:
        node = StructureTreeNode(self._with_ref(label, object_id), kind, object_id)
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
