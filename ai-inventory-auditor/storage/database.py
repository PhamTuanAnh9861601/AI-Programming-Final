
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_FILE = PROJECT_ROOT / "data" / "inventory_auditor.db"


def get_connection():
    """Mở kết nối đến SQLite database."""
    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


def init_database():
    """Tạo bảng lưu phiếu kiểm kê nếu chưa tồn tại."""
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS audit_requests (
                audit_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                expected_stock REAL NOT NULL,
                physical_count REAL NOT NULL,
                variance REAL NOT NULL,
                severity TEXT NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


if __name__ == "__main__":
    init_database()
    print(f"Database initialized: {DATABASE_FILE}")
