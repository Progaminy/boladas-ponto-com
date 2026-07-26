#!/usr/bin/env bash
set -e

echo "=== Boladas-ponto-com — A Iniciar Aplicação ==="

if [ ! -d ".venv" ]; then
    echo "A criar ambiente virtual Python..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "A verificar dependências..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "A copiar .env.example para .env..."
        cp .env.example .env
    fi
fi

echo "A executar testes de verificação de integridade..."
pytest -q

echo "A arrancar servidor Uvicorn em http://127.0.0.1:8000 ..."
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
