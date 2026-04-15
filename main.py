"""
Belge İndeks API - Ana Uygulama (v2)
======================================
Belge hazırlama, indeksleme, anlamsal arama ve Gemini entegrasyonu.
"""
import os
import shutil
import json
import logging
import time
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, BackgroundTasks, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

from config import BELGELER_DIR, INDEKS_DIR, HOST, PORT
from gelismis_parser import belge_isle, BelgeSonuc, BelgeBolum
from chunker import belge_parcala
from indeksleyici import (
    indeks_basla, chunk_ekle, ara, belge_sil,
    belge_indeksli_mi, istatistikler,
)
from gemini_client import cevap_uret, niyet_analizi

# ── Logging ───────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Dizinler ──────────────────────────────────────────────
HAZIRLANAN_DIR = BELGELER_DIR / "hazirlanan"
HAZIRLANAN_DIR.mkdir(parents=True, exist_ok=True)
GECICI_DIR = BELGELER_DIR / "gecici"
GECICI_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Belge İndeks Sistemi v2 başlatılıyor...")
    indeks_basla()
    yeni_sayac = _otomatik_tara()
    if yeni_sayac > 0:
        logger.info(f"Başlangıçta {yeni_sayac} yeni belge indekslendi.")
    logger.info("Sistem hazır.")
    yield
    logger.info("Sistem kapanıyor.")


app = FastAPI(
    title="Belge İndeks Sistemi",
    description="Belge hazırlama, indeksleme ve anlamsal sorgulama.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Yardımcılar ──────────────────────────────────────────

def _belge_indeksle_metin(metin: str, belge_adi: str, dosya_yolu: str) -> dict:
    baslangic = time.time()
    if not metin or not metin.strip():
        return {"belge": belge_adi, "durum": "hata", "mesaj": "Boş metin"}
    chunks = belge_parcala(metin, belge_adi, dosya_yolu)
    if not chunks:
        return {"belge": belge_adi, "durum": "hata", "mesaj": "Parçalanamadı"}
    eklenen = chunk_ekle(chunks)
    sure = round(time.time() - baslangic, 2)
    logger.info(f"İndekslendi: {belge_adi} → {eklenen} chunk ({sure}s)")
    return {"belge": belge_adi, "durum": "basarili", "chunk_sayisi": eklenen,
            "karakter_sayisi": len(metin), "sure_saniye": sure}


def _otomatik_tara() -> int:
    sayac = 0
    for dosya in HAZIRLANAN_DIR.rglob("*.txt"):
        if not belge_indeksli_mi(dosya.stem):
            metin = dosya.read_text(encoding="utf-8")
            sonuc = _belge_indeksle_metin(metin, dosya.stem, str(dosya))
            if sonuc["durum"] == "basarili":
                sayac += 1
    return sayac


# ── Modeller ─────────────────────────────────────────────

class SorguIstek(BaseModel):
    sorgu: str
    top_k: int = 10
    gemini: bool = True

class AramaIstek(BaseModel):
    sorgu: str
    top_k: int = 10

class OnayIstek(BaseModel):
    dosya_adi: str
    duzenlenmis_html: str
    temiz_metin: str


# ══════════════════════════════════════════════════════════
#  BELGE HAZIRLAMA
# ══════════════════════════════════════════════════════════

@app.post("/hazirla/yukle")
async def belge_hazirla_yukle(dosya: UploadFile = File(...)):
    """Belge yükler, yapısal analiz yapar, düzenleme için önizleme döndürür."""
    gecici_yol = GECICI_DIR / dosya.filename
    with open(gecici_yol, "wb") as f:
        shutil.copyfileobj(dosya.file, f)
    try:
        sonuc = belge_isle(gecici_yol)
        return {
            "dosya_adi": sonuc.dosya_adi,
            "format": sonuc.format,
            "sayfa_sayisi": sonuc.sayfa_sayisi,
            "bolum_sayisi": len(sonuc.bolumler),
            "tablo_sayisi": len(sonuc.tablolar),
            "tablolar": sonuc.tablolar,
            "uyarilar": sonuc.uyarilar,
            "html_onizleme": sonuc.to_html(),
            "temiz_metin": sonuc.to_temiz_metin(),
            "bolumler": [
                {"tip": b.tip, "icerik": b.icerik, "seviye": b.seviye,
                 "sayfa_no": b.sayfa_no, "meta": b.meta}
                for b in sonuc.bolumler
            ],
        }
    except Exception as e:
        logger.error(f"Belge hazırlama hatası: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/hazirla/onayla")
async def belge_hazirla_onayla(istek: OnayIstek):
    """Düzenlenen belgeyi kaydeder ve indeksler."""
    hedef = HAZIRLANAN_DIR / f"{Path(istek.dosya_adi).stem}.txt"
    hedef.write_text(istek.temiz_metin, encoding="utf-8")
    html_hedef = HAZIRLANAN_DIR / f"{Path(istek.dosya_adi).stem}.html"
    html_hedef.write_text(istek.duzenlenmis_html, encoding="utf-8")
    sonuc = _belge_indeksle_metin(istek.temiz_metin, Path(istek.dosya_adi).stem, str(hedef))
    (GECICI_DIR / istek.dosya_adi).unlink(missing_ok=True)
    return sonuc


# ══════════════════════════════════════════════════════════
#  DOĞRUDAN İNDEKSLEME
# ══════════════════════════════════════════════════════════

@app.post("/yukle")
async def belge_yukle(dosya: UploadFile = File(...)):
    gecici_yol = GECICI_DIR / dosya.filename
    with open(gecici_yol, "wb") as f:
        shutil.copyfileobj(dosya.file, f)
    belge_adi = Path(dosya.filename).stem
    if belge_indeksli_mi(belge_adi):
        gecici_yol.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="Zaten indekslenmiş.")
    sonuc = belge_isle(gecici_yol)
    temiz_metin = sonuc.to_temiz_metin()
    if not temiz_metin.strip():
        gecici_yol.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail="Belge okunamadı.")
    hedef = HAZIRLANAN_DIR / f"{belge_adi}.txt"
    hedef.write_text(temiz_metin, encoding="utf-8")
    indeks_sonuc = _belge_indeksle_metin(temiz_metin, belge_adi, str(hedef))
    gecici_yol.unlink(missing_ok=True)
    indeks_sonuc["uyarilar"] = sonuc.uyarilar
    indeks_sonuc["tablo_sayisi"] = len(sonuc.tablolar)
    return indeks_sonuc


@app.post("/toplu-yukle")
async def toplu_yukle(dosyalar: list[UploadFile] = File(...)):
    sonuclar = []
    for dosya in dosyalar:
        gecici_yol = GECICI_DIR / dosya.filename
        with open(gecici_yol, "wb") as f:
            shutil.copyfileobj(dosya.file, f)
        belge_adi = Path(dosya.filename).stem
        if belge_indeksli_mi(belge_adi):
            sonuclar.append({"belge": dosya.filename, "durum": "atlandı"})
            gecici_yol.unlink(missing_ok=True)
            continue
        sonuc = belge_isle(gecici_yol)
        temiz_metin = sonuc.to_temiz_metin()
        if temiz_metin.strip():
            hedef = HAZIRLANAN_DIR / f"{belge_adi}.txt"
            hedef.write_text(temiz_metin, encoding="utf-8")
            sonuclar.append(_belge_indeksle_metin(temiz_metin, belge_adi, str(hedef)))
        else:
            sonuclar.append({"belge": dosya.filename, "durum": "hata", "mesaj": "İçerik çıkarılamadı"})
        gecici_yol.unlink(missing_ok=True)
    return {"toplam": len(dosyalar),
            "basarili": sum(1 for s in sonuclar if s.get("durum") == "basarili"),
            "detay": sonuclar}


# ══════════════════════════════════════════════════════════
#  SORGULAMA
# ══════════════════════════════════════════════════════════

@app.post("/sorgula")
async def sorgula(istek: SorguIstek):
    if not istek.sorgu.strip():
        raise HTTPException(status_code=400, detail="Sorgu boş olamaz")
    baslangic = time.time()
    arama_sonuclari = ara(istek.sorgu, top_k=istek.top_k)
    if not arama_sonuclari:
        return {"sorgu": istek.sorgu, "sonuc_sayisi": 0, "mesaj": "İlgili belge bulunamadı.", "sonuclar": []}
    belge_gruplari = {}
    for s in arama_sonuclari:
        ad = s["chunk"]["belge_adi"]
        if ad not in belge_gruplari:
            belge_gruplari[ad] = []
        belge_gruplari[ad].append({
            "madde_no": s["chunk"].get("madde_no", ""),
            "bolum": s["chunk"].get("bolum_baslik", ""),
            "skor": s["skor"],
            "onizleme": s["chunk"]["metin"][:200] + "...",
        })
    yanit = {"sorgu": istek.sorgu, "sonuc_sayisi": len(arama_sonuclari), "ilgili_belgeler": belge_gruplari}
    if istek.gemini:
        yanit["niyet_analizi"] = niyet_analizi(istek.sorgu)
        yanit["gemini_yanit"] = cevap_uret(istek.sorgu, arama_sonuclari)
    yanit["sure_saniye"] = round(time.time() - baslangic, 2)
    return yanit


@app.post("/ara")
async def sadece_ara(istek: AramaIstek):
    sonuclar = ara(istek.sorgu, top_k=istek.top_k)
    belge_gruplari = {}
    for s in sonuclar:
        ad = s["chunk"]["belge_adi"]
        if ad not in belge_gruplari:
            belge_gruplari[ad] = []
        belge_gruplari[ad].append({
            "madde_no": s["chunk"].get("madde_no", ""),
            "skor": s["skor"],
            "metin": s["chunk"]["metin"],
        })
    return {"sorgu": istek.sorgu, "sonuc_sayisi": len(sonuclar), "belgeler": belge_gruplari}


@app.post("/tara")
async def dizin_tara():
    return {"yeni_indekslenen": _otomatik_tara(), "istatistikler": istatistikler()}


@app.delete("/sil/{belge_adi}")
async def belge_sil_endpoint(belge_adi: str):
    silindi = belge_sil(belge_adi)
    if not silindi:
        raise HTTPException(status_code=404, detail="Belge bulunamadı")
    for uz in (".txt", ".html"):
        (HAZIRLANAN_DIR / f"{belge_adi}{uz}").unlink(missing_ok=True)
    return {"mesaj": f"'{belge_adi}' silindi", "istatistikler": istatistikler()}


@app.get("/istatistik")
async def istatistik_endpoint():
    return istatistikler()


@app.get("/belgeler")
async def belge_listesi():
    dosyalar = []
    for dosya in HAZIRLANAN_DIR.rglob("*.txt"):
        dosyalar.append({"ad": dosya.stem,
                         "boyut_kb": round(dosya.stat().st_size / 1024, 1),
                         "indeksli": belge_indeksli_mi(dosya.stem)})
    return {"belgeler": dosyalar, "toplam": len(dosyalar)}


@app.get("/saglik")
async def saglik_kontrol():
    return {"durum": "saglikli", "istatistikler": istatistikler()}


@app.get("/")
async def anasayfa():
    ui_path = Path(__file__).parent / "ui.html"
    if ui_path.exists():
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))
    return {"mesaj": "Belge İndeks Sistemi v2", "istatistikler": istatistikler()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)
