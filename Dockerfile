FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends espeak-ng ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY web web
COPY download_models.py .
ENV MODELS_DIR=/models DATA_DIR=/data OLLAMA_URL=http://ollama:11434
VOLUME ["/models", "/data"]
EXPOSE 8000
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000"]
