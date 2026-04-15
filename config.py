import os
from pathlib import Path

# ── Dizinler ──────────────────────────────────────────────
BASE_DIR = Path(os.getenv("BASE_DIR", "/app"))
BELGELER_DIR = BASE_DIR / "belgeler"
INDEKS_DIR = BASE_DIR / "indeks"

BELGELER_DIR.mkdir(parents=True, exist_ok=True)
INDEKS_DIR.mkdir(parents=True, exist_ok=True)

# ── Embedding Modeli ──────────────────────────────────────
# Türkçe destekli, hafif çok dilli model
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)

# ── Chunk Ayarları ────────────────────────────────────────
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "512"))       # token cinsinden
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "64"))  # örtüşme

# ── Arama Ayarları ────────────────────────────────────────
TOP_K = int(os.getenv("TOP_K", "10"))                  # en iyi kaç chunk
SKOR_ESIGI = float(os.getenv("SKOR_ESIGI", "0.25"))   # min benzerlik skoru

# ── Gemini ────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ── Sunucu ────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))
