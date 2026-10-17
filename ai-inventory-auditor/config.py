
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

# Cấu hình RAG
# Mô hình embedding (mặc định tiếng Anh; thử "paraphrase-multilingual-MiniLM-L12-v2"
# cho tiếng Việt rồi so sánh bằng: python evaluation/eval_retrieval.py).
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
# "line" = mỗi quy tắc một đoạn (mặc định); "fixed" = 150 ký tự cố định.
CHUNK_MODE = os.getenv("CHUNK_MODE", "line")
# Ngưỡng điểm tối thiểu của bằng chứng (hybrid). Để trống = tắt. Hiệu chỉnh bằng
# eval_retrieval.py rồi đặt giá trị, ví dụ RETRIEVAL_MIN_SCORE=0.45.
_min_score = os.getenv("RETRIEVAL_MIN_SCORE", "").strip()
RETRIEVAL_MIN_SCORE = float(_min_score) if _min_score else None

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
