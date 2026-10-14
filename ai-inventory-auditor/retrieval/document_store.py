"""Mô hình tài liệu, chia đoạn và nạp tệp chính sách từ ổ đĩa."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# Mô hình tài liệu
@dataclass
class Document:
    content: str
    doc_id: str = ""
    title: str = ""
    source: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


# Mô hình đoạn tài liệu
@dataclass
class DocumentChunk:
    content: str
    chunk_id: str = ""
    doc_id: str = ""
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None


# Chia tài liệu thành các đoạn
def chunk_document(
    doc: Document,
    chunk_size: int = 150,
    overlap: int = 30
) -> list[DocumentChunk]:
    

    """Chia văn bản tài liệu thành các đoạn có độ dài cố định và phần chồng lặp."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size - 1")

    chunks = []
    text = doc.content
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        chunk = DocumentChunk(
            content=text[start:end],
            chunk_id=f"{doc.doc_id}_chunk_{len(chunks)}",
            doc_id=doc.doc_id,
            chunk_index=len(chunks),
            metadata={
                **doc.metadata,
                "title": doc.title,
                "source": doc.source,
                "chunk_size": chunk_size,
                "overlap": overlap,
            }
        )

        chunks.append(chunk)

        start += chunk_size - overlap

        if start >= len(text):
            break

    return chunks


# Kho lưu trữ tài liệu
@dataclass
class DocumentStore:
    documents: dict[str, Document] = field(default_factory=dict)
    chunks: dict[str, DocumentChunk] = field(default_factory=dict)
    chunk_size: int = 150
    overlap: int = 30

    # Thêm tài liệu
    def add(self, document: Document) -> str:
        if not document.doc_id:
            document.doc_id = f"doc_{len(self.documents) + 1:04d}"

        self.documents[document.doc_id] = document

        chunks = chunk_document(
            document,
            chunk_size=self.chunk_size,
            overlap=self.overlap,
        )

        for chunk in chunks:
            self.add_chunk(chunk)

        return document.doc_id

    # Lấy tài liệu
    def get(self, doc_id: str) -> Optional[Document]:
        return self.documents.get(doc_id)

    # Xóa tài liệu
    def delete(self, doc_id: str) -> bool:

        if doc_id in self.documents:
            del self.documents[doc_id]

            chunk_ids = [
                chunk_id
                for chunk_id, chunk in self.chunks.items()
                if chunk.doc_id == doc_id
            ]

            for chunk_id in chunk_ids:
                del self.chunks[chunk_id]

            return True

        return False

    # Liệt kê tài liệu
    def list_all(self) -> list[Document]:
        return list(self.documents.values())

    # Thêm đoạn tài liệu
    def add_chunk(self, chunk: DocumentChunk) -> str:
        if not chunk.chunk_id:
            chunk.chunk_id = f"chunk_{len(self.chunks) + 1:04d}"

        self.chunks[chunk.chunk_id] = chunk

        return chunk.chunk_id

    # Lấy đoạn tài liệu
    def get_chunk(self, chunk_id: str) -> Optional[DocumentChunk]:
        return self.chunks.get(chunk_id)

    # Lấy các đoạn của một tài liệu
    def get_chunks_by_doc(self, doc_id: str) -> list[DocumentChunk]:

        return [
            chunk
            for chunk in self.chunks.values()
            if chunk.doc_id == doc_id
        ]

    # Đếm số lượng
    def count(self) -> dict:
        return {
            "documents": len(self.documents),
            "chunks": len(self.chunks),
        }

    
# Hàm nạp tệp
    @classmethod
    def from_directory(
        cls,
        directory: str | Path,
        chunk_size: int = 150,
        overlap: int = 30,
    ) -> "DocumentStore":
        
        """Nạp các tệp chính sách .txt và đọc phần metadata đầu tệp nếu có."""
        path = Path(directory)
        if not path.is_dir():
            raise FileNotFoundError(f"Document directory does not exist: {path}")

        store = cls(chunk_size=chunk_size, overlap=overlap)

        for file_path in sorted(path.glob("*.txt")):
            raw_text = file_path.read_text(encoding="utf-8-sig")
            header = {}
            lines = raw_text.splitlines()
            body_start = 0

            for line_number, line in enumerate(lines):
                match = re.match(r"^\s*([A-Z_]+)\s*:\s*(.*?)\s*$", line)
                if match and match.group(1) in {
                    "DOC_ID", "TITLE", "VERSION", "DATE", "OWNER"
                }:
                    header[match.group(1).lower()] = match.group(2)
                    body_start = line_number + 1
                elif not line.strip() and not header:
                    body_start = line_number + 1
                else:
                    break

            content = (
                "\n".join(lines[body_start:]).strip()
                if header
                else raw_text.strip()
            )

            document = Document(
                content=content,
                doc_id=header.get("doc_id", file_path.stem),
                title=header.get("title", file_path.stem),
                source=str(file_path),
                metadata={
                    key: value
                    for key, value in header.items()
                    if key not in {"doc_id", "title"}
                },
            )
            store.add(document)

        return store


# Hàm nạp các tệp .txt
def main() -> None:

    """Nạp chính sách của dự án và in thống kê kho như trong bài lab."""
    project_root = Path(__file__).resolve().parents[1]
    documents_path = project_root / "data" / "documents"
    store = DocumentStore.from_directory(
        documents_path,
        chunk_size=150,
        overlap=30,
    )

    print(store.count())
    print(f"\nDocuments ({len(store.list_all())}):")

    for document in store.list_all():
        chunks = store.get_chunks_by_doc(document.doc_id)
        print(
            f"  - {document.title} ({document.doc_id}): "
            f"{len(chunks)} chunks"
        )

    print(f"\nAll chunks ({len(store.chunks)}):")
    for chunk_id, chunk in store.chunks.items():
        print(f"  - [{chunk_id}] {chunk.content[:60]}...")


if __name__ == "__main__":
    main()
