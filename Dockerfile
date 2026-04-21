FROM python:3.11-slim
WORKDIR /app

# ASP-04 Doc Intelligence — I-DOC-07 (ASP-FEAT-ASP-04 v1.0 §9.4 / §13 OQ-1).
# OCR pipeline needs both:
#   - poppler-utils: pdftotext (primary, for text-based PDFs)
#   - tesseract-ocr: pytesseract fallback (for scanned-image PDFs)
# apt cache cleared in the same layer to keep image size down.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ASP-02 RAG — I-RAG-02 (Architect 20:10 IST Option C).
# Pre-download the RAG embedding model at image build time so first
# request has zero network latency and no runtime fetch is ever required.
# Must match settings.RAG_EMBEDDING_MODEL default in app/config.py.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" \
    && echo "sentence-transformers/all-MiniLM-L6-v2 preloaded at build time"

COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
