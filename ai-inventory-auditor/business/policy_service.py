"""Đọc quy tắc ưu tiên từ chính sách hiện hành thay vì hard-code ngưỡng."""
from __future__ import annotations
import re
from pathlib import Path
from config import DATA_DIR

class PolicyService:
    def __init__(self, documents_dir: Path | None = None):
        self.documents_dir = Path(documents_dir or DATA_DIR / "documents")

    def _current_priority_policy(self) -> str:
        candidates = []
        for path in self.documents_dir.glob("*.txt"):
            text = path.read_text(encoding="utf-8-sig")
            header = dict(re.findall(r"^([A-Z_]+):\s*(.*?)\s*$", text, re.M))
            title = header.get("TITLE", "").casefold()
            if "chính sách kiểm kê tồn kho" in title or "quy tắc mức ưu tiên" in title:
                candidates.append((header.get("DATE", ""), text))
        if not candidates:
            raise FileNotFoundError("Không tìm thấy tài liệu chính sách ưu tiên.")
        return max(candidates, key=lambda item: item[0])[1]

    def classify_variance(self, variance: float | None) -> str:
        if variance is None:
            return "UNKNOWN"
        if variance == 0:
            return "NONE"
        policy = self._current_priority_policy()
        # Extract the current document's boundary. The document remains source of truth.
        high_match = re.search(r"(?:abs\(variance\)|chênh lệch tuyệt đối)\s*(?:>=|≥)\s*(\d+)", policy, re.I)
        normal_match = re.search(r"(?:1\s*<=\s*abs\(variance\)\s*<=\s*(\d+)|từ\s*1\s*đến\s*(\d+))", policy, re.I)
        if not high_match:
            high_match = re.search(r"từ\s*(\d+)\s*đơn vị trở lên", policy, re.I)
        if high_match and abs(variance) >= float(high_match.group(1)):
            return "HIGH"
        if normal_match:
            upper = normal_match.group(1) or normal_match.group(2)
            if 0 < abs(variance) <= float(upper):
                return "NORMAL"
        # Fail closed when the policy format is unknown rather than inventing a tier.
        return "UNKNOWN"
