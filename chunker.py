"""
Akıllı metin parçalayıcı (chunker).
Hukuki belgelerde madde/bölüm yapısını tanır.
"""
import re
from dataclasses import dataclass, field
from typing import List

from config import CHUNK_SIZE, CHUNK_OVERLAP


@dataclass
class Chunk:
    """Bir metin parçası."""
    metin: str
    belge_adi: str
    belge_yolu: str
    chunk_no: int
    madde_no: str = ""          # Varsa madde numarası
    bolum_baslik: str = ""      # Varsa bölüm başlığı
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "metin": self.metin,
            "belge_adi": self.belge_adi,
            "belge_yolu": self.belge_yolu,
            "chunk_no": self.chunk_no,
            "madde_no": self.madde_no,
            "bolum_baslik": self.bolum_baslik,
            **self.metadata,
        }

    @staticmethod
    def from_dict(d: dict) -> "Chunk":
        return Chunk(
            metin=d["metin"],
            belge_adi=d["belge_adi"],
            belge_yolu=d["belge_yolu"],
            chunk_no=d["chunk_no"],
            madde_no=d.get("madde_no", ""),
            bolum_baslik=d.get("bolum_baslik", ""),
        )


# ── Madde / Bölüm Desenleri (Türk hukuk belgeleri) ───────
MADDE_DESENI = re.compile(
    r"(?:^|\n)"
    r"(?:Madde|MADDE|madde)\s*(\d+[\w/]*)"
    r"[\s\-–:\.]*",
    re.MULTILINE
)

BOLUM_DESENI = re.compile(
    r"(?:^|\n)"
    r"(?:BÖLÜM|Bölüm|KISIM|Kısım|BİRİNCİ BÖLÜM|İKİNCİ BÖLÜM|ÜÇÜNCÜ BÖLÜM)"
    r"[\s\-–:]*"
    r"(.+?)(?:\n|$)",
    re.MULTILINE
)


def _kelime_say(metin: str) -> int:
    return len(metin.split())


def madde_bazli_parcala(metin: str, belge_adi: str, belge_yolu: str) -> List[Chunk]:
    """
    Önce madde yapısını bulmaya çalışır.
    Madde bulunamazsa sabit boyutlu parçalama yapar.
    """
    # Madde konumlarını bul
    maddeler = list(MADDE_DESENI.finditer(metin))

    if len(maddeler) >= 3:
        # Yeterli madde var → madde bazlı parçala
        return _madde_parcala(metin, maddeler, belge_adi, belge_yolu)
    else:
        # Madde yok → sabit boyutlu parçala
        return _sabit_parcala(metin, belge_adi, belge_yolu)


def _madde_parcala(
    metin: str,
    maddeler: list,
    belge_adi: str,
    belge_yolu: str,
) -> List[Chunk]:
    """Madde bazlı parçalama. Uzun maddeler alt parçalara bölünür."""
    chunks: List[Chunk] = []
    chunk_sayac = 0

    # Belge başlangıcı (ilk madde öncesi) → bir chunk
    ilk_pos = maddeler[0].start()
    if ilk_pos > 50:
        giris = metin[:ilk_pos].strip()
        if giris:
            chunks.append(Chunk(
                metin=giris,
                belge_adi=belge_adi,
                belge_yolu=belge_yolu,
                chunk_no=chunk_sayac,
                bolum_baslik="Giriş / Başlık",
            ))
            chunk_sayac += 1

    # Her madde için
    for i, m in enumerate(maddeler):
        baslangic = m.start()
        bitis = maddeler[i + 1].start() if i + 1 < len(maddeler) else len(metin)
        madde_metin = metin[baslangic:bitis].strip()
        madde_no = m.group(1)

        if _kelime_say(madde_metin) > CHUNK_SIZE:
            # Uzun madde → alt parçalara böl
            alt_parcalar = _sabit_parcala(
                madde_metin, belge_adi, belge_yolu,
                baslangic_no=chunk_sayac,
                madde_no=madde_no,
            )
            chunks.extend(alt_parcalar)
            chunk_sayac += len(alt_parcalar)
        else:
            chunks.append(Chunk(
                metin=madde_metin,
                belge_adi=belge_adi,
                belge_yolu=belge_yolu,
                chunk_no=chunk_sayac,
                madde_no=madde_no,
            ))
            chunk_sayac += 1

    return chunks


def _sabit_parcala(
    metin: str,
    belge_adi: str,
    belge_yolu: str,
    baslangic_no: int = 0,
    madde_no: str = "",
) -> List[Chunk]:
    """Sabit boyutlu, örtüşmeli parçalama."""
    kelimeler = metin.split()
    chunks: List[Chunk] = []
    i = 0
    chunk_sayac = baslangic_no

    while i < len(kelimeler):
        parca = kelimeler[i : i + CHUNK_SIZE]
        parca_metin = " ".join(parca)

        if parca_metin.strip():
            chunks.append(Chunk(
                metin=parca_metin,
                belge_adi=belge_adi,
                belge_yolu=belge_yolu,
                chunk_no=chunk_sayac,
                madde_no=madde_no,
            ))
            chunk_sayac += 1

        i += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


def belge_parcala(metin: str, belge_adi: str, belge_yolu: str) -> List[Chunk]:
    """
    Ana giriş noktası.
    Belge metnini alır, chunk listesi döndürür.
    """
    if not metin or not metin.strip():
        return []
    return madde_bazli_parcala(metin, belge_adi, belge_yolu)
