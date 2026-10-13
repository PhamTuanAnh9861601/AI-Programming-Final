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


