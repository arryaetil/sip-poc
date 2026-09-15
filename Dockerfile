FROM python:3.13-slim

WORKDIR /workspace

COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app ./backend/app
COPY knowledge ./knowledge

WORKDIR /workspace/backend

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
