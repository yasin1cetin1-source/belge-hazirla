"""
Gemini API istemcisi.
Bulunan chunk'ları bağlam olarak alır, kullanıcı sorusunu yanıtlar.
"""
import logging
from typing import List

import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

_client_hazir = False


def _hazirla():
    global _client_hazir
    if not _client_hazir:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY ortam değişkeni tanımlanmamış!")
        genai.configure(api_key=GEMINI_API_KEY)
        _client_hazir = True


SISTEM_PROMPTU = """Sen bir Türk hukuk ve mevzuat uzmanısın. 
Sana verilen belge parçalarını (bağlam) kullanarak kullanıcının sorusunu yanıtla.

Kurallar:
1. SADECE verilen bağlamdaki bilgilere dayanarak yanıt ver.
2. Bağlamda olmayan bilgiyi uydurma - bilmediğini açıkça belirt.
3. Yanıtında hangi belgeden ve hangi maddeden alıntı yaptığını belirt.
4. Birden fazla belge ilgiliyse hepsini karşılaştırmalı olarak değerlendir.
5. Çelişen hükümler varsa bunu açıkça belirt.
6. Cevaplarını maddesel ve anlaşılır yaz.
7. Her zaman Türkçe yanıt ver.
"""


def cevap_uret(sorgu: str, sonuclar: List[dict]) -> str:
    """
    Arama sonuçlarını bağlam olarak kullanarak Gemini'den yanıt üretir.
    """
    _hazirla()

    # Bağlamı oluştur
    baglam_parcalari = []
    for i, s in enumerate(sonuclar, 1):
        chunk = s["chunk"]
        skor = s["skor"]
        baslik = f"[Kaynak {i}] Belge: {chunk['belge_adi']}"
        if chunk.get("madde_no"):
            baslik += f" | Madde: {chunk['madde_no']}"
        if chunk.get("bolum_baslik"):
            baslik += f" | Bölüm: {chunk['bolum_baslik']}"
        baslik += f" | Benzerlik: {skor}"

        baglam_parcalari.append(f"{baslik}\n{chunk['metin']}\n")

    baglam = "\n---\n".join(baglam_parcalari)

    kullanici_mesaji = f"""Bağlam (ilgili belge parçaları):
{baglam}

---

Kullanıcı Sorusu: {sorgu}

Lütfen yukarıdaki bağlama dayanarak soruyu kapsamlı bir şekilde yanıtla. 
Kaynak belge ve madde numaralarını belirt."""

    try:
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=SISTEM_PROMPTU,
        )

        response = model.generate_content(
            kullanici_mesaji,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=4096,
            ),
        )

        return response.text

    except Exception as e:
        logger.error(f"Gemini hatası: {e}")
        return f"Yanıt üretilirken hata oluştu: {str(e)}"


def niyet_analizi(sorgu: str) -> str:
    """
    Kullanıcının ne yapmak istediğini analiz eder.
    """
    _hazirla()

    try:
        model = genai.GenerativeModel(model_name=GEMINI_MODEL)
        prompt = f"""Aşağıdaki sorguyu analiz et ve kullanıcının ne yapmak istediğini kısaca açıkla.
Türk hukuku bağlamında düşün. Tek paragraf yaz.

Sorgu: {sorgu}"""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                max_output_tokens=256,
            ),
        )
        return response.text

    except Exception as e:
        logger.error(f"Niyet analizi hatası: {e}")
        return ""
