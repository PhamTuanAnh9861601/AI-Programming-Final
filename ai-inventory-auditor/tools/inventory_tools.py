
from typing import Any

from business.inventory_service import InventoryService
from business.audit_service import AuditService
from storage.audit_repository import AuditRepository
from pathlib import Path
import threading


MIN_EVIDENCE = 5  # số đoạn bằng chứng tối thiểu mỗi lần tra cứu


class InventoryTools:
    """Cung cấp các tool nghiệp vụ cho AI Agent."""

    def __init__(self):
        self.inventory_service = InventoryService()
        self.audit_service = AuditService()
        self.audit_repository = AuditRepository()
        self._rag_pipeline = None
        self._rag_lock = threading.Lock()

    @property
    def rag_pipeline(self):
        """Nạp kho tài liệu một lần (an toàn khi nhiều luồng gọi cùng lúc)."""
        if self._rag_pipeline is None:
            with self._rag_lock:
                if self._rag_pipeline is None:
                    from config import CHUNK_MODE, DATA_DIR, EMBEDDING_MODEL
                    from retrieval.rag_pipeline import RAGPipeline

                    self._rag_pipeline = RAGPipeline.from_directory(
                        DATA_DIR / "documents",
                        model_name=EMBEDDING_MODEL,
                        chunk_mode=CHUNK_MODE,
                    )
        return self._rag_pipeline

    def warm_up(self) -> None:
        """Nạp sẵn mô hình embedding và chỉ mục để câu hỏi đầu tiên không bị chậm."""
        _ = self.rag_pipeline

    def search_inventory_policy(
        self, query: str, top_k: int = 3, search_mode: str = "hybrid"
    ) -> dict[str, Any]:
        """Tra cứu chính sách và trả bằng chứng có doc_id/version/date."""
        if not query or not query.strip():
            raise ValueError("query không được để trống")
        if not 1 <= top_k <= 10:
            raise ValueError("top_k phải nằm trong khoảng 1..10")
        # Đoạn chứa câu trả lời hay xếp hạng 4-5; các đoạn rất ngắn nên trả tối thiểu 5.
        top_k = max(top_k, MIN_EVIDENCE)

        # Chọn phiên bản mới nhất theo metadata của toàn corpus trước retrieval,
        # để bản cũ không thắng chỉ vì nó trùng từ khóa truy vấn hơn.
        from config import RETRIEVAL_MIN_SCORE
        from retrieval.rag_pipeline import current_doc_ids

        evidence = self.rag_pipeline.retrieve(
            query, top_k=max(top_k * 3, top_k), search_mode=search_mode,
            metadata_filter={"doc_id": current_doc_ids(self.rag_pipeline.store)},
            min_score=RETRIEVAL_MIN_SCORE,
        )
        selected = evidence
        # Giữ kết quả có điểm cao, nhưng loại đoạn trùng cùng doc/chunk.
        seen = set()
        results = []
        for item in selected:
            key = (item.doc_id, item.chunk_id)
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "doc_id": item.doc_id,
                "title": item.title,
                "version": item.metadata.get("version", "unknown"),
                "date": item.metadata.get("date", "unknown"),
                "chunk_id": item.chunk_id,
                "score": round(float(item.score), 4),
                "content": item.content,
            })
            if len(results) >= top_k:
                break

        return {
            "query": query,
            "search_mode": search_mode,
            "evidence_count": len(results),
            "doc_ids": list(dict.fromkeys(item["doc_id"] for item in results)),
            "evidence": results,
            "message": "Không tìm thấy bằng chứng phù hợp." if not results else "Đã truy xuất bằng chứng chính sách.",
        }

    def get_stock_data(self, product_id: str) -> dict[str, Any]:
        """Lấy dữ liệu tồn kho và độ lệch của một sản phẩm."""
        result = self.inventory_service.get_stock_data(product_id)

        if hasattr(result, "__dataclass_fields__"):
            data = {
                field: getattr(result, field)
                for field in result.__dataclass_fields__
            }
            if data.get("data_quality_flag"):
                data["data_quality_note"] = (
                    "Tồn dự kiến âm là bất thường dữ liệu cần rà soát (INV-DOC-009, INV-DOC-011). "
                    "Không suy ra nguyên nhân và không chỉ định giao dịch hay người chịu trách nhiệm."
                )
            return data

        if isinstance(result, dict):
            return result

        raise TypeError(
            "InventoryService trả về kiểu dữ liệu không được hỗ trợ."
        )

    def get_transactions(self, product_id: str) -> dict[str, Any]:
        """Liệt kê giao dịch của một sản phẩm kèm trạng thái và việc có được tính vào tồn kho."""
        rows = self.inventory_service.get_transactions(product_id)
        result = {
            "product_id": product_id.strip().upper(),
            "transaction_count": len(rows),
            "transactions": rows,
        }
        if self.inventory_service.get_stock_data(product_id).data_quality_flag:
            result["data_quality_note"] = (
                "Sản phẩm này có tồn dự kiến âm (bất thường dữ liệu, INV-DOC-009/011). "
                "Chỉ liệt kê dữ kiện; không tính số dư từng bước để chỉ ra giao dịch 'gây ra' "
                "và không kết luận nguyên nhân hay người chịu trách nhiệm."
            )
        return result

    def get_all_stock_data(self) -> list[dict[str, Any]]:
        """Lấy dữ liệu tồn kho của tất cả sản phẩm."""
        results = self.inventory_service.get_all_stock_data()
        output = []

        for result in results:
            if hasattr(result, "__dataclass_fields__"):
                output.append({
                    field: getattr(result, field)
                    for field in result.__dataclass_fields__
                })
            elif isinstance(result, dict):
                output.append(result)
            else:
                raise TypeError(
                    "Có kết quả tồn kho không đúng kiểu dữ liệu."
                )

        return output

    def create_audit_request(
        self,
        product_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Tạo phiếu kiểm toán qua AuditService."""
        result = self.audit_service.audit_product(product_id, reason=reason)

        if not result.get("audit_created"):
            return {
                "success": False,
                "product_id": product_id,
                "message": result.get(
                    "message",
                    "Không tạo phiếu kiểm toán.",
                ),
            }

        audit = result.get("audit")
        if not audit:
            return {
                "success": False,
                "product_id": product_id,
                "message": (
                    "AuditService báo đã tạo phiếu nhưng "
                    "không trả về thông tin phiếu."
                ),
            }

        # Lý do phải được lấy từ bản ghi đã đọc lại, không chỉ từ input.
        return {
            "success": True,
            "product_id": product_id,
            "reason": audit.get("reason", reason) if isinstance(audit, dict) else reason,
            "audit": audit,
            "message": "Đã yêu cầu tạo phiếu kiểm toán.",
        }

    def get_audit_request(
        self,
        audit_id: str,
    ) -> dict[str, Any]:
        """Đọc lại phiếu theo ID để xác minh dữ liệu đã lưu."""
        result = self.audit_repository.get_by_id(audit_id)

        if result is None:
            return {
                "success": False,
                "audit_id": audit_id,
                "message": "Không tìm thấy phiếu kiểm toán.",
            }

        if hasattr(result, "keys"):
            result = dict(result)

        return {
            "success": True,
            "audit": result,
            "message": "Đã đọc được phiếu kiểm toán từ storage.",
        }


def build_tool_registry(
    inventory_tools: InventoryTools | None = None,
):
    """Tạo registry ánh xạ tên tool sang hàm thực thi."""
    inventory_tools = inventory_tools or InventoryTools()

    return {
        "get_stock_data": inventory_tools.get_stock_data,
        "get_all_stock_data": inventory_tools.get_all_stock_data,
        "get_transactions": inventory_tools.get_transactions,
        "search_inventory_policy": inventory_tools.search_inventory_policy,
        "create_audit_request": inventory_tools.create_audit_request,
        "get_audit_request": inventory_tools.get_audit_request,
    }
