from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# 1.======= ENUMS =========

class TransactionType(str, Enum):
    """Loại giao dịch kho (INV-DOC-003, INV-DOC-004)"""
    IN = "IN"
    OUT = "OUT"


class TransactionStatus(str, Enum):
    """Trạng thái giao dịch (INV-DOC-003, INV-DOC-004)"""
    POSTED = "POSTED"
    DRAFT = "DRAFT"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class AuditPriority(str, Enum):
    """Mức độ ưu tiên của phiếu kiểm kê (INV-DOC-002, INV-DOC-007)"""
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    NONE = "NONE"


class AuditStatus(str, Enum):
    """Trạng thái xử lý phiếu kiểm kê (INV-DOC-006)"""
    OPEN = "OPEN"
    CLOSED = "CLOSED"

# ===== 2. DOMAIN MODELS =======

@dataclass
class Product:
    """Thông tin sản phẩm và tồn đầu kỳ (products.csv)"""
    product_id: str
    product_name: str = ""
    category: str = ""
    opening_stock: int = 0
    physical_count: Optional[int] = None
    unit: str = ""


@dataclass
class Transaction:
    """Thông tin giao dịch nhập/xuất kho (transactions.csv)"""
    transaction_id: str
    product_id: str
    transaction_type: TransactionType
    quantity: int
    status: TransactionStatus
    transaction_date: Optional[datetime] = None  

@dataclass
class StockSummary:
    """Kết quả tính toán tồn kho dự kiến & chênh lệch (INV-DOC-001, INV-DOC-005)"""
    product_id: str
    opening_stock: int
    total_in_posted: int
    total_out_posted: int
    expected_stock: int
    physical_count: Optional[int] = None
    variance: Optional[int] = None
    unit: str = "cái"            
    severity: str = "NORMAL"


@dataclass
class AuditTicket:
    """Phiếu yêu cầu kiểm kê chênh lệch (INV-DOC-002, INV-DOC-006)"""
    product_id: str
    expected_stock: int
    physical_count: int
    variance: int
    severity: str = "NORMAL"
    reason: str = ""
    priority: AuditPriority = AuditPriority.NORMAL
    policy_doc_id: str = "INV-DOC-002"
    audit_id: str = ""
    status: AuditStatus = AuditStatus.OPEN
    created_at: datetime = field(default_factory=datetime.now)



# 3. TEST MODELS

if __name__ == "__main__":
    print("--- 1. Test Product ---")
    product = Product(
        product_id="SPD001", 
        product_name="Cảm biến siêu âm HC-SR04", 
        opening_stock=80
    )
    print(product)

    print("\n--- 2. Test Transaction ---")
    tx = Transaction(
        transaction_id="TX90252",
        product_id="SP001",
        transaction_type=TransactionType.IN,
        quantity=30,
        status=TransactionStatus.POSTED,
        transaction_date= datetime.now()
    )
    print(tx)
    print(f"Kiểm tra Enum Type: {tx.transaction_type == TransactionType.IN}")

    print("\n--- 3. Test StockSummary ---")
    summary = StockSummary(
        product_id="SP001",
        opening_stock=100,
        total_in_posted=50,
        total_out_posted=20,
        expected_stock=130,  # 100 + 50 - 20
        physical_count=80,
        variance=-50,
        unit="cái",
        severity="HIGH"
    )
    print(summary)

    print("\n--- 4. Test AuditTicket ---")
    ticket = AuditTicket(
        audit_id="AUD-001",
        product_id="SP001",
        expected_stock=130,
        physical_count=80,
        variance=-50,
        priority=AuditPriority.HIGH,
        policy_doc_id="INV-DOC-002"
    )
    print(ticket)
    print(f"Trạng thái mặc định phiếu: {ticket.status.value}")