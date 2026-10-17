
from typing import Any

from business.inventory_service import InventoryService
from business.audit_service import AuditService
from storage.audit_repository import AuditRepository
from pathlib import Path
from functools import cached_property


class InventoryTools:
    """Cung cấp các tool nghiệp vụ cho AI Agent."""

    def __init__(self):
        self.inventory_service = InventoryService()
        self.audit_service = AuditService()
        self.audit_repository = AuditRepository()

    @cached_property
    def rag_pipeline(self):
        """Nạp kho tài liệu một lần, chỉ khi tool tìm chính sách được gọi."""
        from config import DATA_DIR
        from retrieval.rag_pipeline import RAGPipeline

        return RAGPipeline.from_directory(DATA_DIR / "documents")

    def search_inventory_policy(
        self, query: str, top_k: int = 3, search_mode: str = "hybrid",
        min_score: float = 0.25,
    ) -> dict[str, Any]:
        """Tra cứu chính sách và trả bằng chứng có doc_id/version/date."""
        if not query or not query.strip():
            raise ValueError("query không được để trống")
        if not 1 <= top_k <= 10:
            raise ValueError("top_k phải nằm trong khoảng 1..10")
        if not 0 <= min_score <= 1:
            raise ValueError("min_score phải nằm trong khoảng 0..1")

        evidence = self.rag_pipeline.retrieve(
            query, top_k=top_k, search_mode=search_mode, min_score=min_score,
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
            "min_score": min_score,
            "evidence_count": len(results),
            "doc_ids": list(dict.fromkeys(item["doc_id"] for item in results)),
            "evidence": results,
            "message": "Không tìm thấy bằng chứng phù hợp." if not results else "Đã truy xuất bằng chứng chính sách.",
        }

    def get_stock_data(self, product_id: str) -> dict[str, Any]:
        """Lấy dữ liệu tồn kho và độ lệch của một sản phẩm."""
        result = self.inventory_service.get_stock_data(product_id)

        if hasattr(result, "__dataclass_fields__"):
            return {
                field: getattr(result, field)
                for field in result.__dataclass_fields__
            }

        if isinstance(result, dict):
            return result

        raise TypeError(
            "InventoryService trả về kiểu dữ liệu không được hỗ trợ."
        )

    def get_transactions(self, product_id: str) -> dict[str, Any]:
        """Liệt kê giao dịch của một sản phẩm kèm trạng thái và việc có được tính vào tồn kho."""
        rows = self.inventory_service.get_transactions(product_id)
        return {
            "product_id": product_id.strip().upper(),
            "transaction_count": len(rows),
            "transactions": rows,
        }

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
