FROM python:3.11-slim
WORKDIR /app
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
