# Belge Hazırlama ve İndeks Sistemi v2

Hukuki belgeleri **akıllıca okur**, **yapısını korur**, **düzenlemenize olanak tanır** ve ardından anlamsal olarak indeksler.

## Sorun ve Çözüm

**Sorun:** SGK genelgeleri, kanunlar gibi belgeler PDF'den TXT'ye çevrildiğinde tablolar bozulur, madde yapısı kaybolur, görseller okunamaz.

**Çözüm:** Bu sistem belgeleri 3 aşamalı bir pipeline'dan geçirir:

1. **Akıllı Okuma** — PDF'lerdeki tabloları otomatik algılar ve HTML tabloya çevirir. Taranmış belgelerde OCR uygular. DOCX'te başlık/madde yapısını korur.
2. **Düzenleme** — Web arayüzünde belgeyi görsel olarak inceler, hataları düzeltir, gereksiz kısımları silersiniz.
3. **İndeksleme** — Onayladığınız temiz metin FAISS vektör indeksine eklenir.

## Desteklenen Format ve Özellikler

| Format | Tablo | OCR | Madde Algılama | Başlık Yapısı |
|--------|-------|-----|----------------|---------------|
| PDF (metin) | Otomatik | - | Otomatik | Font boyutundan |
| PDF (taranmış) | - | Türkçe+İngilizce | OCR sonrası | - |
| DOCX | Otomatik | - | Otomatik | Stil'den |
| TXT/MD | - | - | Otomatik | BÜYÜK HARF'ten |
| Görsel (PNG/JPG) | - | Türkçe+İngilizce | OCR sonrası | - |

## Kurulum (Railway)

### 1. Ortam Değişkenleri

| Değişken | Açıklama | Varsayılan |
|----------|----------|------------|
| `GEMINI_API_KEY` | Google Gemini API anahtarı | (zorunlu) |
| `GEMINI_MODEL` | Gemini model adı | `gemini-2.0-flash` |
| `PORT` | Sunucu portu | `8080` |

### 2. Volume (ÖNEMLİ!)

İki volume oluşturun:
- `/app/belgeler` — belgeler ve hazırlanan metinler
- `/app/indeks` — FAISS vektör indeksi

### 3. Deploy

```bash
railway login
railway link
railway up
```

## Kullanım

### Web Arayüzü

Tarayıcınızda `https://YOUR-APP.railway.app` adresine gidin.

**Belge Hazırla** sekmesi:
1. Belgeyi sürükleyip bırakın
2. Sol panelde yapısal önizlemeyi inceleyin (başlıklar, maddeler, tablolar renkli)
3. Hataları düzeltin (metin düzenlenebilir)
4. "Onayla ve indeksle" butonuna tıklayın

**Sorgula** sekmesi:
1. Sorunuzu yazın
2. "Sorgula" = Gemini ile kapsamlı yanıt
3. "Hızlı ara" = Sadece indeks araması (Gemini çağırmaz)

### API

```bash
# Belge hazırla (önizleme al)
curl -X POST https://APP.railway.app/hazirla/yukle -F "dosya=@belge.pdf"

# Düzenlenmiş belgeyi onayla
curl -X POST https://APP.railway.app/hazirla/onayla \
  -H "Content-Type: application/json" \
  -d '{"dosya_adi":"belge.pdf","duzenlenmis_html":"...","temiz_metin":"..."}'

# Otomatik yükle (hazırlama adımını atla)
curl -X POST https://APP.railway.app/yukle -F "dosya=@belge.pdf"

# Sorgula
curl -X POST https://APP.railway.app/sorgula \
  -H "Content-Type: application/json" \
  -d '{"sorgu":"Kıdem tazminatında fazla mesai dikkate alınır mı?"}'
```

## Dosya Yapısı

```
belge-indeks/
├── main.py              # FastAPI ana uygulama
├── config.py            # Konfigürasyon
├── gelismis_parser.py   # Akıllı belge okuyucu (tablo, OCR, yapı)
├── parser.py            # Temel belge okuyucu (eski uyumluluk)
├── chunker.py           # Madde bazlı parçalayıcı
├── indeksleyici.py      # FAISS vektör indeks yöneticisi
├── gemini_client.py     # Gemini API istemcisi
├── ui.html              # Web arayüzü
├── Dockerfile           # Docker yapılandırması (OCR dahil)
├── railway.json         # Railway yapılandırması
└── requirements.txt     # Python bağımlılıkları
```
