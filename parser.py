"""
Belge okuyucu: PDF, TXT, DOCX dosyalarını metin olarak çıkarır.
"""
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def pdf_oku(dosya_yolu: Path) -> str:
    """PDF dosyasını metin olarak okur."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(dosya_yolu))
        metinler = []
        for sayfa in doc:
            metinler.append(sayfa.get_text())
        doc.close()
        return "\n".join(metinler)
    except Exception as e:
        logger.error(f"PDF okuma hatası ({dosya_yolu}): {e}")
        return ""


def docx_oku(dosya_yolu: Path) -> str:
    """DOCX dosyasını metin olarak okur."""
    try:
        from docx import Document
        doc = Document(str(dosya_yolu))
        paragraflar = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n".join(paragraflar)
    except Exception as e:
        logger.error(f"DOCX okuma hatası ({dosya_yolu}): {e}")
        return ""


def txt_oku(dosya_yolu: Path) -> str:
    """TXT dosyasını okur. Farklı encoding'leri dener."""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1254"):
        try:
            return dosya_yolu.read_text(encoding=enc)
        except (UnicodeDecodeError, Exception):
            continue
    logger.error(f"TXT okuma hatası ({dosya_yolu}): desteklenen encoding bulunamadı")
    return ""


# ── Desteklenen formatlar ─────────────────────────────────
OKUYUCULAR = {
    ".pdf": pdf_oku,
    ".docx": docx_oku,
    ".doc": docx_oku,
    ".txt": txt_oku,
    ".md": txt_oku,
    ".csv": txt_oku,
}


def belge_oku(dosya_yolu: str | Path) -> Optional[str]:
    """
    Dosya uzantısına göre uygun okuyucuyu seçer ve metni döndürür.
    """
    yol = Path(dosya_yolu)
    if not yol.exists():
        logger.error(f"Dosya bulunamadı: {yol}")
        return None

    uzanti = yol.suffix.lower()
    okuyucu = OKUYUCULAR.get(uzanti)
    if okuyucu is None:
        logger.warning(f"Desteklenmeyen format: {uzanti} ({yol.name})")
        return None

    metin = okuyucu(yol)
    if not metin or not metin.strip():
        logger.warning(f"Boş içerik: {yol.name}")
        return None

    # Temel temizlik
    metin = _temizle(metin)
    return metin


def _temizle(metin: str) -> str:
    """Metni normalize eder."""
    # Çoklu boşlukları teke indir
    metin = re.sub(r"[ \t]+", " ", metin)
    # 3'ten fazla boş satırı 2'ye indir
    metin = re.sub(r"\n{3,}", "\n\n", metin)
    return metin.strip()
