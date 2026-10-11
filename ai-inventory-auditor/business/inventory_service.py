
import csv
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional


# Thư mục gốc: ai-inventory-auditor/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

PRODUCTS_FILE = PROJECT_ROOT / "data" / "products.csv"
TRANSACTIONS_FILE = PROJECT_ROOT / "data" / "transactions.csv"


@dataclass
class InventoryResult:
    product_id: str
    product_name: str
    category: str
    opening_stock: float
    total_in: float
    total_out: float
    expected_stock: float
    physical_count: Optional[float]
    variance: Optional[float]
    severity: str
    unit: str


def _read_csv(file_path: Path) -> list[dict]:
    """Đọc CSV thành danh sách dictionary."""
    if not file_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file: {file_path}")

    with file_path.open("r", encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def _number(value: Optional[str], field_name: str) -> float:
    """Chuyển dữ liệu số thành float và báo lỗi nếu không hợp lệ."""
    if value is None or not value.strip():
        raise ValueError(f"Thiếu giá trị số ở cột {field_name}")

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(
            f"Giá trị không hợp lệ ở cột {field_name}: {value}"
        ) from exc


class InventoryService:
    def __init__(
        self,
        products_file: Path = PRODUCTS_FILE,
        transactions_file: Path = TRANSACTIONS_FILE,
    ):
        self.products_file = Path(products_file)
        self.transactions_file = Path(transactions_file)

    def get_stock_data(self, product_id: str) -> InventoryResult:
        """Tính tồn kho dự kiến và chênh lệch cho một sản phẩm."""
        products = _read_csv(self.products_file)
        transactions = _read_csv(self.transactions_file)

        product_id = product_id.strip().upper()

        product = next(
            (
                row for row in products
                if row["product_id"].strip().upper() == product_id
            ),
            None,
        )

        if product is None:
            raise ValueError(f"Không tìm thấy sản phẩm: {product_id}")

        opening_stock = _number(
            product["opening_stock"], "opening_stock"
        )

        total_in = 0.0
        total_out = 0.0

        for transaction in transactions:
            if transaction["product_id"].strip().upper() != product_id:
                continue

            # Chỉ tính giao dịch đã được ghi nhận.
            status = transaction["status"].strip().upper()
            if status != "POSTED":
                continue

            transaction_type = (
                transaction["transaction_type"].strip().upper()
            )
            quantity = _number(transaction["quantity"], "quantity")

            if quantity < 0:
                raise ValueError(
                    f"Số lượng âm trong giao dịch "
                    f"{transaction.get('transaction_id', 'UNKNOWN')}"
                )

            if transaction_type == "IN":
                total_in += quantity
            elif transaction_type == "OUT":
                total_out += quantity
            else:
                raise ValueError(
                    f"Loại giao dịch không hợp lệ: {transaction_type}"
                )

        expected_stock = opening_stock + total_in - total_out

        # Nếu chưa kiểm đếm thực tế thì không tính variance.
        raw_count = product.get("physical_count", "")
        if raw_count is None or not raw_count.strip():
            physical_count = None
            variance = None
            severity = "UNKNOWN"
        else:
            physical_count = _number(raw_count, "physical_count")
            variance = physical_count - expected_stock

            if variance == 0:
                severity = "NONE"
            elif abs(variance) >= 10:
                severity = "HIGH"
            else:
                severity = "NORMAL"

        return InventoryResult(
            product_id=product_id,
            product_name=product["product_name"],
            category=product["category"],
            opening_stock=opening_stock,
            total_in=total_in,
            total_out=total_out,
            expected_stock=expected_stock,
            physical_count=physical_count,
            variance=variance,
            severity=severity,
            unit=product["unit"],
        )

    def get_all_stock_data(self) -> list[InventoryResult]:
        """Tính tồn kho cho tất cả sản phẩm."""
        products = _read_csv(self.products_file)

        return [
            self.get_stock_data(row["product_id"])
            for row in products
        ]


if __name__ == "__main__":
    service = InventoryService()

    for product_id in ["SP001", "SP002", "SP003", "SP004"]:
        result = service.get_stock_data(product_id)
        print(asdict(result))

"""
HIGH: chênh lệch tuyệt đối từ 10 đơn vị trở lên.
NORMAL: chênh lệch từ 1 đến 9 đơn vị.
NONE: không có chênh lệch.
UNKNOWN: chưa có số liệu kiểm đếm thực tế.
"""