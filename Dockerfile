FROM python:3.11-slim

# Sistem bağımlılıkları + Tesseract OCR
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        tesseract-ocr \
        tesseract-ocr-tur \
        tesseract-ocr-eng \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/belgeler/hazirlanan /app/belgeler/gecici /app/indeks

# Embedding modelini build sırasında indir (hızlı cold start)
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2')"

EXPOSE 8080

CMD ["python", "main.py"]
