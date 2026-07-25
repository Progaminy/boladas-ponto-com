FROM python:3.12-slim

# ffmpeg/ffprobe são necessários para validar a duração real dos vídeos
# enviados pelos utilizadores (ver app/media_validate.py) — sem isto, a app
# ainda arranca, mas rejeita uploads de vídeo de forma explícita em vez de
# fingir que validou a duração.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
