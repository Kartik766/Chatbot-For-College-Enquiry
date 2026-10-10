"""Central configuration. Everything can be overridden from .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
PDF_PATH = Path(os.getenv("PDF_PATH", DATA_DIR / "Merged_data.pdf"))

KNOWLEDGE_PDF = Path(os.getenv("KNOWLEDGE_PDF", DATA_DIR / "knowledge.pdf"))
OCR_PAGES_JSON = OUTPUT_DIR / "ocr_pages.json"
CHUNKS_JSON = OUTPUT_DIR / "chunks.json"
INDEX_DIR = OUTPUT_DIR / "vector_index"

# OCR
OCR_DPI = int(os.getenv("OCR_DPI", "200"))
OCR_WORKERS = int(os.getenv("OCR_WORKERS", str(max(1, (os.cpu_count() or 2) - 1))))
OCR_LANG = os.getenv("OCR_LANG", "eng")
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")  # Windows: C:\\Program Files\\Tesseract-OCR\\tesseract.exe
MIN_TEXT_CHARS = int(os.getenv("MIN_TEXT_CHARS", "80"))

# Chunking (words)
CHUNK_WORDS = int(os.getenv("CHUNK_WORDS", "350"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "60"))
MIN_CHUNK_WORDS = int(os.getenv("MIN_CHUNK_WORDS", "25"))

# Retrieval
EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
TOP_K = int(os.getenv("TOP_K", "5"))

# Groq (model is intentionally NOT hard-coded)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))
HISTORY_MESSAGES = int(os.getenv("HISTORY_MESSAGES", "6"))

PORT = int(os.getenv("PORT", "3000"))
