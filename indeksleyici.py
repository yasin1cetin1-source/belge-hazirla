"""
Embedding üretici ve FAISS vektör indeks yöneticisi.
"""
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Optional, Tuple

from config import EMBEDDING_MODEL, INDEKS_DIR, TOP_K, SKOR_ESIGI
from chunker import Chunk

logger = logging.getLogger(__name__)

# ── Singleton model & index ───────────────────────────────
_model = None
_index = None
_chunks: List[dict] = []

FAISS_DOSYA = INDEKS_DIR / "vektor.index"
META_DOSYA = INDEKS_DIR / "meta.json"
BELGE_KAYIT = INDEKS_DIR / "belgeler.json"


def _model_yukle():
    """Embedding modelini yükler (lazy)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Model yükleniyor: {EMBEDDING_MODEL}")
        _model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Model yüklendi.")
    return _model


def embedding_uret(metinler: List[str]) -> np.ndarray:
    """Metin listesi için embedding vektörleri üretir."""
    model = _model_yukle()
    vektorler = model.encode(
        metinler,
        show_progress_bar=False,
        normalize_embeddings=True,   # cosine similarity için
        batch_size=64,
    )
    return np.array(vektorler, dtype="float32")


# ── FAISS İndeks Yönetimi ─────────────────────────────────

def _indeks_yukle():
    """Mevcut indeksi diskten yükler."""
    global _index, _chunks
    import faiss

    if FAISS_DOSYA.exists() and META_DOSYA.exists():
        _index = faiss.read_index(str(FAISS_DOSYA))
        _chunks = json.loads(META_DOSYA.read_text(encoding="utf-8"))
        logger.info(f"İndeks yüklendi: {_index.ntotal} vektör, {len(_chunks)} chunk")
    else:
        # Boş indeks oluştur
        boyut = _model_yukle().get_sentence_embedding_dimension()
        _index = faiss.IndexFlatIP(boyut)  # Inner Product (normalized = cosine)
        _chunks = []
        logger.info("Yeni boş indeks oluşturuldu.")


def _indeks_kaydet():
    """İndeksi diske kaydeder."""
    import faiss
    if _index is not None:
        faiss.write_index(_index, str(FAISS_DOSYA))
        META_DOSYA.write_text(
            json.dumps(_chunks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"İndeks kaydedildi: {_index.ntotal} vektör")


def indeks_hazir() -> bool:
    return _index is not None


def indeks_basla():
    """Uygulanma başlangıcında çağrılır."""
    _model_yukle()
    _indeks_yukle()


def _belge_kayitlari() -> dict:
    """Hangi belgelerin indekslendiğini takip eder."""
    if BELGE_KAYIT.exists():
        return json.loads(BELGE_KAYIT.read_text(encoding="utf-8"))
    return {}


def _belge_kayit_ekle(belge_adi: str, bilgi: dict):
    kayitlar = _belge_kayitlari()
    kayitlar[belge_adi] = bilgi
    BELGE_KAYIT.write_text(
        json.dumps(kayitlar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def belge_indeksli_mi(belge_adi: str) -> bool:
    return belge_adi in _belge_kayitlari()


def chunk_ekle(yeni_chunklar: List[Chunk]) -> int:
    """
    Chunk'ları indekse ekler.
    Döndürülen değer: eklenen chunk sayısı.
    """
    global _index, _chunks

    if _index is None:
        _indeks_yukle()

    if not yeni_chunklar:
        return 0

    metinler = [c.metin for c in yeni_chunklar]
    vektorler = embedding_uret(metinler)

    _index.add(vektorler)
    _chunks.extend([c.to_dict() for c in yeni_chunklar])

    _indeks_kaydet()

    # Belge kaydını güncelle
    belge_adlari = set(c.belge_adi for c in yeni_chunklar)
    for ad in belge_adlari:
        chunk_sayisi = sum(1 for c in yeni_chunklar if c.belge_adi == ad)
        _belge_kayit_ekle(ad, {"chunk_sayisi": chunk_sayisi})

    return len(yeni_chunklar)


def belge_sil(belge_adi: str) -> bool:
    """
    Bir belgeyi indeksten siler. Tüm indeksi yeniden oluşturur.
    (FAISS ID-bazlı silmeyi desteklemediği için)
    """
    global _index, _chunks
    import faiss

    if _index is None:
        _indeks_yukle()

    eski_sayi = len(_chunks)
    kalan_chunks = [c for c in _chunks if c["belge_adi"] != belge_adi]

    if len(kalan_chunks) == eski_sayi:
        return False  # Belge bulunamadı

    # Yeniden indeksle
    if kalan_chunks:
        metinler = [c["metin"] for c in kalan_chunks]
        vektorler = embedding_uret(metinler)
        boyut = vektorler.shape[1]
        _index = faiss.IndexFlatIP(boyut)
        _index.add(vektorler)
    else:
        boyut = _model_yukle().get_sentence_embedding_dimension()
        _index = faiss.IndexFlatIP(boyut)

    _chunks = kalan_chunks
    _indeks_kaydet()

    # Belge kaydını sil
    kayitlar = _belge_kayitlari()
    kayitlar.pop(belge_adi, None)
    BELGE_KAYIT.write_text(
        json.dumps(kayitlar, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return True


def ara(sorgu: str, top_k: int = TOP_K, esik: float = SKOR_ESIGI) -> List[dict]:
    """
    Anlamsal arama yapar.
    Döndürür: [{"chunk": {...}, "skor": float}, ...]
    """
    if _index is None or _index.ntotal == 0:
        return []

    sorgu_vektor = embedding_uret([sorgu])
    skorlar, indeksler = _index.search(sorgu_vektor, min(top_k, _index.ntotal))

    sonuclar = []
    for skor, idx in zip(skorlar[0], indeksler[0]):
        if idx < 0 or skor < esik:
            continue
        sonuclar.append({
            "chunk": _chunks[idx],
            "skor": round(float(skor), 4),
        })

    return sonuclar


def istatistikler() -> dict:
    """İndeks istatistiklerini döndürür."""
    kayitlar = _belge_kayitlari()
    return {
        "toplam_vektor": _index.ntotal if _index else 0,
        "toplam_chunk": len(_chunks),
        "toplam_belge": len(kayitlar),
        "belgeler": kayitlar,
    }
