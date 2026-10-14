
import os
from pathlib import Path

from dotenv import load_dotenv

# Thư mục gốc của dự án
PROJECT_ROOT = Path(__file__).resolve().parent

# Đọc biến môi trường từ file .env
load_dotenv(PROJECT_ROOT / ".env")

# Cấu hình Groq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

# Giới hạn vòng lặp của Agent
MAX_STEPS = 8

# Thời gian chờ và số lần thử lại khi gọi API
API_TIMEOUT = 30
MAX_RETRIES = 2

# Đường dẫn dữ liệu
DATA_DIR = PROJECT_ROOT / "data"
PRODUCTS_CSV = DATA_DIR / "products.csv"
TRANSACTIONS_CSV = DATA_DIR / "transactions.csv"
DATABASE_PATH = DATA_DIR / "inventory_auditor.db"

# Prompt của Agent
SYSTEM_PROMPT_PATH = PROJECT_ROOT / "agent" / "prompt" / "system_prompt.txt"
