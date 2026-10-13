from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# Document model
@dataclass
class Document:
    content: str
    doc_id: str = ""
    title: str = ""
    source: str = ""
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


# Document chunk model
@dataclass
class DocumentChunk:
    content: str
    chunk_id: str = ""
    doc_id: str = ""
    chunk_index: int = 0
    metadata: dict = field(default_factory=dict)
    embedding: Optional[list[float]] = None


# Chunk document
def chunk_document(
    doc: Document,
    chunk_size: int = 150,
    overlap: int = 30
) -> list[DocumentChunk]:

    chunks = []
    text = doc.content.strip()
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
                "chunk_size": chunk_size
            }
        )

        chunks.append(chunk)

        start += chunk_size - overlap

        if start >= len(text):
            break

    return chunks


# Document store
@dataclass
class DocumentStore:
    documents: dict[str, Document] = field(default_factory=dict)
    chunks: dict[str, DocumentChunk] = field(default_factory=dict)

    # Add document
    def add(self, document: Document) -> str:

        if not document.doc_id:
            document.doc_id = f"doc_{len(self.documents) + 1:04d}"

        self.documents[document.doc_id] = document

        chunks = chunk_document(document)

        for chunk in chunks:
            self.add_chunk(chunk)

        return document.doc_id

    # Get document
    def get(self, doc_id: str) -> Optional[Document]:
        return self.documents.get(doc_id)

    # Delete document
    def delete(self, doc_id: str) -> bool:

        if doc_id in self.documents:

            del self.documents[doc_id]

            chunk_ids = [
                cid
                for cid, chunk in self.chunks.items()
                if chunk.doc_id == doc_id
            ]

            for cid in chunk_ids:
                del self.chunks[cid]

            return True

        return False

    # List documents
    def list_all(self) -> list[Document]:
        return list(self.documents.values())

    # Add chunk
    def add_chunk(self, chunk: DocumentChunk) -> str:

        if not chunk.chunk_id:
            chunk.chunk_id = f"chunk_{len(self.chunks) + 1:04d}"

        self.chunks[chunk.chunk_id] = chunk

        return chunk.chunk_id

    # Get chunk
    def get_chunk(
        self,
        chunk_id: str
    ) -> Optional[DocumentChunk]:

        return self.chunks.get(chunk_id)

    # Get document chunks
    def get_chunks_by_doc(
        self,
        doc_id: str
    ) -> list[DocumentChunk]:

        return [
            chunk
            for chunk in self.chunks.values()
            if chunk.doc_id == doc_id
        ]

    # Count items
    def count(self) -> dict:

        return {
            "documents": len(self.documents),
            "chunks": len(self.chunks)
        }


# Create store
store = DocumentStore()

# DOC-001
doc1 = Document(
    doc_id="INV-DOC-001",
    title="Chính sách kiểm kê tồn kho",
    source="INV-DOC-001_policy_v1.txt",
    metadata={
        "version": "1.0",
        "date": "2026-08-01",
        "owner": "Inventory Department"
    },
    content="""
    1. Tồn kho dự kiến = tồn đầu kỳ + tổng nhập đã POSTED - tổng xuất đã POSTED trong kỳ.
    2. Nếu tồn thực tế khác tồn dự kiến, cần tạo phiếu yêu cầu kiểm kê lại.
    3. Phiếu phải có mã sản phẩm, tồn dự kiến, tồn thực tế, chênh lệch và lý do kiểm tra.
    4. Không kết luận nguyên nhân chênh lệch nếu không có bằng chứng bổ sung."""
)

# DOC-002
doc2 = Document(
    doc_id="INV-DOC-002",
    title="Chính sách kiểm kê tồn kho",
    source="INV-DOC-002_policy_v2.txt",
    metadata={
        "version": "2.0",
        "date": "2026-10-01",
        "owner": "Inventory Department"
    },
    content="""
    1. Tồn kho dự kiến = tồn đầu kỳ + tổng nhập đã POSTED - tổng xuất đã POSTED trong kỳ.
    2. Nếu tồn thực tế khác tồn dự kiến, tạo phiếu kiểm kê để xác minh.
    3. Chênh lệch tuyệt đối >= 10 đơn vị: mức ưu tiên HIGH.
    4. Chênh lệch tuyệt đối từ 1 đến 9 đơn vị: mức ưu tiên NORMAL.
    5. Chênh lệch bằng 0 thì không tạo phiếu kiểm kê chênh lệch.
    6. Phiếu phải ghi product_id, expected_stock, physical_count, variance, priority và policy_doc_id.
    7. Không kết luận nguyên nhân thất thoát chỉ từ số liệu tồn kho.
    8. Thiếu physical_count hoặc dữ liệu giao dịch thì không được suy đoán; yêu cầu bổ sung."""
)

# DOC-003
doc3 = Document(
    doc_id="INV-DOC-003",
    title="Quy trình nhập kho",
    source="INV-DOC-003_receiving_policy.txt",
    metadata={
        "version": "1.0",
        "date": "2026-07-15",
        "owner": "Warehouse Operations"
    },
    content="""
    1. Giao dịch nhập kho dùng transaction_type=IN.
    2. Quantity phải là số nguyên dương.
    3. Chỉ giao dịch status=POSTED mới được tính vào tồn kho.
    4. DRAFT, CANCELLED và REJECTED không được tính."""
)

# DOC-004
doc4 = Document(
    doc_id="INV-DOC-004",
    title="Quy trình xuất kho",
    source="INV-DOC-004_issuing_policy.txt",
    metadata={
        "version": "1.0",
        "date": "2026-07-15",
        "owner": "Warehouse Operations"
    },
    content="""
    1. Giao dịch xuất kho dùng transaction_type=OUT.
    2. Quantity được lưu dạng số dương và được trừ khi xuất khỏi kho.
    3. Chỉ giao dịch status=POSTED mới được tính.
    4. DRAFT, CANCELLED và REJECTED không được tính."""
)

# DOC-005
doc5 = Document(
    doc_id="INV-DOC-005",
    title="Từ điển dữ liệu tồn kho",
    source="INV-DOC-005_data_dictionary.txt",
    metadata={
        "version": "1.0",
        "date": "2026-07-10",
        "owner": "Data Team"
    },
    content="""
    product_id: mã sản phẩm duy nhất.
    opening_stock: tồn đầu kỳ.
    physical_count: số lượng đếm thực tế; rỗng nghĩa là chưa có số liệu.
    transaction_type: IN hoặc OUT.
    quantity: số lượng giao dịch, luôn là số dương.
    status: POSTED, DRAFT, CANCELLED hoặc REJECTED.
    expected_stock = opening_stock + tổng IN POSTED - tổng OUT POSTED.
    variance = physical_count - expected_stock."""
)

# DOC-006
doc6 = Document(
    doc_id="INV-DOC-006",
    title="Quy trình xử lý phiếu kiểm kê",
    source="INV-DOC-006_audit_workflow.txt",
    metadata={
        "version": "1.0",
        "date": "2026-09-01",
        "owner": "Warehouse Operations"
    },
    content="""
    1. Chỉ tạo phiếu khi có product_id, expected_stock và physical_count.
    2. Phiếu mới có trạng thái OPEN.
    3. Mỗi phiếu có audit_id, created_at, variance, priority và policy_doc_id.
    4. Sau khi tạo phiếu, hệ thống phải đọc lại bằng audit_id để xác minh bản ghi.
    5. Chỉ thông báo tạo thành công khi đọc lại thấy đúng product_id và trạng thái.
    6. Không tự động sửa tồn kho thực tế từ kết quả kiểm kê."""
)

# DOC-007
doc7 = Document(
    doc_id="INV-DOC-007",
    title="Quy tắc mức ưu tiên",
    source="INV-DOC-007_priority_policy.txt",
    metadata={
        "version": "1.0",
        "date": "2026-10-01",
        "owner": "Inventory Department"
    },
    content="""
    Theo chính sách hiện hành INV-DOC-002 version 2.0:
    - abs(variance) >= 10: HIGH.
    - 1 <= abs(variance) <= 9: NORMAL.
    - variance = 0: không tạo phiếu chênh lệch.
    Nếu chính sách khác phiên bản mâu thuẫn, ưu tiên phiên bản có ngày hiệu lực mới hơn."""
)

# DOC-008
doc8 = Document(
    doc_id="INV-DOC-008",
    title="Xử lý dữ liệu thiếu",
    source="INV-DOC-008_missing_data_policy.txt",
    metadata={
        "version": "1.0",
        "date": "2026-08-15",
        "owner": "Inventory Department"
    },
    content="""
    Nếu physical_count trống, không tính variance và không tạo phiếu.
    Nếu thiếu opening_stock hoặc không xác định được giao dịch POSTED trong kỳ, báo không đủ dữ liệu.
    Không tự điền số lượng thiếu bằng 0.
    Nếu chỉ có số liệu tồn kho mà không có chứng cứ nguyên nhân, không kết luận nguyên nhân chênh lệch."""
)


#Add documents
for doc in [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8]:
    store.add(doc)

#Print count
print(store.count())

# Print documents
print(f"\nDocuments ({len(store.list_all())}):")

for document in store.list_all():

    chunks = store.get_chunks_by_doc(
        document.doc_id
    )

    print(
        f"  - {document.title} "
        f"({document.doc_id}): "
        f"{len(chunks)} chunks"
    )


# Print chunks
print(f"\nAll chunks ({len(store.chunks)}):")

for chunk_id, chunk in store.chunks.items():

    print(
        f"  - [{chunk_id}] "
        f"{chunk.content[:60]}..."
    )
